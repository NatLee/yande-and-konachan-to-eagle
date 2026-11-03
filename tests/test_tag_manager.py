import os
import tempfile
import unittest

import pytest
import yaml

from yk2eagle.tag_manager import TagManager


class TestTagManager(unittest.TestCase):
    def test_get_tags_from_name(self):
        tags_data = {
            '2girls': ['多人', '女性', '兩位'],
            'bikini': ['泳衣', '比基尼'],
            'miko': ['巫女服'],
            'swimsuit': ['泳衣'],
            'swimsuits': ['泳衣'],
            'wallpaper': ['桌布'],
        }

        fd, temp_path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)

        try:
            with open(temp_path, "w", encoding="utf-8") as temp_file:
                yaml.safe_dump(tags_data, temp_file, allow_unicode=True, sort_keys=False)

            tag_manager = TagManager(temp_path)

            testing_names = [
                'blue_eyes_megurine_luka_purple_hair_vocaloid',
                '2girls_amakase_minatsu_asakura_yume_bikini_da_capo_ii_swimsuit',
                'bikini_breast_hold_cleavage_crease_kotona_elegance_re_mie_sakai_kyuuta_swimsuits_wet_zoids_zoids_genesis',
                'miko_murakami_suigun_wallpaper'
            ]

            expected_results = [
                [],
                ['泳衣', '多人', '女性', '兩位', '比基尼'],
                ['泳衣','比基尼'],
                ['巫女服', '桌布']
            ]

            for i, testing_name in enumerate(testing_names):
                tags = tag_manager.get_tags_from_name(testing_name)
                self.assertEqual(set(tags), set(expected_results[i]), f"Expected {expected_results[i]} but got {tags}")

        finally:
            os.remove(temp_path)



def write_map(tmp_path, text):
    path = tmp_path / 'map.yaml'
    path.write_text(text, encoding='utf-8')
    return str(path)


def test_site_tags_map_to_your_tags_in_order_and_unmapped_ones_are_dropped(tmp_path):
    manager = TagManager(write_map(tmp_path, 'bikini: [比基尼, 泳衣]\nswimsuit: [泳衣]\nmiko: [巫女服]\n'))

    assert manager.get_ch_tags_from_eng(['swimsuit', 'long_hair', 'bikini']) == ['泳衣', '比基尼']
    assert manager.get_ch_tags_from_eng([]) == []


def test_a_tag_written_without_a_list_is_one_tag(tmp_path):
    # Before: "miko: 巫女服" gave the three tags 巫, 女 and 服.
    manager = TagManager(write_map(tmp_path, 'miko: 巫女服\nempty:\n'))

    assert manager.mapper == {'miko': ['巫女服'], 'empty': []}
    assert manager.get_ch_tags_from_eng(['miko', 'empty']) == ['巫女服']


def test_an_empty_map_file_maps_nothing(tmp_path):
    manager = TagManager(write_map(tmp_path, '# nothing yet\n'))

    assert manager.mapper == {}
    assert manager.get_ch_tags_from_eng(['bikini']) == []


def test_a_file_that_is_not_a_map_says_so(tmp_path):
    path = write_map(tmp_path, '- bikini\n- miko\n')

    with pytest.raises(ValueError, match='must map site tags to your tags'):
        TagManager(path)


def test_write_saves_a_map_that_reads_back_the_same(tmp_path):
    path = write_map(tmp_path, '{}\n')
    TagManager(path).write({'bikini': ['比基尼', '泳衣']})

    assert TagManager(path).mapper == {'bikini': ['比基尼', '泳衣']}
    assert '比基尼' in (tmp_path / 'map.yaml').read_text(encoding='utf-8')
