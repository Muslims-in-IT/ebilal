"""Generate eBilal's icons: an old-school radio (antenna, speaker grille,
tuning dial, knobs) in the app's gold + teal on charcoal.

One set of shapes, in a 100x100 design box, drives every output so they match:
  ebilal_web/icons/*.png   PWA + Apple touch icons
  ebilal_web/favicon.ico   browser tab
  ebilal_web/icons/radio.svg  header mark / scalable favicon

Run once after changing the design (outputs are committed):
  .venv/bin/pip install pillow && .venv/bin/python other/make_icons.py
"""
from PIL import Image, ImageDraw

BG = "#2A2622"      # charcoal (theme colour)
GOLD = "#D4AF59"
TEAL = "#4FD1C5"
CREAM = "#FBF7EA"

# (kind, params...) in design units. Centre of the drawing is ~(50, 50).
SHAPES = [
    ("line",    (68, 36, 83, 13), 3.2, GOLD),            # antenna
    ("circle",  (83, 13), 3.6, TEAL),                    # antenna tip
    ("rrect",   (12, 34, 88, 82), 9, GOLD),              # cabinet
    ("rect",    (20, 82, 28, 87), GOLD),                 # left foot
    ("rect",    (72, 82, 80, 87), GOLD),                 # right foot
    ("circle",  (35, 58), 15.5, BG),                     # speaker
    ("ring",    (35, 58), 10.5, 2.6, TEAL),              # grille ring
    ("circle",  (35, 58), 4, TEAL),                      # grille centre
    ("rrect",   (55, 43, 81, 56), 3, CREAM),             # tuning dial
    ("line",    (59, 52, 77, 52), 1.2, GOLD),            # dial scale
    ("line",    (67, 45, 67, 55), 2.2, TEAL),            # needle
    ("circle",  (61, 69.5), 5, BG),                      # knob
    ("circle",  (75, 69.5), 5, BG),                      # knob
]
DESIGN_CENTRE_Y = 50  # the art spans y 9..87


def render_png(size, content):
    """content: fraction of the canvas the 100-unit design box may occupy."""
    ss = 4
    big = size * ss
    img = Image.new("RGB", (big, big), BG)
    d = ImageDraw.Draw(img)
    k = big * content / 100.0
    ox = (big - 100 * k) / 2
    oy = (big - 100 * k) / 2 + (50 - DESIGN_CENTRE_Y) * k

    def P(x, y):
        return (ox + x * k, oy + y * k)

    for kind, *a in SHAPES:
        if kind == "line":
            (x1, y1, x2, y2), w, c = a
            d.line([P(x1, y1), P(x2, y2)], fill=c, width=max(1, round(w * k)))
        elif kind == "circle":
            (cx, cy), r, c = a
            x, y = P(cx, cy)
            d.ellipse([x - r * k, y - r * k, x + r * k, y + r * k], fill=c)
        elif kind == "ring":
            (cx, cy), r, w, c = a
            x, y = P(cx, cy)
            d.ellipse([x - r * k, y - r * k, x + r * k, y + r * k], outline=c, width=max(1, round(w * k)))
        elif kind == "rrect":
            (x1, y1, x2, y2), r, c = a
            d.rounded_rectangle([P(x1, y1), P(x2, y2)], radius=r * k, fill=c)
        elif kind == "rect":
            (x1, y1, x2, y2), c = a
            d.rectangle([P(x1, y1), P(x2, y2)], fill=c)
    return img.resize((size, size), Image.LANCZOS)


def svg(background=False):
    """Scalable version. Without background it sits on the page (header mark)."""
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="eBilal">']
    if background:
        out.append(f'<rect width="100" height="100" rx="22" fill="{BG}"/>')
    for kind, *a in SHAPES:
        if kind == "line":
            (x1, y1, x2, y2), w, c = a
            out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>')
        elif kind == "circle":
            (cx, cy), r, c = a
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>')
        elif kind == "ring":
            (cx, cy), r, w, c = a
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c}" stroke-width="{w}"/>')
        elif kind == "rrect":
            (x1, y1, x2, y2), r, c = a
            out.append(f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" rx="{r}" fill="{c}"/>')
        elif kind == "rect":
            (x1, y1, x2, y2), c = a
            out.append(f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" fill="{c}"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    for name, size, content in [
        ("icon-192.png", 192, 0.86),
        ("icon-512.png", 512, 0.86),
        ("icon-maskable-512.png", 512, 0.62),  # stays inside the maskable safe zone
        ("apple-touch-icon.png", 180, 0.80),   # iOS rounds the corners itself
    ]:
        render_png(size, content).save(f"ebilal_web/icons/{name}", optimize=True)
        print("wrote", name)

    render_png(256, 0.96).save("ebilal_web/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("wrote favicon.ico")

    with open("ebilal_web/icons/radio.svg", "w") as f:
        f.write(svg(background=False))
    with open("ebilal_web/icons/favicon.svg", "w") as f:
        f.write(svg(background=True))
    print("wrote radio.svg, favicon.svg")
