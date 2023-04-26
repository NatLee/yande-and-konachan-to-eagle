import argparse
import datetime
from pathlib import Path
from tqdm import tqdm
from loguru import logger

from config import Config
from eaglewrapper import Eagle

from tag_manager import TagManager
from image_scraper import ImageScraper

def create_default_config_file(config_path):
    default_config = '''[yande]
site = https://yande.re
last_download_max_id = 0
[konachan]
site = https://konachan.com
last_download_max_id = 0
'''
    logger.warning(f'Path [{config_path}] does not exist!')
    logger.warning('Creating default config file to the specific path!')
    print(f'Default content of the config:\n----\n{default_config}\n----\n')

    with open(config_path, 'w', encoding='utf-8') as config_file:
        config_file.write(default_config)
    return True

def main(config_path, yaml_path, target):
    if not Path(config_path).exists():
        create_default_config_file(config_path)
    cfg = Config(config_path)
    site = cfg.get_site(target)

    tag_parser = TagManager(yaml_path)

    last_download_max_id = cfg.get_last_download_max_id(target)
    logger.info(f'Last download Max. ID: {last_download_max_id}')
    now_max_id = ImageScraper.get_newest_image_id(site=site)
    logger.info(f'Now Max. ID: {now_max_id}')

    eagle = Eagle()
    scraper = ImageScraper(site, tag_parser)
    tbar = tqdm(range(last_download_max_id + 1, now_max_id + 1))

    for idx in tbar:
        desc = f'Now downloading ID: {idx}'
        tbar.set_description(desc)
        image_name, tags, source, file_url = scraper.get_tags_from_image_page(f'{site}/post/show/{idx}')

        tags = tag_parser.get_ch_tags_from_eng(tags)

        if image_name != '':
            annotation = f'AUTO_DOWNLOAD\n{datetime.datetime.now()}\n{source}'
            eagle.add_from_url(file_url, image_name, tags, file_url, annotation)

        cfg.set_last_download_max_id(target, idx)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Yande and Konachan to Eagle")
    parser.add_argument("--config_path", default="./config.ini", help="Path to the config file")
    parser.add_argument("--yaml_path", default="map.yaml", help="Path to the YAML file")
    parser.add_argument("--target", default="konachan", choices=["yande", "konachan"], help="Target site for image crawling")

    args = parser.parse_args()

    try:
        main(args.config_path, args.yaml_path, args.target)
    except KeyboardInterrupt:
        logger.info('Stop image crawling!')

