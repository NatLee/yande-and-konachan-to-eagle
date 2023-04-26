import re
from typing import Tuple, Union, Dict
import urllib.parse
import json

import requests
from bs4 import BeautifulSoup
from loguru import logger
import xmltodict

from tag_manager import TagManager

class ImageScraper:
    def __init__(self, site: str, tag_parser: TagManager):
        self.site = site
        self.tag_parser = tag_parser

    def get_tags_from_image_page(self, url: str) -> Tuple[str, list, str, Union[str, None]]:
        r = requests.get(url)
        html = BeautifulSoup(r.text, 'html.parser')

        image_name = ""
        tags = []
        source = ""
        file_url = None

        try:
            post_view = html.find_all('div', attrs={'id': 'post-view'})[-1]
            data = json.loads(post_view.find_all('script')[0].string.replace('Post.register_resp(', '')[:-3]).get('posts')[0]
            tags = data.get('tags').split(' ')
            source = data.get('source')
            if source is None:
                source = ''
            file_url = data.get('file_url')
            parse_link = urllib.parse.unquote(file_url)
            image_name = parse_link.split('/')[-1].replace(' ', '_')
        except Exception as _:
            if r.text.find('This post does not exist.') != -1:
                logger.warning(f'{url} :: NOT EXIST')
            elif r.text.find('This post was deleted.') != -1:
                logger.warning(f'{url} :: DELETED')
            else:
                logger.warning(f'{url} :: UNKNOWN')

        return image_name, tags, source, file_url

    @staticmethod
    def get_newest_image_id(site: str):
        url = f'{site}/post/atom'
        req = requests.get(url)
        ids = []

        def extract_number_from_string(input_string: str) -> int:
            match = re.search(r'/(\d+)', input_string)
            return int(match.group(1)) if match else None

        for entry in xmltodict.parse(req.text)['feed']['entry']:
            img_id = extract_number_from_string(entry['id'])
            if img_id == None:
                continue
            ids.append(img_id)

        return max(ids)

    @staticmethod
    def get_large_image_urls_with_list_page_number(page_number: int, site: str, format_patterns=['jpg', 'png', 'gif']) -> Tuple[Dict[int, dict], int, int]:

        url = f'{site}/post?page={page_number}'
        r = requests.get(url, timeout=10)
        html = BeautifulSoup(r.text, 'html.parser')

        post = html.find_all('ul', attrs={'id': 'post-list-posts'})[-1]
        direct_links = post.find_all('a', attrs={'class': 'directlink'})

        large_image_infos = {}
        image_ids = []

        for direct_link in direct_links:
            image_link = direct_link.get('href')
            parse_link = urllib.parse.unquote(image_link)
            parts = parse_link.split(' ')

            image_name = parse_link.split('/')[-1].replace(' ', '_')
            image_format = parse_link.split('.')[-1]

            image_id = int(parse_link.replace(' -', '').split(' ')[1])
            image_ids.append(image_id)

            tags = []

            for part in parts[2:]:
                for format_pattern in format_patterns:
                    part = part.replace(f'.{format_pattern}', '')
                tags.append(part)

            large_image_infos[image_id] = {
                'url': image_link,
                'name': image_name,
                'format': image_format,
                'tags': tags
            }

        return large_image_infos, min(image_ids), max(image_ids)

    def iter_all_list_page_to_get_images(self, last_download_max_id: int) -> Dict[str, dict]:
        page_number_count = 1
        image_infos = {}
        while True:

            logger.info(f'page: {page_number_count}')
            large_image_infos, min_id, max_id = self.get_large_image_urls_with_list_page_number(page_number_count, self.site)

            logger.info(f'min: {min_id}, max: {max_id}')

            for iid, data in large_image_infos.items():
                if iid > last_download_max_id:
                    url = data.get('url')
                    name = data.get('name')
                    tags = data.get('tags')

                    image_infos[name] = {
                        'tag': tags,
                        'url': url
                    }

            if min_id > last_download_max_id:
                page_number_count = page_number_count + 1
            else:
                break

        return image_infos