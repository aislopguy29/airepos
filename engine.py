"""aislop engine: 1080x1920 @ 60 fps renderer, text/callout sprites, procedural audio, ffmpeg encoder.
Every style module imports this; nothing here is style specific."""
import math, os, wave, subprocess, json
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 60, 48000
SAFE_TOP, SAFE_BOT = 240, 1680            # centre 3:4 crop shown in the profile grid
FONTS = {
    "bold":  "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "med":   "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "black": "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "mono":  "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
}

# ---------------------------------------------------------------- math helpers
def clamp(x, a=0.0, b=1.0):
    if isinstance(x, np.ndarray): return np.clip(x, a, b)
    return a if x < a else b if x > b else x
def lerp(a, b, t): return a + (b - a) * t
def smooth(t): t = clamp(t); return t * t * (3 - 2 * t)
def out_back(t, s=1.9):
    t = clamp(t) - 1; return 1 + t * t * ((s + 1) * t + s)
def hsv(h, s=1.0, v=1.0):
    import colorsys; r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v); return (int(r*255), int(g*255), int(b*255))
def mulc(c, k): return tuple(int(clamp(x*k, 0, 255)) for x in c)

# ---------------------------------------------------------------- text sprites
_fc, _tc = {}, {}
def font(kind, size):
    k = (kind, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(FONTS[kind], size)
    return _fc[k]

def text_sprite(txt, size, color=(255, 255, 255), kind="bold", stroke=0, stroke_color=(0, 0, 0), spacing=0):
    """RGBA uint8 sprite with straight alpha (no dark fringes). spacing = extra px between letters."""
    key = (txt, size, color, kind, stroke, stroke_color, spacing)
    if key in _tc: return _tc[key]
    f = font(kind, size); pad = stroke + 4
    if spacing:
        widths = [f.getlength(ch) + spacing for ch in txt]
        l, t, r, b = f.getbbox(txt, stroke_width=stroke); w = int(sum(widths)) + 2 * pad; h = b - t + 2 * pad
        def paint(mask, st):
            d = ImageDraw.Draw(mask); x = pad
            for ch, wd in zip(txt, widths):
                d.text((x, pad - t), ch, font=f, fill=255, stroke_width=st); x += wd
    else:
        l, t, r, b = f.getbbox(txt, stroke_width=stroke); w = r - l + 2 * pad; h = b - t + 2 * pad
        def paint(mask, st): ImageDraw.Draw(mask).text((pad - l, pad - t), txt, font=f, fill=255, stroke_width=st)
    outer = Image.new("L", (w, h), 0); paint(outer, stroke)
    inner = Image.new("L", (w, h), 0); paint(inner, 0)
    o = np.asarray(outer); i = np.asarray(inner).astype(np.float32) / 255.0
    rgb = np.empty((h, w, 3), np.float32)
    for c in range(3): rgb[..., c] = stroke_color[c] * (1 - i) + color[c] * i
    spr = np.dstack([rgb.astype(np.uint8), o]); _tc[key] = spr
    return spr

def blit(frame, spr, cx, cy, alpha=1.0, scale=1.0, anchor="c"):
    """Alpha-composite RGBA sprite onto RGB frame. anchor: c centre, l left-centre, r right-centre."""
    if alpha <= 0.003: return
    if scale != 1.0:
        nw, nh = max(1, int(spr.shape[1] * scale)), max(1, int(spr.shape[0] * scale))
        spr = cv2.resize(spr, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    h, w = spr.shape[:2]
    x0 = int(round(cx - (w / 2 if anchor == "c" else 0 if anchor == "l" else w)))
    y0 = int(round(cy - h / 2)); x1, y1 = x0 + w, y0 + h
    a0, b0, a1, b1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if a0 >= a1 or b0 >= b1: return
    s = spr[b0 - y0:b1 - y0, a0 - x0:a1 - x0]
    a = s[..., 3:4].astype(np.float32) * (alpha / 255.0)
    roi = frame[b0:b1, a0:a1]
    roi[:] = (roi * (1.0 - a) + s[..., :3] * a).astype(np.uint8)

def pill(frame, x0, y0, x1, y1, color, alpha=0.6):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    a0, b0, a1, b1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if a0 >= a1 or b0 >= b1: return
    mask = np.zeros((b1 - b0, a1 - a0), np.uint8); rad = (y1 - y0) // 2
    cv2.rectangle(mask, (rad - (a0 - x0), 0 - (b0 - y0)), (x1 - x0 - rad - (a0 - x0) - 1 + (x1 - x1), y1 - y0 - (b0 - y0) - 1), 255, -1)
    cv2.circle(mask, (rad - (a0 - x0), rad - (b0 - y0)), rad, 255, -1, cv2.LINE_AA)
    cv2.circle(mask, (x1 - x0 - rad - (a0 - x0) - 1, rad - (b0 - y0)), rad, 255, -1, cv2.LINE_AA)
    m = (mask.astype(np.float32) * (alpha / 255.0))[..., None]
    roi = frame[b0:b1, a0:a1]; roi[:] = (roi * (1 - m) + np.array(color, np.float32) * m).astype(np.uint8)

def arrow_down(frame, cx, cy, size, color, alpha=1.0):
    pts = np.array([[cx - size, cy - size * .55], [cx + size, cy - size * .55], [cx, cy + size * .75]], np.int32)
    if alpha >= 0.99: cv2.fillPoly(frame, [pts], color, cv2.LINE_AA); return
    ov = frame.copy(); cv2.fillPoly(ov, [pts], color, cv2.LINE_AA); cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)

# ---------------------------------------------------------------- background / frame furniture
def make_bg(top=(7, 9, 22), bottom=(20, 8, 38), glow=(40, 30, 90)):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg = np.array(top, np.float32) * (1 - y) + np.array(bottom, np.float32) * y
    bg = np.broadcast_to(bg, (H, W, 3)).copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * .75)) ** 2 + ((yy - H * .52) / (H * .5)) ** 2)
    bg += (np.array(glow, np.float32) * np.clip(1 - d, 0, 1)[..., None] ** 2) * .55   # soft centre glow
    bg *= (1.0 - 0.35 * np.clip(d - .55, 0, 1))[..., None]                            # vignette
    return np.clip(bg, 0, 255).astype(np.uint8)

