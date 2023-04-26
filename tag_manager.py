import yaml

class TagManager:
    def __init__(self, filename: str):
        self.filename = filename
        self.mapper = self.read()
        self.eng_keys = sorted(self.mapper.keys(), key=lambda x: '_' in x, reverse=True)
        self.dash_eng_keys = [key for key in self.eng_keys if '_' in key]

    def read(self):
        with open(self.filename, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        return data

    def write(self, data: dict) -> None:
        with open(self.filename, 'w', encoding='utf-8') as file:
            yaml.safe_dump(
                data,
                file,
                allow_unicode=True,
                sort_keys=False
            )

    def get_tags_from_name(self, name: str) -> list:
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

    def get_ch_tags_from_eng(self, eng_tags: list) -> list:
        ch_tags = set()
        for eng_tag in eng_tags:
            ch_tag = self.mapper.get(eng_tag)
            if ch_tag:
                ch_tags.update(ch_tag)
        return list(ch_tags)
