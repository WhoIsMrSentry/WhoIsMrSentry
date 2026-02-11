from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

LOGO_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'logos'
SKIP = {'freertos.png'}
HEIGHT = 28
LOGO_SIZE = 18
PADDING_X = 8
GAP = 6

COLORS = {
    'wsl': '#2D89EF',
    'openbci': '#00A6ED',
    'brainbay': '#6C3483',
    'neuropype': '#0AA37F',
}

TEXTS = {
    'wsl': 'WSL',
    'openbci': 'OpenBCI',
    'brainbay': 'BrainBay',
    'neuropype': 'Neuropype',
}

def load_font():
    try:
        return ImageFont.truetype("arial.ttf", 12)
    except Exception:
        return ImageFont.load_default()

FONT = load_font()


def text_size(draw: ImageDraw.ImageDraw, text: str):
    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=FONT)
        return right - left, bottom - top
    return draw.textsize(text, font=FONT)


def make_png_badge(p: Path):
    name = p.stem.lower()
    if p.name in SKIP:
        print('Skipping', p.name)
        return
    if name not in COLORS:
        print('No color/text mapping for', name, '— skipping')
        return
    color = COLORS[name]
    text = TEXTS[name]
    temp = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp)
    tw, th = text_size(temp_draw, text)

    left_w = LOGO_SIZE + (PADDING_X * 2)
    total_w = left_w + GAP + tw + PADDING_X
    img = Image.new('RGBA', (total_w, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # full badge background (solid color)
    draw.rounded_rectangle(((0, 0), (total_w, HEIGHT)), radius=6, fill=color)

    # paste logo
    try:
        logo = Image.open(p).convert('RGBA')
        logo = logo.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
        img.paste(logo, (PADDING_X, (HEIGHT - LOGO_SIZE) // 2), logo)
    except Exception as e:
        print('Could not open/paste logo', p.name, e)
    # text
    text_x = left_w + GAP
    text_y = (HEIGHT - th) // 2
    draw.text((text_x, text_y), text, font=FONT, fill=(255, 255, 255))

    out = LOGO_DIR / f'{name}-badge.png'
    img.save(out)
    print('Wrote', out)


def main():
    for p in LOGO_DIR.iterdir():
        if p.suffix.lower() != '.png':
            continue
        make_png_badge(p)

if __name__ == '__main__':
    main()
