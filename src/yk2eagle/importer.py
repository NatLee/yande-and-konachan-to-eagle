"""Hand posts to Eagle: one ``add_from_url`` call per post, with your tags."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Callable, Iterable

from eaglewrapper import Eagle, EagleAPIError
from loguru import logger

from .moebooru import Post
from .tag_manager import TagManager

ANNOTATION_HEADER = 'AUTO_DOWNLOAD'


def annotation_for(post: Post, now: datetime.datetime) -> str:
    """The item's note in Eagle: a marker, when it was added, and where the image came from."""
    return f'{ANNOTATION_HEADER}\n{now}\n{post.source}'


@dataclass
class Summary:
    """What happened to each post, by post ID."""

    imported: list[int] = field(default_factory=list)
    no_file: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)


class Importer:
    """Adds posts to Eagle.

    Args:
        tag_manager: Turns the site tags into the tags the items get.
        eagle: An ``Eagle`` made with ``raise_errors=True``, so a refused item raises.
        post_url: Gives the address of a post's page, for messages.
        now: The clock for the annotation.

    An ``EagleConnectionError`` (Eagle closed) is not caught: the run stops there, before
    the post is counted, so the next run starts with that post again.
    """

    def __init__(self, tag_manager: TagManager, eagle: Eagle, *, post_url: Callable[[int], str] = str,
                 now: Callable[[], datetime.datetime] = datetime.datetime.now):
        self.tag_manager = tag_manager
        self.eagle = eagle
        self.post_url = post_url
        self.now = now
        self.summary = Summary()

    def run(self, posts: Iterable[Post], after_each: Callable[[Post], None] = lambda post: None) -> Summary:
        """Handle every post; call ``after_each`` once a post is done (added, skipped or refused)."""
        for post in posts:
            self.handle(post)
            after_each(post)
        return self.summary

    def handle(self, post: Post) -> None:
        if not post.name:  # no file URL: the post was deleted, or the site hides the file
            logger.warning(f'{self.post_url(post.id)} :: NO FILE (deleted or hidden), skipped')
            self.summary.no_file.append(post.id)
            return
        tags = self.tag_manager.get_ch_tags_from_eng(post.tags)
        try:
            self.eagle.add_from_url(post.file_url, post.name, tags, post.file_url, annotation_for(post, self.now()))
        except EagleAPIError as exc:
            logger.warning(f'{self.post_url(post.id)} :: Eagle did not add it: {exc.message}')
            self.summary.failed.append(post.id)
            return
        self.summary.imported.append(post.id)
