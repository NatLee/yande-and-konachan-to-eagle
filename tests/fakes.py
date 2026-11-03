"""Small stand-ins for a Moebooru site and for Eagle, served over real HTTP on 127.0.0.1.

Each one listens on a free port picked by the system, so tests never need the real sites
or a running Eagle, and never touch Eagle's own port.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, quote, urlsplit

Reply = tuple[int, dict[str, str], bytes]


def json_reply(data: Any, status: int = 200, headers: Optional[dict[str, str]] = None) -> Reply:
    return status, dict({'Content-Type': 'application/json; charset=utf-8'}, **(headers or {})), \
        json.dumps(data, ensure_ascii=False).encode('utf-8')


class FakeServer:
    """A real HTTP server; subclasses answer requests in :meth:`answer`."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.scripted: list[Reply] = []  # answered first, one per request, before :meth:`answer`
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._serve('GET')

            def do_POST(self) -> None:
                self._serve('POST')

            def _serve(self, method: str) -> None:
                parts = urlsplit(self.path)
                length = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(length) if length else b''
                request = {
                    'method': method, 'path': parts.path,
                    'query': {key: values[-1] for key, values in parse_qs(parts.query).items()},
                    'json': json.loads(raw) if raw else None, 'headers': dict(self.headers),
                }
                server.requests.append(request)
                status, headers, body = server.scripted.pop(0) if server.scripted else server.answer(request)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: Any) -> None:  # keep the test output quiet
                pass

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.httpd.server_port}'
        # A short poll interval makes shutdown() quick, so each test ends without a pause.
        self._thread = threading.Thread(target=self.httpd.serve_forever, kwargs={'poll_interval': 0.02},
                                        daemon=True)

    def __enter__(self) -> FakeServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def answer(self, request: dict[str, Any]) -> Reply:
        return json_reply({'error': 'not here'}, 404)


def make_post(post_id: int, tags: str = 'landscape sky', rating: str = 's', *, site: str = 'yande.re',
              source: str = '', with_file: bool = True) -> dict[str, Any]:
    """A post as /post.json returns it (only the fields the tool reads, plus a few others)."""
    md5 = f'{post_id:032x}'
    file_name = quote(f'{site} {post_id} {tags}.jpg')
    return {
        'id': post_id, 'tags': tags, 'rating': rating, 'source': source, 'md5': md5, 'status': 'active',
        'file_url': f'https://files.{site}/image/{md5}/{file_name}' if with_file else None,
        'width': 1920, 'height': 1080, 'score': 1,
    }


class FakeSite(FakeServer):
    """Answers ``GET /post.json`` the way Moebooru does, for the search terms the tool sends.

    Understands plain tags (all must match), ``rating:x``, ``id:>N`` and ``order:id``
    (oldest first; newest first otherwise), plus ``limit`` and ``page``.
    """

    def __init__(self, posts: Optional[list[dict[str, Any]]] = None) -> None:
        super().__init__()
        self.posts = list(posts or [])

    @property
    def searches(self) -> list[str]:
        return [request['query'].get('tags', '') for request in self.requests if request['path'] == '/post.json']

    def answer(self, request: dict[str, Any]) -> Reply:
        if request['path'] != '/post.json':
            return super().answer(request)
        terms = request['query'].get('tags', '').split()
        posts = sorted(self.posts, key=lambda post: post['id'], reverse='order:id' not in terms)
        for term in terms:
            if term.startswith('id:>'):
                posts = [post for post in posts if post['id'] > int(term[4:])]
            elif term.startswith('rating:'):
                posts = [post for post in posts if post['rating'] == term[7:8]]
            elif term != 'order:id':
                posts = [post for post in posts if term in post['tags'].split()]
        limit = int(request['query'].get('limit', 100))
        page = int(request['query'].get('page', 1))
        return json_reply(posts[(page - 1) * limit:page * limit])


class FakeEagle(FakeServer):
    """Answers the Eagle V1 calls the tool makes, and remembers what was added."""

    def __init__(self) -> None:
        super().__init__()
        self.refuse: set[str] = set()  # item names to answer with {"status": "error"}
        self.folders: list[dict[str, Any]] = []

    @property
    def added(self) -> list[dict[str, Any]]:
        return [request['json'] for request in self.requests
                if request['path'] == '/api/item/addFromURL' and request['json']['name'] not in self.refuse]

    def answer(self, request: dict[str, Any]) -> Reply:
        path, body = request['path'], request['json']
        if path == '/api/application/info':
            return json_reply({'status': 'success', 'data': {'version': '4.0.0', 'buildVersion': '20260327'}})
        if path == '/api/item/addFromURL':
            if body['name'] in self.refuse:
                return json_reply({'status': 'error', 'message': 'Unsupported file'})
            return json_reply({'status': 'success'})
        if path == '/api/folder/list':
            return json_reply({'status': 'success', 'data': self.folders})
        if path == '/api/folder/create':
            folder = {'id': f'FOLDER{len(self.requests)}', 'name': body['folderName'], 'children': []}
            self.folders.append(folder)
            return json_reply({'status': 'success', 'data': folder})
        return super().answer(request)
