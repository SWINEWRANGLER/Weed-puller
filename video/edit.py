"""Cut the WP-1 sales video: interpolate field shots to 24 fps, add titles,
motion graphics and callouts, grain + vignette, music, and encode 1080p H.264.

usage: python edit.py FRAMES_DIR MUSIC_WAV OUT_MP4 [--draft]
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 24
FONT_B = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
FONT_M = "/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf"
FONT_R = "/usr/share/fonts/opentype/inter/Inter-Regular.otf" if os.path.exists("/usr/share/fonts/opentype/inter/Inter-Regular.otf") else FONT_M
ORANGE = (255, 108, 28)
WHITE = (255, 255, 255)
INK = (14, 18, 16)

# shot, start s, end s, source fps
TIMELINE = [
    ("s1", 0.0, 3.5, 12), ("s2", 3.5, 8.5, 12), ("s3", 8.5, 15.0, 24), ("s4", 15.0, 20.0, 24),
    ("s5", 20.0, 28.0, 12), ("s6", 28.0, 33.0, 12), ("s7", 33.0, 37.5, 12), ("map", 37.5, 43.5, 24),
    ("s8", 43.5, 49.5, 24), ("s9", 49.5, 57.0, 24), ("end", 57.0, 60.0, 24),
]

# eyebrow, headline, sub, t_in, t_out (seconds, local to the shot)
TITLES = {
    "s1": [(None, "Pulled weeds grow back.", None, 0.35, 1.85), (None, "Unless the root comes too.", None, 1.95, 3.45)],
    "s2": [("INTRODUCING", "WEED PULLER WP-1", "The autonomous spot weeder", 0.55, 4.75)],
    "s3": [("BUILT TO WORK", "Engineered for real yards.", "4WD  ·  RTK-GNSS  ·  LiDAR  ·  Hot-swap battery", 0.5, 6.2)],
    "s4": [("AI VISION", "Knows a weed from a native.", "On-board detection with species-level ID", 0.4, 4.75)],
    "s5": [("ROOT EXTRACTION", "Four steel tines. The whole root.", "No digging. No chemicals.", 0.6, 7.7)],
    "s6": [("SOIL CARE", "Every hole backfilled with sand.", "The lawn stays level, like a repaired green.", 0.5, 4.75)],
    "s7": [("AUTONOMOUS", "Works on its own.", "RTK-GNSS positioning to ±2 cm", 0.4, 4.3)],
    "s8": [("PORTABLE", "One lift. Into the ATV.", "18.5 kg  ·  Two carry handles  ·  Four strap points", 0.5, 5.8)],
    "s9": [("WP-1", "Pull weeds. Not your back.", None, 2.2, 7.4)],
}


def font(path, size):
    return ImageFont.truetype(path, size)


F_EYE = font(FONT_M, 22)
F_HEAD = font(FONT_B, 76)
F_HEAD_BIG = font(FONT_B, 104)
F_SUB = font(FONT_M, 32)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def spaced(draw, xy, text, fnt, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x


def draw_title(img, item, t, big=False):
    eye, head, sub, t0, t1 = item
    if t < t0 or t > t1 + 0.01:
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0 = 120
    fh = F_HEAD_BIG if big else F_HEAD
    base_y = H - 150 - (fh.size - 76)
    out = 1.0 - ease_out((t - (t1 - 0.35)) / 0.35) if t > t1 - 0.35 else 1.0

    def el(delay):
        k = ease_out((t - t0 - delay) / 0.45)
        return k * out, (1 - k) * 22

    if eye:
        a, dy = el(0.0)
        y = base_y - fh.size - 46 + dy
        d.rectangle((x0, y + 10, x0 + 34, y + 13), fill=ORANGE + (int(255 * a),))
        spaced(d, (x0 + 48, y), eye, F_EYE, ORANGE + (int(255 * a),), 4)
    a, dy = el(0.08)
    d.text((x0, base_y - fh.size + dy), head, font=fh, fill=WHITE + (int(255 * a),))
    if sub:
        a, dy = el(0.18)
        d.text((x0 + 2, base_y + 22 + dy), sub, font=F_SUB, fill=(235, 238, 236, int(225 * a)))
    shadow = layer.filter(ImageFilter.GaussianBlur(10))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.putalpha(shadow.getchannel("A").point(lambda v: int(v * 0.45)))
    img.alpha_composite(sh)
    img.alpha_composite(layer)


def scrim():
    """Soft dark gradient lower-left so titles read on any frame."""
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    a = np.clip((y - 0.5) / 0.5, 0, 1) ** 1.6 * np.clip(1.25 - x * 1.1, 0, 1) * 0.68
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def vignette():
    y = np.linspace(-1, 1, H)[:, None]
    x = np.linspace(-1, 1, W)[None, :]
    r = np.sqrt((x * 0.85) ** 2 + y ** 2)
    return np.clip(1.0 - 0.28 * np.clip(r - 0.55, 0, 1) ** 1.5, 0, 1)[..., None].astype(np.float32)


# ----------------------------------------------------------------- map graphic

BOUND = [(0, 6), (52, 0), (128, 4), (140, 46), (133, 92), (70, 96), (8, 90), (2, 48)]
PERIM = [(6, 11), (50, 5.5), (123, 9), (134, 46), (127, 86), (70, 90), (13, 84), (8, 48)]
OBST = [("c", (30, 30), 4.5, "Gum tree"), ("c", (96, 70), 5, "Jacaranda"), ("c", (112, 24), 3.2, "Lemon tree"),
        ("r", (18, 58, 14, 10), None, "Shed"), ("c", (38, 64), 2.2, "Tank"), ("r", (64, 14, 22, 16), None, "House")]
ZONES = [((92, 36, 20, 14), "Veggie garden"), ((48, 70, 16, 14), "Septic"), ((64, 40, 14, 10), "Play area")]
DAM = ((116, 66), 7, "Dam")


def pip(p, poly):
    ins = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins


def blocked(p):
    for (x, y, w, h), _ in ZONES:
        if x - 1 <= p[0] <= x + w + 1 and y - 1 <= p[1] <= y + h + 1:
            return True
    if math.hypot(p[0] - DAM[0][0], p[1] - DAM[0][1]) < DAM[1] + 1:
        return True
    for kind, a, r, _ in OBST:
        if kind == "c" and math.hypot(p[0] - a[0], p[1] - a[1]) < r + 1.2:
            return True
        if kind == "r" and a[0] - 1.2 <= p[0] <= a[0] + a[2] + 1.2 and a[1] - 1.2 <= p[1] <= a[1] + a[3] + 1.2:
            return True
    return False


LANES = []
for yy in np.arange(10, 90, 3.0):
    seg = None
    for xx in np.arange(0, 142, 0.5):
        ok = pip((xx, yy), PERIM) and not blocked((xx, yy))
        if ok and seg is None:
            seg = [xx, xx]
        elif ok:
            seg[1] = xx
        elif seg:
            LANES.append((yy, seg[0], seg[1])); seg = None
    if seg:
        LANES.append((yy, seg[0], seg[1]))


def poly_len(poly):
    return sum(math.dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def along(poly, d):
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        L = math.dist(a, b)
        if d <= L:
            return (a[0] + (b[0] - a[0]) * d / L, a[1] + (b[1] - a[1]) * d / L), i
        d -= L
    return poly[0], len(poly) - 1


def map_frame(t):
    """6 s motion graphic. t in seconds."""
    S = 2
    img = Image.new("RGB", (W * S, H * S), (16, 21, 18))
    d = ImageDraw.Draw(img, "RGBA")
    sc, ox, oy = 7.4 * S, 820 * S, 175 * S

    def P(p):
        return (ox + p[0] * sc, oy + p[1] * sc)

    for gx in range(0, 150, 10):
        d.line([P((gx, -4)), P((gx, 100))], fill=(255, 255, 255, 12), width=S)
    for gy in range(-4, 101, 10):
        d.line([P((-4, gy)), P((146, gy))], fill=(255, 255, 255, 12), width=S)

    # phase 1 (0-2.2s): trace boundary
    k1 = ease_out(t / 2.2)
    L = poly_len(BOUND)
    tip, idx = along(BOUND, L * k1)
    pts = [P(p) for p in BOUND[: idx + 1]] + [P(tip)]
    if k1 >= 0.999:
        d.polygon([P(p) for p in BOUND], fill=(70, 110, 50, 40))
        pts = [P(p) for p in BOUND] + [P(BOUND[0])]
    d.line(pts, fill=(235, 240, 236, 255), width=4 * S, joint="curve")
    for p in BOUND[: idx + 1]:
        x, y = P(p)
        d.rectangle((x - 5 * S, y - 5 * S, x + 5 * S, y + 5 * S), fill=(235, 240, 236, 255))
    # obstacles appear as the scan passes
    fsm = font(FONT_M, 17 * S)
    for i, (kind, a, r, name) in enumerate(OBST):
        appear = ease_out((t - 0.25 - i * 0.28) / 0.4)
        if appear <= 0:
            continue
        al = int(255 * appear)
        if kind == "c":
            cx, cy = P(a)
            rr = r * sc
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(120, 140, 125, int(al * 0.85)))
            lx, ly = cx, cy + rr + 8 * S
        else:
            x, y = P((a[0], a[1]))
            d.rectangle((x, y, x + a[2] * sc, y + a[3] * sc), fill=(120, 140, 125, int(al * 0.85)))
            lx, ly = x + a[2] * sc / 2, y + a[3] * sc + 8 * S
        d.text((lx, ly), name, font=fsm, fill=(190, 200, 192, al), anchor="mt")
    if k1 < 0.999:
        x, y = P(tip)
        rr = 14 * sc * 0.6
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(80, 170, 230, 30), outline=(80, 170, 230, 120), width=2 * S)
        d.rectangle((x - 9 * S, y - 9 * S, x + 9 * S, y + 9 * S), fill=ORANGE + (255,))

    # phase 2 (2.2-3.4s): operating perimeter (dashed orange)
    k2 = ease_out((t - 2.2) / 1.0)
    if k2 > 0:
        Lp = poly_len(PERIM)
        dash = 3.0
        dist = 0.0
        while dist < Lp * k2:
            a, _ = along(PERIM, dist)
            b, _ = along(PERIM, min(dist + dash, Lp * k2))
            d.line([P(a), P(b)], fill=ORANGE + (255,), width=4 * S)
            dist += dash * 1.9
    # phase 3 (3.3-4.6s): exclusion zones
    fz = font(FONT_B, 18 * S)
    for i, ((x, y, w, h), name) in enumerate(ZONES + [((DAM[0][0] - DAM[1], DAM[0][1] - DAM[1], DAM[1] * 2, DAM[1] * 2), DAM[2])]):
        k = ease_out((t - 3.3 - i * 0.18) / 0.4)
        if k <= 0:
            continue
        x0, y0 = P((x, y)); x1, y1 = P((x + w, y + h))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        sx, sy = (x1 - x0) / 2 * (0.6 + 0.4 * k), (y1 - y0) / 2 * (0.6 + 0.4 * k)
        box = (cx - sx, cy - sy, cx + sx, cy + sy)
        if name == "Dam":
            d.ellipse(box, fill=(210, 60, 50, int(70 * k)), outline=(235, 80, 65, int(255 * k)), width=3 * S)
        else:
            d.rectangle(box, fill=(210, 60, 50, int(70 * k)), outline=(235, 80, 65, int(255 * k)), width=3 * S)
        d.text((cx, cy), name, font=fz, fill=(255, 205, 195, int(255 * k)), anchor="mm")
    # phase 4 (4.5-6s): coverage lanes sweep + robot
    k4 = (t - 4.5) / 1.4
    if k4 > 0:
        n = int(len(LANES) * min(1, k4))
        for (yy, a, b) in LANES[:n]:
            d.line([P((a, yy)), P((b, yy))], fill=(80, 170, 230, 170), width=2 * S)
        if n:
            yy, a, b = LANES[n - 1]
            x, y = P((b, yy))
            d.rectangle((x - 9 * S, y - 9 * S, x + 9 * S, y + 9 * S), fill=ORANGE + (255,))

    # copy block on the left
    steps = [(0.0, "01", "Auto-maps the boundary", "LiDAR + RTK trace the fence line on the first run"),
             (2.2, "02", "Set the perimeter", "Choose exactly where it works"),
             (3.3, "03", "Mark no-go zones", "Gardens, septic, dams, play areas"),
             (4.5, "04", "Plans its own route", "Coverage lanes around every obstacle")]
    fnum = font(FONT_M, 20 * S)
    ft = font(FONT_B, 40 * S)
    fs = font(FONT_M, 23 * S)
    feye = font(FONT_M, 22 * S)
    d.rectangle((120 * S, 170 * S, 154 * S, 173 * S), fill=ORANGE + (255,))
    spaced(d, (168 * S, 160 * S), "SMART BOUNDARIES", feye, ORANGE + (255,), 4 * S)
    y = 250 * S
    for (ts, num, title, sub) in steps:
        k = ease_out((t - ts) / 0.45)
        active = 1.0 if t >= ts else 0.0
        al = int(255 * (0.3 + 0.7 * k)) if active else 60
        d.text((120 * S, y + 8 * S), num, font=fnum, fill=ORANGE + (al,))
        d.text((170 * S, y), title, font=ft, fill=(240, 243, 241, al))
        d.text((171 * S, y + 54 * S), sub, font=fs, fill=(170, 180, 174, al))
        y += 150 * S
    img = img.resize((W, H), Image.LANCZOS)
    return img


# ----------------------------------------------------------------- overlays

def lerp_track(track, f_src):
    """track keyed by 1-based source frame; f_src may be fractional."""
    a = max(1, min(int(math.floor(f_src)), len(track)))
    b = max(1, min(a + 1, len(track)))
    k = f_src - math.floor(f_src)
    ta, tb = track[str(a)], track[str(b)]
    return {key: [ta[key][0] * (1 - k) + tb[key][0] * k, ta[key][1] * (1 - k) + tb[key][1] * k] for key in ta}


def overlay_s7(img, t, trk, trail):
    d = ImageDraw.Draw(img, "RGBA")
    p = trk["robot"]
    x, y = p[0] * W, p[1] * H
    trail.append((x, y))
    if len(trail) > 1:
        for i in range(0, len(trail) - 1, 2):
            d.line([trail[i], trail[i + 1]], fill=(255, 255, 255, 110), width=3)
    for k in range(3):
        ph = ((t * 0.9) + k / 3) % 1.0
        r = 40 + ph * 220
        d.ellipse((x - r, y - r, x + r, y + r), outline=(110, 200, 255, int(150 * (1 - ph))), width=2)
    tag = "RTK FIX  ·  ±1.4 cm"
    f = font(FONT_M, 22)
    tw = d.textlength(tag, font=f)
    bx, by = x + 120, y - 150
    d.line([(x + 30, y - 30), (bx, by + 18)], fill=(255, 255, 255, 200), width=2)
    d.rectangle((bx, by, bx + tw + 28, by + 38), fill=(14, 18, 16, 200))
    d.text((bx + 14, by + 7), tag, font=f, fill=(255, 255, 255, 255))


def overlay_s8(img, t, trk):
    d = ImageDraw.Draw(img, "RGBA")
    k = ease_out((t - 0.8) / 0.8)
    if k <= 0:
        return
    al = int(255 * k)
    f = font(FONT_B, 28)

    def dim(a, b, label, side=1):
        ax, ay = a[0] * W, a[1] * H
        bx, by = b[0] * W, b[1] * H
        mx, my = ax + (bx - ax) * k, ay + (by - ay) * k
        d.line([(ax, ay), (mx, my)], fill=(255, 255, 255, al), width=3)
        for (px, py) in ((ax, ay), (mx, my)):
            d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=ORANGE + (al,))
        cx, cy = (ax + bx) / 2, (ay + by) / 2
        tw = d.textlength(label, font=f)
        d.rectangle((cx - tw / 2 - 12, cy - 22 + side * 36, cx + tw / 2 + 12, cy + 18 + side * 36), fill=(14, 18, 16, int(210 * k)))
        d.text((cx, cy - 2 + side * 36), label, font=f, fill=(255, 255, 255, al), anchor="mm")

    dim(trk["len_a"], trk["len_b"], "850 mm", 1)
    dim(trk["wid_a"], trk["wid_b"], "610 mm", 1)
    g = trk["grip"]
    gx, gy = g[0] * W, g[1] * H
    k2 = ease_out((t - 1.8) / 0.6)
    if k2 > 0:
        a2 = int(255 * k2)
        d.ellipse((gx - 9, gy - 9, gx + 9, gy + 9), outline=ORANGE + (a2,), width=3)
        lx, ly = gx - 40, gy - 120
        d.line([(gx - 6, gy - 8), (lx + 60, ly + 40)], fill=(255, 255, 255, a2), width=2)
        f2 = font(FONT_M, 24)
        txt = "Carry handle"
        tw = d.textlength(txt, font=f2)
        d.rectangle((lx - tw + 60 - 14, ly + 20, lx + 60 + 14, ly + 58), fill=(14, 18, 16, int(210 * k2)))
        d.text((lx + 60, ly + 39), txt, font=f2, fill=(255, 255, 255, a2), anchor="rm")


def end_card(base, t):
    """3 s logo lock-up over the darkened final hero frame."""
    k = ease_out(t / 0.9)
    img = base.convert("RGBA")
    dark = Image.new("RGBA", (W, H), (8, 10, 9, int(200 * k)))
    img.alpha_composite(dark)
    d = ImageDraw.Draw(img, "RGBA")
    a = int(255 * ease_out((t - 0.3) / 0.7))
    fbig = font(FONT_B, 132)
    fsub = font(FONT_M, 34)
    feye = font(FONT_M, 24)
    cx = W / 2
    tw = d.textlength("WEED PULLER", font=fbig)
    d.text((cx, H / 2 - 40), "WEED PULLER", font=fbig, fill=(255, 255, 255, a), anchor="mm")
    d.rectangle((cx - tw / 2, H / 2 + 46, cx - tw / 2 + 120 * ease_out((t - 0.5) / 0.6), H / 2 + 52), fill=ORANGE + (a,))
    ex = cx - tw / 2
    spaced(d, (ex + 140, H / 2 + 34), "WP-1  AUTONOMOUS SPOT WEEDER", feye, ORANGE + (a,), 5)
    a2 = int(255 * ease_out((t - 0.9) / 0.6))
    d.text((cx, H / 2 + 130), "Pull weeds. Not your back.", font=fsub, fill=(225, 230, 227, a2), anchor="mm")
    fade = 1.0 - ease_out((t - 2.5) / 0.5) if t > 2.5 else 1.0
    if fade < 1:
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - fade)))))
    return img


# ----------------------------------------------------------------- pipeline

def interp_field(frames_dir, shot, draft):
    src = os.path.join(frames_dir, shot)
    dst = os.path.join(frames_dir, shot + "_24")
    n_src = len([f for f in os.listdir(src) if f.endswith(".png")])
    if os.path.isdir(dst) and len(os.listdir(dst)) >= n_src * 2 - 2:
        return dst
    os.makedirs(dst, exist_ok=True)
    if draft:
        vf = "fps=24"
    else:
        vf = "minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(src, "%04d.png"),
                    "-vf", vf, os.path.join(dst, "%04d.png")], check=True)
    return dst


def main():
    frames_dir, music, out = sys.argv[1:4]
    draft = "--draft" in sys.argv
    vig = vignette()
    scr = scrim()
    rng = np.random.default_rng(1)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", music, "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "medium" if draft else "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-shortest", out], stdin=subprocess.PIPE)
    last_frame = None
    trail = []
    for shot, t0, t1, sfps in TIMELINE:
        n = int(round((t1 - t0) * FPS))
        if shot in ("s1", "s2", "s5", "s6", "s7"):
            src = interp_field(frames_dir, shot, draft)
        elif shot not in ("map", "end"):
            src = os.path.join(frames_dir, shot)
        else:
            src = None
        files = sorted(f for f in os.listdir(src) if f.endswith(".png")) if src else []
        track = None
        if shot in ("s7", "s8"):
            tp = os.path.join(frames_dir, shot, "track.json")
            if os.path.exists(tp):
                track = json.load(open(tp))["track"]
        for i in range(n):
            t = i / FPS
            if shot == "map":
                img = map_frame(t).convert("RGBA")
            elif shot == "end":
                img = end_card(last_frame, t)
            else:
                fi = min(len(files) - 1, int(i * len(files) / n)) if files else 0
                img = Image.open(os.path.join(src, files[fi])).convert("RGB").resize((W, H), Image.LANCZOS).convert("RGBA")
                if shot != "s9" or True:
                    img.alpha_composite(scr)
                if track:
                    f_src = 1 + t * sfps
                    trk = lerp_track(track, f_src)
                    if shot == "s7":
                        overlay_s7(img, t, trk, trail)
                    else:
                        overlay_s8(img, t, trk)
                for item in TITLES.get(shot, []):
                    draw_title(img, item, t, big=(shot == "s2"))
                if shot == "s9":
                    last_frame = Image.open(os.path.join(src, files[-1])).convert("RGB").resize((W, H), Image.LANCZOS)
            arr = np.asarray(img.convert("RGB")).astype(np.float32)
            gt = t0 + t
            if gt < 0.6:
                arr *= gt / 0.6
            if shot != "map":
                arr *= vig
            arr += rng.normal(0, 3.2, (H, W, 1)).astype(np.float32)
            enc.stdin.write(np.clip(arr, 0, 255).astype(np.uint8).tobytes())
        print("cut", shot, n, "frames", flush=True)
    enc.stdin.close()
    enc.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()