def bake_source_bar(bg, text, y=1622, h=50):
    """Source line shown on every frame (house rule: all numbers cite a .gov source)."""
    spr = text_sprite(text, 23, (205, 210, 225), "med")
    if spr.shape[1] > W - 120: spr = cv2.resize(spr, (W - 120, int(spr.shape[0] * (W - 120) / spr.shape[1])), interpolation=cv2.INTER_AREA)
    pill(bg, (W - spr.shape[1]) // 2 - 28, y, (W + spr.shape[1]) // 2 + 28, y + h, (0, 0, 0), 0.55)
    blit(bg, spr, W / 2, y + h / 2)
    return bg

def add_glow(frame, layer_half, sigma=9, strength=1.0):
    """layer_half: (H/2,W/2,3) uint8 drawn at half res; blurred, upscaled and added."""
    g = cv2.GaussianBlur(layer_half, (0, 0), sigma)
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    cv2.addWeighted(frame, 1.0, g, strength, 0, frame)

# ---------------------------------------------------------------- audio
def midi_hz(m): return 440.0 * 2 ** ((np.asarray(m, np.float64) - 69) / 12)
PENTA = [0, 2, 4, 7, 9]
def penta(i, root=60):
    """i-th note of a major pentatonic ladder (can be negative)."""
    return root + 12 * (i // 5) + PENTA[i % 5]
# Ode to Joy (Beethoven, 1824 - public domain composition). Notes only; timing comes from events.
ODE = [64,64,65,67,67,65,64,62,60,60,62,64,64,62,62, 64,64,65,67,67,65,64,62,60,60,62,64,62,60,60]
_inst = {}
def _t(d): return np.arange(int(d * SR), dtype=np.float64) / SR
def kalimba(freq, dur=1.0):
    k = ("k", round(freq, 2), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); env = np.exp(-t * 4.2) * (1 - np.exp(-t * 900))
    s = np.sin(2*np.pi*freq*t) + .33*np.sin(2*np.pi*freq*2*t)*np.exp(-t*8) + .22*np.sin(2*np.pi*freq*5.4*t)*np.exp(-t*34)
    _inst[k] = (s * env * .5).astype(np.float32); return _inst[k]
def bell(freq, dur=1.6):
    k = ("b", round(freq, 2), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); env = np.exp(-t * 2.6) * (1 - np.exp(-t * 1200))
    s = np.sin(2*np.pi*freq*t + 2.2*np.sin(2*np.pi*freq*3.5*t)*np.exp(-t*6))
    _inst[k] = (s * env * .5).astype(np.float32); return _inst[k]
def tick(freq, dur=0.07):
    k = ("t", round(freq, 1), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); s = np.sin(2*np.pi*freq*t) * np.exp(-t * 70) * (1 - np.exp(-t * 3000))
    _inst[k] = (s * .6).astype(np.float32); return _inst[k]
def thump(dur=0.4, f0=140, f1=42):
    k = ("th", dur, f0, f1)
    if k in _inst: return _inst[k]
    t = _t(dur); f = f1 + (f0 - f1) * np.exp(-t * 18)
    s = np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t * 9) * (1 - np.exp(-t * 1500))
    _inst[k] = s.astype(np.float32); return _inst[k]
def riser(dur, f0=200, f1=2400, seed=1):
    t = _t(dur); u = t / dur; f = f0 * (f1 / f0) ** u
    sweep = np.sin(2*np.pi*np.cumsum(f)/SR)
    n = np.random.default_rng(seed).standard_normal(len(t)); n = np.convolve(n, np.ones(6)/6, "same")
    env = u ** 2.2
    return ((.55 * sweep + .35 * n) * env * .6).astype(np.float32)
def slide_down(dur=1.0, f0=520, f1=150):
    t = _t(dur); u = t / dur; f = f0 * (f1 / f0) ** u * (1 + .012 * np.sin(2*np.pi*6*t))
    ph = 2*np.pi*np.cumsum(f)/SR; s = np.sin(ph) + .3*np.sin(2*ph)
    return (s * np.exp(-u * 2.2) * (1 - np.exp(-t * 200)) * .5).astype(np.float32)
def chord(midis, dur=2.0, fn=bell):
    out = np.zeros(int(dur * SR), np.float32)
    for m in midis:
        b = fn(float(midi_hz(m)), dur); out[:len(b)] += b[:len(out)] * (1.0 / len(midis) ** .5)
    return out
def whoosh(dur=0.35, seed=3):
    t = _t(dur); n = np.random.default_rng(seed).standard_normal(len(t))
    n = np.convolve(n, np.ones(14)/14, "same"); env = np.sin(np.pi * t / dur) ** 2
    return (n * env * .5).astype(np.float32)

# ---------------------------------------------------------------- music-bed instruments (all original synthesis)
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
          "mixolydian": [0, 2, 4, 5, 7, 9, 10], "lydian": [0, 2, 4, 6, 7, 9, 11], "phrygian": [0, 1, 3, 5, 7, 8, 10],
          "harmonic_minor": [0, 2, 3, 5, 7, 8, 11]}
