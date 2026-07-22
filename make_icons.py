"""Render PNG icons from the pet SVG using PyQt5's QSvgRenderer."""
import sys, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QPainter, QImage, QPixmap
from PyQt5.QtCore import Qt, QRectF, QByteArray

app = QApplication(sys.argv)

svg_path = r"D:\opencode\desktop-pet\pet.svg"
with open(svg_path, "rb") as f:
    svg_bytes = QByteArray(f.read())

# We want icon to show only the idle pose (first 200x200 region of the 1200x200 sheet)
renderer = QSvgRenderer(svg_bytes)
if not renderer.isValid():
    print("SVG invalid!"); sys.exit(1)

def render(size, region=None):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    if region is None:
        renderer.render(p)
    else:
        # render only sub-rect of viewBox
        renderer.setViewBox(region)
        renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return img

# idle pose region: x in [0,200], y in [0,200] of the 1200x200 sheet
idle_region = QRectF(0, 0, 200, 200)

out_dir = r"D:\opencode\desktop-pet\icons"
os.makedirs(out_dir, exist_ok=True)

for size in [16, 32, 48, 64, 128, 256]:
    img = render(size, idle_region)
    path = os.path.join(out_dir, f"icon-{size}.png")
    img.save(path)
    print("saved", path, size)

print("done")
