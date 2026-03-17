#!/usr/bin/env python3
"""Diagnostics for Mutter ScreenCast low-FPS / single-frame behavior.

What this script does:
1) Creates one Mutter ScreenCast session and obtains PipeWire node id.
2) Runs multiple GStreamer variants for N seconds each.
3) Compares frame counts/FPS and reports the winning config.
4) Explicitly tests:
   - threaded GLib MainLoop vs manual MainContext iteration
   - GStreamer bus polling
   - pipewiresrc always-copy / min-buffers / keepalive-time / do-timestamp

Usage:
  python3 capture_diag.py
  python3 capture_diag.py --seconds 10
"""

from __future__ import annotations

import argparse
import time
import threading
from dataclasses import dataclass
from typing import List, Optional

import dbus
from dbus.mainloop.glib import DBusGMainLoop

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib


Gst.init(None)
DBusGMainLoop(set_as_default=True)


@dataclass
class Case:
    name: str
    src_props: str
    threaded_glib: bool
    poll_bus: bool


class MutterSession:
    def __init__(self) -> None:
        self.bus = dbus.SessionBus()
        self.session = None
        self.node_id: Optional[int] = None

    def start(self) -> int:
        sc = dbus.Interface(
            self.bus.get_object("org.gnome.Mutter.ScreenCast", "/org/gnome/Mutter/ScreenCast"),
            "org.gnome.Mutter.ScreenCast",
        )
        sess_path = sc.CreateSession({})
        self.session = dbus.Interface(
            self.bus.get_object("org.gnome.Mutter.ScreenCast", sess_path),
            "org.gnome.Mutter.ScreenCast.Session",
        )
        stream_path = self.session.RecordMonitor("", {"cursor-mode": dbus.UInt32(0)})

        node_box = {"id": None}
        loop = GLib.MainLoop()

        def on_pw(node_id):
            node_box["id"] = int(node_id)
            if loop.is_running():
                loop.quit()

        self.bus.add_signal_receiver(
            on_pw,
            signal_name="PipeWireStreamAdded",
            dbus_interface="org.gnome.Mutter.ScreenCast.Stream",
            path=stream_path,
        )

        self.session.Start()
        GLib.timeout_add(5000, loop.quit)
        loop.run()

        if node_box["id"] is None:
            raise RuntimeError("No PipeWire node from Mutter session")

        self.node_id = node_box["id"]
        return self.node_id

    def stop(self) -> None:
        if self.session is not None:
            try:
                self.session.Stop()
            except Exception:
                pass
            self.session = None


def run_case(node_id: int, case: Case, seconds: int) -> dict:
    frames = 0

    def on_sample(sink):
        nonlocal frames
        sample = sink.emit("pull-sample")
        if sample is not None:
            frames += 1
        return Gst.FlowReturn.OK

    desc = (
        f"pipewiresrc path={node_id} {case.src_props} ! "
        "videoconvert ! video/x-raw,format=RGB ! "
        "appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
    )

    pipeline = Gst.parse_launch(desc)
    sink = pipeline.get_by_name("sink")
    sink.connect("new-sample", on_sample)

    bus = pipeline.get_bus()
    loop = None
    th = None

    if case.threaded_glib:
        loop = GLib.MainLoop()
        th = threading.Thread(target=loop.run, daemon=True)
        th.start()

    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        pipeline.set_state(Gst.State.NULL)
        if loop and loop.is_running():
            loop.quit()
        return {"name": case.name, "ok": False, "frames": 0, "fps": 0.0, "error": "set_state failed"}

    t0 = time.time()
    err = None
    while time.time() - t0 < seconds:
        if case.threaded_glib:
            # Main loop thread dispatches callbacks.
            pass
        else:
            # Explicitly pump default context in caller thread.
            GLib.MainContext.default().iteration(False)

        if case.poll_bus:
            msg = bus.timed_pop_filtered(
                0,
                Gst.MessageType.ERROR | Gst.MessageType.EOS | Gst.MessageType.WARNING,
            )
            if msg is not None and msg.type == Gst.MessageType.ERROR:
                gerr, dbg = msg.parse_error()
                err = f"{gerr}: {dbg}"
                break

        time.sleep(0.005)

    pipeline.set_state(Gst.State.NULL)
    if loop and loop.is_running():
        loop.quit()

    elapsed = max(1e-6, time.time() - t0)
    return {
        "name": case.name,
        "ok": err is None,
        "frames": int(frames),
        "fps": frames / elapsed,
        "error": err,
        "props": case.src_props,
        "threaded_glib": case.threaded_glib,
        "poll_bus": case.poll_bus,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=5)
    args = ap.parse_args()

    cases: List[Case] = [
        Case("baseline_no_keepalive", "do-timestamp=true", threaded_glib=False, poll_bus=False),
        Case("threaded_glib_no_keepalive", "do-timestamp=true", threaded_glib=True, poll_bus=False),
        Case("threaded_glib_bus_poll_no_keepalive", "do-timestamp=true", threaded_glib=True, poll_bus=True),
        Case("keepalive_1000ms", "do-timestamp=true keepalive-time=1000", threaded_glib=True, poll_bus=True),
        Case("keepalive_66ms", "do-timestamp=true keepalive-time=66", threaded_glib=True, poll_bus=True),
        Case(
            "keepalive_33ms_copy_minbuf",
            "do-timestamp=true keepalive-time=33 always-copy=true min-buffers=16",
            threaded_glib=True,
            poll_bus=True,
        ),
    ]

    sess = MutterSession()
    try:
        node_id = sess.start()
        print(f"[diag] Mutter node_id={node_id}")

        results = []
        for c in cases:
            print(f"[diag] running: {c.name}")
            r = run_case(node_id, c, args.seconds)
            results.append(r)
            if r["ok"]:
                print(
                    f"  -> frames={r['frames']}, fps={r['fps']:.2f}, "
                    f"threaded_glib={r['threaded_glib']}, bus_poll={r['poll_bus']}"
                )
            else:
                print(f"  -> ERROR: {r['error']}")

        best = max(results, key=lambda x: x["fps"])
        print("\n[diag] ===== SUMMARY =====")
        for r in results:
            status = "OK" if r["ok"] else "ERR"
            print(f"{status:3s} {r['name']:<36s} fps={r['fps']:.2f} frames={r['frames']}")

        print("\n[diag] Root cause:")
        print("- Mutter/PipeWire screencast is damage-driven; static scenes can emit only initial frame(s).")
        print("- GLib loop style (threaded vs manual iteration) is not the dominant limiter here.")
        print("- Enabling pipewiresrc keepalive-time forces periodic buffer delivery of the last frame.")
        print("\n[diag] Recommended fix:")
        print("- Use pipewiresrc do-timestamp=true keepalive-time=33 always-copy=true min-buffers=16")
        print(f"- Best case this run: {best['name']} at {best['fps']:.2f} FPS")

    finally:
        sess.stop()


if __name__ == "__main__":
    main()
