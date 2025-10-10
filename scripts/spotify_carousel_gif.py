import json
import math
import os
import io
from typing import List, Tuple

import requests
from PIL import Image, ImageDraw

ASSET_PATH = os.path.join("assets", "spotify_carousel.gif")
DATA_PATH = os.path.join("docs", "spotify_top.json")
PRIMARY = "#88001b"
BACKGROUND = (8, 8, 8)
CANVAS = (900, 520)
FRAME_COUNT = 28


def load_data() -> List[dict]:
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            "docs/spotify_top.json not found. Ensure spotify_top_json.py ran before this script."
        )
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    tracks = payload.get("short_term") or []
    if not tracks:
        tracks = payload.get("medium_term") or payload.get("long_term") or []
    return tracks[:7]


def fetch_image(url: str, size: Tuple[int, int]) -> Image.Image:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        img = Image.new("RGB", size, PRIMARY)
    return img.resize(size, Image.LANCZOS)


def gradient_background(canvas: Tuple[int, int]) -> Image.Image:
    width, height = canvas
    base = Image.new("RGB", canvas, BACKGROUND)
    overlay = Image.new("RGB", canvas, (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(height):
        alpha = int(255 * (y / height) ** 1.2)
        color = (
            int(0 + (24 * y / height)),
            int(0 + (8 * y / height)),
            int(0 + (12 * y / height)),
        )
        draw.line([(0, y), (width, y)], fill=color)
    return Image.blend(base, overlay, 0.45)


def positions() -> List[Tuple[int, int, float, float]]:
    # (x_offset, y_offset, scale, opacity)
    return [
        (-270, 100, 0.58, 0.35),
        (-200, 60, 0.7, 0.5),
        (-120, 30, 0.82, 0.72),
        (0, 0, 1.0, 1.0),
        (120, 30, 0.82, 0.72),
        (200, 60, 0.7, 0.5),
        (270, 100, 0.58, 0.35),
    ]


def compose_frame(background: Image.Image, deck: List[Image.Image], labels: List[str], frame_idx: int) -> Image.Image:
    canvas = background.copy()
    draw = ImageDraw.Draw(canvas)
    slots = positions()

    order = sorted(range(len(slots)), key=lambda i: slots[i][2])
    center_x = CANVAS[0] // 2
    center_y = CANVAS[1] // 2 - 40

    for idx in order:
        if idx >= len(deck):
            continue
        img = deck[idx]
        label = labels[idx]
        x_off, y_off, scale, opacity = slots[idx]
        w = int(img.width * scale)
        h = int(img.height * scale)
        thumb = img.resize((w, h), Image.LANCZOS)

        thumb_with_border = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
        border = ImageDraw.Draw(thumb_with_border)
        border.rounded_rectangle(
            [0, 0, w + 12, h + 12], radius=18, outline=PRIMARY, width=4, fill=(0, 0, 0, 0)
        )
        thumb_with_border.paste(thumb, (6, 6))
        thumb_with_border.putalpha(int(255 * opacity))

        pos_x = center_x + x_off - (w // 2)
        pos_y = center_y + y_off - (h // 2)
        canvas.paste(thumb_with_border, (pos_x - 6, pos_y - 6), thumb_with_border)

        if scale >= 1.0:
            label_width = int(w * 0.8)
            label_box = Image.new("RGBA", (label_width, 48), (0, 0, 0, 180))
            label_draw = ImageDraw.Draw(label_box)
            label_draw.text((10, 14), label, fill="#f1f1f1")
            canvas.paste(label_box, (center_x - label_width // 2, pos_y + h - 10), label_box)

    # bottom caption
    caption = "Short-term top tracks • auto-updated"
    draw.text((CANVAS[0] // 2 - 200, CANVAS[1] - 60), caption, fill=(200, 200, 200))
    draw.line(
        [(CANVAS[0] // 2 - 220, CANVAS[1] - 68), (CANVAS[0] // 2 + 220, CANVAS[1] - 68)],
        fill=PRIMARY,
        width=2,
    )

    return canvas


def build_frames(tracks: List[dict]) -> List[Image.Image]:
    if not tracks:
        placeholder = Image.new("RGB", CANVAS, BACKGROUND)
        draw = ImageDraw.Draw(placeholder)
        draw.text((CANVAS[0] // 2 - 120, CANVAS[1] // 2), "No tracks available", fill=(220, 220, 220))
        return [placeholder]

    images = [fetch_image(t.get("image", ""), (340, 340)) for t in tracks]
    labels = [f"{t.get('name', '')} — {', '.join(t.get('artists', []))}" for t in tracks]

    background = gradient_background(CANVAS)
    frames = []

    deck = images.copy()
    lab = labels.copy()
    for i in range(FRAME_COUNT):
        frames.append(compose_frame(background, deck[: len(positions())], lab[: len(positions())], i))
        deck = deck[1:] + deck[:1]
        lab = lab[1:] + lab[:1]
    return frames


def save_gif(frames: List[Image.Image]):
    os.makedirs(os.path.dirname(ASSET_PATH), exist_ok=True)
    frames[0].save(
        ASSET_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        optimize=False,
        disposal=2,
    )


def main():
    tracks = load_data()
    frames = build_frames(tracks)
    save_gif(frames)


if __name__ == "__main__":
    main()
