#!/usr/bin/env python3
"""Tests for `clawui status` runtime health command."""

import json
import subprocess
import sys


def _run_cmd(args):
    return subprocess.run(
        [sys.executable, "-m", "clawui", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_status_json_shape():
    proc = _run_cmd(["status", "--json"])
    assert proc.returncode == 0, proc.stderr

    data = json.loads(proc.stdout)
    assert "version" in data
    assert "display" in data
    assert "backends" in data

    backends = data["backends"]
    for key in ["atspi", "x11", "cdp", "marionette", "screenshot", "ocr"]:
        assert key in backends
        assert "available" in backends[key]


def test_status_text_smoke():
    proc = _run_cmd(["status"])
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "Runtime Status" in out
    assert "AT-SPI" in out
    assert "CDP" in out
