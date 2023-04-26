import os
import sys
from pathlib import Path
sys.path.append(Path('./').absolute().as_posix())

import yaml
import tempfile
import unittest
from tag_manager import TagManager


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

