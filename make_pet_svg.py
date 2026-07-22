"""Generate the desktop pet's SVG spritesheet (one file, multiple poses).

Poses (each 200x200, laid in a 6x1 row -> 1200x200):
  0 idle        - standing, slight smile, tongue tip
  1 happy       - big smile, happy eye arcs, raised ears
  2 sad         - droopy ears, frown, tear
  3 eat         - chewing, closed eyes, food crumb
  4 sleep       - eyes closed, zzz, peaceful
  5 drag        - stretched limbs, surprised O-mouth

Refined version: gradient body shading, fur tufts, glossy eyes,
paw details, soft drop shadow, more expressive face.

Run: python make_pet_svg.py
"""
import os

# shared palette
BODY       = "#E8C79A"
BODY_DK    = "#C99A5E"   # darker shade for body lower
BODY_LT    = "#F4DDB0"   # highlight
BELLY      = "#FBEDD0"
BELLY_DK   = "#E8D9B0"
EAR        = "#7A4A28"
EAR_INNER  = "#B0764A"
EAR_HL     = "#9A6238"
NOSE       = "#2A1C14"
NOSE_HL    = "#6A4A36"
EYE        = "#1A1208"
EYE_HL     = "#FFFFFF"
BLUSH      = "#FFB0B0"
TONGUE     = "#F08090"
TONGUE_DK  = "#D86070"
MOUTH      = "#5A3A26"
PAW        = "#C99A5E"
PAW_DK     = "#A87A3E"
SHADOW     = "rgba(0,0,0,0.22)"
FUR        = "#D4A775"   # fur tufts, slightly darker than body


def _defs():
    """SVG defs: gradients & filters used across poses."""
    return f'''
  <defs>
    <radialGradient id="bodyGrad" cx="50%" cy="35%" r="65%">
      <stop offset="0%" stop-color="{BODY_LT}"/>
      <stop offset="55%" stop-color="{BODY}"/>
      <stop offset="100%" stop-color="{BODY_DK}"/>
    </radialGradient>
    <radialGradient id="headGrad" cx="40%" cy="30%" r="70%">
      <stop offset="0%" stop-color="{BODY_LT}"/>
      <stop offset="60%" stop-color="{BODY}"/>
      <stop offset="100%" stop-color="{BODY_DK}"/>
    </radialGradient>
    <linearGradient id="bellyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{BELLY}"/>
      <stop offset="100%" stop-color="{BELLY_DK}"/>
    </linearGradient>
    <linearGradient id="earGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{EAR}"/>
      <stop offset="100%" stop-color="{EAR_HL}"/>
    </linearGradient>
    <radialGradient id="eyeGrad" cx="40%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#3A2A1A"/>
      <stop offset="100%" stop-color="{EYE}"/>
    </radialGradient>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="1.2"/>
    </filter>
  </defs>'''


def _shadow():
    return f'<ellipse cx="100" cy="190" rx="46" ry="6" fill="{SHADOW}"/>'


def _tail(rot):
    return f'''
  <g transform="translate(72,138) rotate({rot})">
    <rect x="-20" y="-7" width="36" height="14" rx="7" fill="url(#bodyGrad)"/>
    <circle cx="18" cy="0" r="9" fill="{BODY_LT}"/>
    <circle cx="18" cy="0" r="9" fill="{BODY}" opacity="0.5"/>
  </g>'''


def _fur_tufts():
    """Little fur bumps along the body top edge for texture."""
    return f'''
  <g fill="{FUR}" opacity="0.55">
    <circle cx="70" cy="108" r="3"/>
    <circle cx="78" cy="106" r="2.5"/>
    <circle cx="122" cy="106" r="2.5"/>
    <circle cx="130" cy="108" r="3"/>
    <circle cx="84" cy="138" r="2.5"/>
    <circle cx="116" cy="138" r="2.5"/>
  </g>'''


