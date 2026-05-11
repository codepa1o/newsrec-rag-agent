# MIND Small 数据集放置说明

本项目默认读取：

```text
data/mind/MINDsmall_train/news.tsv
data/mind/MINDsmall_train/behaviors.tsv
```

建议从 Microsoft MIND 官方页面下载 MINDsmall train/dev 数据。下载并解压后，把 `news.tsv` 和 `behaviors.tsv` 放到上面的目录。

没有下载数据时，项目会自动使用内置 sample 数据，方便先跑通 API、前端和测试。

验证解析：

```powershell
python scripts/ingest_mind.py --news data/mind/MINDsmall_train/news.tsv --behaviors data/mind/MINDsmall_train/behaviors.tsv
```
