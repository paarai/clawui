"""
Recording and playback of GUI automation actions.
Records a sequence of actions (tool calls with parameters) to a JSON file.
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional


class Recorder:
    """Records automation actions."""

    def __init__(self, filepath: str = None):
        self.filepath = filepath or f"recordings/recording_{int(time.time())}.json"
        self.actions: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def record(self, tool_name: str, input_data: Dict[str, Any], result: Any = None):
        """Record a single action."""
        entry = {
            "timestamp": time.time() - self.start_time,
            "tool": tool_name,
            "input": input_data,
            "result": result
        }
        self.actions.append(entry)

    def save(self):
        """Save recording to file."""
        import os
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, 'w') as f:
            json.dump({
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "duration": time.time() - self.start_time,
                    "count": len(self.actions)
                },
                "actions": self.actions
            }, f, indent=2)
        return self.filepath

    @classmethod
    def load(cls, filepath: str) -> "Recorder":
        """Load recording from file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        rec = cls(filepath)
        rec.actions = data.get("actions", [])
        rec.start_time = 0  # not used after load
        return rec


class Player:
    """Plays back recorded actions through a given agent."""

    def __init__(self, recorder: Recorder, execute_func):
        self.recorder = recorder
        self.execute = execute_func  # function(tool_name, input_data) -> result

    def play(self, delay: float = 0.5, dry_run: bool = False) -> List[Any]:
        """Play back all actions with optional delay between."""
        results = []
        for action in self.recorder.actions:
            if dry_run:
                print(f"[DRY] {action['tool']}: {action['input']}")
                results.append(None)
            else:
                res = self.execute(action["tool"], action["input"])
                results.append(res)
                print(f"Executed {action['tool']}")
            time.sleep(delay)
        return results


# Convenience wrappers for OpenClaw agent integration
_recorder_instance: Optional[Recorder] = None

def start_recording(filepath: str = None) -> Recorder:
    """Start a new recording session."""
    global _recorder_instance
    _recorder_instance = Recorder(filepath)
    return _recorder_instance

def record_action(tool_name: str, input_data: Dict[str, Any], result: Any = None):
    """Record an action if recording is active."""
    if _recorder_instance is not None:
        _recorder_instance.record(tool_name, input_data, result)

def stop_recording() -> Optional[str]:
    """Stop recording and save file."""
    global _recorder_instance
    if _recorder_instance is not None:
        path = _recorder_instance.save()
        _recorder_instance = None
        return path
    return None

def play_recording(filepath: str, execute_func, delay: float = 0.5, dry_run: bool = False):
    """Playback a recording."""
    rec = Recorder.load(filepath)
    player = Player(rec, execute_func)
    return player.play(delay=delay, dry_run=dry_run)


def export_to_script(filepath: str, output: str = None, delay: float = 0.5) -> str:
    """Export a recording JSON file to a standalone Python script.

    The generated script uses only clawui public API (no agent framework needed).
    """
    rec = Recorder.load(filepath)
    if not output:
        output = filepath.replace('.json', '.py')

    # Map tool names to their Python import + call
    _TOOL_MAP = {
        # Desktop actions
        "click": ("from clawui.actions import click", "click({x}, {y})"),
        "double_click": ("from clawui.actions import double_click", "double_click({x}, {y})"),
        "right_click": ("from clawui.actions import right_click", "right_click({x}, {y})"),
        "type_text": ("from clawui.actions import type_text", "type_text({text!r})"),
        "press_key": ("from clawui.actions import press_key", "press_key({key!r})"),
        "scroll": ("from clawui.actions import scroll", "scroll(direction={direction!r}, amount={amount})"),
        "screenshot": ("from clawui.screenshot import take_screenshot", "take_screenshot()"),
        # CDP browser actions
        "cdp_navigate": (None, "cdp.navigate({url!r})"),
        "cdp_click": (None, "cdp.click({selector!r})"),
        "cdp_type": (None, "cdp.type_text({selector!r}, {text!r})"),
        "cdp_click_at": (None, "cdp.dispatch_mouse({x}, {y}, 'click')"),
        "cdp_execute_js": (None, "cdp.evaluate({code!r})"),
        "cdp_screenshot": (None, "cdp.screenshot()"),
        "cdp_get_text": (None, "cdp.evaluate('document.querySelector({selector!r}).textContent')"),
        "cdp_scroll": (None, "cdp.evaluate('window.scrollBy(0, {amount})')"),
    }

    imports = set()
    imports.add("import time")
    lines = []
    needs_cdp = False

    for action in rec.actions:
        tool = action["tool"]
        inp = action.get("input", {})

        if tool in _TOOL_MAP:
            imp, call_tpl = _TOOL_MAP[tool]
            if imp:
                imports.add(imp)
            if tool.startswith("cdp_"):
                needs_cdp = True
            try:
                call = call_tpl.format(**inp)
            except (KeyError, IndexError):
                # Fallback: generic call
                call = f"# {tool}({inp})"
            lines.append(call)
        else:
            # Unknown tool: emit as comment
            lines.append(f"# TODO: {tool}({json.dumps(inp, ensure_ascii=False)})")

        lines.append(f"time.sleep({delay})")

    # Build script
    script_lines = [
        '#!/usr/bin/env python3',
        f'"""Auto-generated ClawUI script from {filepath}"""',
        '',
    ]
    script_lines.extend(sorted(imports))
    if needs_cdp:
        script_lines.append("from clawui.cdp_helper import CDPClient")
    script_lines.append('')
    script_lines.append('')
    script_lines.append('def main():')
    if needs_cdp:
        script_lines.append('    cdp = CDPClient()')
        script_lines.append('    cdp.connect()')
        script_lines.append('')
    if not lines:
        script_lines.append('    pass  # empty recording')
    else:
        for line in lines:
            script_lines.append(f'    {line}')
    if needs_cdp:
        script_lines.append('')
        script_lines.append('    cdp.close()')
    script_lines.append('')
    script_lines.append('')
    script_lines.append('if __name__ == "__main__":')
    script_lines.append('    main()')
    script_lines.append('')

    import os
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
    with open(output, 'w') as f:
        f.write('\n'.join(script_lines))
    os.chmod(output, 0o755)
    return output
