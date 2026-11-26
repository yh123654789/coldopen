#!/usr/bin/env python
"""make_cover.py — cinematic cover from a video frame or an image (vertical 3:4 / horizontal 4:3).

  python make_cover.py --video ep.mp4 --at 0.95 --size 1080x1440 --bias-x 0.25 \
      --title "地海" --en "THE MYSTERIOUS SEA" --chapter "第 186 — 187 章 · 活船" --out cover/v.jpg

Pitfall: pick a frame without burned-in subtitles. Check with --list-frames first.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from make_title_card import FONT_CANDIDATES, SANS_CANDIDATES, pick_font, spaced


def load_source(args) -> Image.Image:
    if args.image:
        return Image.open(args.image).convert("RGB")
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(n - 1, int(n * args.at))))
    ok, fr = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("frame grab failed")
    return Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))


def list_frames(video: str, count: int, out_dir: Path) -> None:
    cap = cv2.VideoCapture(video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * i / count))
        ok, fr = cap.read()
        if ok:
            p = out_dir / f"frame_{i:02d}.jpg"
            cv2.imwrite(str(p), fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
            print(p)
    cap.release()


def crop_ratio(img: Image.Image, ratio: float, bias_x: float, bias_y: float) -> Image.Image:
    w, h = img.size
    if w / h > ratio:
        nw = int(h * ratio)
        x = int((w - nw) * bias_x)
        return img.crop((x, 0, x + nw, h))
    nh = int(w / ratio)
    y = int((h - nh) * bias_y)
    return img.crop((0, y, w, y + nh))


def gradient(size, y0, y1, a0, a1, color=(0, 0, 0)):
    w = size[0]
    band = Image.new("RGBA", (w, max(1, y1 - y0)), color + (0,))
    px = band.load()
    for y in range(band.size[1]):
        t = y / max(1, band.size[1] - 1)
        a = int(a0 + (a1 - a0) * t)
        for x in range(w):
            px[x, y] = color + (a,)
    return band


def vignette(size, strength):
    w, h = size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([-w * 0.35, -h * 0.35, w * 1.35, h * 1.35], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.12))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, black, mask.point(lambda v: int((255 - v) * strength / 255)))


def build(args) -> Path:
    w, h = args.size
    title_font = pick_font(FONT_CANDIDATES, args.font)
    sans_font = pick_font(SANS_CANDIDATES, args.sans)

    img = load_source(args)
    img = crop_ratio(img, w / h, args.bias_x, args.bias_y).resize((w, h), Image.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(args.brightness)
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Color(img).enhance(1.05)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(1.0)), 0.18)
    img = Image.blend(img, vignette((w, h), 105), args.vignette)

    canvas = img.convert("RGBA")
    canvas.alpha_composite(gradient((w, h), 0, int(h * 0.30), args.top_fade, 0), (0, 0))
    canvas.alpha_composite(gradient((w, h), int(h * 0.52), h, 20, args.bottom_fade), (0, int(h * 0.52)))

    d = ImageDraw.Draw(canvas)
    f_lead = ImageFont.truetype(sans_font, max(16, args.title_size // 9))
    f_title = ImageFont.truetype(title_font, args.title_size)
    f_en = ImageFont.truetype(sans_font, max(14, args.title_size // 9))
    f_ch = ImageFont.truetype(sans_font, max(16, args.title_size // 7))

    if args.lead:
        spaced(d, (0, int(h * 0.115)), args.lead, f_lead, (226, 232, 240, 210), 6, center_x=w / 2)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    spaced(dl, (0, int(h * args.title_y)), args.title, f_title, (255, 255, 255, 255),
           int(args.title_size * 0.16), center_x=w / 2)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(18)))
    canvas.alpha_composite(layer)

    bbox = layer.getbbox()
    bottom = bbox[3] if bbox else int(h * 0.6)
    d = ImageDraw.Draw(canvas)
    ly = bottom + int(h * 0.045)
    d.line([(w / 2 - w * 0.12, ly), (w / 2 + w * 0.12, ly)], fill=(235, 240, 245, 120), width=2)
    y = ly + int(h * 0.030)
    if args.en:
        spaced(d, (0, y), args.en, f_en, (232, 238, 245, 205), 2, center_x=w / 2)
        y += f_en.size + int(h * 0.022)
    if args.chapter:
        spaced(d, (0, y), args.chapter, f_ch, (240, 244, 250, 225), 4, center_x=w / 2)

    if args.badge:
        bw = d.textlength(args.badge, font=f_lead) + 34
        bh = f_lead.size + 22
        bx, by = w - bw - int(w * 0.055), h - bh - int(h * 0.045)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2,
                            outline=(235, 240, 246, 150), width=2)
        d.text((bx + 17, by + 11), args.badge, font=f_lead, fill=(240, 244, 250, 220))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95, subsampling=0)
    print("cover:", out, canvas.size)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--video")
    src.add_argument("--image")
    ap.add_argument("--at", type=float, default=0.95, help="frame position 0..1")
    ap.add_argument("--size", default="1080x1440")
    ap.add_argument("--title", default="地海")
    ap.add_argument("--en", default="THE MYSTERIOUS SEA")
    ap.add_argument("--chapter", default="")
    ap.add_argument("--lead", default="A I  生 成  ·  微 型 剧 集")
    ap.add_argument("--badge", default="AI 创作")
    ap.add_argument("--title-size", type=int, default=300)
    ap.add_argument("--title-y", type=float, default=0.32)
    ap.add_argument("--bias-x", type=float, default=0.5)
    ap.add_argument("--bias-y", type=float, default=0.5)
    ap.add_argument("--brightness", type=float, default=1.35)
    ap.add_argument("--vignette", type=float, default=0.28)
    ap.add_argument("--top-fade", type=int, default=135)
    ap.add_argument("--bottom-fade", type=int, default=185)
    ap.add_argument("--font")
    ap.add_argument("--sans")
    ap.add_argument("--out", default="cover/cover.jpg")
    ap.add_argument("--list-frames", type=int, help="dump N frames and exit")
    a = ap.parse_args(argv)

    if a.list_frames:
        list_frames(a.video, a.list_frames, Path(a.out).parent / "frames")
        return 0
    w, h = (int(v) for v in a.size.lower().split("x"))
    a.size = (w, h)
    build(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
