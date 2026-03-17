#!/usr/bin/env python3
"""Auto-play v5: PipeWire streaming capture (Wayland-friendly, higher FPS)."""

import subprocess, time, sys, os, urllib.parse, shutil
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

from pipewire_capture import PipeWireCapture

# Prefer Mutter-based capture (no portal dialog, no flash)
try:
    from mutter_capture import MutterCapture as _MutterCapture
    _USE_MUTTER = True
except ImportError:
    _MutterCapture = None
    _USE_MUTTER = False

CL, CR, CT, CB = 80, 380, 60, 560
CW, CH = CR - CL, CB - CT
CX = (CL + CR) // 2
PY = CB - 50


def _detect_xwayland_auth() -> tuple[str, str | None]:
    # On GNOME Wayland, Xwayland auth is dynamic and must be read from the Xwayland process args.
    # Example: /usr/bin/Xwayland :0 ... -auth /run/user/1000/.mutter-Xwaylandauth.XXXX
    try:
        r = subprocess.run(
            ['bash', '-lc', "ps -ef | awk '/Xwayland :[0-9]+/ && !/awk/ {d=$9; a=\"\"; for(i=1;i<=NF;i++) if($i==\"-auth\") a=$(i+1); if(d!~/:/) d=\":0\"; print d, a; exit}'"],
            capture_output=True,
            text=True,
        )
        line = (r.stdout or '').strip()
        if line:
            parts = line.split()
            disp = parts[0] if parts else ':0'
            xa = parts[1] if len(parts) > 1 else None
            return disp, xa
    except Exception:
        pass
    return ':0', None


def _xdotool_env_prefix() -> str:
    disp = os.environ.get('DISPLAY')
    xa = os.environ.get('XAUTHORITY')

    if not disp or not xa:
        d2, xa2 = _detect_xwayland_auth()
        disp = disp or d2 or ':0'
        xa = xa or xa2

    if not xa:
        home = os.path.expanduser('~')
        cand = [
            os.path.join(home, '.Xauthority'),
            f'/run/user/{os.getuid()}/gdm/Xauthority',
        ]
        for p in cand:
            if os.path.exists(p):
                xa = p
                break

    if xa:
        return f'DISPLAY={disp} XAUTHORITY={xa}'
    return f'DISPLAY={disp or ":0"}'


def sh(c):
    return subprocess.run(['bash', '-lc', c], capture_output=True, text=True)


def xmove(x, y):
    pref = _xdotool_env_prefix()
    r = sh(f"{pref} xdotool mousemove {x} {y}")
    return r.returncode == 0


def portal_screenshot(output_path='/dev/shm/_ac.png', timeout_ms=2000):
    # Hard-disabled to eliminate all screenshot flash side-effects.
    # Keep function for compatibility with old call sites.
    return None


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


def _try_auto_restart(capture, cooldown_ok=True):
    if _ocr_engine is None or capture is None or not cooldown_ok:
        return False

    try:
        frame = capture.get_frame()
        if frame is None:
            print('[AI v5] auto-restart check skipped: no frame')
            return False

        check_path = '/dev/shm/_state_check.png'
        Image.fromarray(frame).save(check_path)

        res, _ = _ocr_engine(check_path)
        for box, text, conf in (res or []):
            t = str(text)
            if '重新开始' in t:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                # OCR is on cropped frame; convert to global screen coordinates
                x, y = int(sum(xs) / len(xs)) + CL, int(sum(ys) / len(ys)) + CT
                xpref = _xdotool_env_prefix()
                sh(f'{xpref} xdotool mousemove {x} {y}; sleep 0.08; {xpref} xdotool click 1')
                conf_v = float(conf) if conf is not None else 0.0
                print(f'[AI v5] auto-restart detected "{t}" (conf={conf_v:.2f}), clicked at ({x},{y})')
                time.sleep(0.9)
                sh(f'{xpref} xdotool mousemove {CX} {PY}; sleep 0.05; {xpref} xdotool mousedown 1')
                print('[AI v5] auto-restart: mouse control re-grabbed (mousedown restored)')
                return True
    except Exception as e:
        print(f'[AI v5] auto-restart check failed: {e}')
        return False

    return False


