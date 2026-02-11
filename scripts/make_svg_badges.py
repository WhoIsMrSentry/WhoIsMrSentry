import base64
from pathlib import Path

LOGO_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'logos'
OUT_DIR = LOGO_DIR
SKIP = {'freertos.png'}
BADGE_WIDTH = 200
HEIGHT = 28
LOGO_SIZE = 20

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


def make_badge(p: Path):
    name = p.stem.lower()
    if p.name in SKIP:
        print('Skipping', p.name)
        return
    if name not in COLORS:
        print('No color/text mapping for', name, '— skipping')
        return
    with open(p, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    color = COLORS[name]
    text = TEXTS[name]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{BADGE_WIDTH}" height="{HEIGHT}" viewBox="0 0 {BADGE_WIDTH} {HEIGHT}">
  <defs>
    <style type="text/css">@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');</style>
  </defs>
  <rect width="{HEIGHT}" height="{HEIGHT}" rx="4" fill="{color}"/>
  <image x="4" y="4" width="{LOGO_SIZE}" height="{LOGO_SIZE}" href="data:image/png;base64,{b64}" />
  <rect x="{HEIGHT}" y="0" width="{BADGE_WIDTH-HEIGHT}" height="{HEIGHT}" rx="4" fill="#2b2b2b" />
  <text x="{HEIGHT+8}" y="{HEIGHT/2+5}" font-family="Inter, Arial, sans-serif" font-size="12" fill="#ffffff">{text}</text>
</svg>'''
    out = OUT_DIR / f'{name}-badge.svg'
    out.write_text(svg, encoding='utf-8')
    print('Wrote', out)


def main():
    for p in LOGO_DIR.iterdir():
        if p.suffix.lower() != '.png':
            continue
        make_badge(p)

if __name__ == '__main__':
    main()