def _paws():
    """Front legs + paws with toe details. Legs are rounded rectangles
    extending down from body, giving the lower body real structure
    instead of looking like a ball."""
    return f'''
  <g>
    <!-- back legs (slightly behind, darker) -->
    <rect x="80" y="150" width="12" height="28" rx="6" fill="{BODY_DK}"/>
    <rect x="108" y="150" width="12" height="28" rx="6" fill="{BODY_DK}"/>
    <!-- front legs -->
    <rect x="88" y="152" width="12" height="30" rx="6" fill="{BODY}"/>
    <rect x="100" y="152" width="12" height="30" rx="6" fill="{BODY}"/>
    <!-- paws -->
    <ellipse cx="94" cy="184" rx="9" ry="6" fill="{PAW}"/>
    <ellipse cx="106" cy="184" rx="9" ry="6" fill="{PAW}"/>
    <!-- toe beans -->
    <circle cx="90" cy="184" r="1.6" fill="{PAW_DK}"/>
    <circle cx="94" cy="186" r="1.6" fill="{PAW_DK}"/>
    <circle cx="98" cy="184" r="1.6" fill="{PAW_DK}"/>
    <circle cx="102" cy="184" r="1.6" fill="{PAW_DK}"/>
    <circle cx="106" cy="186" r="1.6" fill="{PAW_DK}"/>
    <circle cx="110" cy="184" r="1.6" fill="{PAW_DK}"/>
  </g>'''


def _eyes(eye_y, eye_open, style="open"):
    """style: open / happy / closed / sad / eat"""
    if style == "open":
        return f'''
  <g>
    <ellipse cx="86" cy="{eye_y}" rx="{eye_open+0.5}" ry="{eye_open+1}" fill="url(#eyeGrad)"/>
    <ellipse cx="114" cy="{eye_y}" rx="{eye_open+0.5}" ry="{eye_open+1}" fill="url(#eyeGrad)"/>
    <circle cx="{86+1.5}" cy="{eye_y-1.8}" r="1.8" fill="{EYE_HL}"/>
    <circle cx="{114+1.5}" cy="{eye_y-1.8}" r="1.8" fill="{EYE_HL}"/>
    <circle cx="{86-1.5}" cy="{eye_y+1.5}" r="0.8" fill="#fff" opacity="0.6"/>
    <circle cx="{114-1.5}" cy="{eye_y+1.5}" r="0.8" fill="#fff" opacity="0.6"/>
  </g>'''
    if style == "happy":
        return f'''
  <g stroke="{EYE}" stroke-width="2.6" fill="none" stroke-linecap="round">
    <path d="M80,87 Q86,80 92,87"/>
    <path d="M108,87 Q114,80 120,87"/>
  </g>'''
    if style == "closed":
        return f'''
  <g stroke="{EYE}" stroke-width="2.4" fill="none" stroke-linecap="round">
    <path d="M80,{eye_y+1} Q86,{eye_y-2} 92,{eye_y+1}"/>
    <path d="M108,{eye_y+1} Q114,{eye_y-2} 120,{eye_y+1}"/>
  </g>'''
    if style == "sad":
        return f'''
  <g>
    <ellipse cx="86" cy="{eye_y+1}" rx="4.5" ry="4" fill="url(#eyeGrad)"/>
    <ellipse cx="114" cy="{eye_y+1}" rx="4.5" ry="4" fill="url(#eyeGrad)"/>
    <circle cx="87" cy="{eye_y-0.5}" r="1.3" fill="#fff"/>
    <circle cx="115" cy="{eye_y-0.5}" r="1.3" fill="#fff"/>
    <path d="M83,{eye_y-4} Q86,{eye_y-6} 89,{eye_y-4}" stroke="{EYE}" stroke-width="1.5" fill="none" stroke-linecap="round"/>
    <path d="M111,{eye_y-4} Q114,{eye_y-6} 117,{eye_y-4}" stroke="{EYE}" stroke-width="1.5" fill="none" stroke-linecap="round"/>
  </g>'''
    if style == "eat":
        return f'''
  <g stroke="{EYE}" stroke-width="2.2" fill="none" stroke-linecap="round">
    <path d="M81,{eye_y} Q86,{eye_y+3} 91,{eye_y}"/>
    <path d="M109,{eye_y} Q114,{eye_y+3} 119,{eye_y}"/>
  </g>'''
    return ""