def ai_decide(px, enemies, powerups):
    best_x, best_s = CW // 2, -999999
    close_line = CH * 0.5

    for frac in [0.08, 0.15, 0.22, 0.3, 0.38, 0.46, 0.54, 0.62, 0.7, 0.78, 0.85, 0.92]:
        cx = int(CW * frac)
        s = 0.0

        for ex, ey in enemies:
            dx = abs(cx - ex)
            is_close = ey >= close_line

            if is_close:
                # Bottom half = real danger zone, prioritize dodge/survival
                closeness = max(0.0, 1.0 - dx / 80.0)
                danger = max(0.0, (ey - close_line) / (CH - close_line + 1e-6))
                s -= closeness * (260 + 520 * danger)
                if dx < 25:
                    s -= 380
            else:
                # Top half = safer, reward aligning for auto-fire scoring
                align = max(0.0, 1.0 - dx / 95.0)
                far_bonus = max(0.0, (close_line - ey) / close_line)
                s += align * (120 + 180 * far_bonus)

                # Extra reward for staying near top enemies' lane (aggressive scoring)
                if ey < CH * 0.35 and dx < 42:
                    s += 70

        for ppx, ppy in powerups:
            if abs(cx - ppx) < 90 and ppy > CH * 0.25:
                s += max(0, 90 - abs(cx - ppx)) * 1.5

        # Keep motion reasonable; avoid jitter while still allowing aggressive positioning
        s -= abs(cx - CW // 2) * 0.08
        s -= abs(cx - px) * 0.17

        if s > best_s:
            best_s = s
            best_x = cx

    return best_x


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    print(f'[AI v5] PipeWire streaming capture, {dur}s auto-play')
    print('[AI v5] Portal screenshots disabled; no screenshot flash expected.')

    if _USE_MUTTER:
        print('[AI v5] Using Mutter ScreenCast (no portal, no flash)')
        cap = _MutterCapture(crop=(CL, CT, CR, CB), rgb=True)
    else:
        print('[AI v5] Falling back to PipeWire Portal capture')
        cap = PipeWireCapture(crop=(CL, CT, CR, CB), rgb=True)
    cap.start()
    time.sleep(0.5)

    xpref = _xdotool_env_prefix()
    print(f'[AI v5] xdotool env: {xpref}')

    px = CW // 2; sx = CX
    ok_move = xmove(sx, PY); time.sleep(0.1)
    ok_down = (sh(f'{xpref} xdotool mousedown 1').returncode == 0); time.sleep(0.1)
    if not (ok_move and ok_down):
        print('[AI v5] WARN: xdotool may not control display (check DISPLAY/XAUTHORITY)')

    start = time.time(); dec = 0; mv = 0; tx = CW // 2
    saves = {5.0, 30.0, 60.0, 85.0}; saved = set()
    last_restart_check = 0.0
    restart_cooldown_until = 0.0
    last_cap_recover = 0.0
    cap_recover_count = 0

    try:
        while time.time() - start < dur:
            f = cap.get_frame()
            if f is not None:
                enemies, powerups = detect(f)
                tx = ai_decide(px, enemies, powerups)
                dec += 1
                if dec % 20 == 0:
                    el = time.time() - start
                    print(f'[AI v5] t={el:.0f}s dec={dec} mv={mv} enemies={len(enemies)} pups={len(powerups)} cap_fps={cap.fps():.1f}')

            dx = tx - px; step = max(-18, min(18, dx))
            if abs(step) > 1:
                px += step; px = max(12, min(CW-12, px)); sx = px + CL
                xmove(sx, PY); mv += 1

            el = time.time() - start
            # Periodic saves disabled (portal_screenshot causes screen flash)
            # for t in saves:
            #     if t not in saved and el >= t:
            #         portal_screenshot(f'/dev/shm/ai_v5_{int(t)}s.png')
            #         saved.add(t)

            if (el - last_restart_check) >= 15.0:
                last_restart_check = el
                if _try_auto_restart(cap, cooldown_ok=(time.time() >= restart_cooldown_until)):
                    restart_cooldown_until = time.time() + 20.0
                    print('[AI v5] restart cooldown armed for 20s')

            # Capture watchdog: if stream stalls, recreate capture session.
            now = time.time()
            stalled = False
            if hasattr(cap, 'seconds_since_last_frame'):
                stalled = cap.seconds_since_last_frame() > 0.8
            elif cap.fps() < 0.3 and el > 2.0:
                stalled = True

            if stalled and (now - last_cap_recover) > 2.0:
                cap_recover_count += 1
                last_cap_recover = now
                print(f'[AI v5] WARN: capture stalled, restarting session #{cap_recover_count}')
                try:
                    cap.stop()
                except Exception as e:
                    print(f'[AI v5] WARN: cap.stop failed: {e}')
                try:
                    if _USE_MUTTER:
                        cap = _MutterCapture(crop=(CL, CT, CR, CB), rgb=True)
                    else:
                        cap = PipeWireCapture(crop=(CL, CT, CR, CB), rgb=True)
                    cap.start()
                    time.sleep(0.15)
                except Exception as e:
                    print(f'[AI v5] WARN: cap restart failed: {e}')

            time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        sh(f'{_xdotool_env_prefix()} xdotool mouseup 1')
        cap.stop()
        # Final screenshot disabled (portal_screenshot causes screen flash)
        # portal_screenshot('/dev/shm/ai_v5_final.png')
        el = time.time() - start
        print(f'[AI v5] Done! {dec} decisions, {mv} moves in {el:.1f}s')
        print(f'[AI v5] Rate: {dec/el:.1f} dec/s, {mv/el:.1f} mv/s, capture fps: {cap.fps():.1f}')


if __name__ == '__main__':
    main()
