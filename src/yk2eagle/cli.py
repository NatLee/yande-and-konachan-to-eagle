"""The command line: ``yande-and-konachan-to-eagle`` (or ``yk2eagle``, or ``python main.py``)."""
from __future__ import annotations

import argparse
import configparser
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

import yaml
from eaglewrapper import Eagle, EagleAPIError, EagleConnectionError, EagleError, EagleResponseError
from eaglewrapper.client import DEFAULT_BASE_URL as EAGLE_DEFAULT_URL
from loguru import logger
from tqdm import tqdm

from . import __version__
from .config import Config, create_default_config_file
from .importer import Importer, Summary
from .moebooru import SITES, MoebooruClient, Post, SiteError
from .tag_manager import TagManager

DEFAULT_TARGET = 'konachan'
EAGLE_TIMEOUT = 60  # seconds to wait for Eagle to answer one call


class CliError(Exception):
    """A problem the user can fix; printed as one line, without a traceback."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Yande and Konachan to Eagle')
    # The options of the 2023 script: names and defaults stay as they were.
    parser.add_argument('--config_path', default='./config.ini',
                        help='Path to the config file (created with the defaults when missing)')
    parser.add_argument('--yaml_path', default='map.yaml',
                        help='Path to the YAML file that maps site tags to your tags')
    parser.add_argument('--target', default=DEFAULT_TARGET, choices=list(SITES),
                        help='Target site for image crawling')
    parser.add_argument('--eagle-url', default=EAGLE_DEFAULT_URL,
                        help='Where Eagle listens (default: %(default)s, Eagle on this computer). For Eagle on '
                             'another computer, also set EAGLE_API_TOKEN to the token from Eagle > Preferences '
                             '> Developer.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    return parser


def setup_logging() -> None:
    """Send log lines through tqdm, so they do not break the progress bar."""
    logger.remove()
    logger.add(lambda message: tqdm.write(message, end='', file=sys.stderr),
               format='<level>{level: <8}</level> {message}', level='INFO', colorize=sys.stderr.isatty())


def load_config(path: str) -> Config:
    if not Path(path).exists():
        create_default_config_file(path)
    try:
        return Config(path)
    except (OSError, configparser.Error) as exc:
        raise CliError(f'Cannot read the config file {path}: {exc}') from exc


def load_tag_map(path: str) -> TagManager:
    try:
        return TagManager(path)
    except FileNotFoundError as exc:
        raise CliError(f'No tag map at {path}. Copy map.example.yaml there and edit it (see the README).') from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise CliError(f'Cannot read the tag map {path}: {exc}') from exc


def connect_eagle(url: str) -> Eagle:
    """An ``Eagle`` that raises on failures, after checking that Eagle answers at ``url``."""
    eagle = Eagle(base_url=url, timeout=EAGLE_TIMEOUT, raise_errors=True)
    info = eagle.get_application_info() or {}
    logger.info(f'Eagle {info.get("version", "?")} (build {info.get("buildVersion", "?")}) at {eagle.host}')
    return eagle


def eagle_problem(exc: EagleError, url: str) -> str:
    """One line that says what went wrong with Eagle and what to do."""
    if isinstance(exc, EagleConnectionError):
        return f'Eagle is not answering at {url}. Open Eagle, then run this again.'
    if isinstance(exc, EagleResponseError):
        return f'Something answers at {url}, but not the way Eagle does ({exc}). Check --eagle-url.'
    if isinstance(exc, EagleAPIError):
        return f'Eagle said no: {exc.message}'
    return f'Eagle: {exc}'


def with_progress(posts: Iterable[Post], bar: tqdm) -> Iterator[Post]:
    for post in posts:
        bar.set_description(f'Now downloading ID: {post.id}')
        yield post
        bar.update()


def report(summary: Summary) -> None:
    logger.info(f'Done: {len(summary.imported)} added to Eagle, {len(summary.no_file)} without a file, '
                f'{len(summary.failed)} refused by Eagle.')
    if summary.failed:
        logger.warning('Eagle refused: ' + ', '.join(f'#{post_id}' for post_id in summary.failed))


def run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config_path)
    tag_manager = load_tag_map(args.yaml_path)
    eagle = connect_eagle(args.eagle_url)
    client = MoebooruClient(cfg.get_site(args.target))

    last_download_max_id = cfg.get_last_download_max_id(args.target)
    logger.info(f'Last download Max. ID: {last_download_max_id}')

    importer = Importer(tag_manager, eagle, post_url=client.post_url)
    with tqdm(unit='post', dynamic_ncols=True) as bar:
        summary = importer.run(
            with_progress(client.newer_than(last_download_max_id), bar),
            after_each=lambda post: cfg.set_last_download_max_id(args.target, post.id))
    report(summary)
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