def _noise(n, seed): return np.random.default_rng(seed).standard_normal(n)
def _hp(x, k=3):
    return x - np.convolve(x, np.ones(k) / k, "same")
def epiano(freq, dur=1.2):
    """Soft FM electric piano (tine + bark), slight tremolo."""
    k = ("ep", round(freq, 2), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); env = np.exp(-t * 1.7) * (1 - np.exp(-t * 500))
    s = np.sin(2*np.pi*freq*t + 1.1*np.exp(-t*3.5)*np.sin(2*np.pi*freq*t)) + .18*np.sin(2*np.pi*freq*4*t)*np.exp(-t*14)
    s *= 1 + .12 * np.sin(2*np.pi*4.6*t)
    _inst[k] = (s * env * .45).astype(np.float32); return _inst[k]
def piano(freq, dur=1.4):
    k = ("pi", round(freq, 2), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); s = np.zeros_like(t)
    for h, a in ((1, 1), (2, .45), (3, .22), (4, .12), (5, .06)): s += a * np.sin(2*np.pi*freq*h*1.0007**h*t) * np.exp(-t*(1.4 + h*.9))
    _inst[k] = (s * (1 - np.exp(-t * 700)) * .4).astype(np.float32); return _inst[k]
def pluck(freq, dur=0.8):
    k = ("pl", round(freq, 2), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); s = np.zeros_like(t)
    for h in range(1, 9): s += np.sin(2*np.pi*freq*h*t) / h * np.exp(-t*(3 + h*2.2))
    _inst[k] = (s * (1 - np.exp(-t * 900)) * .45).astype(np.float32); return _inst[k]
