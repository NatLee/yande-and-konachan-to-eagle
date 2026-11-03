import configparser
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import make_post

from yk2eagle import cli
from yk2eagle.config import default_config_text
from yk2eagle.moebooru import MoebooruClient, make_session

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'map.yaml').write_text('landscape: [風景]\nsky: [天空]\n', encoding='utf-8')
    return tmp_path


class QuickClient(MoebooruClient):
    """The real client, minus the polite pause between requests and before retries."""

    def __init__(self, site, **kwargs):
        super().__init__(site, session=make_session(backoff_factor=0), interval=0, **kwargs)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(cli, 'MoebooruClient', QuickClient)


def write_config(path, site_url, last_id=0, target='yande'):
    path.write_text(f'[{target}]\nsite = {site_url}\nlast_download_max_id = {last_id}\n', encoding='utf-8')


def read_last_id(path, target='yande'):
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding='utf-8')
    return cfg.getint(target, 'last_download_max_id')


def closed_port_url():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return f'http://127.0.0.1:{sock.getsockname()[1]}'


def test_the_2023_options_keep_their_names_and_defaults():
    args = cli.build_parser().parse_args([])

    assert (args.config_path, args.yaml_path, args.target) == ('./config.ini', 'map.yaml', 'konachan')


@pytest.mark.parametrize('argv, expected', [
    (['--target', 'yande'], ('./config.ini', 'map.yaml', 'yande')),
    (['--t', 'yande', '--config', 'my.ini', '--yaml', 'my.yaml'], ('my.ini', 'my.yaml', 'yande')),
    (['--config_path=a.ini', '--yaml_path=b.yaml', '--target=konachan'], ('a.ini', 'b.yaml', 'konachan')),
])
def test_the_2023_command_lines_still_parse_the_same(argv, expected):
    # Abbreviations such as --t and --config worked in 2023, so new options must not collide with them.
    args = cli.build_parser().parse_args(argv)

    assert (args.config_path, args.yaml_path, args.target) == expected


def test_new_posts_go_to_eagle_and_the_progress_is_saved(workdir, site, fake_eagle):
    site.posts = [make_post(i) for i in (9, 10, 11, 12)]
    write_config(workdir / 'config.ini', site.url, last_id=9)

    code = cli.main(['--target', 'yande', '--eagle-url', fake_eagle.url])

    assert code == 0
    assert [item['name'] for item in fake_eagle.added] == [
        'yande.re_10_landscape_sky.jpg', 'yande.re_11_landscape_sky.jpg', 'yande.re_12_landscape_sky.jpg']
    assert fake_eagle.added[0]['tags'] == ['風景', '天空']
    assert read_last_id(workdir / 'config.ini') == 12

    # The next run starts after post 12 and finds nothing new.
    assert cli.main(['--target', 'yande', '--eagle-url', fake_eagle.url]) == 0
    assert len(fake_eagle.added) == 3
    assert site.searches[-1] == 'id:>12 order:id'


def test_a_missing_config_file_is_created_with_the_defaults(workdir, fake_eagle, monkeypatch, capsys):
    monkeypatch.setattr('yk2eagle.cli.MoebooruClient.newer_than', lambda self, post_id: iter(()))

    assert cli.main(['--eagle-url', fake_eagle.url]) == 0

    assert (workdir / 'config.ini').read_text(encoding='utf-8') == default_config_text()
    assert 'Default content of the config' in capsys.readouterr().out


def test_eagle_not_running_is_explained_before_the_site_is_asked(workdir, site, capsys):
    write_config(workdir / 'config.ini', site.url)
    url = closed_port_url()

    assert cli.main(['--target', 'yande', '--eagle-url', url]) == 1

    assert f'Eagle is not answering at {url}. Open Eagle' in capsys.readouterr().err
    assert site.requests == []


def test_a_blocked_site_is_explained(workdir, site, fake_eagle, capsys):
    write_config(workdir / 'config.ini', site.url, target='konachan')
    site.scripted = [(403, {'Content-Type': 'text/html'}, b'<title>Just a moment...</title>')]

    assert cli.main(['--eagle-url', fake_eagle.url]) == 1

    assert 'check your browser' in capsys.readouterr().err
    assert fake_eagle.added == []


def test_refused_posts_are_listed_and_make_the_exit_code_1(workdir, site, fake_eagle, capsys):
    site.posts = [make_post(1), make_post(2)]
    fake_eagle.refuse = {'yande.re_1_landscape_sky.jpg'}
    write_config(workdir / 'config.ini', site.url)

    assert cli.main(['--target', 'yande', '--eagle-url', fake_eagle.url]) == 1

    err = capsys.readouterr().err
    assert 'Eagle refused: #1' in err
    assert 'Unsupported file' in err
    assert read_last_id(workdir / 'config.ini') == 2  # as in 2023, the run moves on


def test_a_broken_tag_map_is_one_line_not_a_traceback(workdir, fake_eagle, capsys):
    (workdir / 'map.yaml').write_text('- not\n- a map\n', encoding='utf-8')

    assert cli.main(['--eagle-url', fake_eagle.url]) == 1

    assert 'Cannot read the tag map map.yaml' in capsys.readouterr().err


def test_main_py_still_runs_from_a_checkout():
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--help'],
                            capture_output=True, text=True, check=True)

    for option in ('--config_path', '--yaml_path', '--target'):
        assert option in result.stdout
