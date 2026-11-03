"""The command line: ``yande-and-konachan-to-eagle`` (or ``yk2eagle``, or ``python main.py``)."""
from __future__ import annotations

import argparse
import configparser
import itertools
import sys
from importlib import resources
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional, Sequence

import yaml
from eaglewrapper import Eagle, EagleAPIError, EagleConnectionError, EagleError, EagleResponseError
from eaglewrapper.client import DEFAULT_BASE_URL as EAGLE_DEFAULT_URL
from loguru import logger
from tqdm import tqdm

from . import __version__
from .config import Config, create_default_config_file
from .history import HISTORY_FILE, ImportHistory, default_history_path
from .importer import Importer, Summary, resolve_folder
from .moebooru import SITES, MoebooruClient, Post, SiteError
from .tag_manager import EXAMPLE_MAP, TagManager, create_map_from_example

DEFAULT_TARGET = 'konachan'
EAGLE_TIMEOUT = 60  # seconds to wait for Eagle to answer one call


class CliError(Exception):
    """A problem the user can fix; printed as one line, without a traceback."""


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f'must be 1 or more, not {value}')
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Yande and Konachan to Eagle',
        epilog='Without --search, it imports every post newer than the last run (the ID is kept in the '
               'config file). Posts already imported are skipped either way.')
    # The options of the 2023 script: names and defaults stay as they were. New options must not
    # start with "--t", "--c" or "--y", or the abbreviations that worked then would become ambiguous.
    parser.add_argument('--config_path', default='./config.ini',
                        help='Path to the config file (created with the defaults when missing)')
    parser.add_argument('--yaml_path', default='map.yaml',
                        help='Path to the YAML file that maps site tags to your tags '
                             '(created from the example map when missing)')
    parser.add_argument('--target', default=DEFAULT_TARGET, choices=list(SITES),
                        help='Target site for image crawling')
    parser.add_argument('--search', metavar='TAGS',
                        help='Import the posts that match this search instead of the new ones, newest first. '
                             'Same syntax as the search box on the site, e.g. "landscape rating:s" or "id:12345"')
    parser.add_argument('--limit', type=positive_int, metavar='N',
                        help='Look at N posts at most (posts already imported count too)')
    parser.add_argument('--folder', metavar='NAME',
                        help='Put the images in this Eagle folder (name or ID; created if there is none)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only list what would be imported: Eagle is not contacted and no file is written')
    parser.add_argument('--history-path', metavar='PATH',
                        help=f'File that lists the posts already imported (default: {HISTORY_FILE} next to '
                             'the config file)')
    parser.add_argument('--eagle-url', default=EAGLE_DEFAULT_URL,
                        help='Where Eagle listens (default: %(default)s, Eagle on this computer). For Eagle on '
                             'another computer, also set EAGLE_API_TOKEN to the token from Eagle > Preferences '
                             '> Developer')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    return parser


def setup_logging() -> None:
    """Send log lines through tqdm, so they do not break the progress bar."""
    logger.remove()
    logger.add(lambda message: tqdm.write(message, end='', file=sys.stderr),
               format='<level>{level: <8}</level> {message}', level='INFO', colorize=sys.stderr.isatty())


def load_config(path: str, dry_run: bool) -> Config:
    if not Path(path).exists():
        if dry_run:
            logger.info(f'No config file at {path}: using the defaults (dry run, nothing written).')
        else:
            create_default_config_file(path)
    try:
        return Config(path)
    except (OSError, configparser.Error) as exc:
        raise CliError(f'Cannot read the config file {path}: {exc}') from exc