def marimba(freq, dur=0.7):
    k = ("ma", round(freq, 2), dur)
    if k in _inst: return _inst[k]
    t = _t(dur); s = np.sin(2*np.pi*freq*t)*np.exp(-t*6) + .3*np.sin(2*np.pi*freq*3.93*t)*np.exp(-t*22)
    _inst[k] = (s * (1 - np.exp(-t * 1500)) * .55).astype(np.float32); return _inst[k]
def pulse(freq, dur=0.25, duty=.25, decay=6.0):
    t = _t(dur); ph = (freq * t) % 1.0; s = np.where(ph < duty, 1.0, -1.0) - (2 * duty - 1)
    s = np.convolve(s, np.ones(3) / 3, "same")
    return (s * np.exp(-t * decay) * (1 - np.exp(-t * 2000)) * .22).astype(np.float32)
def triangle(freq, dur=0.3, decay=4.0):
    t = _t(dur); s = 2 / np.pi * np.arcsin(np.sin(2*np.pi*freq*t))
    return (s * np.exp(-t * decay) * (1 - np.exp(-t * 2000)) * .4).astype(np.float32)
def saw(freq, dur=0.5, harm=10, attack=.01, decay=3.0, detune=0.0):
    t = _t(dur); s = np.zeros_like(t)
    for d in ((0.0,) if not detune else (-detune, 0.0, detune)):
        f = freq * (1 + d)
        for h in range(1, harm + 1):
            if f * h > 9000: break
            s += np.sin(2*np.pi*f*h*t + h) / h
    env = (1 - np.exp(-t / max(attack, 1e-3))) * np.exp(-t * decay)
    return (s * env * .18).astype(np.float32)
def pad(freqs, dur=3.0, attack=.6, release=.8, harm=6):
    t = _t(dur); s = np.zeros_like(t)
    for f in freqs:
        for d in (-.004, .0, .0045):
            for h in range(1, harm + 1): s += np.sin(2*np.pi*f*(1 + d)*h*t + 1.7*h + d*900) / (h ** 1.4)
    env = np.minimum(1, t / attack) * np.minimum(1, (dur - t) / release)
    return (s * env * (.11 / max(1, len(freqs)) ** .5)).astype(np.float32)
def sub(freq, dur=0.6, decay=2.5):
    t = _t(dur); s = np.sin(2*np.pi*freq*t) + .15*np.sin(4*np.pi*freq*t)
    return (s * np.exp(-t * decay) * (1 - np.exp(-t * 300)) * .6).astype(np.float32)
def snare(dur=0.18, seed=5, tone=185):
    t = _t(dur); n = _hp(_noise(len(t), seed), 4)
    s = .8 * n * np.exp(-t * 22) + .5 * np.sin(2*np.pi*tone*t) * np.exp(-t * 30)
    return (s * .5).astype(np.float32)
