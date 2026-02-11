from PIL import Image, ImageOps
from pathlib import Path

LOGO_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'logos'
TARGET_SIZE = 128

def make_square_and_resize(im: Image.Image, size: int) -> Image.Image:
    im = im.convert('RGBA')
    x, y = im.size
    # Center-crop to square
    if x != y:
        min_side = min(x, y)
        left = (x - min_side) // 2
        top = (y - min_side) // 2
        im = im.crop((left, top, left + min_side, top + min_side))
    im = im.resize((size, size), Image.LANCZOS)
    return im

def process_all():
    if not LOGO_DIR.exists():
        print('Logo directory not found:', LOGO_DIR)
        return
    for p in LOGO_DIR.iterdir():
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.svg'):
            continue
        if p.suffix.lower() == '.svg':
            print('Skipping SVG (no rasterize):', p.name)
            continue
        try:
            im = Image.open(p)
            out = make_square_and_resize(im, TARGET_SIZE)
            out.save(p)
            print('Resized', p.name)
        except Exception as e:
            print('Error processing', p.name, e)

if __name__ == '__main__':
    process_all()
