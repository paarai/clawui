#!/usr/bin/env python3
"""Auto-play v4: Silent XDG Portal capture + score-based dodge + powerup collection.

Key improvement over v3: No screen flicker. Uses XDG Desktop Portal instead of gnome-screenshot.
"""
import subprocess, time, sys, os, threading, urllib.parse, shutil
import numpy as np
from PIL import Image

try:
    from rapidocr_onnxruntime import RapidOCR
    _ocr_engine = RapidOCR()
except Exception:
    _ocr_engine = None

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

CL, CR, CT, CB = 80, 380, 60, 560
CW, CH = CR - CL, CB - CT
CX = (CL + CR) // 2
PY = CB - 50

def sh(c): subprocess.run(['bash', '-c', c], capture_output=True)
def xmove(x, y): os.system(f'DISPLAY=:0 xdotool mousemove {x} {y}')


def portal_screenshot(output_path='/dev/shm/_ac.png', timeout_ms=2000):
    """Take screenshot via XDG Portal - no flash."""
    os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS', f'unix:path=/run/user/{os.getuid()}/bus')
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    result = [None]
    loop = GLib.MainLoop()

    def on_response(conn, sender, path, iface, signal, params):
        response, results = params
        if response == 0:
            uri = results.get('uri', '')
            if uri:
                result[0] = urllib.parse.unquote(uri.replace('file://', ''))
        loop.quit()

    sub_id = bus.signal_subscribe(
        None, 'org.freedesktop.portal.Request', 'Response',
        None, None, Gio.DBusSignalFlags.NONE, on_response
    )
    try:
        bus.call_sync(
            'org.freedesktop.portal.Desktop',
            '/org/freedesktop/portal/desktop',
            'org.freedesktop.portal.Screenshot', 'Screenshot',
            GLib.Variant('(sa{sv})', ('', {'interactive': GLib.Variant('b', False)})),
            GLib.VariantType('(o)'), Gio.DBusCallFlags.NONE, timeout_ms
        )
        GLib.timeout_add(timeout_ms, loop.quit)
        loop.run()
    finally:
        bus.signal_unsubscribe(sub_id)

    if result[0]:
        try:
            shutil.copy2(result[0], output_path)
            return output_path
        except:
            return result[0]
    return None


class AsyncCapture:
    """Silent async capture using XDG Portal."""
    def __init__(self):
        self._frame = None
        self._lock = threading.Lock()
        self._running = True
        self._count = 0
        self._cap_times = []
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            t0 = time.time()
            path = portal_screenshot('/dev/shm/_ac_portal.png')
            if path:
                try:
                    img = np.array(Image.open(path))
                    c = img[CT:CB, CL:CR, :3]
                    with self._lock:
                        self._frame = c
                        self._count += 1
                        self._cap_times.append(time.time() - t0)
                except:
                    pass

    def get(self):
        with self._lock:
            return self._frame, self._count

    def avg_ms(self):
        with self._lock:
            if not self._cap_times:
                return 0
            return sum(self._cap_times[-20:]) / min(len(self._cap_times), 20) * 1000

    def stop(self):
        self._running = False


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


def _try_auto_restart(cooldown_ok=True):
    """Detect GAME OVER and click 重新开始 automatically. Returns True if restarted."""
    if _ocr_engine is None:
        return False
    shot = portal_screenshot('/dev/shm/_state_check.png')
    if not shot:
        return False
    try:
        res, _ = _ocr_engine('/dev/shm/_state_check.png')
        for box, text, conf in (res or []):
            t = str(text)
            if cooldown_ok and ('重新开始' in t):
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x, y = int(sum(xs)/len(xs)), int(sum(ys)/len(ys))
                sh(f'DISPLAY=:0 xdotool mousemove {x} {y}; sleep 0.08; DISPLAY=:0 xdotool click 1')
                time.sleep(0.8)
                # re-grab control drag anchor
                sh(f'DISPLAY=:0 xdotool mousemove {CX} {PY}; sleep 0.05; DISPLAY=:0 xdotool mousedown 1')
                print(f'[AI v4] auto-restart clicked at ({x},{y})')
                return True
    except Exception:
        return False
    return False


def ai_decide(px, enemies, powerups):
    best_x, best_s = CW // 2, -999999
    for frac in [0.08, 0.15, 0.22, 0.3, 0.38, 0.46, 0.54, 0.62, 0.7, 0.78, 0.85, 0.92]:
        cx = int(CW * frac); s = 0.0
        for ex, ey in enemies:
            dx = abs(cx - ex); danger = max(0, ey - CH*0.2) / (CH*0.8)
            if dx < 70: s -= (70-dx) * (1+danger*4)
            if dx < 25 and danger > 0.4: s -= 500
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
    print(f'[AI v4] Silent capture, {dur}s auto-play')

    cap = AsyncCapture()
    time.sleep(1.5)

    px = CW // 2; sx = CX
    xmove(sx, PY); time.sleep(0.1)
    sh('DISPLAY=:0 xdotool mousedown 1'); time.sleep(0.1)

    start = time.time(); lf = 0; dec = 0; mv = 0; tx = CW // 2
    saves = {5.0, 30.0, 60.0, 85.0}; saved = set()
    last_restart_check = 0.0
    restart_cooldown_until = 0.0

    try:
        while time.time() - start < dur:
            f, c = cap.get()
            if f is not None and c > lf:
                lf = c
                enemies, powerups = detect(f)
                tx = ai_decide(px, enemies, powerups)
                dec += 1
                if dec % 10 == 0:
                    el = time.time() - start
                    avg_cap = cap.avg_ms()
                    print(f'[AI v4] t={el:.0f}s dec={dec} mv={mv} enemies={len(enemies)} pups={len(powerups)} x={sx} cap={avg_cap:.0f}ms')

            dx = tx - px; step = max(-18, min(18, dx))
            if abs(step) > 1:
                px += step; px = max(12, min(CW-12, px)); sx = px + CL
                xmove(sx, PY); mv += 1

            el = time.time() - start
            for t in saves:
                if t not in saved and el >= t:
                    portal_screenshot(f'/dev/shm/ai_v4_{int(t)}s.png')
                    saved.add(t)

            # Every 15s: check GAME OVER and restart (rate-limited to avoid slowing loop)
            if (el - last_restart_check) >= 15.0:
                last_restart_check = el
                if _try_auto_restart(cooldown_ok=(time.time() >= restart_cooldown_until)):
                    restart_cooldown_until = time.time() + 20.0

            time.sleep(0.03)

    except KeyboardInterrupt:
        pass
    finally:
        sh('DISPLAY=:0 xdotool mouseup 1')
        cap.stop()
        portal_screenshot('/dev/shm/ai_v4_final.png')
        el = time.time() - start
        avg_cap = cap.avg_ms()
        print(f'[AI v4] Done! {dec} decisions, {mv} moves in {el:.1f}s')
        print(f'[AI v4] Rate: {dec/el:.1f} dec/s, {mv/el:.1f} mv/s, avg capture: {avg_cap:.0f}ms')


if __name__ == '__main__':
    main()
