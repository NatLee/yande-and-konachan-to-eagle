# Yande and Konachan to Eagle with Tags

[EN](./README.md) | [TW](./README.TW.md)

![image](https://user-images.githubusercontent.com/10178964/234870235-f0dbe874-c1e8-4320-9c52-d6d920fa274d.png)

## Introduction

This repo is an example of image scraping and tag management using [Eagle](https://eagle.cool/) and [Eagle-Wapper](https://github.com/NatLee/Eagle-Wrapper) with Python.

The execution involves obtaining image URLs and tags from specified websites (`yande.re` or `konachan.com`), and then pushing them to Eagle for storage.

## Usage

At first, you need to create a map by copying `./map.example.yaml` to `./map.yaml`.

You can modify the map with your own tags which will be parsed from the name.

> Notice that the tags in the map are not all tags in the sites, please add more tags by yourself.

Then, install the required packages, including the necessary `eaglewrapper`:

```bash
pip install -r requirements
```

Next, run `main.py` using Python:

```bash
python main.py
```

You can use arguments to specify the configuration file location, mapping file, and specific website. For more details, use `python main.py --help` to view:

```
usage: main.py [-h] [--config_path CONFIG_PATH] [--yaml_path YAML_PATH] [--target {yande,konachan}]

Yande and Konachan to Eagle

optional arguments:
  -h, --help            show this help message and exit
  --config_path CONFIG_PATH
                        Path to the config file
  --yaml_path YAML_PATH
                        Path to the YAML file
  --target {yande,konachan}
                        Target site for image crawling
```



## Contributor

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center"><a href="https://github.com/NatLee"><img src="https://avatars.githubusercontent.com/u/10178964?v=3?s=100" width="100px;" alt="Nat Lee"/><br /><sub><b>Nat Lee</b></sub></a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
