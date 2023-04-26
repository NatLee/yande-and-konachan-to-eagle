from configparser import ConfigParser

class Config:
    def __init__(self, config_path):
        self.config_path = config_path
        self.cfg = ConfigParser()
        self.cfg.optionxform = str
        self.cfg.read(self.config_path, encoding='utf-8')

    def get_site(self, target):
        return self.cfg.get(target, 'site')
    
    def get_last_download_max_id(self, target):
        return self.cfg.getint(target, 'last_download_max_id')

    def set_last_download_max_id(self, target, count):
        self.cfg.set(target, 'last_download_max_id', str(count))
        self.write_config()
        return
    
    def write_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as c:
            self.cfg.write(c)
        return
