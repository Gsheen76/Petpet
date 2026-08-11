from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1] / "assets" / "scenes" / "home"
ROOT.mkdir(parents=True, exist_ok=True)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


background = Image.new("RGB", (1800, 540), "#f0d9bc")
draw = ImageDraw.Draw(background)
draw.rectangle((0, 0, 1800, 360), fill="#ead6c2")
draw.rectangle((0, 360, 1800, 540), fill="#c99570")
for x in range(0, 1800, 90):
    draw.line((x, 360, x, 540), fill="#b98562", width=2)
for y in range(405, 540, 45):
    draw.line((0, y, 1800, y), fill="#b98562", width=2)
draw.rectangle((0, 338, 1800, 360), fill="#a9795d")
draw.rectangle((690, 78, 1110, 302), fill="#f8ead8", outline="#bd8e70", width=8)
draw.rectangle((725, 112, 1075, 286), fill="#b8d1c1")
draw.rectangle((725, 196, 1075, 286), fill="#86a895")
draw.ellipse((770, 135, 875, 240), fill="#f2c78d")
draw.ellipse((905, 145, 1020, 260), fill="#e59b86")
rounded(draw, (95, 230, 390, 345), 20, "#b87b67", "#8f5e52", 5)
rounded(draw, (70, 285, 415, 354), 18, "#cf8f73", "#8f5e52", 5)
draw.rectangle((116, 180, 370, 246), fill="#c3a07d", outline="#8f6e5a", width=5)
draw.rectangle((145, 200, 340, 224), fill="#f2d9a8")
draw.ellipse((1370, 92, 1575, 300), fill="#f4e7d6", outline="#c79b79", width=8)
draw.rectangle((1396, 120, 1548, 272), fill="#d9a87e")
draw.ellipse((1420, 140, 1515, 235), fill="#9fb89f")
background.save(ROOT / "home-background.png")


def transparent(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


img = transparent((440, 110))
d = ImageDraw.Draw(img)
d.ellipse((10, 8, 430, 100), fill="#d9a889", outline="#ad765e", width=5)
d.ellipse((42, 22, 398, 86), fill="#e7bf9b")
img.save(ROOT / "rug.png")

img = transparent((300, 190))
d = ImageDraw.Draw(img)
rounded(d, (15, 50, 285, 176), 24, "#c47f6e", "#925b57", 6)
rounded(d, (24, 12, 276, 102), 22, "#d99579", "#925b57", 6)
d.rectangle((35, 160, 62, 188), fill="#744d4b")
d.rectangle((238, 160, 265, 188), fill="#744d4b")
img.save(ROOT / "sofa.png")

img = transparent((120, 220))
d = ImageDraw.Draw(img)
d.rectangle((49, 125, 71, 208), fill="#9d6f56")
d.ellipse((20, 180, 100, 215), fill="#a86f59", outline="#845345", width=4)
for box in ((12, 20, 68, 112), (45, 2, 106, 120), (58, 50, 115, 155)):
    d.ellipse(box, fill="#789b7b", outline="#55765e", width=4)
img.save(ROOT / "plant.png")

img = transparent((220, 150))
d = ImageDraw.Draw(img)
d.rectangle((8, 8, 212, 142), fill="#f4e1bc", outline="#9c705d", width=7)
d.ellipse((42, 35, 110, 103), fill="#eaa67e")
d.ellipse((110, 46, 180, 114), fill="#91b79a")
d.arc((58, 44, 155, 120), 10, 170, fill="#8b5e55", width=5)
img.save(ROOT / "wall-art.png")
