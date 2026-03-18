#!/usr/bin/env python3
"""Plane game auto-player using ClawUI vision + mouse control.

Strategy:
- Stay in the bottom 30% of the game canvas
- Detect enemies and dodge them (move away from nearest threats)
- Detect and collect powerups (prioritize weapon/bomb)
- Maintain a weaving pattern to maximize bullet coverage
- The game auto-shoots, so we just need to position well
"""

import sys
import os
import time
import json
import base64
import math
import subprocess
from datetime import datetime

sys.path.insert(0, '/home/hung/.openclaw/workspace/skills/gui-automation')

from src.screenshot import take_screenshot
from src.actions import click, mouse_move, drag

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("WARNING: cv2 not available, using basic mode")

# ── Config ──
GAME_DURATION = 600  # 10 minutes
LOG_INTERVAL = 30    # log every 30 seconds
FRAME_DELAY = 0.08   # ~12 FPS decision rate
SAFE_ZONE_RATIO = 0.75  # stay in bottom 25% normally

# Stats tracking
stats = {
    "start_time": None,
    "scores": [],         # (timestamp, score)
    "deaths": 0,
    "max_score_seen": 0,
    "frames_processed": 0,
    "strategy_notes": [],
}


def detect_game_region(img):
    """Find the dark game canvas in the screenshot."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # The game canvas is the dark area (space background)
    # Look for a large dark rectangular region
    _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best = None
    best_area = 0
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        # Game canvas should be tall and narrow (phone simulator)
        if area > best_area and h > 300 and w > 150 and h > w * 1.2:
            best = (x, y, w, h)
            best_area = area
    
    return best


def detect_player(img, roi):
    """Detect the blue player aircraft."""
    x0, y0, w, h = roi
    crop = img[y0:y0+h, x0:x0+w]
    
    # Player is blue (#4488ff area)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # Blue hue range
    lower_blue = np.array([100, 100, 150])
    upper_blue = np.array([130, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # Find the largest blue cluster in the bottom half
    bottom_half = mask[h//2:, :]
    ys, xs = np.where(bottom_half > 0)
    if len(xs) < 10:
        # Try full image
        ys, xs = np.where(mask > 0)
        if len(xs) < 10:
            return None
    else:
        ys = ys + h // 2
    
    cx = int(np.mean(xs)) + x0
    cy = int(np.mean(ys)) + y0
    return (cx, cy)


def detect_enemies(img, roi):
    """Detect red/orange/purple enemy shapes."""
    x0, y0, w, h = roi
    crop = img[y0:y0+h, x0:x0+w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    
    enemies = []
    
    # Red enemies (#ff4444): H 0-10 or 170-180
    lower_red1 = np.array([0, 120, 120])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 120, 120])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
    
    # Orange enemies (#ff8800): H 10-25
    lower_orange = np.array([10, 120, 150])
    upper_orange = np.array([25, 255, 255])
    mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
    
    # Purple enemies (#cc44ff): H 140-160
    lower_purple = np.array([130, 80, 120])
    upper_purple = np.array([160, 255, 255])
    mask_purple = cv2.inRange(hsv, lower_purple, upper_purple)
    
    combined = mask_red | mask_orange | mask_purple
    
    # Cluster detection
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if area < 50:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"]) + x0
        cy = int(M["m01"] / M["m00"]) + y0
        size = math.sqrt(area)
        enemies.append((cx, cy, size))
    
    return enemies


def detect_powerups(img, roi):
    """Detect bright powerup items (they tend to be bright colored dots)."""
    x0, y0, w, h = roi
    crop = img[y0:y0+h, x0:x0+w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    
    powerups = []
    
    # Powerups are bright saturated colors, often green/cyan/yellow
    # Green (weapon): H 40-80
    lower_green = np.array([40, 100, 150])
    upper_green = np.array([80, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    # Cyan (shield): H 80-100  
    lower_cyan = np.array([80, 100, 150])
    upper_cyan = np.array([100, 255, 255])
    mask_cyan = cv2.inRange(hsv, lower_cyan, upper_cyan)
    
    # Yellow (life/bomb): H 25-40
    lower_yellow = np.array([25, 100, 180])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    combined = mask_green | mask_cyan | mask_yellow
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for c in contours:
        area = cv2.contourArea(c)
        if area < 30:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"]) + x0
        cy = int(M["m01"] / M["m00"]) + y0
        powerups.append((cx, cy))
    
    return powerups


def detect_enemy_bullets(img, roi):
    """Detect small bright pink/red enemy bullets."""
    x0, y0, w, h = roi
    crop = img[y0:y0+h, x0:x0+w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    
    # Enemy bullets are small bright pink dots (#ff3366)
    lower_pink = np.array([160, 100, 200])
    upper_pink = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower_pink, upper_pink)
    
    bullets = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if 5 < area < 200:  # small dots
            M = cv2.moments(c)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"]) + x0
            cy = int(M["m01"] / M["m00"]) + y0
            bullets.append((cx, cy))
    
    return bullets


def detect_score(img, roi):
    """Try to read score from top-right area using OCR or color detection."""
    # For now, we'll track game state visually
    # Score is displayed as white text in top area
    return None


def calculate_target(player_pos, enemies, powerups, bullets, roi):
    """Calculate optimal move target.
    
    Strategy:
    1. If powerup is close and safe to reach → go for it
    2. Otherwise dodge nearest threats
    3. Default: weave left-right at safe Y to maximize coverage
    """
    x0, y0, w, h = roi
    px, py = player_pos
    
    canvas_center_x = x0 + w // 2
    safe_y = y0 + int(h * SAFE_ZONE_RATIO)
    
    # Calculate danger from enemies + bullets
    threats = []
    for ex, ey, size in enemies:
        dist = math.sqrt((px - ex)**2 + (py - ey)**2)
        # Only care about enemies that are close or approaching
        if ey > y0 + h * 0.3:  # enemies in lower 70%
            danger = max(0, 200 - dist) * (1 + size/10)
            if dist < 120:
                danger *= 3  # very close = very dangerous
            threats.append((ex, ey, danger))
    
    for bx, by in bullets:
        dist = math.sqrt((px - bx)**2 + (py - by)**2)
        if dist < 150:
            threats.append((bx, by, max(0, 150 - dist) * 5))
    
    # Start with a base weaving position
    t = time.time()
    weave_x = canvas_center_x + math.sin(t * 1.5) * (w * 0.3)
    target_x = weave_x
    target_y = safe_y
    
    # Dodge: move away from threats
    if threats:
        # Weighted average threat direction
        dodge_x = 0
        dodge_y = 0
        total_weight = 0
        for tx, ty, danger in threats:
            if danger > 0:
                dx = px - tx
                dy = py - ty
                dist = max(1, math.sqrt(dx*dx + dy*dy))
                dodge_x += (dx / dist) * danger
                dodge_y += (dy / dist) * danger
                total_weight += danger
        
        if total_weight > 50:  # significant threat
            dodge_x /= total_weight
            dodge_y /= total_weight
            # Apply dodge as an offset
            dodge_strength = min(1.0, total_weight / 200)
            target_x = px + dodge_x * w * 0.4 * dodge_strength
            target_y = py + dodge_y * h * 0.2 * dodge_strength
    
    # Collect powerups if safe
    if powerups:
        nearest_pu = min(powerups, key=lambda p: math.sqrt((px-p[0])**2 + (py-p[1])**2))
        pu_dist = math.sqrt((px - nearest_pu[0])**2 + (py - nearest_pu[1])**2)
        
        # Check if path to powerup is safe
        path_safe = True
        for ex, ey, size in enemies:
            # Is enemy between us and powerup?
            mid_x = (px + nearest_pu[0]) / 2
            mid_y = (py + nearest_pu[1]) / 2
            if math.sqrt((mid_x - ex)**2 + (mid_y - ey)**2) < 80:
                path_safe = False
                break
        
        if pu_dist < 200 and path_safe:
            target_x = nearest_pu[0]
            target_y = nearest_pu[1]
    
    # Clamp to game bounds
    margin = 20
    target_x = max(x0 + margin, min(x0 + w - margin, target_x))
    target_y = max(y0 + h * 0.3, min(y0 + h - margin, target_y))
    
    return int(target_x), int(target_y)


def check_game_over(img, roi):
    """Detect game over screen (look for restart button or text)."""
    x0, y0, w, h = roi
    crop = img[y0:y0+h, x0:x0+w]
    
    # Game over typically shows white text in center
    # Check for a large white area in center region
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    center_region = gray[h//3:h*2//3, w//4:w*3//4]
    white_pixels = np.sum(center_region > 200)
    total_pixels = center_region.size
    
    # If more than 5% of center is bright white text, likely game over
    return white_pixels / total_pixels > 0.05


def restart_game(roi):
    """Click center of game to restart."""
    x0, y0, w, h = roi
    center_x = x0 + w // 2
    center_y = y0 + h // 2
    click(center_x, center_y)
    time.sleep(1)
    # Click again to dismiss any overlay
    click(center_x, center_y + 50)
    time.sleep(0.5)


def grab_frame():
    """Take screenshot and decode to numpy array."""
    b64 = take_screenshot()
    img_bytes = base64.b64decode(b64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


def main():
    print(f"=== Plane Game Bot Starting ===")
    print(f"Duration: {GAME_DURATION}s ({GAME_DURATION//60} min)")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    
    if not HAS_CV2:
        print("ERROR: OpenCV required for game automation")
        return
    
    stats["start_time"] = time.time()
    
    # Initial screenshot to find game region
    print("Detecting game canvas...")
    img = grab_frame()
    roi = detect_game_region(img)
    
    if roi is None:
        print("ERROR: Could not find game canvas! Taking fallback approach...")
        # Fallback: use approximate coordinates from the screenshot we saw earlier
        # Game canvas was roughly at x=170, y=95, w=225, h=525
        roi = (170, 95, 225, 525)
        print(f"Using fallback ROI: {roi}")
    else:
        print(f"Game canvas found: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")
    
    # Initial click to start/ensure game is active
    x0, y0, w, h = roi
    click(x0 + w//2, y0 + h - 100)
    time.sleep(0.5)
    
    game_over_count = 0
    last_log_time = time.time()
    last_player_pos = (x0 + w//2, y0 + int(h * SAFE_ZONE_RATIO))
    consecutive_no_player = 0
    
    print("Starting automation loop...")
    
    while time.time() - stats["start_time"] < GAME_DURATION:
        frame_start = time.time()
        stats["frames_processed"] += 1
        
        try:
            img = grab_frame()
            
            # Re-detect ROI occasionally (every 100 frames)
            if stats["frames_processed"] % 100 == 0:
                new_roi = detect_game_region(img)
                if new_roi:
                    roi = new_roi
                    x0, y0, w, h = roi
            
            # Check game over
            if check_game_over(img, roi):
                game_over_count += 1
                stats["deaths"] += 1
                elapsed = time.time() - stats["start_time"]
                print(f"[{elapsed:.0f}s] Game Over #{game_over_count}! Restarting...")
                restart_game(roi)
                consecutive_no_player = 0
                time.sleep(1)
                continue
            
            # Detect game objects
            player = detect_player(img, roi)
            enemies = detect_enemies(img, roi)
            powerups = detect_powerups(img, roi)
            bullets = detect_enemy_bullets(img, roi)
            
            if player is None:
                consecutive_no_player += 1
                if consecutive_no_player > 20:
                    # Might be game over or menu, try clicking
                    click(x0 + w//2, y0 + h//2)
                    time.sleep(0.5)
                    consecutive_no_player = 0
                # Use last known position
                player = last_player_pos
            else:
                consecutive_no_player = 0
                last_player_pos = player
            
            # Calculate optimal move
            target_x, target_y = calculate_target(player, enemies, powerups, bullets, roi)
            
            # Move mouse to target (smooth movement via drag)
            # Use mouse_move for smooth control
            mouse_move(target_x, target_y)
            
            # Periodic logging
            if time.time() - last_log_time > LOG_INTERVAL:
                elapsed = time.time() - stats["start_time"]
                remaining = GAME_DURATION - elapsed
                print(f"[{elapsed:.0f}s] Enemies: {len(enemies)}, Powerups: {len(powerups)}, "
                      f"Bullets: {len(bullets)}, Deaths: {stats['deaths']}, "
                      f"Player: ({player[0]}, {player[1]}), "
                      f"Remaining: {remaining:.0f}s")
                last_log_time = time.time()
            
        except Exception as e:
            print(f"Frame error: {e}")
            time.sleep(0.5)
        
        # Frame rate control
        elapsed_frame = time.time() - frame_start
        if elapsed_frame < FRAME_DELAY:
            time.sleep(FRAME_DELAY - elapsed_frame)
    
    # Final report
    total_time = time.time() - stats["start_time"]
    print(f"\n=== 10-Minute Test Complete ===")
    print(f"Total time: {total_time:.0f}s")
    print(f"Frames processed: {stats['frames_processed']}")
    print(f"Total deaths/restarts: {stats['deaths']}")
    print(f"Avg FPS: {stats['frames_processed']/total_time:.1f}")
    
    # Take final screenshot
    img = grab_frame()
    cv2.imwrite('/tmp/plane_game_final.png', img)
    print("Final screenshot saved to /tmp/plane_game_final.png")
    
    # Save stats
    stats["end_time"] = time.time()
    stats["total_frames"] = stats["frames_processed"]
    with open('/tmp/plane_game_stats.json', 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    print("Stats saved to /tmp/plane_game_stats.json")


if __name__ == "__main__":
    main()
