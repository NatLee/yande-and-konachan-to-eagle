"""Read posts from yande.re and konachan.com through their JSON API.

Both sites run Moebooru, which answers ``GET /post.json?tags=...&limit=...&page=...``
with a list of posts. ``tags`` takes what the site's search box takes: tags,
``rating:s``, ``id:>1000``, ``order:id`` and so on.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional
from urllib.parse import unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import PROJECT_URL, __version__

#: The sites ``--target`` can pick, and the address a new config file gives each one.
SITES = {
    'yande': 'https://yande.re',
    'konachan': 'https://konachan.com',
}

POSTS_PATH = '/post.json'
POST_PAGE_PATH = '/post/show/{id}'
PAGE_SIZE = 100          # posts per request
REQUEST_INTERVAL = 1.0   # seconds between two requests to the site, to go easy on it
TIMEOUT = 30             # seconds to wait for an answer
RETRIES = 5              # extra tries after a connection error, an HTTP 429 (too many requests) or a 5xx
BACKOFF_FACTOR = 1.0     # the wait between retries doubles from here; a Retry-After header wins
RETRY_STATUSES = (429, 500, 502, 503, 504)
USER_AGENT = f'yande-and-konachan-to-eagle/{__version__} (+{PROJECT_URL})'


class SiteError(Exception):
    """The site could not be read. The message says why in plain words."""


class SiteBlockedError(SiteError):
    """The site turned the request away, e.g. with Cloudflare's browser check."""


@dataclass(frozen=True)
class Post:
    """One post, with the fields this tool uses."""

    id: int
    tags: tuple[str, ...]
    file_url: str
    source: str = ''
    rating: str = ''

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Post:
        return cls(
            id=int(data['id']),
            tags=tuple(str(data.get('tags') or '').split()),
            file_url=str(data.get('file_url') or ''),
            source=str(data.get('source') or ''),
            rating=str(data.get('rating') or ''),
        )

    @property
    def name(self) -> str:
        """The item name in Eagle: the file name at the end of ``file_url``, spaces as underscores.

        For example ``yande.re_1272029_landscape_sky.jpg``. Empty when the post has no file.
        """
        return unquote(self.file_url).split('/')[-1].replace(' ', '_')


def make_session(retries: int = RETRIES, backoff_factor: float = BACKOFF_FACTOR) -> requests.Session:
    """A ``requests`` session that retries connection errors, 429 and 5xx, and names this tool."""
    retry = Retry(
        total=retries, connect=retries, read=retries, status=retries,
        backoff_factor=backoff_factor, status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({'GET'}), respect_retry_after_header=True,
        raise_on_status=False,  # hand back the last answer, so the error message can say what it was
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers['User-Agent'] = USER_AGENT
    return session


def _is_challenge(resp: requests.Response) -> bool:
    """Whether the answer is a "prove you are a browser" page rather than data."""
    if resp.headers.get('cf-mitigated') == 'challenge':
        return True
    return resp.status_code == 403 and 'text/html' in resp.headers.get('Content-Type', '')


def _describe(data: Any) -> str:
    if isinstance(data, dict) and data.get('reason'):
        return f'"{data["reason"]}"'
    return f'a {type(data).__name__}'


class MoebooruClient:
    """Reads posts from one Moebooru site.

    Args:
        site: The site's address, e.g. ``https://yande.re``.
        session: The ``requests`` session to use; :func:`make_session` by default.
        page_size: Posts per request.
        interval: Seconds to leave between two requests.
        timeout: Seconds to wait for an answer.
        sleep, clock: For tests.
    """

    def __init__(self, site: str, *, session: Optional[requests.Session] = None, page_size: int = PAGE_SIZE,
                 interval: float = REQUEST_INTERVAL, timeout: float = TIMEOUT,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.site = site.rstrip('/')
        self.session = session if session is not None else make_session()
        self.page_size = page_size
        self.interval = interval
        self.timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: Optional[float] = None

    def __repr__(self) -> str:
        return f'MoebooruClient({self.site!r})'

    def post_url(self, post_id: int) -> str:
        """The address of a post's page on the site."""
        return self.site + POST_PAGE_PATH.format(id=post_id)

    def list_posts(self, tags: str = '', page: int = 1) -> list[Post]:
        """One page of the posts that match ``tags``, as the site lists them.

        Raises:
            SiteError: The site could not be reached or did not answer with posts.
        """
        data = self._get_json(POSTS_PATH, {'tags': tags, 'limit': self.page_size, 'page': page})
        if not isinstance(data, list):
            raise SiteError(f'{self.site} answered the search "{tags}" with {_describe(data)} '
                            'instead of a list of posts.')
        return [Post.from_api(item) for item in data]

    def search(self, tags: str = '') -> Iterator[Post]:
        """Every post that matches ``tags``, page by page, in the site's order (newest first by default)."""
        seen: set[int] = set()
        for page in itertools.count(1):
            fresh = [post for post in self.list_posts(tags, page) if post.id not in seen]
            if not fresh:
                return
            seen.update(post.id for post in fresh)
            yield from fresh

    def newer_than(self, post_id: int) -> Iterator[Post]:
        """Every post with an ID above ``post_id``, oldest first.

        Each request asks for the posts after the last ID seen (``id:>N order:id``),
        so posts uploaded during the run cannot shift the pages.
        """
        cursor = post_id
        while True:
            posts = [post for post in self.list_posts(f'id:>{cursor} order:id') if post.id > cursor]
            if not posts:
                return
            yield from posts
            cursor = max(post.id for post in posts)

    def _wait_turn(self) -> None:
        if self._last_request is not None:
            wait = self.interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)

    def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        self._wait_turn()
        try:
            resp = self.session.get(self.site + path, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            raise SiteError(f'Cannot reach {self.site}, even after retrying ({type(exc).__name__}). '
                            'Check the connection and the site address in the config file.') from exc
        finally:
            self._last_request = self._clock()

        if _is_challenge(resp):
            raise SiteBlockedError(
                f'{self.site} turned the request away with a "check your browser" page (HTTP {resp.status_code}). '
                'It is not letting scripts in from this network right now. Try again later or from another '
                'network; this tool does not try to get around such checks.')
        if resp.status_code == 429:
            raise SiteError(f'{self.site} still says "too many requests" (HTTP 429) after waiting and retrying. '
                            'Wait a while and run again: the progress so far is saved.')
        if resp.status_code >= 400:
            raise SiteError(f'{self.site} answered HTTP {resp.status_code} for {resp.url}.')
        try:
            return resp.json()
        except ValueError as exc:
            raise SiteError(f'{self.site} answered with something that is not JSON '
                            f'({resp.headers.get("Content-Type", "no content type")}). '
                            'Is the site address in the config file right?') from exc
