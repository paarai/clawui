"""OCR-based UI text detection tool for ClawUI.

Primary: RapidOCR (fastest, ~150ms)
Fallback: Tesseract (slower but universal)
"""

import os
import sys
from typing import List, Dict, Any

# Add current module path
sys.path.insert(0, os.path.dirname(__file__))


# Initialize OCR engine at module import (singleton)
try:
    from rapidocr_onnxruntime import RapidOCR
    _ocr_engine = RapidOCR()
    _has_rapidocr = True
except ImportError:
    _ocr_engine = None
    _has_rapidocr = False

def ocr_find_text(image_data: str, text: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
    """
    Find occurrences of `text` in screenshot via OCR.
    Returns list of matches: [{text, bbox: [[x1,y1],[x2,y2],...], center: [x,y], score}]
    Uses global engine; threshold 0.3 by default for better recall.
    """
    # Try RapidOCR first if available
    if _has_rapidocr and _ocr_engine is not None:
        try:
            # image_data is base64 string without data: prefix
            if image_data.startswith('data:'):
                import base64
                header, b64 = image_data.split(',', 1)
                image_bytes = base64.b64decode(b64)
            else:
                import base64
                image_bytes = base64.b64decode(image_data)
            
            result, _ = _ocr_engine(image_bytes)
            matches = []
            if result:
                for box, ocr_text, score in result:
                    if text.lower() in ocr_text.lower() and score >= threshold:
                        # Compute center
                        xs = [p[0] for p in box]
                        ys = [p[1] for p in box]
                        center = [int(sum(xs)/len(xs)), int(sum(ys)/len(ys))]
                        matches.append({
                            "text": ocr_text,
                            "bbox": box,
                            "center": center,
                            "score": float(score)
                        })
            return matches
        except Exception as e:
            print(f"[ocr_find_text] RapidOCR failed: {e}")
            # Fall through to Tesseract if RapidOCR errors out
            pass
    
    # Fallback to Tesseract
    try:
        # Ensure image_bytes is defined for Tesseract fallback
        if 'image_bytes' not in locals():
            if image_data.startswith('data:'):
                import base64
                header, b64 = image_data.split(',', 1)
                image_bytes = base64.b64decode(b64)
            else:
                import base64
                image_bytes = base64.b64decode(image_data)

        import subprocess
        import tempfile
        # Save image to temp file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        
        # Run tesseract with TSV output
        cmd = ['tesseract', tmp_path, 'stdout', '--psm', '11', 'tsv']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        os.unlink(tmp_path)
        
        if result.returncode != 0:
            raise RuntimeError(f"Tesseract error: {result.stderr}")
        
        lines = result.stdout.strip().split('\n')
        matches = []
        import csv
        reader = csv.DictReader(lines, delimiter='\t')
        for row in reader:
            if 'text' in row and 'left' in row:
                if text.lower() in row['text'].lower():
                    x = int(row['left']) + int(row['width'])/2
                    y = int(row['top']) + int(row['height'])/2
                    matches.append({
                        "text": row['text'],
                        "bbox": [[int(row['left']), int(row['top'])],
                                 [int(row['left'])+int(row['width']), int(row['top'])],
                                 [int(row['left'])+int(row['width']), int(row['top'])+int(row['height'])],
                                 [int(row['left']), int(row['top'])+int(row['height'])]],
                        "center": [int(x), int(y)],
                        "score": 0.5  # Tesseract has no confidence
                    })
        return matches
    except Exception as e:
        print(f"[ocr_find_text] Tesseract failed: {e}")
        return []


# Standalone test
if __name__ == "__main__":
    # Take a screenshot and search for text
    from src.screenshot import take_screenshot
    img = take_screenshot()
    if img:
        import base64
        b64 = base64.b64decode(img) if isinstance(img, str) else img
        matches = ocr_find_text(base64.b64encode(b64).decode(), "新建")
        print(f"Found {len(matches)} matches for '新建':")
        for m in matches:
            print(f"  {m['text']} at {m['center']} (score {m['score']:.2f})")
