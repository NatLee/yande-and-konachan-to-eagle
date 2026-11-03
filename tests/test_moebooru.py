import socket

import pytest
from fakes import json_reply, make_post

from yk2eagle import __version__
from yk2eagle.moebooru import (SITES, USER_AGENT, MoebooruClient, Post, SiteBlockedError, SiteError,
                               make_session)


def test_the_two_sites_and_their_addresses():
    # The addresses a new config file gets; they were the same in the 2023 script.
    assert SITES == {'yande': 'https://yande.re', 'konachan': 'https://konachan.com'}


def test_a_post_reads_the_api_fields_and_is_named_after_its_file():
    post = Post.from_api(make_post(1272029, 'long_hair landscape', 'q', source='https://example.com/art/9'))

    assert post.id == 1272029
    assert post.tags == ('long_hair', 'landscape')
    assert post.rating == 'q'
    assert post.source == 'https://example.com/art/9'
    # Same rule as the 2023 script: the decoded file name, spaces turned into underscores.
    assert post.name == 'yande.re_1272029_long_hair_landscape.jpg'


def test_a_post_without_a_file_has_no_name():
    post = Post.from_api(dict(make_post(5, with_file=False), source=None))

    assert (post.file_url, post.name, post.source) == ('', '', '')


def test_list_posts_asks_for_one_page_and_names_the_tool(site, quick_client):
    site.posts = [make_post(i) for i in range(1, 6)]

    posts = quick_client.list_posts('landscape', page=2)

    assert [post.id for post in posts] == [2, 1]  # newest first, page 2 of 3-post pages
    request = site.requests[0]
    assert request['query'] == {'tags': 'landscape', 'limit': '3', 'page': '2'}
    assert request['headers']['User-Agent'] == USER_AGENT
    assert __version__ in USER_AGENT


def test_newer_than_goes_oldest_first_and_asks_by_id(site, quick_client):
    site.posts = [make_post(i) for i in (3, 4, 5, 7, 8, 9, 10)]

    ids = [post.id for post in quick_client.newer_than(3)]

    assert ids == [4, 5, 7, 8, 9, 10]
    # Each page starts after the last ID seen, so new uploads cannot shift the pages.
    assert site.searches == ['id:>3 order:id', 'id:>7 order:id', 'id:>10 order:id']


def test_search_walks_the_pages_until_one_brings_nothing_new(site, quick_client):
    site.posts = [make_post(i, 'sky' if i % 2 else 'sea') for i in range(1, 9)]

    ids = [post.id for post in quick_client.search('sky')]

    assert ids == [7, 5, 3, 1]
    assert [request['query']['page'] for request in site.requests] == ['1', '2', '3']


def test_search_stops_when_the_site_keeps_sending_the_same_page(site, quick_client):
    same_page = json_reply([make_post(2), make_post(1)])
    site.scripted = [same_page, same_page]

    assert [post.id for post in quick_client.search('')] == [2, 1]
    assert len(site.requests) == 2


def test_requests_are_spaced_out(site):
    times, waits = iter([100.0, 100.2, 101.0]), []
    client = MoebooruClient(site.url, interval=1.0, clock=lambda: next(times), sleep=waits.append)

    client.list_posts()  # clock: 100.0 after the request
    client.list_posts()  # clock: 100.2 before, 101.0 after

    assert waits == [pytest.approx(0.8)]


def test_busy_answers_are_retried(site, quick_client):
    site.posts = [make_post(1)]
    site.scripted = [json_reply({}, 503), json_reply({}, 429, {'Retry-After': '0'})]

    assert [post.id for post in quick_client.list_posts()] == [1]
    assert len(site.requests) == 3


def test_rate_limiting_that_does_not_end_is_explained(site):
    site.scripted = [json_reply({}, 429, {'Retry-After': '0'})] * 3
    client = MoebooruClient(site.url, session=make_session(retries=2, backoff_factor=0), interval=0)

    with pytest.raises(SiteError, match=r'too many requests.*progress so far is saved'):
        client.list_posts()
    assert len(site.requests) == 3


def test_a_browser_check_page_is_explained(site, quick_client):
    site.scripted = [(403, {'Content-Type': 'text/html; charset=UTF-8', 'cf-mitigated': 'challenge'},
                      b'<html><title>Just a moment...</title></html>')]

    with pytest.raises(SiteBlockedError, match=r'"check your browser" page \(HTTP 403\)'):
        quick_client.list_posts()
    assert len(site.requests) == 1  # not retried


def test_an_answer_that_is_not_json_is_explained(site, quick_client):
    site.scripted = [(200, {'Content-Type': 'text/html'}, b'<html>maintenance</html>')]

    with pytest.raises(SiteError, match='not JSON'):
        quick_client.list_posts()


def test_a_refused_search_shows_the_reason_from_the_site(site, quick_client):
    site.scripted = [json_reply({'success': False, 'reason': 'You can only search up to 6 tags at once'})]

    with pytest.raises(SiteError, match='You can only search up to 6 tags at once'):
        quick_client.list_posts('a b c d e f g')


def test_other_http_errors_name_the_status(site, quick_client):
    site.scripted = [json_reply({}, 404)]

    with pytest.raises(SiteError, match='HTTP 404'):
        quick_client.list_posts()


def test_a_site_that_cannot_be_reached_is_explained():
    with socket.socket() as sock:  # a port nobody listens on
        sock.bind(('127.0.0.1', 0))
        url = f'http://127.0.0.1:{sock.getsockname()[1]}'
    client = MoebooruClient(url, session=make_session(retries=1, backoff_factor=0), interval=0)

    with pytest.raises(SiteError, match='Cannot reach'):
        client.list_posts()


def test_post_url_points_at_the_post_page():
    assert MoebooruClient('https://yande.re/').post_url(42) == 'https://yande.re/post/show/42'
