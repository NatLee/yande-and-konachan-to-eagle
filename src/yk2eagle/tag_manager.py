"""Turn the tags of a post into your own tags, with a YAML map such as ``map.yaml``.

The map lists a site tag and the tags you want in Eagle for it::

    bikini:
    - 比基尼
    - 泳衣
    miko: 巫女服    # a single tag can skip the list

Site tags that are not in the map are left out. A starting map ships with the package
(:data:`EXAMPLE_MAP`); the command line copies it to ``map.yaml`` on the first run.
"""
from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

import yaml

TagMap = dict[str, list[str]]

#: The example map inside the package, a few dozen common tags with Chinese names.
EXAMPLE_MAP = resources.files(__package__) / 'map.example.yaml'


def create_map_from_example(path: str) -> None:
    """Write the example map to ``path``, making its folder if needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with resources.as_file(EXAMPLE_MAP) as example:
        shutil.copyfile(example, path)


def normalize_map(data: Any, source: str = 'the tag map') -> TagMap:
    """Return the map as ``{site tag: [your tags]}``.

    An empty file is an empty map, and a tag written without a list (``miko: 巫女服``)
    becomes a one-item list instead of one tag per character.

    Raises:
        ValueError: The YAML is not a mapping of site tags to tags.
    """
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f'{source} must map site tags to your tags (e.g. "bikini: [比基尼, 泳衣]"), '
                         f'not a {type(data).__name__}')
    tag_map: TagMap = {}
    for site_tag, tags in data.items():
        if tags is None:
            tags = []
        elif not isinstance(tags, (list, tuple)):
            tags = [tags]
        tag_map[str(site_tag)] = [str(tag) for tag in tags]
    return tag_map


class TagManager:
    """A tag map read from a YAML file.

    Args:
        filename: Path of the YAML file.

    Raises:
        OSError: The file cannot be read.
        ValueError: The file is not a tag map.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.mapper = self.read()
        self.eng_keys = sorted(self.mapper.keys(), key=lambda x: '_' in x, reverse=True)
        self.dash_eng_keys = [key for key in self.eng_keys if '_' in key]

    def read(self) -> TagMap:
        with open(self.filename, 'r', encoding='utf-8') as file:
            return normalize_map(yaml.safe_load(file), self.filename)

    def write(self, data: dict) -> None:
        with open(self.filename, 'w', encoding='utf-8') as file:
            yaml.safe_dump(
                data,
                file,
                allow_unicode=True,
                sort_keys=False
            )

    def get_tags_from_name(self, name: str) -> list[str]:
        """Your tags for the site tags found in a file name such as ``2girls_bikini_swimsuit``.

        Tags that contain an underscore (``animal_ears``) are matched first, as substrings;
        the rest of the name is split on underscores.
        """
        tags = set()
        # Check dash keys
        for dash_eng_key in self.dash_eng_keys:
            if dash_eng_key in name:
                attrs = self.mapper[dash_eng_key]
                tags.update(attrs)
                # Replace dash
                name = name.replace(dash_eng_key, '')
        # Check normal keys
        name_key = set(name.split('_'))
        # Find intersections
        it_tags = list(name_key & set(self.eng_keys))
        for it_tag in it_tags:
            attrs = self.mapper[it_tag]
            tags.update(attrs)
        return list(tags)

    def get_ch_tags_from_eng(self, eng_tags: Iterable[str]) -> list[str]:
        """Your tags for a list of site tags, each once, in the order they first appear."""
        ch_tags: dict[str, None] = {}
        for eng_tag in eng_tags:
            ch_tags.update(dict.fromkeys(self.mapper.get(eng_tag, [])))
        return list(ch_tags)
