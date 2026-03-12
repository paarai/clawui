#!/usr/bin/env python3
"""
Apply retry enhancements to ClawUI agent.py

Improves reliability by adding automatic retry with exponential backoff to:
- find_element
- vision_find_element
- cdp_navigate
"""

import os

def main():
    # Locate agent.py in the ClawUI submodule
    base_dir = os.path.dirname(__file__)
    agent_path = os.path.join(base_dir, '..', 'ClawUI', 'skills', 'gui-automation', 'src', 'agent.py')
    agent_path = os.path.normpath(agent_path)

    if not os.path.exists(agent_path):
        print(f"Error: agent.py not found at {agent_path}")
        return 1

    with open(agent_path, 'r') as f:
        content = f.read()

    # Old blocks (exact match required)
    old_find_element = r'''        elif name == "find_element":
            elements = find_elements(
                role=input_data.get("role"),
                name=input_data.get("name"),
            )
            text = "\n".join(str(e) for e in elements[:20])
            return {"type": "text", "text": text or "(no elements found)"}
'''

    new_find_element = r'''        elif name == "find_element":
            max_attempts = int(os.getenv('CLAWUI_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_RETRY_DELAY', '0.5'))
            for attempt in range(max_attempts):
                try:
                    elements = find_elements(
                        role=input_data.get("role"),
                        name=input_data.get("name"),
                    )
                    if elements:
                        text = "\n".join(str(e) for e in elements[:20])
                        return {"type": "text", "text": text}
                    if attempt < max_attempts - 1:
                        print(f"[WARN] find_element: no elements (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": "(no elements found)"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] find_element error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Find element error after {max_attempts} attempts: {e}"}
'''

    old_vision = r'''        elif name == "vision_find_element":
            description = input_data.get("description", "").strip()
            if not description:
                return {"type": "text", "text": "Missing 'description' parameter"}
            try:
                from .vision_backend import VisionBackend
            except ImportError:
                return {"type": "text", "text": "VisionBackend not available"}
            img = take_screenshot()
            if not img:
                return {"type": "text", "text": "Failed to take screenshot"}
            vb = VisionBackend()
            prompt = f"Locate the UI element that matches: '{description}'. Return JSON with x, y (center coordinates), and confidence (0-1)."
            try:
                resp = vb.chat([
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                    ]}
                ], tools=[], system="You are a vision assistant that returns only JSON with x, y, confidence keys.")
                text = resp.get("text", "").strip()
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL) or re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1) if '```' in text else json_match.group(0)
                    data = json.loads(json_str)
                    x = data.get("x")
                    y = data.get("y")
                    conf = data.get("confidence", 0.5)
                    if x is not None and y is not None:
                        return {"type": "dict", "x": x, "y": y, "confidence": conf, "raw": text}
                return {"type": "text", "text": f"Vision response could not be parsed: {text}"}
            except Exception as e:
                return {"type": "text", "text": f"Vision error: {e}"}
'''

    new_vision = r'''        elif name == "vision_find_element":
            description = input_data.get("description", "").strip()
            if not description:
                return {"type": "text", "text": "Missing 'description' parameter"}
            try:
                from .vision_backend import VisionBackend
            except ImportError:
                return {"type": "text", "text": "VisionBackend not available"}
            img = take_screenshot()
            if not img:
                return {"type": "text", "text": "Failed to take screenshot"}
            max_attempts = int(os.getenv('CLAWUI_VISION_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_VISION_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    vb = VisionBackend()
                    prompt = f"Locate the UI element that matches: '{description}'. Return JSON with x, y (center coordinates), and confidence (0-1)."
                    resp = vb.chat([
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                        ]}
                    ], tools=[], system="You are a vision assistant that returns only JSON with x, y, confidence keys.")
                    text = resp.get("text", "").strip()
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL) or re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1) if '```' in text else json_match.group(0)
                        data = json.loads(json_str)
                        x = data.get("x")
                        y = data.get("y")
                        conf = data.get("confidence", 0.5)
                        if x is not None and y is not None:
                            return {"type": "dict", "x": x, "y": y, "confidence": conf, "raw": text}
                    # No valid coordinates produced - retry if possible
                    if attempt < max_attempts - 1:
                        print(f"[WARN] vision_find_element: no coordinates (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Vision response could not produce coordinates: {text}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] vision_find_element error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"Vision error after {max_attempts} attempts: {e}"}
'''

    old_cdp_navigate = r'''        elif name == "cdp_navigate":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available. Start Chromium with --remote-debugging-port=9222"}
            cdp.navigate(input_data["url"])
            time.sleep(2)
            title = cdp.get_page_title()
            return {"type": "text", "text": f"Navigated to {input_data['url']} - Title: {title}"}
'''

    new_cdp_navigate = r'''        elif name == "cdp_navigate":
            cdp = _get_cdp()
            if not cdp:
                return {"type": "text", "text": "CDP not available. Start Chromium with --remote-debugging-port=9222"}
            max_attempts = int(os.getenv('CLAWUI_CDP_RETRY_MAX', '3'))
            delay = float(os.getenv('CLAWUI_CDP_RETRY_DELAY', '1.0'))
            for attempt in range(max_attempts):
                try:
                    cdp.navigate(input_data["url"])
                    time.sleep(2)
                    title = cdp.get_page_title()
                    return {"type": "text", "text": f"Navigated to {input_data['url']} - Title: {title}"}
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"[WARN] cdp_navigate error: {e} (attempt {attempt+1}/{max_attempts}), retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return {"type": "text", "text": f"CDP navigate failed after {max_attempts} attempts: {e}"}
'''

    # Perform replacements
    replaced = False
    for old, new in [
        (old_find_element, new_find_element),
        (old_vision, new_vision),
        (old_cdp_navigate, new_cdp_navigate),
    ]:
        if old in content:
            content = content.replace(old, new)
            print(f"Applied one replacement.")
            replaced = True
        else:
            print(f"Warning: could not find expected block to replace (maybe already updated?).")

    if not replaced:
        print("No changes made.")
        return 0

    # Write back
    with open(agent_path, 'w') as f:
        f.write(content)

    print("Successfully applied retry improvements to agent.py")
    return 0

if __name__ == "__main__":
    exit(main())
