# 踩过的坑（省你时间）

一次真实发布（4.5 分钟 / 113MB / AI 生成短剧）从零跑通的全过程记录。按「你大概率会撞上」的顺序排。

## 1. 创作者中心的提交类按钮不响应程序化点击

**现象**：`发布`、`设置竖封面`、`完成`、`继续编辑`、`上传封面`、`自主声明` 这些按钮，用 `pyautogui.click` 点了完全没反应；同一页面的输入框、左侧导航、滚动都正常。

**不是坐标问题**，同一坐标点输入框能聚焦、点左侧导航能跳页。

**试过全部无效**：
- `pyautogui.click` / `doubleClick`
- `moveTo` 停留后再点、`mouseDown` + `mouseUp` 分离
- `PostMessage(WM_LBUTTONDOWN/UP)` 直接发给窗口
- 点击按钮不同位置（左中右、上边缘）
- `Tab` 聚焦后 `Enter`（偶尔触发，但会误触「暂存离开」把草稿退回上传页）

**结论**：把它们留给人。工具的职责是「把内容摆好」。

## 2. 标题框只吃输入法

**现象**：
- `Ctrl+V` → 没反应
- `SendInput` + `KEYEVENTF_UNICODE`（直接注入字符）→ 没反应
- `Backspace` / `Ctrl+A` → 没反应

同一个页面的简介 `textarea` **接受** `Ctrl+V`、中文、换行。

**唯一有效路径**：
```
点简介框 → Shift+Tab 回到标题 input → 打拼音（如 d h）→ 按数字选词
```
候选第一条通常就是要的词；不确定就截图看候选条。

**更要命的**：标题 30 字上限，**写满后彻底锁死**，任何输入都进不去，连退格都不响应。所以必须一次写对。曾经把整段简介粘进标题框，字数被截到 30 后框就此变砖，只能重开页面。

## 3. 重开页面会丢文字字段

视频在服务端草稿里，但**标题、简介不会保存**。`继续编辑` 恢复出来的只有视频，文字要重填。

## 4. 两个窗口都叫「抖音」

主窗口和创作者中心窗口 `GetWindowText` 都返回「抖音」。按标题匹配必然挑错，导致点击落在被遮挡的窗口上。

**对策**：用 `dy.py list` 查 hwnd，或按「位于原点」/「最大的」来判定主窗口。

## 5. 其它应用会抢焦点

Harness / ChatGPT 等窗口抢到前台后，`pyautogui.click` 会点到它们身上（曾把中文打进用户的聊天输入框）。每次操作前 `dy.py front` 重新抬窗口。

## 6. 客户端不接受 `--remote-debugging-port`

```powershell
# 这样起不来调试端口，launcher 丢弃参数
Start-Process douyin.exe -ArgumentList '--remote-debugging-port=9333'
```
`/json/version` 永远连不上。CDP 接不进 webview，所以没有 DOM 操作的可能。

## 7. 强杀客户端后起不来

`taskkill /F /IM douyin.exe` + `douyin_guard.exe` 之后：
- `Start-Process "D:\douyin\douyin.exe"` → 没反应
- 双击快捷方式 `.lnk` → 没反应
- 清 `D:\douyin\lock` → 没反应
- **`explorer.exe "D:\douyin\douyin.exe"` → 起来了**

所以要重启客户端时，直接用 explorer。

## 8. 客户端 cookie 解不出来

`%APPDATA%\douyin\tt_Cookies` 里能看到 `sessionid` / `sid_tt` / `ttwid`，值是 `v10` 前缀的 AES 密文。但：

- `Local State` 的 `os_crypt.encrypted_key` 用 DPAPI 解出来的 32 字节 key，解 `sessionid` 报 `InvalidTag`
- 抖音设了 `os_crypt.audit_enabled=true`，密钥不在标准位置
- AES-CBC / CTR 各种组合都是乱码

**结论**：拿不到客户端登录态去做网页版。网页版只能扫码一次。

## 9. 网页版：页面会被关掉

用 Playwright `connect_over_cdp` 打开 `creator.douyin.com`，页面几秒后 `TargetClosedError`。

一开始误判成反爬，实际是**用户自己关的窗口**。排查时先确认没人在操作。

## 10. 抖音会补全话题

简介里写 `#蒸汽朋克`，抖音可能自动补成 `#蒸汽朋克打火机`。回车/发布前看一眼，不想要就删。

## 11. 封面是发布的前置

`发布` 按钮可能是 disabled（缺封面），但视觉上仍是黑色，点了没反应会误以为点不动。

**对策**：先设一张封面（点 AI 推荐封面 → 设置竖封面），再发布。

## 12. 文件对话框

Electron 走的是原生 Win32 对话框：

- 类名 `#32770`，标题「打开」
- 文件名输入框 **id 1148**（Vista 之后）
- `SendMessageW(edit, WM_SETTEXT, ...)` 写路径 + `PostMessageW(hwnd, WM_COMMAND, IDOK)` 提交

不要试着用键盘输入——对话框可能没拿到焦点。

## 13. 比例坐标 + DPI

坐标按「相对窗口宽高」存，屏幕分辨率/缩放才不影响。但还要 `SetProcessDpiAwareness(2)`，否则 125%/150% 缩放下 `GetWindowRect` 和 `pyautogui` 的坐标系会错开 1.25/1.5 倍。

`dy.py` 在 import 时就设了这个。