def load_tag_map(path: str, dry_run: bool) -> TagManager:
    try:
        if Path(path).exists():
            return TagManager(path)
        if dry_run:
            logger.info(f'No tag map at {path}: using the example map (dry run, nothing written).')
            with resources.as_file(EXAMPLE_MAP) as example:
                return TagManager(str(example))
        create_map_from_example(path)
        logger.warning(f'Path [{path}] does not exist! Created it from the example map: '
                       'edit it to give the images your own tags.')
        return TagManager(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise CliError(f'Cannot read the tag map {path}: {exc}') from exc


def load_history(path: str) -> ImportHistory:
    try:
        return ImportHistory(path)
    except (OSError, ValueError) as exc:
        raise CliError(f'Cannot read the import history: {exc}') from exc


def connect_eagle(url: str) -> Eagle:
    """An ``Eagle`` that raises on failures, after checking that Eagle answers at ``url``."""
    eagle = Eagle(base_url=url, timeout=EAGLE_TIMEOUT, raise_errors=True)
    info = eagle.get_application_info() or {}
    logger.info(f'Eagle {info.get("version", "?")} (build {info.get("buildVersion", "?")}) at {eagle.host}')
    return eagle


def eagle_problem(exc: EagleError, url: str) -> str:
    """One line that says what went wrong with Eagle and what to do."""
    if isinstance(exc, EagleConnectionError):
        return (f'Eagle is not answering at {url}. Open Eagle, then run this again '
                '(or add --dry-run to only see what would be imported).')
    if isinstance(exc, EagleResponseError):
        return f'Something answers at {url}, but not the way Eagle does ({exc}). Check --eagle-url.'
    if isinstance(exc, EagleAPIError):
        return f'Eagle said no: {exc.message}'
    return f'Eagle: {exc}'


def with_progress(posts: Iterable[Post], bar: tqdm) -> Iterator[Post]:
    for post in posts:
        bar.set_description(f'Post ID {post.id}')
        yield post
        bar.update()


def report(summary: Summary, dry_run: bool) -> None:
    others = (f'{len(summary.already_imported)} already imported, {len(summary.no_file)} without a file')
    if dry_run:
        logger.info(f'Dry run: {len(summary.imported)} would be added to Eagle, {others}. '
                    'Nothing was sent to Eagle and no file was written.')
        return
    logger.info(f'Done: {len(summary.imported)} added to Eagle, {others}, {len(summary.failed)} refused by Eagle.')
    if summary.failed:
        logger.warning('Eagle refused: ' + ', '.join(f'#{post_id}' for post_id in summary.failed)
                       + f'. To try one again: --search id:{summary.failed[0]}')


def run(args: argparse.Namespace) -> int:
    dry_run = args.dry_run
    cfg = load_config(args.config_path, dry_run)
    tag_manager = load_tag_map(args.yaml_path, dry_run)
    history = load_history(args.history_path or default_history_path(args.config_path))
    eagle = None if dry_run else connect_eagle(args.eagle_url)
    folder_id = resolve_folder(eagle, args.folder) if eagle is not None and args.folder else None
    if dry_run and args.folder:
        logger.info(f'The images would go to the Eagle folder "{args.folder}".')
    client = MoebooruClient(cfg.get_site(args.target))

    posts: Iterable[Post]
    save_progress: Optional[Callable[[Post], None]] = None
    if args.search is None:
        last_download_max_id = cfg.get_last_download_max_id(args.target)
        logger.info(f'Last download Max. ID: {last_download_max_id}')
        posts = client.newer_than(last_download_max_id)
        if not dry_run:  # remember each post, so an interrupted run picks up from there
            save_progress = lambda post: cfg.set_last_download_max_id(args.target, post.id)  # noqa: E731
    else:
        logger.info(f'Searching {client.site} for "{args.search}"')
        posts = client.search(args.search)
    if args.limit is not None:
        posts = itertools.islice(posts, args.limit)

    importer = Importer(tag_manager, eagle, target=args.target, history=history, folder_id=folder_id,
                        post_url=client.post_url, say=lambda line: tqdm.write(line, file=sys.stdout))
    with tqdm(total=args.limit, unit='post', dynamic_ncols=True) as bar:
        summary = importer.run(with_progress(posts, bar), after_each=save_progress)
    report(summary, dry_run)
    return 1 if summary.failed else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    try:
        return run(args)
    except KeyboardInterrupt:
        logger.info('Stop image crawling!')
        return 0
    except EagleError as exc:
        logger.error(eagle_problem(exc, args.eagle_url))
    except (CliError, SiteError) as exc:
        logger.error(str(exc))
    return 1
