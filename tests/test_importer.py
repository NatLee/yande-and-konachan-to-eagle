import datetime
import socket

import pytest
from eaglewrapper import Eagle, EagleConnectionError
from fakes import make_post

from yk2eagle.importer import Importer, annotation_for
from yk2eagle.moebooru import Post
from yk2eagle.tag_manager import TagManager

NOW = datetime.datetime(2026, 11, 4, 9, 30, 0, 123456)


@pytest.fixture
def tag_manager(tmp_path):
    path = tmp_path / 'map.yaml'
    path.write_text('landscape: [風景]\nsky: [天空, 風景]\nbikini: 比基尼\n', encoding='utf-8')
    return TagManager(str(path))


def posts(*items):
    return [Post.from_api(item) for item in items]


def importer_for(fake_eagle, tag_manager, **kwargs):
    eagle = Eagle(base_url=fake_eagle.url, raise_errors=True)
    return Importer(tag_manager, eagle, post_url=lambda post_id: f'https://yande.re/post/show/{post_id}',
                    now=lambda: NOW, **kwargs)


def test_each_post_goes_to_eagle_as_in_2023(fake_eagle, tag_manager):
    batch = posts(make_post(11, 'landscape sky long_hair', source='https://example.com/art/11'),
                  make_post(12, 'bikini'))

    summary = importer_for(fake_eagle, tag_manager).run(batch)

    assert summary.imported == [11, 12]
    first = fake_eagle.added[0]
    # The same fields the 2023 script sent through eaglewrapper 1.1.1's add_from_url.
    assert first == {
        'url': batch[0].file_url,
        'name': 'yande.re_11_landscape_sky_long_hair.jpg',
        'website': batch[0].file_url,
        'tags': ['風景', '天空'],
        'annotation': 'AUTO_DOWNLOAD\n2026-11-04 09:30:00.123456\nhttps://example.com/art/11',
        'modificationTime': None,
        'headers': {},
    }
    assert fake_eagle.added[1]['tags'] == ['比基尼']


def test_the_annotation_keeps_the_2023_layout():
    post = Post.from_api(make_post(1, source=''))

    assert annotation_for(post, NOW) == 'AUTO_DOWNLOAD\n2026-11-04 09:30:00.123456\n'


def test_posts_without_a_file_are_skipped(fake_eagle, tag_manager):
    summary = importer_for(fake_eagle, tag_manager).run(posts(make_post(1, with_file=False), make_post(2)))

    assert summary.no_file == [1]
    assert summary.imported == [2]
    assert [item['name'] for item in fake_eagle.added] == ['yande.re_2_landscape_sky.jpg']


def test_a_post_eagle_refuses_is_counted_and_the_rest_go_on(fake_eagle, tag_manager):
    fake_eagle.refuse = {'yande.re_2_landscape_sky.jpg'}
    done = []

    summary = importer_for(fake_eagle, tag_manager).run(posts(make_post(1), make_post(2), make_post(3)),
                                                        after_each=lambda post: done.append(post.id))

    assert summary.failed == [2]
    assert summary.imported == [1, 3]
    assert done == [1, 2, 3]


def test_a_closed_eagle_stops_the_run_before_the_post_counts(tag_manager):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        url = f'http://127.0.0.1:{sock.getsockname()[1]}'
    importer = Importer(tag_manager, Eagle(base_url=url, raise_errors=True))
    done = []

    with pytest.raises(EagleConnectionError):
        importer.run(posts(make_post(1)), after_each=lambda post: done.append(post.id))
    assert done == []
    assert importer.summary.imported == []
