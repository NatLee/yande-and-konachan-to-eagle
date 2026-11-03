"""Hand posts to Eagle: one ``add_from_url`` call per post, with your tags."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from eaglewrapper import Eagle, EagleAPIError
from loguru import logger

from .history import ImportHistory
from .moebooru import Post
from .tag_manager import TagManager

ANNOTATION_HEADER = 'AUTO_DOWNLOAD'


def annotation_for(post: Post, now: datetime.datetime) -> str:
    """The item's note in Eagle: a marker, when it was added, and where the image came from."""
    return f'{ANNOTATION_HEADER}\n{now}\n{post.source}'


def find_folder(folders: list[dict[str, Any]], wanted: str) -> Optional[dict[str, Any]]:
    """The first folder, subfolders included and in Eagle's order, whose ID or name is ``wanted``."""
    for folder in folders:
        if wanted in (folder.get('id'), folder.get('name')):
            return folder
        found = find_folder(folder.get('children') or [], wanted)
        if found is not None:
            return found
    return None


def resolve_folder(eagle: Eagle, wanted: str) -> str:
    """The ID of the Eagle folder named (or with the ID) ``wanted``; a new top-level folder if none is."""
    folder = find_folder(eagle.list_folders() or [], wanted)
    if folder is None:
        folder = eagle.create_folder(wanted) or {}
        logger.info(f'Created the Eagle folder "{wanted}"')
    return folder['id']


@dataclass
class Summary:
    """What happened to each post, by post ID. In a dry run, ``imported`` means "would be"."""

    imported: list[int] = field(default_factory=list)
    already_imported: list[int] = field(default_factory=list)
    no_file: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)


class Importer:
    """Adds posts to Eagle, or only lists them (a dry run).

    Args:
        tag_manager: Turns the site tags into the tags the items get.
        eagle: An ``Eagle`` made with ``raise_errors=True``, so a refused item raises.
            ``None`` for a dry run: nothing is sent, each post is described through ``say``.
        target: The site's name in the history (``yande``, ``konachan``).
        history: Posts imported earlier, skipped here; posts Eagle accepts are added to it.
        folder_id: The Eagle folder for the new items; ``None`` for none.
        post_url: Gives the address of a post's page, for messages.
        say: Where the dry-run lines go.
        now: The clock for the annotation.

    An ``EagleConnectionError`` (Eagle closed) is not caught: the run stops there, before
    the post is counted, so the next run starts with that post again.
    """

    def __init__(self, tag_manager: TagManager, eagle: Optional[Eagle], *, target: str = '',
                 history: Optional[ImportHistory] = None, folder_id: Optional[str] = None,
                 post_url: Callable[[int], str] = str, say: Callable[[str], None] = print,
                 now: Callable[[], datetime.datetime] = datetime.datetime.now):
        self.tag_manager = tag_manager
        self.eagle = eagle
        self.target = target
        self.history = history
        self.folder_id = folder_id
        self.post_url = post_url
        self.say = say
        self.now = now
        self.summary = Summary()

    @property
    def dry_run(self) -> bool:
        return self.eagle is None

    def run(self, posts: Iterable[Post], after_each: Optional[Callable[[Post], None]] = None) -> Summary:
        """Handle every post; call ``after_each`` once a post is done (added, skipped or refused)."""
        for post in posts:
            self.handle(post)
            if after_each is not None:
                after_each(post)
        return self.summary

    def handle(self, post: Post) -> None:
        if self.history is not None and (self.target, post.id) in self.history:
            self.summary.already_imported.append(post.id)
            return
        if not post.name:  # no file URL: the post was deleted, or the site hides the file
            logger.warning(f'{self.post_url(post.id)} :: NO FILE (deleted or hidden), skipped')
            self.summary.no_file.append(post.id)
            return
        tags = self.tag_manager.get_ch_tags_from_eng(post.tags)
        if self.eagle is None:
            self.say(f'#{post.id} [{post.rating}] {post.name} -> {", ".join(tags) or "(no tags from the map)"}')
            self.summary.imported.append(post.id)
            return
        try:
            self.eagle.add_from_url(post.file_url, post.name, tags, post.file_url, annotation_for(post, self.now()),
                                    folder_id=self.folder_id)
        except EagleAPIError as exc:
            logger.warning(f'{self.post_url(post.id)} :: Eagle did not add it: {exc.message}')
            self.summary.failed.append(post.id)
            return
        if self.history is not None:
            self.history.add(self.target, post.id)
        self.summary.imported.append(post.id)
