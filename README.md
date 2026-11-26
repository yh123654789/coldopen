# douyin-publish

**抖音短剧发布工具箱**：给视频贴电影片头卡、出海报封面、驱动抖音桌面客户端完成上传与填表。Windows，Python 3.10+。

> 这是把一次真实发布（113MB 短剧、4.5 分钟、AI 生成）从头跑通之后，把踩到的坑固化成工具的结果。所有「为什么这么绕」的原因都写在 [docs/PITFALLS.md](docs/PITFALLS.md)。

## 它能做什么

| 能力 | 说明 |
|---|---|
| 片头标题卡 | 给视频前面垫 2.5 秒电影感标题卡（大字片名 + 英文副标 + 章节 + `AI 创作` 角标），成片开篇即片名，封面也可直接取这一帧 |
| 封面合成 | 从成片抽帧 → 竖版 1080×1440 / 横版 1600×1200，自动压暗、暗角、排版 |
| 客户端自动化 | 上传视频、填标题、填简介、话题标签 |
| 换机器可用 | 坐标按「相对窗口比例」存 + DPI 感知 + 交互式校准；客户端路径从注册表自动探测 |
| 网页版框架 | `scripts/web_publish.py` 走 DOM，长期更稳，需扫码登录一次 |

## 为什么最后两下要你点

抖音桌面客户端的创作者中心是 Electron webview，实测这一整类控件**不响应程序化点击**：`发布`、`设置竖封面`、`完成`、`继续编辑`、`上传封面`。

同一页面里输入框、左侧导航、Tab、输入法注入都正常。所以：

- 文字走剪贴板或输入法
- **标题框只吃输入法**（粘贴、Unicode 注入、退格全部无效），且 30 字写满即永久锁死 → 必须一次写对
- 最后点「设置竖封面」和「发布」这两下，留给人

试过的、无效的路子：全局鼠标点击、按下抬起分离、`PostMessage` 直接发消息、Tab+Enter 兜底、UIA（Electron 未开 accessibility，树是空的）、`--remote-debugging-port`（被 launcher 丢弃）、客户端 cookie 解密（抖音私有加密）。

## 安装

```powershell
git clone https://github.com/<you>/douyin-publish.git
cd douyin-publish
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

`install.ps1` 会建 `.venv`、装依赖、跑环境自检。

依赖：`pyautogui` `pillow` `opencv-python-headless` `imageio-ffmpeg` `pywin32` `playwright`（网页版用）。
不需要 `playwright install`，只用系统已装的 Chrome。

## 换台电脑：一条命令校准

坐标存的是**相对窗口宽高的比例**，所以屏幕分辨率、DPI 缩放都不影响。唯一会变的是布局细节，校准一次即可：

```powershell
.\.venv\Scripts\python.exe .\scripts\dy.py front       # 打开客户端后，把窗口规整成标准尺寸
.\.venv\Scripts\python.exe .\scripts\dy.py calibrate   # 按提示把鼠标指到控件上，回车记录
```

`calibrate` 会依次问你 6 个控件的位置，写进 `config.local.json`（优先级高于 `config.example.json`）：

```
upload_icon           主界面右上角「投稿」
sidebar_my            左侧导航「我的」（别点到上面那行「朋友」）
upload_video_button   创作者中心「上传视频」
title_field           「填写作品标题」输入框
desc_field            「添加作品简介」文本框
publish_button        最底部「发布」
```

## 跑一条完整流程

```powershell
# 全自动到「填完标题」，最后两下人工
.\examples\publish_one.ps1 -Video "D:\ep.mp4" -Title "地海" -Pinyin dh -Chapter "第 186 — 187 章 · 活船"
```

或者手工一步步来：

```powershell
# 1. 片头卡 + 成片（cover/master_with_title.mp4）
.\.venv\Scripts\python.exe .\scripts\make_title_card.py --video "D:\ep.mp4" `
    --title "地海" --en "THE MYSTERIOUS SEA" --chapter "第 186 — 187 章 · 活船" --out cover

# 2. 挑一帧当封面（先看候选，避开带烧录字幕的帧）
.\.venv\Scripts\python.exe .\scripts\make_cover.py --video "D:\ep.mp4" --list-frames 10 --out cover/v.jpg
.\.venv\Scripts\python.exe .\scripts\make_cover.py --video "D:\ep.mp4" --at 0.95 `
    --size 1080x1440 --bias-x 0.25 --title "地海" --chapter "第 186 — 187 章 · 活船" --out cover/vertical.jpg

# 3. 上传
.\.venv\Scripts\python.exe .\scripts\dy.py front
.\.venv\Scripts\python.exe .\scripts\dy.py click upload_video_button 2
.\.venv\Scripts\python.exe .\scripts\dy.py dialog "$PWD\cover\master_with_title.mp4"

# 4. 简介（直接粘）
.\.venv\Scripts\python.exe .\scripts\dy.py click desc_field 1
.\.venv\Scripts\python.exe .\scripts\dy.py paste "地海之下没有天空……`n#地海 #AI创作"

# 5. 标题（输入法：打拼音 → 数字选词）
.\.venv\Scripts\python.exe .\scripts\dy.py click desc_field 1
.\.venv\Scripts\python.exe .\scripts\dy.py hotkey shift tab
.\.venv\Scripts\python.exe .\scripts\dy.py ime dh 1
.\.venv\Scripts\python.exe .\scripts\dy.py shot title_check      # 截图确认

# 6. 人工：设置竖封面 → 发布
```

## 命令速查

```powershell
dy.py doctor                 环境自检（依赖 / 客户端 / Chrome / 窗口 / 配置）
dy.py list                   列出窗口和 hwnd
dy.py front [--hwnd N] [--rect 0,0,1440,960]
dy.py calibrate              交互式校准坐标
dy.py shot NAME              截图到 out/shots/
dy.py click NAME|X Y         点控件（按名字）或点绝对坐标
dy.py paste "文本"            剪贴板 + Ctrl+V
dy.py ime dh 1               输入法：打 dh，选第 1 个候选
dy.py dialog "D:/a.mp4"      填「打开」对话框并确认
dy.py key enter / hotkey ctrl v / scroll -600 8 / wait 2
```

## 文案约定（短剧号）

- 标题 ≤30 字（超了框就锁死），例：`地海`
- 简介 ≤80 字，含 **AI 创作标注** + 话题标签
- 昵称 ≤20 字，例：`地海剧场`

```
《地海》AI 生成悬疑短剧 · 连载中
查尔斯带着钢铁左手，在地海之下寻找通往地表的出口
每周更新｜点合集追更｜内容由 AI 创作
```

## 已知限制

- 仅 Windows（win32 API、`GetDlgItem`、DPAPI、注册表）
- 客户端不接受调试端口，接不进 CDP
- 客户端被强杀后用 `Start-Process` 拉不起来，要用 `explorer.exe "<安装目录>\douyin.exe"`
- 抖音会更新 UI，版本升级后可能要重新 `calibrate`
- 请遵守平台规则；AI 生成内容保留标注

## 目录

```
install.ps1              一键安装
requirements.txt
config.example.json      比例坐标 + 文案模板
scripts/
  dy.py                  窗口/点击/粘贴/输入法/对话框/截图/校准/自检
  make_title_card.py     片头卡 + 拼接成片
  make_cover.py          封面合成、抽帧
  web_publish.py         网页版 DOM 路线（框架）
examples/
  publish_one.ps1        一条命令跑完整流程
docs/
  PITFALLS.md            所有坑和无效尝试（省你时间）
out/                     运行产物
```

## License

MIT
