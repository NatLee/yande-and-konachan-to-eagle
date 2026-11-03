"""Keep the README examples honest: every command must parse, and both languages must agree."""
import re
import shlex
from pathlib import Path

import pytest

from yk2eagle import cli

ROOT = Path(__file__).resolve().parent.parent
READMES = ['README.md', 'README.TW.md']
COMMAND = 'yande-and-konachan-to-eagle'


def blocks(readme, language):
    return re.findall(rf'```{language}\n(.*?)```', (ROOT / readme).read_text(encoding='utf-8'), re.S)


def commands(readme):
    return [line for block in blocks(readme, 'bash') for line in block.splitlines() if line.startswith(COMMAND)]


@pytest.mark.parametrize('readme', READMES)
def test_every_command_in_the_readme_uses_real_options(readme):
    assert commands(readme)
    for command in commands(readme):
        cli.build_parser().parse_args(shlex.split(command)[1:])  # exits with code 2 on an unknown option


def test_both_readmes_show_the_same_commands_and_python_example():
    english, chinese = READMES
    assert commands(english) == commands(chinese)
    assert blocks(english, 'python') == blocks(chinese, 'python')


@pytest.mark.parametrize('readme', READMES)
def test_the_python_example_compiles(readme):
    for block in blocks(readme, 'python'):
        compile(block, readme, 'exec')