def _nose(cx, cy):
    return f'''
  <g>
    <ellipse cx="{cx}" cy="{cy}" rx="7" ry="5" fill="{NOSE}"/>
    <ellipse cx="{cx-1.5}" cy="{cy-1.5}" rx="2.2" ry="1.5" fill="{NOSE_HL}" opacity="0.7"/>
    <ellipse cx="{cx+1.5}" cy="{cy+1.5}" rx="1" ry="0.6" fill="#fff" opacity="0.4"/>
  </g>'''


def _ears(head_cy, rot_l=-18, rot_r=18, droop=0):
    """Floppy ears behind head. droop shifts them down (for sad)."""
    dy = droop
    return f'''
  <g>
    <ellipse cx="62" cy="{head_cy-20+dy}" rx="14" ry="26" fill="url(#earGrad)" transform="rotate({rot_l} 62 {head_cy-20+dy})"/>
    <ellipse cx="138" cy="{head_cy-20+dy}" rx="14" ry="26" fill="url(#earGrad)" transform="rotate({rot_r} 138 {head_cy-20+dy})"/>
    <ellipse cx="62" cy="{head_cy-16+dy}" rx="7" ry="15" fill="{EAR_INNER}" transform="rotate({rot_l} 62 {head_cy-16+dy})"/>
    <ellipse cx="138" cy="{head_cy-16+dy}" rx="7" ry="15" fill="{EAR_INNER}" transform="rotate({rot_r} 138 {head_cy-16+dy})"/>
  </g>'''


def _head(head_cy):
    return f'''
  <g>
    <circle cx="100" cy="{head_cy}" r="34" fill="url(#headGrad)"/>
    <ellipse cx="88" cy="{head_cy-12}" rx="14" ry="9" fill="{BODY_LT}" opacity="0.4"/>
    <ellipse cx="100" cy="{head_cy+12}" rx="22" ry="17" fill="url(#bellyGrad)"/>
  </g>'''


def _mouth_smile(cy):
    return f'<path d="M88,{cy} Q100,{cy+6} 112,{cy}" stroke="{MOUTH}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'


def _mouth_big_smile(cy):
    return f'<path d="M82,{cy-1} Q100,{cy+12} 118,{cy-1}" stroke="{MOUTH}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'


def _mouth_frown(cy):
    return f'<path d="M88,{cy+3} Q100,{cy-2} 112,{cy+3}" stroke="{MOUTH}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'


def _tongue(cy):
    return f'<path d="M94,{cy} Q94,{cy+9} 100,{cy+11} Q106,{cy+9} 106,{cy} Z" fill="{TONGUE}"/><path d="M100,{cy+2} L100,{cy+9}" stroke="{TONGUE_DK}" stroke-width="0.8" fill="none"/>'


def _blush(head_cy):
    return f'''
  <g opacity="0.75">
    <ellipse cx="70" cy="{head_cy+14}" rx="5" ry="3.5" fill="{BLUSH}"/>
    <ellipse cx="130" cy="{head_cy+14}" rx="5" ry="3.5" fill="{BLUSH}"/>
  </g>'''


def _tear(head_cy):
    return f'<path d="M86,{head_cy+6} Q83,{head_cy+14} 86,{head_cy+18} Q89,{head_cy+14} 86,{head_cy+6} Z" fill="#7EC8FF" opacity="0.85"/>'


