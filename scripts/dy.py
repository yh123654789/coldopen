#!/usr/bin/env python
"""dy.py — Douyin desktop automation kit (Windows). Machine-independent by design.

Coordinates are stored as *fractions of the window* (0..1), so the same config
works on a 1080p laptop and a 4K desktop as long as the app layout is the same.
DPI awareness is forced on so screen coordinates match what you see.

  python dy.py doctor                 环境自检（依赖 / 客户端 / Chrome / 窗口）
  python dy.py list                   列出可见窗口，找抖音的 hwnd
  python dy.py front                  把抖音主窗口抬到前台并规整成标准尺寸
  python dy.py calibrate              交互式校准：鼠标指到控件上按回车，自动记录比例坐标
  python dy.py shot step1             截图到 out/shots/
  python dy.py click upload_video     按名字点击（配置里的比例坐标）
  python dy.py click 860 345          按绝对屏幕坐标点击
  python dy.py paste "文本"            剪贴板 + Ctrl+V
  python dy.py ime dh 1               输入法：打拼音→按数字选词（标题专用）
  python dy.py dialog "D:/a.mp4"      填原生“打开”对话框并确认
  python dy.py key enter / hotkey ctrl v / scroll -600 8 / wait 2

Why the shape of this tool: the Douyin creator center is an Electron webview in
which submit-style buttons ignore synthetic clicks, while inputs, Tab navigation
and IME input still work. Text therefore goes in via clipboard or IME, and the
final 发布 click stays with a human.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

# ---- make screen coordinates DPI-correct before anything reads them -----------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.12

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
SW_RESTORE = 9
WM_SETTEXT = 0x000C
WM_COMMAND = 0x0111
IDOK = 1

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEFAULT_CONFIG = ROOT / "config.example.json"
LOCAL_CONFIG = ROOT / "config.local.json"

TARGET_TITLES = ("抖音", "Douyin")


# ------------------------------------------------------------------ config
def load_config() -> dict:
    for p in (LOCAL_CONFIG, DEFAULT_CONFIG):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8-sig"))
    return {"coords": {}}


def save_local(cfg: dict) -> None:
    LOCAL_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ windows
def visible_windows() -> list[dict]:
    rows = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            t = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, t, 512)
            if t.value:
                r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                rows.append({"hwnd": hwnd, "title": t.value, "x": r.left, "y": r.top,
                             "w": r.right - r.left, "h": r.bottom - r.top})
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return rows


def find_app_window(prefer_largest: bool = False) -> dict | None:
    cands = [w for w in visible_windows() if any(t in w["title"] for t in TARGET_TITLES)]
    if not cands:
        return None
    if prefer_largest:
        return max(cands, key=lambda w: w["w"] * w["h"])
    # the main client window is normally the one sitting at the origin
    at_origin = [w for w in cands if w["x"] <= 4 and w["y"] <= 4]
    return (at_origin or cands)[0]


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def front(hwnd: int, rect: str | None = None) -> tuple[int, int, int, int]:
    if rect:
        x, y, w, h = (int(v) for v in rect.split(","))
        user32.MoveWindow(hwnd, x, y, w, h, True)
        time.sleep(0.3)
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.4)
    return window_rect(hwnd)


# ------------------------------------------------------------------ coords
def resolve(name: str, cfg: dict, win: tuple[int, int, int, int] | None) -> tuple[int, int]:
    """Turn a coordinate name (fraction of window) into absolute screen pixels."""
    coords = cfg.get("coords", {})
    if name not in coords:
        raise SystemExit(f"unknown coordinate name: {name} (have: {', '.join(sorted(coords))})")
    fx, fy = coords[name]
    if win is None:
        raise SystemExit("no window found; run `dy.py front` first or pass --hwnd")
    x, y, w, h = win
    return int(x + fx * w), int(y + fy * h)


# ------------------------------------------------------------------ input
def paste(text: str, settle: float = 1.4) -> None:
    subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
    time.sleep(0.35)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(settle)


def send_unicode(text: str, gap: float = 0.05) -> None:
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    for ch in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, ord(ch), flags, 0, None))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(gap)


def ime(pinyin: str, pick: int | None = 1, gap: float = 0.4) -> None:
    """Type latin letters so the Chinese IME builds candidates, then pick one.

    Only reliable route into Douyin's title input (it ignores paste/unicode).
    Screenshot first when unsure which candidate is correct.
    """
    for ch in pinyin:
        pyautogui.press(ch)
        time.sleep(gap)
    if pick:
        time.sleep(0.6)
        pyautogui.press(str(pick))
        time.sleep(1.2)


# ------------------------------------------------------------------ dialogs
def file_dialog(path: str) -> bool:
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "#32770":
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, t, 256)
                found.append((hwnd, t.value))
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    if not found:
        print("no native file dialog found")
        return False
    hwnd, title = found[-1]
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.6)
    edit = user32.GetDlgItem(hwnd, 1148)
    if not edit:
        print("filename edit not found in", title)
        return False
    user32.SendMessageW(edit, WM_SETTEXT, 0, ctypes.c_wchar_p(path))
    time.sleep(0.5)
    user32.PostMessageW(hwnd, WM_COMMAND, IDOK, 0)
    print("submitted:", path)
    return True


def shot(name: str) -> Path:
    d = OUT / "shots"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.png"
    pyautogui.screenshot(str(p))
    print(p)
    return p


# ------------------------------------------------------------------ env probe
def find_client() -> dict:
    """Locate the Douyin desktop client without hardcoding a path."""
    info = {"exe": None, "install_dir": None, "user_data": None}
    try:
        import winreg
        roots = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
        subs = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        for root in roots:
            for sub in subs:
                try:
                    with winreg.OpenKey(root, sub) as k:
                        for i in range(winreg.QueryInfoKey(k)[0]):
                            entry = winreg.EnumKey(k, i)
                            try:
                                with winreg.OpenKey(k, entry) as sk:
                                    try:
                                        disp = winreg.QueryValueEx(sk, "DisplayName")[0]
                                    except OSError:
                                        continue
                                    if "抖音" not in disp and "douyin" not in disp.lower():
                                        continue
                                    try:
                                        loc = winreg.QueryValueEx(sk, "InstallLocation")[0]
                                    except OSError:
                                        loc = ""
                                    if loc and not info["install_dir"]:
                                        info["install_dir"] = loc.rstrip("\\/")
                            except OSError:
                                continue
                except OSError:
                    continue
    except Exception as e:
        print("registry probe skipped:", e)
    for guess in [info["install_dir"], r"C:\Program Files\douyin", r"D:\douyin",
                  r"D:\Programs\douyin", os.path.expandvars(r"%LOCALAPPDATA%\Programs\douyin")]:
        if guess and Path(guess, "douyin.exe").exists():
            info["install_dir"] = guess
            info["exe"] = str(Path(guess, "douyin.exe"))
            break
    appdata = Path(os.environ.get("APPDATA", "")) / "douyin"
    if appdata.exists():
        info["user_data"] = str(appdata)
    return info


def find_chrome() -> str | None:
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")):
        if Path(p).exists():
            return p
    return None


def doctor() -> int:
    cfg = load_config()
    print("== python ==")
    print(" ", sys.version.split()[0], sys.executable)
    print("== dependencies ==")
    for mod in ("pyautogui", "PIL", "cv2", "imageio_ffmpeg", "playwright"):
        try:
            __import__(mod)
            print(f"  ok   {mod}")
        except Exception as e:
            print(f"  MISS {mod}  ({type(e).__name__})")
    print("== douyin client ==")
    c = find_client()
    for k, v in c.items():
        print(f"  {k}: {v or 'not found'}")
    print("== chrome ==")
    print("  ", find_chrome() or "not found (web route unavailable)")
    print("== window ==")
    w = find_app_window()
    print("  ", w or "not running")
    print("== config ==")
    print("  ", LOCAL_CONFIG if LOCAL_CONFIG.exists() else DEFAULT_CONFIG)
    print("   coords:", len(cfg.get("coords", {})))
    print("== screen ==")
    print("  ", pyautogui.size())
    return 0


# ------------------------------------------------------------------ calibrate
CALIB_STEPS = [
    ("upload_icon", "抖音主界面右上角「投稿」图标（不带红点也行）"),
    ("sidebar_my", "左侧导航「我的」（不要点上面那行「朋友」）"),
    ("upload_video_button", "创作者中心「上传视频」黑色按钮"),
    ("title_field", "发布页「填写作品标题」输入框中央"),
    ("desc_field", "发布页「添加作品简介」文本框中央"),
    ("publish_button", "页面最底部「发布」黑色按钮"),
]


def calibrate() -> int:
    cfg = load_config()
    cfg.setdefault("coords", {})
    win = find_app_window()
    if not win:
        raise SystemExit("抖音客户端没在运行，先打开它")
    hwnd = win["hwnd"]
    front(hwnd)
    x, y, w, h = window_rect(hwnd)
    print(f"窗口 hwnd={hwnd} rect=({x},{y},{w},{h})")
    print("接下来按提示把鼠标移到对应控件上，然后按回车记录；直接回车跳过。\n")
    pt = wintypes.POINT()
    for name, desc in CALIB_STEPS:
        input(f"[{name}] 请把鼠标放到：{desc} → 按回车 ")
        user32.GetCursorPos(ctypes.byref(pt))
        fx = round((pt.x - x) / w, 4)
        fy = round((pt.y - y) / h, 4)
        if not (0 <= fx <= 1 and 0 <= fy <= 1):
            print("  警告：鼠标不在窗口内，已跳过")
            continue
        cfg["coords"][name] = [fx, fy]
        print(f"  记录 {name} = [{fx}, {fy}]")
    cfg.setdefault("window", {})["rect"] = "0,0,1440,960"
    save_local(cfg)
    print("\n已写入", LOCAL_CONFIG)
    return 0


# ------------------------------------------------------------------ cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Douyin desktop automation kit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor")
    sub.add_parser("list")
    sub.add_parser("calibrate")

    p = sub.add_parser("front")
    p.add_argument("--hwnd", type=int)
    p.add_argument("--rect")

    p = sub.add_parser("shot")
    p.add_argument("name")

    for nm in ("click", "dclick"):
        p = sub.add_parser(nm)
        p.add_argument("target", nargs="+", help="坐标名 或 X Y")
        p.add_argument("--settle", type=float, default=1.2)

    p = sub.add_parser("paste")
    p.add_argument("text")
    p.add_argument("--settle", type=float, default=1.4)

    p = sub.add_parser("ime")
    p.add_argument("pinyin")
    p.add_argument("pick", type=int, nargs="?", default=1)

    p = sub.add_parser("type")
    p.add_argument("text")

    p = sub.add_parser("key")
    p.add_argument("key")

    p = sub.add_parser("hotkey")
    p.add_argument("keys", nargs="+")

    p = sub.add_parser("scroll")
    p.add_argument("amount", type=int)
    p.add_argument("times", type=int, nargs="?", default=1)

    p = sub.add_parser("dialog")
    p.add_argument("path")

    p = sub.add_parser("wait")
    p.add_argument("seconds", type=float)

    a = ap.parse_args(argv)
    cfg = load_config()

    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "calibrate":
        return calibrate()
    if a.cmd == "list":
        for w in visible_windows():
            print(f"{w['hwnd']:>10}  {w['x']:>5},{w['y']:>5} {w['w']:>5}x{w['h']:<5} {w['title']}")
        return 0

    if a.cmd == "front":
        hwnd = a.hwnd or (find_app_window() or {}).get("hwnd")
        if not hwnd:
            raise SystemExit("no douyin window; start the client first")
        rect = a.rect or cfg.get("window", {}).get("rect")
        print("front", hwnd, front(hwnd, rect))
        return 0

    if a.cmd in ("click", "dclick"):
        if len(a.target) == 1:
            win = find_app_window()
            if not win:
                raise SystemExit("no douyin window")
            x, y = resolve(a.target[0], cfg, window_rect(win["hwnd"]))
        elif len(a.target) == 2:
            x, y = int(a.target[0]), int(a.target[1])
        else:
            raise SystemExit("use: click <name> | click X Y")
        (pyautogui.click if a.cmd == "click" else pyautogui.doubleClick)(x, y)
        time.sleep(a.settle)
        return 0

    if a.cmd == "shot":
        shot(a.name)
    elif a.cmd == "paste":
        paste(a.text, a.settle)
    elif a.cmd == "ime":
        ime(a.pinyin, a.pick)
    elif a.cmd == "type":
        send_unicode(a.text)
    elif a.cmd == "key":
        pyautogui.press(a.key)
        time.sleep(0.3)
    elif a.cmd == "hotkey":
        pyautogui.hotkey(*a.keys)
        time.sleep(0.3)
    elif a.cmd == "scroll":
        for _ in range(a.times):
            pyautogui.scroll(a.amount)
            time.sleep(0.05)
        time.sleep(0.6)
    elif a.cmd == "dialog":
        return 0 if file_dialog(a.path) else 1
    elif a.cmd == "wait":
        time.sleep(a.seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
