"""Annotated screenshot - overlay numbered labels on interactive UI elements.

Takes a screenshot and detects interactive elements via AT-SPI (desktop apps)
or CDP (browser pages), then draws numbered red labels on each element.
The agent can then use click_by_index to click any labeled element.
"""

import base64
import io
import json
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont


@dataclass
class LabeledElement:
    """An interactive element with a numeric label."""
    index: int
    label: str  # display text (e.g., "1: Save")
    role: str
    name: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    source: str  # "atspi" or "cdp"
    selector: str | None = None  # CSS selector for CDP elements
    confidence: float = 0.5  # P3-D: grounding confidence (0-1)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "role": self.role,
            "name": self.name,
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "center": [self.center_x, self.center_y],
            "source": self.source,
            "selector": self.selector,
            "confidence": self.confidence,
        }


# Module-level cache for last annotated result
_last_elements: list[LabeledElement] = []


def get_last_elements() -> list[LabeledElement]:
    """Get the element list from the most recent annotated screenshot."""
    return _last_elements


INTERACTIVE_ROLES = {
    "push button", "toggle button", "radio button", "check box",
    "menu item", "menu", "combo box", "text", "password text",
    "entry", "link", "tab", "tool bar item", "spin button",
    "slider", "page tab", "tree item", "list item", "icon",
}


def _collect_atspi_elements() -> list[dict]:
    """Collect interactive elements from AT-SPI tree."""
    try:
        from .atspi_helper import find_elements
        results = []
        for role in INTERACTIVE_ROLES:
            try:
                els = find_elements(role=role)
                for el in els:
                    if el.width < 5 or el.height < 5:
                        continue
                    if "visible" not in el.states and "showing" not in el.states:
                        continue
                    results.append({
                        "role": el.role,
                        "name": el.name or "",
                        "x": el.x, "y": el.y,
                        "width": el.width, "height": el.height,
                        "source": "atspi",
                    })
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"[annotated] AT-SPI collection failed: {e}")
        return []


def _collect_cdp_elements() -> list[dict]:
    """Collect interactive elements from CDP (browser)."""
    try:
        from .cdp_helper import get_or_create_cdp_client
        client = get_or_create_cdp_client()
        if not client or not client.is_available():
            return []

        js = """
        (function() {
            const sels = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="checkbox"], [role="radio"], [onclick], [tabindex]';
            const els = document.querySelectorAll(sels);
            const results = [];
            for (const el of els) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5) continue;
                if (rect.bottom < 0 || rect.right < 0) continue;
                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute('role') || tag;
                const name = el.textContent?.trim()?.substring(0, 50) || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.value || '';
                let selector = '';
                if (el.id) selector = '#' + el.id;
                else if (el.name) selector = tag + '[name="' + el.name + '"]';
                else selector = tag + ':nth-of-type(' + (Array.from(el.parentNode?.children || []).filter(c => c.tagName === el.tagName).indexOf(el) + 1) + ')';
                results.push({role, name, x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height), selector, source: 'cdp'});
            }
            return JSON.stringify(results.slice(0, 150));
        })()
        """
        resp = client.send_command("Runtime.evaluate", {"expression": js, "returnByValue": True})
        value = resp.get("result", {}).get("result", {}).get("value", "[]")
        if isinstance(value, str):
            return json.loads(value)
        return value or []
    except Exception as e:
        print(f"[annotated] CDP collection failed: {e}")
        return []


def _dedup_elements(elements: list[dict]) -> list[dict]:
    """Remove duplicate elements that overlap significantly."""
    seen = []
    for el in elements:
        cx = el["x"] + el["width"] // 2
        cy = el["y"] + el["height"] // 2
        duplicate = False
        for s in seen:
            sx = s["x"] + s["width"] // 2
            sy = s["y"] + s["height"] // 2
            if abs(cx - sx) < 10 and abs(cy - sy) < 10:
                duplicate = True
                break
        if not duplicate:
            seen.append(el)
    return seen


