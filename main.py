"""Run the tool from a checkout without installing it: ``python main.py [options]``.

It is the same program as the installed ``yande-and-konachan-to-eagle`` command,
so it takes the same options. Install the dependencies first (``pip install -r requirements.txt``).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from yk2eagle.cli import main  # noqa: E402  (needs the path above)

if __name__ == '__main__':
    sys.exit(main())
