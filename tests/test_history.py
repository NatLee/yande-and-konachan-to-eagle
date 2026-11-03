import pytest

from yk2eagle.history import ImportHistory, default_history_path


def test_a_history_that_does_not_exist_yet_is_empty(tmp_path):
    history = ImportHistory(str(tmp_path / 'imported.txt'))

    assert len(history) == 0
    assert ('yande', 1) not in history
    assert not (tmp_path / 'imported.txt').exists()  # reading writes nothing


def test_added_posts_are_written_as_they_go_and_read_back(tmp_path):
    path = tmp_path / 'imported.txt'
    history = ImportHistory(str(path))
    history.add('yande', 1272029)
    history.add('konachan', 391204)

    assert path.read_text(encoding='utf-8') == 'yande 1272029\nkonachan 391204\n'
    again = ImportHistory(str(path))
    assert ('yande', 1272029) in again
    assert ('konachan', 1272029) not in again  # each site has its own IDs
    assert len(again) == 2


def test_blank_lines_and_comments_are_ignored(tmp_path):
    path = tmp_path / 'imported.txt'
    path.write_text('# imported by hand\n\nyande 5\n', encoding='utf-8')

    assert len(ImportHistory(str(path))) == 1


def test_a_line_that_makes_no_sense_names_the_line(tmp_path):
    path = tmp_path / 'imported.txt'
    path.write_text('yande 5\nyande five\n', encoding='utf-8')

    with pytest.raises(ValueError, match='line 2'):
        ImportHistory(str(path))


def test_the_default_history_sits_next_to_the_config_file(tmp_path):
    config = tmp_path / 'settings' / 'config.ini'

    assert default_history_path(str(config)) == str(tmp_path / 'settings' / 'imported.txt')
    assert default_history_path('./config.ini') == 'imported.txt'
