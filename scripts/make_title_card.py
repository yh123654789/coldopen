#!/usr/bin/env python
"""make_title_card.py — build a film-style opening title card and prepend it to a video.

  python make_title_card.py --video "D:/path/ep.mp4" --title "地海" --en "THE MYSTERIOUS SEA" \
      --chapter "第 186 — 187 章 · 活船" --out cover

Produces:
  <out>/title_card.png        the card itself (also usable as a cover source)
  <out>/card_clip.mp4         2.5 s card with silent audio
  <out>/master_with_title.mp4 original video with the card prepended

Requires: pillow, opencv-python-headless, imageio-ffmpeg.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\STZHONGS.TTF",   # 华文中宋 — best cinematic look
    r"C:\Windows\Fonts\STSONG.TTF",     # 华文宋体
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\msyhbd.ttc",     # 微软雅黑
]
SANS_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def pick_font(cands: list[str], override: str | None) -> str:
    if override:
        if not Path(override).exists():
            raise SystemExit(f"font not found: {override}")
        return override
    for c in cands:
        if Path(c).exists():
            return c
    raise SystemExit("no usable font found; pass --font")


def spaced(draw, xy, text, font, fill, tracking=0.0, center_x=None):
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if center_x is not None:
        x = center_x - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking
    return total


def grab_frame(video: Path, at: float, w: int, h: int) -> Image.Image:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open video: {video}")
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(frames - 1, int(frames * at))))
    ok, fr = cap.read()
    cap.release()
    if not ok:
        return Image.new("RGB", (w, h), (6, 10, 16))
    return Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).resize((w, h), Image.LANCZOS)


def build_card(args, out: Path) -> Path:
    w, h = args.size
    title_font = pick_font(FONT_CANDIDATES, args.font)
    sans_font = pick_font(SANS_CANDIDATES, args.sans)

    base = grab_frame(Path(args.video), args.bg_at, w, h)
    base = ImageEnhance.Brightness(base).enhance(0.55).filter(ImageFilter.GaussianBlur(2.2))
    canvas = Image.new("RGBA", (w, h))
    canvas.paste(base, (0, 0))
    canvas.alpha_composite(Image.new("RGBA", (w, h), (4, 8, 14, args.wash)))

    d = ImageDraw.Draw(canvas)
    f_lead = ImageFont.truetype(sans_font, max(12, h // 42))
    f_title = ImageFont.truetype(title_font, args.title_size)
    f_en = ImageFont.truetype(sans_font, max(12, h // 36))
    f_ch = ImageFont.truetype(sans_font, max(12, h // 30))

    cy = int(h * args.title_y)
    if args.lead:
        spaced(d, (0, int(h * 0.24)), args.lead, f_lead, (222, 230, 240, 200), 7, center_x=w / 2)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    spaced(dl, (0, cy), args.title, f_title, (255, 255, 255, 255),
           int(args.title_size * 0.27), center_x=w / 2)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(22)))
    canvas.alpha_composite(layer)

    top = cy + args.title_size + int(h * 0.02)
    d.line([(w / 2 - 96, top), (w / 2 + 96, top)], fill=(235, 242, 250, 130), width=2)
    y = top + int(h * 0.03)
    if args.en:
        spaced(d, (0, y), args.en, f_en, (232, 240, 248, 205), 2, center_x=w / 2)
        y += f_en.size + int(h * 0.022)
    if args.chapter:
        spaced(d, (0, y), args.chapter, f_ch, (240, 245, 250, 225), 4, center_x=w / 2)

    if args.badge:
        bw = d.textlength(args.badge, font=f_lead) + 30
        bh = 15 + 22
        bx, by = w - bw - int(w * 0.042), h - bh - int(h * 0.055)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2,
                            outline=(235, 242, 250, 140), width=2)
        d.text((bx + 15, by + 11), args.badge, font=f_lead, fill=(240, 245, 250, 215))

    out.mkdir(parents=True, exist_ok=True)
    p = out / "title_card.png"
    canvas.convert("RGB").save(p, quality=98)
    print("card:", p)
    return p


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def prepend(card: Path, video: Path, out: Path, seconds: float, size: tuple[int, int]) -> Path:
    ff = ffmpeg_exe()
    w, h = size
    clip = out / "card_clip.mp4"
    master = out / "master_with_title.mp4"
    subprocess.run([
        ff, "-y", "-loop", "1", "-i", str(card),
        "-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=44100:cl=stereo",
        "-filter_complex", f"[0:v]scale={w}:{h},setsar=1,fade=in:0:12,fade=out:36:12[v]",
        "-map", "[v]", "-map", "1:a", "-t", str(seconds), "-r", "24",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", str(clip),
    ], check=True, capture_output=True)

    probe = subprocess.run([ff, "-i", str(video)], capture_output=True, text=True, errors="replace").stderr
    has_audio = "Audio:" in probe
    if has_audio:
        subprocess.run([
            ff, "-y", "-i", str(clip), "-i", str(video),
            "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(master),
        ], check=True, capture_output=True)
    else:
        subprocess.run([
            ff, "-y", "-i", str(clip), "-i", str(video),
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(master),
        ], check=True, capture_output=True)
    print("master:", master, f"{master.stat().st_size / 1048576:.1f} MB")
    return master


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default="cover")
    ap.add_argument("--title", default="地海")
    ap.add_argument("--en", default="THE MYSTERIOUS SEA")
    ap.add_argument("--chapter", default="")
    ap.add_argument("--lead", default="A I  生 成  ·  微 型 剧 集")
    ap.add_argument("--badge", default="AI 创作")
    ap.add_argument("--size", default="1280x720", help="WxH")
    ap.add_argument("--title-size", type=int, default=168)
    ap.add_argument("--title-y", type=float, default=0.34, help="0..1 vertical position")
    ap.add_argument("--bg-at", type=float, default=0.95, help="frame position 0..1 for the backdrop")
    ap.add_argument("--wash", type=int, default=165, help="dark overlay alpha 0..255")
    ap.add_argument("--seconds", type=float, default=2.5)
    ap.add_argument("--font")
    ap.add_argument("--sans")
    ap.add_argument("--no-prepend", action="store_true")
    a = ap.parse_args(argv)

    w, h = (int(v) for v in a.size.lower().split("x"))
    a.size = (w, h)
    out = Path(a.out)
    card = build_card(a, out)
    if not a.no_prepend:
        prepend(card, Path(a.video), out, a.seconds, (w, h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
