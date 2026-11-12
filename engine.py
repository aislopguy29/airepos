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

class Mix:
    def __init__(self, dur):
        self.n = int(dur * SR); self.L = np.zeros(self.n, np.float32); self.R = np.zeros(self.n, np.float32)
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
