---
name: douyin-publish
description: 在抖音（桌面客户端 / 网页版）发布短剧视频：合成电影片头卡、生成封面、上传、填标题简介话题、发布；也用于改抖音昵称和个人简介。用户说“发抖音”“发布作品”“把这个短剧发出去”“改抖音昵称/简介”“矩阵号日更”时用。
---

# 抖音发布（douyin-publish）

素材目录约定：`D:\Projects\douyin-auto`（脚本 + 输出），素材由用户指定。

## 一、环境事实（2026-11 实测，先读这段再动手）

| 事实 | 含义 |
|---|---|
| 客户端 `D:\douyin\douyin.exe`（8.8.0，Electron），数据在 `%APPDATA%\douyin` | 桌面端是主路径，用户通常已登录 |
| 登录态在 `%APPDATA%\douyin\tt_Cookies`，抖音私有加密（`os_crypt.audit_enabled=true`） | **标准 DPAPI 解不开，不要逆向**，网页版只能扫码 |
| 创作者中心是 Electron webview | **发布 / 设置竖封面 / 完成 / 继续编辑 / 上传封面 / 自主声明** 这些按钮鼠标点击无效 |
| 同一 webview 里输入框、左侧导航、滚轮、Tab、输入法注入正常工作 | 填内容能自动化，**提交动作要人点** |
| 客户端不接受 `--remote-debugging-port` | CDP 接不进 webview，别浪费时间 |
| 强杀 `douyin.exe` 后用 `Start-Process` 起不来 | 恢复命令：`explorer.exe "D:\douyin\douyin.exe"` |

## 二、标准工作流

### 1. 片头卡 + 成片
```powershell
cd D:\Projects\douyin-auto
.\.venv\Scripts\python.exe frames.py        # 抽帧到 frames/
.\.venv\Scripts\python.exe title_card.py    # 1280x720 标题卡 + 拼成 cover/master_with_title.mp4
```
片头卡：黑底海水纹理 + 「地 海」华文中宋大字 + 英文副标 + 章节 + 右下「AI 创作」角标，2.5 秒淡入淡出。
修改文案改 `title_card.py` 里的 `TITLE / SUBTITLE_EN / CHAPTER`。

### 2. 封面（可选，用于抖音封面位）
```powershell
.\.venv\Scripts\python.exe cover.py        # 竖 1080x1440 / 横 1600x1200
```
选中某一帧后 `cover_final.py` 出最终版。注意别选带烧录字幕的帧。

### 3. 打开发布页
1. `python listwin.py` 找窗口（会有两个都叫“抖音”：主窗口 + 创作者中心）
2. `python front_hwnd.py <创作者中心hwnd> 0 0 1440 960` 抬到前台
3. 主窗口里点「投稿」`(x≈1203, y≈17)` → 菜单「发布作品」

### 4. 上传视频
```powershell
.\.venv\Scripts\python.exe gui.py click 960 691 3     # 上传视频
.\.venv\Scripts\python.exe up_again.py                 # 文件对话框填路径（GetDlgItem 1148 + IDOK）
```
`up_again.py` 里改视频路径；70MB 约 16 秒传完。

### 5. 填简介（这一步可以直接粘）
```powershell
.\.venv\Scripts\python.exe gui.py click 860 345 1
.\.venv\Scripts\python.exe gui.py paste "简介正文…"
```
**简介 textarea 接受 `Ctrl+V`**，中文、换行、话题都能进。

### 6. 填标题（只能用输入法，重要）
```powershell
.\.venv\Scripts\python.exe fill3.py     # 内含：点简介框 → Shift+Tab → 打 d,h → 按 1 选“地海”
```
- 标题框 **拒绝 paste、拒绝 Unicode 注入、拒绝键盘退格**
- 唯一有效路径：点简介框 → `Shift+Tab` 回到标题 input → 打拼音 → 按数字选词
- 一个字以上：连续打拼音，候选第一条通常是想要的词；不确定就截图看候选
- **30 字上限，写满后彻底锁死**，所以必须一次写对，别填长再改

### 7. 封面与发布（人点）
- 封面：点 AI 推荐封面缩略图 → 需要人点「设置竖封面」（程序点不动）
- 发布：需要人点「发布」黑色按钮（程序点不动）
- 兜底：`Tab` 能把焦点走到这些按钮上，`Enter` 偶尔能触发，但**会误触“暂存离开”导致退回上传页**，不要依赖

### 8. 文案模板（短剧号）
标题 ≤30 字，示例：`地海`
简介示例：
```
地海之下没有天空。查尔斯摊开海图，想找到通往地表的出口——可这艘「活船」，似乎比他更清楚该往哪里开。

AI 生成短剧，人物、场景与配音均由 AI 创作
#地海 #AI创作 #AI短剧 #悬疑 #科幻
```
- 话题标签写进简介即可，抖音会自动识别成蓝色标签
- 注意抖音的话题自动补全：`#蒸汽朋克` 可能被补成 `#蒸汽朋克打火机`，回车前看一眼
- **AI 创作标注必须有**：简介正文 + 片头卡角标，双保险

## 三、踩过的坑（按重要性）

1. **先设一次封面再发布**：发布按钮可能是 disabled 状态（缺封面），视觉上仍是黑色，点了没反应
2. **重开页面会丢文字字段**：视频在服务端草稿里，标题/简介不保存，要重填
3. **两个窗口同名**：`MoveWindow` + `SetForegroundWindow` 要指定 hwnd，别用标题匹配
4. **其它应用（Harness/ChatGPT）会抢焦点**：每次点击前重新抬窗口，或把它们最小化
5. **不要用 Unicode 注入写中文**：`unicode_type.py` 会把字打进当前前台窗口，曾经打进用户的聊天框
6. **文件对话框**：标题是「打开」，类名 `#32770`，文件名控件 id `1148`；`SendMessageW(WM_SETTEXT)` + `PostMessageW(WM_COMMAND, IDOK)`

## 四、长期方案（推荐，待做）

网页版 `creator.douyin.com` + Playwright，`web_publish.py` 已写好框架：
- 直接 `set_input_files` 塞视频，`fill()` 写标题/简介，点按钮走 DOM —— **不依赖任何坐标点击**
- 门槛：需要用户扫码登录一次（客户端 cookie 拿不出来）
- 登录态存在 `D:\Projects\douyin-auto\webprofile`，之后长期复用
- 注意：调试连接期间用户手动关页面会报 `TargetClosedError`，不是反爬

矩阵号日更的调度（cron 拆任务 → 派活 → 收集 → 入库/发布）参考 `agent-autoloop` skill。

## 五、改昵称 / 个人简介

入口：客户端左侧「我的」（注意别点到上面「朋友」，坐标按截图校准）→ 主页「编辑资料」。
昵称、简介都是受控 input，**昵称大概率同样拒绝 paste**，按「Shift+Tab + 输入法」处理；保存按钮需人点。

短剧号命名参考：
- 昵称：`地海剧场`（≤20 字，别用“官方”“认证”）
- 简介（≤80 字）：
```
《地海》AI 生成悬疑短剧 · 连载中
查尔斯带着钢铁左手，在地海之下寻找通往地表的出口
每周更新｜点合集追更｜内容由 AI 创作
```
