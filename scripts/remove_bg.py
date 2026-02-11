from PIL import Image
from pathlib import Path

LOGO_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'logos'
SKIP = {'freertos.png'}
THRESHOLD = 60  # color distance threshold


def avg_color(samples):
    r = sum(s[0] for s in samples) // len(samples)
    g = sum(s[1] for s in samples) // len(samples)
    b = sum(s[2] for s in samples) // len(samples)
    return (r, g, b)


def color_dist(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5


def make_transparent(path: Path, bg_color, thresh=THRESHOLD):
    im = Image.open(path).convert('RGBA')
    px = im.load()
    w, h = im.size
    changed = False
    for y in range(h):
        for x in range(w):
            r,g,b,a = px[x,y]
            if a == 0:
                continue
            if color_dist((r,g,b), bg_color) <= thresh:
                px[x,y] = (r,g,b,0)
                changed = True
    if changed:
        im.save(path)
    return changed


def process_all():
    if not LOGO_DIR.exists():
        print('Logo directory not found:', LOGO_DIR)
        return
    for p in LOGO_DIR.iterdir():
        if p.suffix.lower() != '.png':
            continue
        if p.name.lower() in SKIP:
            print('Skipping (keep as-is):', p.name)
            continue
        try:
            im = Image.open(p).convert('RGBA')
            w,h = im.size
            corners = [im.getpixel((0,0)), im.getpixel((w-1,0)), im.getpixel((0,h-1)), im.getpixel((w-1,h-1))]
            # use RGB part
            samples = [c[:3] for c in corners]
            bg = avg_color(samples)
            changed = make_transparent(p, bg)
            print(('Transparent applied to' if changed else 'No change for'), p.name)
        except Exception as e:
            print('Error processing', p.name, e)

if __name__ == '__main__':
    process_all()
