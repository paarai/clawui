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