def dog_svg(pose, frame=0):
    head_cy = 88
    body_sx, body_sy = 60, 64
    tail_rot = -30
    ears = _ears(head_cy, -18, 18)
    eyes_style = "open"; eye_y = 84; eye_open = 5
    mouth = _mouth_smile(100)
    tongue = _tongue(102)
    extras = ""

    if pose == "happy":
        eyes_style = "happy"
        mouth = _mouth_big_smile(99)
        tongue = _tongue(104)
        ears = _ears(head_cy, -8, 8)  # ears raised
        extras += _blush(head_cy)
        extras += '<circle cx="100" cy="58" r="2" fill="#FFD700" opacity="0.7"/>'  # sparkle
    elif pose == "sad":
        head_cy = 92
        ears = _ears(head_cy, -8, 8, droop=8)  # droopy ears
        eyes_style = "sad"; eye_y = 86
        mouth = _mouth_frown(104)
        tongue = ""
        extras += _tear(head_cy)
    elif pose == "eat":
        eyes_style = "eat"
        mouth = '<ellipse cx="100" cy="102" rx="8" ry="5" fill="{MOUTH}"/>'.replace("{MOUTH}", MOUTH)
        tongue = _tongue(104)
        extras += '<circle cx="100" cy="110" r="2.5" fill="#8A5A32" opacity="0.4"/>'  # crumb
        extras += '<circle cx="105" cy="112" r="1.5" fill="#8A5A32" opacity="0.4"/>'
    elif pose == "sleep":
        eyes_style = "closed"; eye_y = 86
        mouth = _mouth_smile(102)
        tongue = ""
        extras += (f'<text x="138" y="56" font-size="16" fill="#5a6a7a" font-family="sans-serif" font-weight="700">z</text>'
                   f'<text x="150" y="44" font-size="22" fill="#5a6a7a" font-family="sans-serif" font-weight="700">z</text>'
                   f'<text x="164" y="30" font-size="28" fill="#5a6a7a" font-family="sans-serif" font-weight="700">z</text>')
    elif pose == "drag":
        body_sx, body_sy = 54, 70
        ears = _ears(head_cy, -30, 30)
        eyes_style = "open"; eye_y = 82; eye_open = 6
        mouth = '<circle cx="100" cy="102" r="4" fill="{MOUTH}"/>'.replace("{MOUTH}", MOUTH)
        tongue = ""
        extras += '<circle cx="100" cy="76" r="3" fill="#fff" opacity="0.9"/>'  # surprised spark

    return f'''<g>
  {_shadow()}
  {_tail(tail_rot)}
  <!-- body: slightly egg-shaped (taller than wide) so lower body doesn't read as a ball -->
  <ellipse cx="100" cy="142" rx="{body_sx}" ry="{body_sy}" fill="url(#bodyGrad)"/>
  <!-- chest/belly patch, narrower than body so legs show separation -->
  <ellipse cx="100" cy="150" rx="{body_sx-16}" ry="{body_sy-20}" fill="url(#bellyGrad)"/>
  <!-- subtle waist hint: a darker crescent where body meets legs -->
  <path d="M{100-body_sx+18},{142+body_sy-18} Q100,{142+body_sy-2} {100+body_sx-18},{142+body_sy-18}" stroke="{BODY_DK}" stroke-width="1.2" fill="none" opacity="0.4"/>
  {_fur_tufts()}
  {_paws()}
  {ears}
  {_head(head_cy)}
  {_eyes(eye_y, eye_open, eyes_style)}
  {_nose(100, head_cy+8)}
  {mouth}
  {tongue}
  {_blush(head_cy)}
  {extras}
</g>'''


POSES = ["idle","happy","sad","eat","sleep","drag"]
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="200" viewBox="0 0 1200 200">'
       + _defs()
       + "".join(f'<g transform="translate({i*200},0)">{dog_svg(p, i)}</g>' for i, p in enumerate(POSES))
       + '</svg>')

out = r"D:\opencode\desktop-pet\pet.svg"
with open(out, "w", encoding="utf-8") as f:
    f.write(svg)
print("wrote", out, len(svg), "bytes", "poses:", ",".join(POSES))
