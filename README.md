# music_analyze

把网易云音乐收藏的歌全部分析一遍：**BPM × Energy**，并画一张坐标固定的二维分布图。

## 特性

- 网易云扫码 / cookie 登录，cookie 本地保存，失效自动重登
- VIP 账号正常获取完整音频；只有试听片段的歌曲会被明确标记，而不是静默丢弃
- 只下载 128kbps standard 音质，逐首分析后立刻删除音频，磁盘占用极低
- BPM 双引擎：`beat_this`（ISMIR 2024）+ Essentia 交叉验证，带倍频/减半消歧
- Energy 由 EBU R128 响度、onset 率、谱通量、谱质心按固定标尺加权而成
- 结果写入 SQLite，随时中断续跑；图表坐标固定（BPM 40–220，Energy 0–1）

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd api
npm init -y
npm i @neteasecloudmusicapienhanced/api
cd ..
```

要求：Python 3.12（essentia 固定 `2.1b6.dev1389`）、Node 22+。
首次分析会自动下载 beat_this 模型（约 77MB）到 `~/.cache/torch`。

## 使用

```bash
.venv/bin/python run.py login            # 扫码登录；失败可用 --cookie "MUSIC_U=...; __csrf=..."
.venv/bin/python run.py fetch            # 拉收藏（--uid 可分析他人公开歌单）
.venv/bin/python run.py analyze          # 分析（先用 --limit 5 试跑；Ctrl-C 后可续跑）
.venv/bin/python run.py plot             # 出图 + CSV（--by-year 着色，--raw 看未消歧 BPM）
.venv/bin/python run.py status           # 查看进度
.venv/bin/python run.py all              # 一条龙
```

本地 API 服务由脚本自动启动，不需要手动开。

### 常用参数

| 命令 | 说明 |
| --- | --- |
| `login --force` | 强制重新扫码（切换账号） |
| `login --cookie "..."` | 免扫码导入浏览器 cookie（F12 Console 输入 `document.cookie`） |
| `logout` | 退出登录并删除本地 cookie |
| `analyze --aggressive` | 低 BPM 一律翻倍（电子/DnB 曲库推荐） |
| `analyze --allow-trial` | 只有试听片段时也分析（标记 `source_kind=trial`，结果可能不准） |
| `analyze --retry-errors` | 重试之前失败的歌 |
| `analyze --keep-audio` | 保留下载的 128k 音频（默认分析完即删） |

## 输出（`data/`，已 gitignore）

| 文件 | 内容 |
| --- | --- |
| `bpm_energy_distribution.png` | 固定坐标分布图 |
| `tracks.csv` | 每首歌的 BPM / Energy |
| `music.db` | SQLite 结果库，断点续跑 |
| `bpm_review.csv` | 低 BPM / 双引擎分歧曲目，建议人工复核 |
| `bpm_overrides.csv` | 人工修正，每行 `id,bpm` |
| `cookies.json` | 登录态，请勿外传 |

## BPM 说明

八度歧义没有完美算法。实测 Essentia 在 140 BPM 会减半，`beat_this` 能修正，但 174+ 的纯四踩底鼓仍可能被算成 87。缓解方式：

- 默认用 `beat_this` 结果，并根据半拍强度自动消歧
- 电子/DnB 较多时加 `--aggressive`
- 复核 `bpm_review.csv`，有疑问的写进 `bpm_overrides.csv`

## 配置

`music_analyze/config.py`：坐标范围、Energy 权重与标尺、消歧阈值、音质等级、限速等。

## 免责声明

仅供个人学习与数据分析，请尊重版权、支持正版；音频文件即用即删。