def _iou(box_a, box_b):
    """Compute Intersection over Union between two (x, y, w, h) boxes."""
    ax1, ay1 = box_a[0], box_a[1]
    ax2, ay2 = ax1 + box_a[2], ay1 + box_a[3]
    bx1, by1 = box_b[0], box_b[1]
    bx2, by2 = bx1 + box_b[2], by1 + box_b[3]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = box_a[2] * box_a[3]
    area_b = box_b[2] * box_b[3]
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _ocr_cross_validate(elements: list[dict], img_b64: str) -> list[dict]:
    """P3-D: Cross-validate element list with OCR text boxes.

    Elements whose bounding box overlaps an OCR text box (IoU > 0.1 or center
    within element) get a confidence boost.  Returns elements with updated
    'confidence' field.
    """
    try:
        from .ocr_tool import ocr_extract_lines
    except ImportError:
        return elements  # OCR not available

    try:
        ocr_lines = ocr_extract_lines(img_b64, threshold=0.2)
    except Exception:
        return elements

    if not ocr_lines:
        return elements

    # Convert OCR bboxes to (x, y, w, h)
    ocr_boxes = []
    for line in ocr_lines:
        bbox = line.get("bbox", [])
        text = line.get("text", "")
        if len(bbox) >= 4:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            x, y = int(min(xs)), int(min(ys))
            w, h = int(max(xs) - x), int(max(ys) - y)
            ocr_boxes.append({"x": x, "y": y, "w": w, "h": h, "text": text})

    for el in elements:
        el_box = (el["x"], el["y"], el["width"], el["height"])
        el_cx = el["x"] + el["width"] // 2
        el_cy = el["y"] + el["height"] // 2
        best_iou = 0.0
        name_match = False

        for ocr in ocr_boxes:
            ocr_box = (ocr["x"], ocr["y"], ocr["w"], ocr["h"])
            iou = _iou(el_box, ocr_box)
            if iou > best_iou:
                best_iou = iou

            # Also check if OCR center is within element bbox
            ocr_cx = ocr["x"] + ocr["w"] // 2
            ocr_cy = ocr["y"] + ocr["h"] // 2
            if (el["x"] <= ocr_cx <= el["x"] + el["width"]
                    and el["y"] <= ocr_cy <= el["y"] + el["height"]):
                best_iou = max(best_iou, 0.15)

            # Check name match
            if el.get("name") and ocr["text"]:
                if el["name"].lower() in ocr["text"].lower() or ocr["text"].lower() in el["name"].lower():
                    name_match = True

        # Compute confidence: base 0.5, +0.3 for spatial overlap, +0.2 for name match
        conf = 0.5
        if best_iou > 0.1:
            conf += min(best_iou * 1.5, 0.3)
        if name_match:
            conf += 0.2
        el["confidence"] = round(min(conf, 1.0), 2)

    return elements


def annotated_screenshot(sources: str = "auto") -> tuple[str, list[LabeledElement]]:
    """
    Take a screenshot and overlay numbered labels on interactive elements.

    Args:
        sources: "atspi", "cdp", "both", or "auto" (try both, prefer whichever has results)

    Returns:
        (base64_png, list_of_labeled_elements)
    """
    global _last_elements
    from .screenshot import take_screenshot

    # Collect elements
    elements = []
    if sources in ("atspi", "both", "auto"):
        elements.extend(_collect_atspi_elements())
    if sources in ("cdp", "both", "auto"):
        elements.extend(_collect_cdp_elements())

    elements = _dedup_elements(elements)

    # Take screenshot
    img_b64 = take_screenshot(scale=False)

    # P3-D: OCR cross-validation (Mixture of Grounding)
    elements = _ocr_cross_validate(elements, img_b64)

    img = Image.open(io.BytesIO(base64.b64decode(img_b64)))
    draw = ImageDraw.Draw(img)

    # Try to get a font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 14)
        except Exception:
            font = ImageFont.load_default()

    labeled = []
    for i, el in enumerate(elements):
        idx = i + 1
        x, y, w, h = el["x"], el["y"], el["width"], el["height"]
        cx, cy = x + w // 2, y + h // 2
        name = el.get("name", "")
        short_name = name[:20] if name else el["role"]

        le = LabeledElement(
            index=idx,
            label=f"{idx}: {short_name}",
            role=el["role"],
            name=name,
            x=x, y=y, width=w, height=h,
            center_x=cx, center_y=cy,
            source=el.get("source", "unknown"),
            selector=el.get("selector"),
            confidence=el.get("confidence", 0.5),
        )
        labeled.append(le)

        # Draw red rectangle around element
        draw.rectangle([x, y, x + w, y + h], outline="red", width=2)

        # Draw label background + text
        label_text = str(idx)
        bbox = draw.textbbox((0, 0), label_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        lx, ly = max(0, x - 2), max(0, y - th - 4)
        draw.rectangle([lx, ly, lx + tw + 6, ly + th + 4], fill="red")
        draw.text((lx + 3, ly + 2), label_text, fill="white", font=font)

    _last_elements = labeled

    # Encode result
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result_b64 = base64.b64encode(buf.getvalue()).decode()

    return result_b64, labeled
