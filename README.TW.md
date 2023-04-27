# Yande and Konachan to Eagle with Tags

[EN](./README.md) | [TW](./README.TW.md)

![image](https://user-images.githubusercontent.com/10178964/234870235-f0dbe874-c1e8-4320-9c52-d6d920fa274d.png)


## 介紹

這個 repo 是一個圖片抓取和使用 [Eagle](https://eagle.cool/) 進行標籤管理的範例

內容會使用到另一個以 Python 開發的 Wrapper [Eagle-Wapper](https://github.com/NatLee/Eagle-Wrapper) 來實作

執行步驟是從指定網站（`yande.re` 或 `konachan.com`）拿到圖片的URL及標籤，再將它們推送到 Eagle 中進行儲存

## 使用方法

首先，你必須複製一份 `./map.example.yaml` 到 `./map.yaml`

內容是網站上檔案名稱的標籤對應表，並且你可以自由的進行修改他們的對應

> 這邊要注意上面的名稱不一定能對到所有的標籤，請自行查詢後增加

再來，安裝所需套件，內容包含必要的 `eaglewrapper`

```bash
pip install -r requirements
```

接著再使用 python 執行 main.py

```bash
python main.py
```

你可以使用參數來指定設定檔位置、映射文件及特定網站，詳細可以使用`python main.py --help`查看

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
