#!/usr/bin/env python3
"""E2E smoke test for WeChat mini-game in DevTools.

Checks:
1) Game canvas is running (OCR sees score/lives HUD text)
2) Game reaches game-over screen
3) Clicks "重新开始"
4) Game-over text disappears
"""

import subprocess
import tempfile
import time
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

OCR = RapidOCR()


def sh(cmd: str):
    return subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)


def screenshot(path: Path):
    sh(f"DISPLAY=:0 gnome-screenshot -f {path}")


def ocr_texts(path: Path):
    res, _ = OCR(str(path))
    if not res:
        return []
    return [str(t) for _, t, _ in res]


def ocr_find(path: Path, keyword: str):
    res, _ = OCR(str(path))
    if not res:
        return None
    for box, text, conf in res:
        t = str(text)
        if keyword in t:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            return {
                "text": t,
                "conf": float(conf),
                "center": (int(sum(xs) / len(xs)), int(sum(ys) / len(ys))),
            }
    return None


def main():
    out_dir = Path(tempfile.mkdtemp(prefix="minigame-e2e-"))
    print(f"[E2E] artifacts: {out_dir}")

    # Activate devtools
    sh("DISPLAY=:0 xdotool search --name '微信开发者工具' windowactivate --sync")

    # Step 1: verify running HUD
    p0 = out_dir / "step1_running.png"
    screenshot(p0)
    texts = "\n".join(ocr_texts(p0))
    print("[E2E] step1 OCR sample:", texts[:200].replace("\n", " | "))
    if ("分数" not in texts) and ("生命" not in texts):
        raise SystemExit("[E2E][FAIL] HUD not detected: expected 分数/生命")

    # Step 2: wait for game-over
    found_over = False
    over_path = out_dir / "step2_game_over.png"
    for _ in range(45):  # ~90s
        screenshot(over_path)
        txt = "\n".join(ocr_texts(over_path))
        if "游戏结束" in txt and "重新开始" in txt:
            found_over = True
            break
        time.sleep(2)

    if not found_over:
        raise SystemExit("[E2E][FAIL] game-over screen not detected within timeout")
    print("[E2E] game-over detected")

    # Step 3: click restart by OCR location
    hit = ocr_find(over_path, "重新开始")
    if not hit:
        raise SystemExit("[E2E][FAIL] restart button text not found")

    x, y = hit["center"]
    print(f"[E2E] click restart at ({x},{y}), conf={hit['conf']:.2f}")
    sh(f"DISPLAY=:0 xdotool mousemove {x} {y}; sleep 0.15; DISPLAY=:0 xdotool mousedown 1; sleep 0.05; DISPLAY=:0 xdotool mouseup 1")

    # Step 4: verify game-over disappears
    ok = False
    p4 = out_dir / "step4_after_restart.png"
    for _ in range(10):
        time.sleep(1)
        screenshot(p4)
        txt = "\n".join(ocr_texts(p4))
        if "游戏结束" not in txt:
            ok = True
            break

    if not ok:
        raise SystemExit("[E2E][FAIL] game-over text still present after restart click")

    print("[E2E][PASS] restart flow works")


if __name__ == "__main__":
    main()
