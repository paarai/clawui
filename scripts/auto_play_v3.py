#!/usr/bin/env python3
"""Auto-play v3: Async capture + score-based dodge + powerup collection."""
import subprocess, time, sys, os, threading, numpy as np
from PIL import Image

CL, CR, CT, CB = 80, 380, 60, 560
CW, CH = CR - CL, CB - CT
CX = (CL + CR) // 2
PY = CB - 50

def sh(c): subprocess.run(['bash', '-c', c], capture_output=True)
def xmove(x, y): os.system(f'DISPLAY=:0 xdotool mousemove {x} {y}')

class AsyncCapture:
    def __init__(self):
        self._frame = None; self._lock = threading.Lock(); self._running = True; self._count = 0
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        while self._running:
            subprocess.run(['gnome-screenshot', '-f', '/dev/shm/_ac.png'], capture_output=True, env={**os.environ, 'DISPLAY': ':0'})
            try:
                img = np.array(Image.open('/dev/shm/_ac.png'))
                c = img[CT:CB, CL:CR, :3]
                with self._lock: self._frame = c; self._count += 1
            except: pass
    def get(self):
        with self._lock: return self._frame, self._count
    def stop(self): self._running = False

def _cluster(mask, min_px=8):
    ys, xs = np.where(mask)
    if len(xs) < min_px: return []
    g = {}
    for x, y in zip(xs, ys):
        k = (x//20, y//20)
        if k not in g: g[k] = [0,0,0]
        g[k][0] += x; g[k][1] += y; g[k][2] += 1
    return [(s[0]//s[2], s[1]//s[2]) for s in g.values() if s[2] >= min_px]

def detect(canvas):
    r, g, b = canvas[:,:,0].astype(np.int16), canvas[:,:,1].astype(np.int16), canvas[:,:,2].astype(np.int16)
    enemies = _cluster((r > 150) & (g < 80) & (b < 80), 8) + _cluster((r > 200) & (g > 100) & (g < 180) & (b < 60), 8)
    powerups = _cluster((g > 130) & (r < 100) & (b < 100), 10)
    return enemies, powerups

def ai_decide(px, enemies, powerups):
    best_x, best_s = CW // 2, -999999
    for frac in [0.08, 0.15, 0.22, 0.3, 0.38, 0.46, 0.54, 0.62, 0.7, 0.78, 0.85, 0.92]:
        cx = int(CW * frac); s = 0.0
        for ex, ey in enemies:
            dx = abs(cx - ex); danger = max(0, ey - CH*0.2) / (CH*0.8)
            if dx < 70: s -= (70-dx) * (1+danger*4)
            if dx < 25 and danger > 0.4: s -= 500
            # predicted position
            ey2 = min(ey+40, CH)
            danger2 = max(0, ey2 - CH*0.3) / (CH*0.7)
            if abs(cx-ex) < 55: s -= (55-abs(cx-ex)) * danger2 * 2
        for ppx, ppy in powerups:
            if abs(cx-ppx) < 90 and ppy > CH*0.25: s += max(0, 90-abs(cx-ppx)) * 1.5
        s -= abs(cx - CW//2) * 0.1; s -= abs(cx - px) * 0.2
        if s > best_s: best_s = s; best_x = cx
    return best_x

def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    print(f'[AI v3] {dur}s auto-play')
    cap = AsyncCapture(); time.sleep(1.5)
    px = CW // 2; sx = CX
    xmove(sx, PY); time.sleep(0.1); sh('DISPLAY=:0 xdotool mousedown 1'); time.sleep(0.1)
    start = time.time(); lf = 0; dec = 0; mv = 0; tx = CW // 2
    saves = {5.0, 30.0, 60.0, 85.0}; saved = set()
    try:
        while time.time() - start < dur:
            f, c = cap.get()
            if f is not None and c > lf:
                lf = c; enemies, powerups = detect(f); tx = ai_decide(px, enemies, powerups); dec += 1
                if dec % 10 == 0:
                    el = time.time() - start
                    print(f'[AI v3] t={el:.0f}s dec={dec} mv={mv} enemies={len(enemies)} pups={len(powerups)} x={sx}')
            dx = tx - px; step = max(-18, min(18, dx))
            if abs(step) > 1:
                px += step; px = max(12, min(CW-12, px)); sx = px + CL; xmove(sx, PY); mv += 1
            el = time.time() - start
            for t in saves:
                if t not in saved and el >= t:
                    sh(f'DISPLAY=:0 gnome-screenshot -f /dev/shm/ai_v3_{int(t)}s.png'); saved.add(t)
            time.sleep(0.03)
    except KeyboardInterrupt: pass
    finally:
        sh('DISPLAY=:0 xdotool mouseup 1'); cap.stop()
        sh('DISPLAY=:0 gnome-screenshot -f /dev/shm/ai_v3_final.png')
        el = time.time() - start
        print(f'[AI v3] Done! {dec} decisions, {mv} moves in {el:.1f}s ({dec/el:.1f} dec/s, {mv/el:.1f} mv/s)')

if __name__ == '__main__': main()
