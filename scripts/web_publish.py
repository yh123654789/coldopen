"""Publish a Douyin video through creator.douyin.com with Playwright (DOM-level, no coordinate clicking).

Flow: open creator center -> wait for login (QR) -> upload file via input[type=file] ->
fill title/description -> set visibility -> click publish -> verify.

Run:  python web_publish.py [--video PATH] [--title TEXT] [--desc TEXT]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
PROFILE = ROOT.parent / "webprofile"
SHOTS = ROOT.parent / "out" / "shots"
SHOTS.mkdir(exist_ok=True)
PROFILE.mkdir(exist_ok=True)

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
HOME_URL = "https://creator.douyin.com/creator-micro/home"

DEFAULT_VIDEO = ROOT.parent / "out" / "master_with_title.mp4"
DEFAULT_TITLE = "地海"
DEFAULT_DESC = (
    "地海之下没有天空。查尔斯摊开海图，想找到通往地表的出口——可这艘「活船」，似乎比他更清楚该往哪里开。\n\n"
    "AI 生成短剧，人物、场景与配音均由 AI 创作\n"
    "#地海 #AI创作 #AI短剧 #悬疑 #科幻"
)


def shot(page, name: str) -> Path:
    p = SHOTS / f"{name}.png"
    page.screenshot(path=str(p), full_page=False)
    return p


def is_login_page(page) -> bool:
    url = page.url.lower()
    if "login" in url or "passport" in url:
        return True
    try:
        body = page.inner_text("body", timeout=3000)
    except PWTimeout:
        return False
    markers = ("扫码登录", "验证码登录", "密码登录", "登录后查看")
    return any(m in body for m in markers) and "发布视频" not in body


def wait_login(page, timeout_s: int = 300) -> bool:
    print(">> 等待登录（请扫码）…")
    deadline = time.time() + timeout_s
    last = 0
    while time.time() < deadline:
        if not is_login_page(page):
            print(">> 登录成功")
            return True
        if time.time() - last > 15:
            shot(page, "web-qr")
            print(f">> 二维码截图已更新: {SHOTS / 'web-qr.png'}")
            last = time.time()
        page.wait_for_timeout(2000)
    return False


def fill_title(page, title: str) -> bool:
    selectors = [
        'input[placeholder*="作品标题"]',
        'input[placeholder*="标题"]',
        'input[placeholder*="填写作品标题"]',
        'div[contenteditable="true"][data-placeholder*="标题"]',
    ]
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=4000, state="visible")
            el.click()
            el.fill(title)
            print(f">> 标题已填: {title}  (selector={sel})")
            return True
        except Exception:
            continue
    return False


def fill_desc(page, desc: str) -> bool:
    selectors = [
        'div[contenteditable="true"]',
        'textarea[placeholder*="简介"]',
        'textarea',
    ]
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                if el.is_visible():
                    el.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Delete")
                    el.type(desc, delay=1)
                    print(f">> 简介已填 ({len(desc)} 字)  (selector={sel})")
                    return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(DEFAULT_VIDEO))
    ap.add_argument("--title", default=DEFAULT_TITLE)
    ap.add_argument("--desc", default=DEFAULT_DESC)
    ap.add_argument("--publish", action="store_true", help="actually click 发布 at the end")
    ap.add_argument("--login-timeout", type=int, default=300)
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        print("video missing:", video)
        return 1

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            channel="chrome",
            headless=False,
            viewport={"width": 1500, "height": 950},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=["--disable-blink-features=AutomationControlled", "--no-first-run",
                  "--no-default-browser-check"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        shot(page, "web-01-open")
        print("open:", page.url)

        if is_login_page(page):
            if not wait_login(page, args.login_timeout):
                print("login timeout")
                return 2
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
        shot(page, "web-02-upload-page")

        # upload the file straight into the hidden file input
        file_input = None
        for sel in ('input[type="file"]', 'input[accept*="video"]'):
            el = page.query_selector(sel)
            if el:
                file_input = el
                break
        if file_input is None:
            print("no file input found")
            shot(page, "web-err-noinput")
            return 3
        file_input.set_input_files(str(video))
        print(">> 已提交文件:", video.name)
        page.wait_for_timeout(6000)
        shot(page, "web-03-uploading")

        # wait for the edit form to appear
        for _ in range(40):
            if page.query_selector('input[placeholder*="标题"], div[contenteditable="true"]'):
                break
            page.wait_for_timeout(2000)
        page.wait_for_timeout(4000)
        shot(page, "web-04-form")

        title_ok = fill_title(page, args.title)
        page.wait_for_timeout(800)
        desc_ok = fill_desc(page, args.desc)
        page.wait_for_timeout(1500)
        shot(page, "web-05-filled")
        print("title:", title_ok, "desc:", desc_ok)

        # visibility: keep 公开 (default) — log what is selected
        try:
            radios = page.query_selector_all('label:has-text("公开"), span:has-text("公开")')
            print("visibility candidates:", len(radios))
        except Exception:
            pass

        if args.publish:
            clicked = False
            for sel in ('button:has-text("发布")', 'div[role="button"]:has-text("发布")',
                        'button:has-text("立即发布")'):
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible() and btn.is_enabled():
                        btn.click()
                        clicked = True
                        print(">> 已点击发布:", sel)
                        break
                except Exception:
                    continue
            if not clicked:
                print("publish button not clickable")
                shot(page, "web-err-nobutton")
            page.wait_for_timeout(6000)
            shot(page, "web-06-published")
            print("url:", page.url)

        print("screenshots:", SHOTS)
        if not args.publish: page.wait_for_timeout(2000)
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
