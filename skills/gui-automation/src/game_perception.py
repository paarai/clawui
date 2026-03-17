"""Game perception: auto-detect ROI and detect threats/objects in frames.

Provides reusable building blocks for real-time visual game automation.

Supports two detection modes:
  - Color threshold (fast, hardcoded)
  - Adaptive contour (OpenCV, works across visual styles)

Usage:
    from clawui.game_perception import GamePerception
    gp = GamePerception(mode="adaptive")
    roi = gp.auto_detect_roi(screenshot)
    tracked, pickups = gp.detect_and_track(frame)
    best_x, best_y = gp.choose_action(tracked, pickups, player_x, player_y)
"""

from __future__ import annotations
import logging
from typing import List, Optional, Tuple
import numpy as np

logger = logging.getLogger("clawui.game_perception")

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

Pos = Tuple[int, int]
Vel = Tuple[float, float]
TrackedObj = Tuple[Pos, Vel]


# ── Clustering ──────────────────────────────────────────────────

def cluster_mask(mask: np.ndarray, min_px: int = 6) -> List[Pos]:
    """Find centroids of connected pixel clusters in a boolean mask."""
    ys, xs = np.where(mask)
    if len(xs) < min_px:
        return []
    groups = {}
    cell = 20
    for x, y in zip(xs, ys):
        k = (x // cell, y // cell)
        if k not in groups:
            groups[k] = [0, 0, 0]
        groups[k][0] += x
        groups[k][1] += y
        groups[k][2] += 1
    return [(s[0] // s[2], s[1] // s[2]) for s in groups.values() if s[2] >= min_px]


# ── Enemy Tracker ───────────────────────────────────────────────

class ObjectTracker:
    """Track objects across frames to estimate velocity (vx, vy)."""

    def __init__(self, match_distance: int = 60):
        self.prev: List[Pos] = []
        self.velocities: List[Vel] = []
        self.match_distance = match_distance

    def update(self, positions: List[Pos]) -> List[TrackedObj]:
        """Match new positions to previous frame, return [(pos, vel), ...]."""
        new_vels: List[Vel] = []
        matched = set()

        for ex, ey in positions:
            best_d = self.match_distance
            best_idx = -1
            for i, (px, py) in enumerate(self.prev):
                if i in matched:
                    continue
                d = abs(ex - px) + abs(ey - py)
                if d < best_d:
                    best_d = d
                    best_idx = i

            if best_idx >= 0:
                matched.add(best_idx)
                px, py = self.prev[best_idx]
                vx, vy = float(ex - px), float(ey - py)
                if best_idx < len(self.velocities):
                    ovx, ovy = self.velocities[best_idx]
                    vx = ovx * 0.5 + vx * 0.5
                    vy = ovy * 0.5 + vy * 0.5
                new_vels.append((vx, vy))
            else:
                new_vels.append((0.0, 3.0))  # default: moving downward

        self.prev = list(positions)
        self.velocities = new_vels
        return list(zip(positions, new_vels))

    def reset(self):
        self.prev = []
        self.velocities = []


# ── Game Perception ─────────────────────────────────────────────

class GamePerception:
    """Detect game area, threats, and pickups from screen frames."""

    def __init__(self, dark_threshold: float = 30.0, min_cluster_px: int = 6,
                 mode: str = "color"):
        """
        Args:
            mode: "color" (hardcoded thresholds), "adaptive" (OpenCV),
                  or "hybrid" (adaptive + color union for best recall).
        """
        self.dark_threshold = dark_threshold
        self.min_cluster_px = min_cluster_px
        self.mode = mode
        self.tracker = ObjectTracker()
        self._bg_model: Optional[np.ndarray] = None
        self._bg_frames = 0

    def auto_detect_roi(
        self,
        screenshot: np.ndarray,
        margin_top_pct: float = 0.08,
        margin_bottom_pct: float = 0.02,
        margin_lr_pct: float = 0.02,
        min_width: int = 150,
        min_height: int = 300,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Find the largest dark rectangular region in a screenshot.

        Returns (left, right, top, bottom) or None if not found.
        """
        gray = screenshot[:, :, :3].mean(axis=2) if screenshot.ndim == 3 else screenshot.astype(float)
        h, w = gray.shape

        # Find widest contiguous dark column range
        col_mean = gray.mean(axis=0)
        cl, cr = self._longest_run(col_mean < self.dark_threshold)

        if (cr - cl) < min_width:
            logger.warning(f"Dark column range too narrow: {cr - cl}")
            return None

        # Find tallest contiguous dark row range within those columns
        row_mean = gray[:, cl:cr].mean(axis=1)
        ct, cb = self._longest_run(row_mean < self.dark_threshold)

        # Apply margins
        margin_t = max(20, int((cb - ct) * margin_top_pct))
        margin_b = max(5, int((cb - ct) * margin_bottom_pct))
        margin_lr = max(3, int((cr - cl) * margin_lr_pct))
        ct += margin_t
        cb -= margin_b
        cl += margin_lr
        cr -= margin_lr

        if (cr - cl) < min_width or (cb - ct) < min_height:
            logger.warning(f"ROI too small after margins: {cr-cl}x{cb-ct}")
            return None

        logger.info(f"Auto-detected ROI: ({cl},{ct})-({cr},{cb}) = {cr-cl}x{cb-ct}")
        return (cl, cr, ct, cb)

    @staticmethod
    def _longest_run(mask: np.ndarray) -> Tuple[int, int]:
        """Find start, end of the longest contiguous True run."""
        best_s, best_e = 0, 0
        start = None
        for i in range(len(mask)):
            if mask[i]:
                if start is None:
                    start = i
            else:
                if start is not None:
                    if (i - start) > (best_e - best_s):
                        best_s, best_e = start, i
                    start = None
        if start is not None and (len(mask) - start) > (best_e - best_s):
            best_s, best_e = start, len(mask)
        return best_s, best_e

    def detect_objects(
        self,
        frame: np.ndarray,
    ) -> Tuple[List[Pos], List[Pos]]:
        """Detect threats and pickups in cropped RGB frame."""
        if self.mode == "adaptive" and _CV2:
            return self._detect_objects_adaptive(frame)
        if self.mode == "hybrid" and _CV2:
            t1, p1 = self._detect_objects_adaptive(frame)
            t2, p2 = self._detect_objects_color(frame)
            # union + dedup by grid cell
            def _dedup(points, cell=8):
                seen = set()
                out = []
                for x, y in points:
                    k = (int(x)//cell, int(y)//cell)
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append((int(x), int(y)))
                return out
            return _dedup(t1 + t2), _dedup(p1 + p2)
        return self._detect_objects_color(frame)

    def _detect_objects_color(self, frame: np.ndarray) -> Tuple[List[Pos], List[Pos]]:
        r = frame[:, :, 0].astype(np.int16)
        g = frame[:, :, 1].astype(np.int16)
        b = frame[:, :, 2].astype(np.int16)

        mp = self.min_cluster_px
        threats = cluster_mask((r > 150) & (g < 80) & (b < 80), mp)
        threats += cluster_mask((r > 200) & (g > 100) & (g < 180) & (b < 60), mp)
        threats += cluster_mask((r > 200) & (g > 200) & (b > 200), 3)
        threats += cluster_mask((r < 100) & (g > 180) & (b > 180), 3)
        pickups = cluster_mask((g > 130) & (r < 100) & (b < 100), mp + 4)
        return threats, pickups

    def _detect_objects_adaptive(self, frame: np.ndarray) -> Tuple[List[Pos], List[Pos]]:
        """Adaptive detector via background subtraction + contour filtering."""
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        if self._bg_model is None:
            self._bg_model = gray.astype(np.float32)
            self._bg_frames = 1
            return [], []

        cv2.accumulateWeighted(gray, self._bg_model, 0.03)
        bg = cv2.convertScaleAbs(self._bg_model)
        diff = cv2.absdiff(gray, bg)

        # moving bright objects (bullets/enemies) + saturated colored blobs
        _, motion = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)

        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        _, colorful = cv2.threshold(sat, 70, 255, cv2.THRESH_BINARY)
        _, bright = cv2.threshold(val, 180, 255, cv2.THRESH_BINARY)

        mask = cv2.bitwise_or(motion, colorful)
        mask = cv2.bitwise_or(mask, bright)
        mask = cv2.medianBlur(mask, 3)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        threats: List[Pos] = []
        pickups: List[Pos] = []

        for c in cnts:
            area = cv2.contourArea(c)
            if area < 4 or area > 1200:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            cx, cy = x + bw // 2, y + bh // 2
            patch = frame[max(0, y):min(h, y + bh), max(0, x):min(w, x + bw)]
            if patch.size == 0:
                continue
            mean = patch.reshape(-1, 3).mean(axis=0)
            r, g, b = mean
            if g > 120 and g > r + 20 and g > b + 20:
                pickups.append((cx, cy))
            else:
                threats.append((cx, cy))

        return threats, pickups

    def detect_and_track(
        self,
        frame: np.ndarray,
    ) -> Tuple[List[TrackedObj], List[Pos]]:
        """Detect objects and update tracker in one call."""
        threats, pickups = self.detect_objects(frame)
        tracked = self.tracker.update(threats)
        return tracked, pickups


# ── Risk Scorer ─────────────────────────────────────────────────

STRATEGY_PRESETS = {
    "conservative": {
        "threat_weight": 1.3,
        "pickup_weight": 0.8,
        "movement_cost": 0.10,
    },
    "balanced": {
        "threat_weight": 1.0,
        "pickup_weight": 1.2,
        "movement_cost": 0.08,
    },
    "aggressive": {
        "threat_weight": 0.7,
        "pickup_weight": 1.8,
        "movement_cost": 0.05,
    },
}


def score_position_xy(
    cx: int,
    cy: int,
    tracked_threats: List[TrackedObj],
    pickups: List[Pos],
    player_x: int,
    player_y: int,
    frame_h: int,
    frame_w: int,
    lookahead_frames: Tuple[int, ...] = (2, 4),
    strategy: str = "balanced",
) -> float:
    """Score candidate (x,y) using threat prediction + strategy profile."""
    cfg = STRATEGY_PRESETS.get(strategy, STRATEGY_PRESETS["balanced"])
    tw = cfg["threat_weight"]
    pw = cfg["pickup_weight"]
    mc = cfg["movement_cost"]

    s = 0.0
    for (ex, ey), (vx, vy) in tracked_threats:
        dx = abs(cx - ex)
        dy = abs(cy - ey)
        danger = max(0, ey - frame_h * 0.15) / (frame_h * 0.85)
        dist_pen = max(0.0, 120 - (dx * 0.9 + dy * 0.35))
        s -= dist_pen * (1 + danger * 4) * tw

        for i, frames_ahead in enumerate(lookahead_frames):
            weight = 0.65 / (i + 1)
            ex_f = ex + vx * frames_ahead
            ey_f = ey + vy * frames_ahead
            dx_f = abs(cx - ex_f)
            dy_f = abs(cy - ey_f)
            pen = max(0.0, 100 - (dx_f * 0.9 + dy_f * 0.35))
            s -= pen * weight * tw

    for px, py in pickups:
        d = abs(cx - px) * 0.9 + abs(cy - py) * 0.35
        s += max(0.0, 100 - d) * 0.8 * pw

    s -= abs(cx - frame_w // 2) * 0.03
    s -= (abs(cx - player_x) + 0.5 * abs(cy - player_y)) * mc
    return s


def choose_best_xy(
    tracked_threats: List[TrackedObj],
    pickups: List[Pos],
    player_x: int,
    player_y: int,
    frame_h: int,
    frame_w: int,
    n_x: int = 27,
    n_y: int = 5,
    strategy: str = "balanced",
) -> Tuple[int, int]:
    """Choose best (x,y). y-search is small; for x-only games keep y fixed."""
    best = (player_x, player_y)
    best_s = float("-inf")
    y_candidates = [player_y]
    if n_y > 1:
        span = max(6, int(frame_h * 0.03))
        y_candidates = [max(0, min(frame_h - 1, player_y + d)) for d in np.linspace(-span, span, n_y)]

    for ix in range(1, n_x + 1):
        cx = int(frame_w * ix / (n_x + 1))
        for cy in y_candidates:
            s = score_position_xy(cx, int(cy), tracked_threats, pickups, player_x, player_y, frame_h, frame_w, strategy=strategy)
            if s > best_s:
                best_s = s
                best = (cx, int(cy))
    return best


def choose_strategy(tracked_threats: List[TrackedObj], frame_h: int) -> str:
    """Auto-select strategy by current risk level."""
    if not tracked_threats:
        return "aggressive"
    near = 0
    for (ex, ey), _ in tracked_threats:
        if ey > frame_h * 0.6:
            near += 1
    if near >= 8:
        return "conservative"
    if near <= 2:
        return "aggressive"
    return "balanced"


def choose_best_x(
    tracked_threats: List[TrackedObj],
    pickups: List[Pos],
    player_x: int,
    frame_h: int,
    frame_w: int,
    n_candidates: int = 27,
    strategy: str = "balanced",
) -> int:
    if strategy == "auto":
        strategy = choose_strategy(tracked_threats, frame_h)
    x, _ = choose_best_xy(
        tracked_threats, pickups,
        player_x=player_x, player_y=int(frame_h * 0.88),
        frame_h=frame_h, frame_w=frame_w,
        n_x=n_candidates, n_y=1,
        strategy=strategy,
    )
    return x
