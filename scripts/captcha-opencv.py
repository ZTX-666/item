#!/usr/bin/env python3
"""
Captcha Gap Detector - OpenCV Template Matching + Canny Edge Fallback

Usage:
  python captcha-opencv.py --bg <background.png> [--slider <slider_piece.png>]

Output (JSON to stdout):
  {"gap_x": 152, "confidence": 0.87, "method": "template", "image_width": 310}
  {"gap_x": 160, "confidence": 0.65, "method": "canny", "image_width": 310}
  {"error": "description"}
"""

import sys
import json
import argparse
import os
import numpy as np
import cv2

def imread_unicode(path, flags=cv2.IMREAD_GRAYSCALE):
    """Read image supporting non-ASCII (Chinese) paths on Windows."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, flags)
    except Exception:
        return None

def find_gap_template(bg_path, slider_path):
    """
    Template matching: use slider piece to find gap in background.
    This is the gold standard from GitHub research.
    """
    # Read images in grayscale (unicode-safe)
    bg = imread_unicode(bg_path, cv2.IMREAD_GRAYSCALE)
    slider = imread_unicode(slider_path, cv2.IMREAD_GRAYSCALE)

    if bg is None:
        return {"error": f"Cannot read background: {bg_path}"}
    if slider is None:
        return {"error": f"Cannot read slider: {slider_path}"}

    bg_h, bg_w = bg.shape
    sl_h, sl_w = slider.shape

    # Edge detection on both images (improves matching significantly)
    bg_edges = cv2.Canny(bg, 100, 200)
    slider_edges = cv2.Canny(slider, 100, 200)

    # Template matching on edge images
    result = cv2.matchTemplate(bg_edges, slider_edges, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    gap_x = max_loc[0]
    confidence = max_val

    # Also try matching on raw grayscale as secondary signal
    result_raw = cv2.matchTemplate(bg, slider, cv2.TM_CCOEFF_NORMED)
    _, max_val_raw, _, max_loc_raw = cv2.minMaxLoc(result_raw)

    # If raw matching disagrees significantly, use the one with higher confidence
    if abs(max_loc_raw[0] - gap_x) > 10 and max_val_raw > max_val:
        gap_x = max_loc_raw[0]
        confidence = max_val_raw

    return {
        "gap_x": int(gap_x),
        "confidence": round(float(confidence), 4),
        "method": "template",
        "image_width": int(bg_w),
        "image_height": int(bg_h),
        "slider_width": int(sl_w),
        "secondary_x": int(max_loc_raw[0]),
        "secondary_confidence": round(float(max_val_raw), 4),
    }


def find_gap_canny(bg_path):
    """
    Canny edge detection fallback: find gap outline in background image.
    Used when slider piece image is not available.
    """
    bg = imread_unicode(bg_path, cv2.IMREAD_GRAYSCALE)
    if bg is None:
        return {"error": f"Cannot read background: {bg_path}"}

    bg_h, bg_w = bg.shape

    # Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(bg, (5, 5), 0)

    # Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate to connect broken edges
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # The gap creates a distinctive contour - look for it
    # Gap is typically in the right 60% of the image, has a reasonable size
    best_x = None
    best_score = 0
    min_x = int(bg_w * 0.15)  # Gap is rarely at the very left

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        # Gap contour should be:
        # - Not at the very left (x > 15% of width)
        # - Reasonable size (20-100px wide, 20-100px tall)
        # - Roughly square-ish (aspect ratio 0.5-2.0)
        if x < min_x:
            continue
        if w < 15 or w > 120:
            continue
        if h < 15 or h > 120:
            continue
        aspect = w / h if h > 0 else 0
        if aspect < 0.4 or aspect > 2.5:
            continue

        # Score: contour area (bigger = more likely to be the gap)
        area = cv2.contourArea(contour)
        if area > best_score:
            best_score = area
            best_x = x

    # Fallback: column-wise edge density analysis
    if best_x is None:
        col_sums = np.sum(edges, axis=0)
        # Smooth
        kernel_size = 11
        smooth = np.convolve(col_sums, np.ones(kernel_size) / kernel_size, mode='same')
        # Find the peak in the right portion
        search_start = int(bg_w * 0.2)
        search_end = int(bg_w * 0.85)
        best_x = search_start + np.argmax(smooth[search_start:search_end])
        best_score = smooth[best_x]

    # Confidence heuristic: normalize score
    confidence = min(best_score / 5000.0, 0.95) if best_score > 0 else 0.1

    return {
        "gap_x": int(best_x),
        "confidence": round(float(confidence), 4),
        "method": "canny",
        "image_width": int(bg_w),
        "image_height": int(bg_h),
    }


def main():
    parser = argparse.ArgumentParser(description="Captcha gap detector using OpenCV")
    parser.add_argument("--bg", required=True, help="Background image path")
    parser.add_argument("--slider", help="Slider piece image path (enables template matching)")
    args = parser.parse_args()

    if not os.path.exists(args.bg):
        print(json.dumps({"error": f"Background file not found: {args.bg}"}))
        sys.exit(1)

    if args.slider and os.path.exists(args.slider):
        result = find_gap_template(args.bg, args.slider)
    else:
        result = find_gap_canny(args.bg)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