def hat(dur=0.05, seed=7, open_=False):
    t = _t(dur); n = _hp(_noise(len(t), seed), 2)
    return (n * np.exp(-t * (14 if open_ else 75)) * .3).astype(np.float32)
def brush(dur=0.22, seed=9):
    t = _t(dur); n = np.convolve(_noise(len(t), seed), np.ones(5) / 5, "same")
    return (n * np.sin(np.pi * t / dur) ** 1.5 * .35).astype(np.float32)
def rim(dur=0.06):
    t = _t(dur); s = np.sin(2*np.pi*1750*t) * np.exp(-t * 90) + .4*np.sin(2*np.pi*520*t) * np.exp(-t * 60)
    return (s * .35).astype(np.float32)
def vinyl(dur, seed=11):
    rng = np.random.default_rng(seed); n = int(dur * SR)
    s = np.convolve(rng.standard_normal(n), np.ones(40) / 40, "same") * .25
    for i in rng.integers(0, n, int(dur * 7)): s[i:i + 30] += rng.uniform(-.9, .9) * np.exp(-np.arange(min(30, n - i)) / 5)
    return (s * .12).astype(np.float32)

# mood presets for Mix.bed (rotate per VARIETY_RULES.md); every value can be overridden through Mix(mood=..., scale=..., bpm=..., timbre=..., root=...)
MOODS = {
    "lofi":       dict(bpm=84,  scale="dorian",  root=50, prog=[0, 3, 6, 4], timbre="epiano",  comp="stabs", bass="sub",     kit="lofi",  swing=.6,  extra="vinyl"),
    "piano_arp":  dict(bpm=96,  scale="major",   root=55, prog=[0, 5, 3, 4], timbre="piano",   comp="arp",   bass="sub",     kit=None,    swing=.5),
    "chiptune":   dict(bpm=118, scale="major",   root=60, prog=[0, 4, 5, 3], timbre="pulse",   comp="arp",   bass="tri",     kit="chip",  swing=.5),
    "synthwave":  dict(bpm=100, scale="minor",   root=45, prog=[0, 5, 2, 6], timbre="saw",     comp="pad",   bass="eighths", kit="808",   swing=.5),
    "ambient":    dict(bpm=66,  scale="lydian",  root=52, prog=[0, 4, 1, 4], timbre="pad",     comp="pad",   bass=None,      kit=None,    swing=.5),
    "marimba":    dict(bpm=104, scale="mixolydian", root=55, prog=[0, 6, 3, 4], timbre="marimba", comp="arp", bass="sub",   kit="light", swing=.5),
    "cinematic":  dict(bpm=72,  scale="harmonic_minor", root=45, prog=[0, 5, 3, 4], timbre="saw", comp="pad", bass="drone",  kit="taiko", swing=.5),
    "jazzy":      dict(bpm=110, scale="dorian",  root=48, prog=[1, 4, 0, 5], timbre="epiano",  comp="stabs", bass="walk",    kit="brush", swing=.64),
    "dark_pulse": dict(bpm=124, scale="phrygian", root=45, prog=[0, 1, 0, 6], timbre="saw",    comp="pad",   bass="eighths", kit="808",   swing=.5),
}
class Mix:
    def __init__(self, dur, mood=None, scale=None, bpm=None, timbre=None, root=None):
        """mood/scale/bpm/timbre/root only feed Mix.bed(); Mix(dur) alone behaves exactly as before."""
        self.n = int(dur * SR); self.L = np.zeros(self.n, np.float32); self.R = np.zeros(self.n, np.float32)
        p = dict(MOODS.get(mood or "lofi", MOODS["lofi"]))
        for k_, v_ in (("scale", scale), ("bpm", bpm), ("timbre", timbre), ("root", root)):
            if v_ is not None: p[k_] = v_
        self.mood, self.p = mood, p
    def chord_notes(self, degree, size=4, octave=0):
        sc = SCALES[self.p["scale"]]; r = self.p["root"] + 12 * octave
        return [r + sc[(degree + 2 * k) % len(sc)] + 12 * ((degree + 2 * k) // len(sc)) for k in range(size)]
    def scale_note(self, i, octave=1):
        sc = SCALES[self.p["scale"]]; return self.p["root"] + 12 * octave + sc[i % len(sc)] + 12 * (i // len(sc))
    def _voice(self, name, m, dur):
        f = float(midi_hz(m))
        if name == "epiano": return epiano(f, dur)
        if name == "piano": return piano(f, dur)
        if name == "pulse": return pulse(f, dur)
        if name == "saw": return saw(f, dur, attack=.02, decay=2.0, detune=.004)
        if name == "marimba": return marimba(f, dur)
        if name == "pluck": return pluck(f, dur)
        if name == "bell": return bell(f, dur)
        return kalimba(f, dur)
    def bed(self, t0, t1, gain=.3, seed=0, intensity=None, drums_off=(), bars_per_chord=1):
        """Original backing track from t0 to t1 in self.p's mood. intensity(t) -> 0..1 thickens the drums/arp;
        drums_off = [(a, b), ...] video-time windows with drums muted (e.g. a slow-mo breath)."""
        p = self.p; beat = 60.0 / p["bpm"]; bar = 4 * beat; rng = np.random.default_rng(seed)
        inten = intensity or (lambda t: .5); hz = lambda m: float(midi_hz(m))
        quiet = lambda t: any(a <= t < b for a, b in drums_off)
        sw = lambda k8: (2 * p["swing"] - 1) * beat * .5 if k8 % 2 else 0.0    # swing offset for odd 8ths
        if p.get("extra") == "vinyl": self.add(t0, vinyl(t1 - t0, seed + 3), gain * .5)
        nb = int(math.ceil((t1 - t0) / bar))
        for b_ in range(nb):
            tb = t0 + b_ * bar; deg = p["prog"][(b_ // bars_per_chord) % len(p["prog"])]
            ch = self.chord_notes(deg, 4, 1); I = float(inten(tb))
            if tb >= t1: break
            # comping
            if p["comp"] == "stabs":
                for off in ((0.0, beat * 1.5 + sw(3)) if b_ % 2 == 0 else (beat * .5 + sw(1), beat * 2.5 + sw(5))):
                    for j, m in enumerate(ch): self.add(tb + off + j * .012, self._voice(p["timbre"], m, 1.4), gain * .32, (j - 1.5) * .25)
            elif p["comp"] == "arp":
                notes = ch + [ch[1] + 12, ch[2] + 12]; step = beat / (4 if I > .6 else 2)
                for k in range(int(bar / step)):
                    m = notes[(k * 3 + b_) % len(notes)] if p["timbre"] != "pulse" else notes[k % len(notes)]
                    self.add(tb + k * step + (sw(k) if step == beat / 2 else 0), self._voice(p["timbre"], m, .5), gain * .3, ((k % 4) - 1.5) * .2)
            else:
                self.add(tb, pad([hz(m) for m in ch], bar + .4, attack=.5 if p["comp"] == "pad" else 1.2), gain * .55)
            # bass
            r = self.chord_notes(deg, 1, 0)[0] - 12 if p["root"] >= 48 else self.chord_notes(deg, 1, 0)[0]
            if p["bass"] == "sub":
                self.add(tb, sub(hz(r), beat * 1.8), gain * .55); self.add(tb + beat * 2.5 + sw(5), sub(hz(r), beat * 1.2), gain * .4)
            elif p["bass"] == "tri":
                for k in range(8): self.add(tb + k * beat / 2, triangle(hz(r + (12 if k % 2 else 0)), beat * .45), gain * .45)
            elif p["bass"] == "eighths":
                for k in range(8): self.add(tb + k * beat / 2, saw(hz(r), beat * .45, harm=8, decay=6), gain * .5)
            elif p["bass"] == "walk":
                sc_ = [r, r + 2, r + 3, r + 5, r + 7, r + 9, r + 10, r + 12]
                for k in range(4): self.add(tb + k * beat, pluck(hz(sc_[int(rng.integers(0, len(sc_)))] if k else r), beat * .95), gain * .55)
            elif p["bass"] == "drone":
                self.add(tb, pad([hz(r), hz(r + 7)], bar + .3, attack=.8, harm=4), gain * .6)
            # drums
            kit = p["kit"]
            if not kit: continue
            for k8 in range(8):
                t = tb + k8 * beat / 2 + sw(k8)
                if t >= t1 or quiet(t): continue
                if kit in ("lofi", "brush", "light"):
                    if k8 in (0, 5) or (k8 == 3 and I > .7): self.add(t, thump(.3, 120, 44), gain * (.7 if kit == "lofi" else .4))
                    if k8 in (2, 6): self.add(t, snare(.16, k8 + b_) if kit == "lofi" else brush(.2, k8 + b_) if kit == "brush" else rim(), gain * .45)
                    self.add(t, hat(.04, b_ * 8 + k8), gain * (.32 if k8 % 2 == 0 else .2))
                    if I > .75: self.add(t + beat / 4, hat(.03, b_ * 9 + k8 + 99), gain * .14)
                elif kit == "chip":
                    if k8 in (0, 4): self.add(t, thump(.18, 160, 50), gain * .6)
                    if k8 in (2, 6): self.add(t, snare(.1, k8), gain * .4)
                    self.add(t, hat(.03, k8), gain * .2)
                elif kit == "808":
                    if k8 in (0, 3, 4) or (I > .7 and k8 == 7): self.add(t, thump(.5, 110, 38), gain * .75)
                    if k8 in (2, 6): self.add(t, snare(.22, k8 + b_, 200), gain * .45)
                    self.add(t, hat(.035, k8 + b_), gain * .22)
                    if I > .6: self.add(t + beat / 4, hat(.03, k8 + b_ + 50), gain * .15)
                elif kit == "taiko":
                    if k8 in (0, 3, 6): self.add(t, thump(.6, 90, 34), gain * .8)

    def add(self, t, sig, gain=1.0, pan=0.0):
        i = int(round(t * SR))
        if i < 0 or i >= self.n: return
        m = min(len(sig), self.n - i); a = (pan + 1) * math.pi / 4
        self.L[i:i+m] += sig[:m] * gain * math.cos(a); self.R[i:i+m] += sig[:m] * gain * math.sin(a)
    def write(self, path, fade_out=0.25, peak=0.89):
        s = np.stack([self.L, self.R], 1)
        s = np.tanh(s * 1.15) / np.tanh(1.15)                       # gentle soft clip glues stacked notes
        m = float(np.abs(s).max()) or 1.0; s *= peak / m
        k = int(fade_out * SR)
        if k: s[-k:] *= np.linspace(1, 0, k)[:, None]
        pcm = (s * 32767).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

# ---------------------------------------------------------------- encoder
class Encoder:
    """Pipes raw RGB frames to ffmpeg: H.264 high@4.2, 60 fps CFR, BT.709, AAC 48k stereo, faststart.
    Writes to *.part.mp4 and renames on success so a stopped render can never look finished."""
    def __init__(self, path, wav, fps=FPS, crf=18):
        self.path, self.tmp = path, path[:-4] + ".part.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
               "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-profile:v", "high", "-level", "4.2",
               "-g", str(fps * 2), "-bf", "2", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-shortest", self.tmp]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    def write(self, frame): self.p.stdin.write(np.ascontiguousarray(frame).tobytes())
    def close(self):
        self.p.stdin.close(); rc = self.p.wait()
        if rc != 0: raise RuntimeError(f"ffmpeg exited {rc}")
        os.replace(self.tmp, self.path)

def save_png(path, frame): cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

def render(path, wav, n_frames, draw_fn, progress=True):
    """draw_fn(i) -> RGB uint8 frame (H,W,3) for frame index i."""
    enc = Encoder(path, wav)
    for i in range(n_frames):
        enc.write(draw_fn(i))
        if progress and i % 300 == 0: print(f"  frame {i}/{n_frames}", flush=True)
    enc.close()
