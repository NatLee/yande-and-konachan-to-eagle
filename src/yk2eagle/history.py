"""Which posts are already in Eagle, so that later runs skip them.

A plain text file with one line per post that Eagle accepted, ``<target> <post id>``::

    yande 1272029
    konachan 391204

Lines are added as the posts go in, so an interrupted run keeps what it did. Delete a
line (or the whole file) to let a post be imported again.
"""
from __future__ import annotations

from pathlib import Path

#: The file name used next to the config file when ``--history-path`` is not given.
HISTORY_FILE = 'imported.txt'


def default_history_path(config_path: str) -> str:
    return str(Path(config_path).with_name(HISTORY_FILE))


class ImportHistory:
    """The history file at ``path``; a file that does not exist yet is an empty history.

    Raises:
        OSError: The file cannot be read.
        ValueError: A line is not ``<target> <post id>``.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self._imported: set[tuple[str, int]] = set()
        if self.path.exists():
            lines = self.path.read_text(encoding='utf-8').splitlines()
            for number, line in enumerate(lines, 1):
                fields = line.split()
                if not fields or fields[0].startswith('#'):
                    continue
                if len(fields) != 2 or not fields[1].isdigit():
                    raise ValueError(f'{path}, line {number}: expected "<site> <post id>", found {line!r}')
                self._imported.add((fields[0], int(fields[1])))

    def __contains__(self, entry: tuple[str, int]) -> bool:
        return entry in self._imported

    def __len__(self) -> int:
        return len(self._imported)

    def add(self, target: str, post_id: int) -> None:
        """Remember that the post is in Eagle, in memory and in the file."""
        self._imported.add((target, post_id))
        with self.path.open('a', encoding='utf-8') as file:
            file.write(f'{target} {post_id}\n')
