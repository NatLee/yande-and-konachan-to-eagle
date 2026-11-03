"""The config file: each site's address, and the ID of the newest post the last run got to.

::

    [yande]
    site = https://yande.re
    last_download_max_id = 0
    [konachan]
    site = https://konachan.com
    last_download_max_id = 0

A missing section or key falls back to the defaults in :data:`~yk2eagle.moebooru.SITES`
and ``0``, so a config file that only lists one site still works for the other.
"""
from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path

from loguru import logger

from .moebooru import SITES

SITE_KEY = 'site'
LAST_ID_KEY = 'last_download_max_id'


def default_config_text() -> str:
    """What a new config file contains."""
    return ''.join(f'[{target}]\n{SITE_KEY} = {site}\n{LAST_ID_KEY} = 0\n' for target, site in SITES.items())


def create_default_config_file(config_path: str) -> bool:
    """Write a config file with the defaults, and say so."""
    default_config = default_config_text()
    logger.warning(f'Path [{config_path}] does not exist!')
    logger.warning('Creating default config file to the specific path!')
    print(f'Default content of the config:\n----\n{default_config}\n----\n')

    with open(config_path, 'w', encoding='utf-8') as config_file:
        config_file.write(default_config)
    return True


class Config:
    """The config file at ``config_path``. A file that does not exist reads as all defaults."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.cfg = ConfigParser()
        self.cfg.optionxform = str  # type: ignore[assignment,method-assign]  # keep keys as written
        self.cfg.read(self.config_path, encoding='utf-8')

    @property
    def exists(self) -> bool:
        return Path(self.config_path).exists()

    def get_site(self, target: str) -> str:
        return self.cfg.get(target, SITE_KEY, fallback=SITES[target])

    def get_last_download_max_id(self, target: str) -> int:
        return self.cfg.getint(target, LAST_ID_KEY, fallback=0)

    def set_last_download_max_id(self, target: str, count: int) -> None:
        if not self.cfg.has_section(target):
            self.cfg.add_section(target)
        self.cfg.set(target, LAST_ID_KEY, str(count))
        self.write_config()

    def write_config(self) -> None:
        with open(self.config_path, 'w', encoding='utf-8') as c:
            self.cfg.write(c)
