#!/usr/bin/env python3
"""Mutter ScreenCast capture: zero-dialog, no-flash screen capture for GNOME Wayland.

Uses Mutter's native D-Bus ScreenCast API + GStreamer appsink.
No portal dialogs, no screenshot flash, no recording indicator issues.
"""

import os, time, threading, logging
from typing import Optional, Tuple
import numpy as np

import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst

import dbus
from dbus.mainloop.glib import DBusGMainLoop

logger = logging.getLogger("mutter_capture")

Gst.init(None)
DBusGMainLoop(set_as_default=True)


class MutterCapture:
    """High-FPS screen capture via Mutter ScreenCast + GStreamer."""

    def __init__(
        self,
        crop: Optional[Tuple[int, int, int, int]] = None,
        rgb: bool = True,
    ):
        self.crop = crop  # (left, top, right, bottom)
        self.rgb = rgb
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._running = False
        self._frames = 0
        self._start_ts = 0.0
        self._last_frame_ts = 0.0
        self._pipeline = None
        self._session = None
        self._bus = None
        self._loop = None
        self._loop_thread = None

    def _on_sample(self, sink):
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK
        buf = sample.get_buffer()
        caps = sample.get_caps()
        s = caps.get_structure(0)
        w, h = s.get_value("width"), s.get_value("height")
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            arr = np.frombuffer(mapinfo.data, dtype=np.uint8).reshape(h, w, 3).copy()
            if not self.rgb:
                arr = arr[:, :, ::-1]
            if self.crop:
                l, t, r, b = self.crop
                arr = arr[t:b, l:r]
            now = time.time()
            with self._lock:
                self._latest = arr
                self._frames += 1
                self._last_frame_ts = now
        finally:
            buf.unmap(mapinfo)
        return Gst.FlowReturn.OK

    def start(self):
        if self._running:
            return

        self._bus = dbus.SessionBus()

        # Create ScreenCast session
        sc = dbus.Interface(
            self._bus.get_object('org.gnome.Mutter.ScreenCast', '/org/gnome/Mutter/ScreenCast'),
            'org.gnome.Mutter.ScreenCast')
        session_path = sc.CreateSession({})
        self._session = dbus.Interface(
            self._bus.get_object('org.gnome.Mutter.ScreenCast', session_path),
            'org.gnome.Mutter.ScreenCast.Session')

        stream_path = self._session.RecordMonitor('', {'cursor-mode': dbus.UInt32(0)})

        # Wait for PipeWire node
        node_id = [None]
        def on_pw(nid):
            node_id[0] = int(nid)
            if self._loop and self._loop.is_running():
                self._loop.quit()

        self._bus.add_signal_receiver(on_pw,
            signal_name='PipeWireStreamAdded',
            dbus_interface='org.gnome.Mutter.ScreenCast.Stream',
            path=stream_path)

        self._session.Start()

        # Run GLib loop briefly to receive the signal
        self._loop = GLib.MainLoop()
        GLib.timeout_add(3000, self._loop.quit)
        self._loop.run()

        if node_id[0] is None:
            raise RuntimeError("No PipeWire node received from Mutter ScreenCast")

        logger.info(f"[MutterCapture] node_id={node_id[0]}")

        # GStreamer pipeline
        # Mutter screencast is damage-driven on many setups (few/no new buffers when scene is static).
        # keepalive-time forces periodic resend of last frame so downstream gets steady frame cadence.
        desc = (
            f"pipewiresrc path={node_id[0]} do-timestamp=true keepalive-time=33 "
            f"always-copy=true min-buffers=16 ! "
            f"videoconvert ! video/x-raw,format=RGB ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=false"
        )
        self._pipeline = Gst.parse_launch(desc)
        self._appsink = self._pipeline.get_by_name("sink")
        self._appsink.connect("new-sample", self._on_sample)
        self._pipeline.set_state(Gst.State.PLAYING)

        # Background GLib loop for signal dispatch
        self._loop = GLib.MainLoop()
        self._loop_thread = threading.Thread(target=self._loop.run, daemon=True)
        self._loop_thread.start()

        self._running = True
        self._start_ts = time.time()
        with self._lock:
            self._last_frame_ts = 0.0
        logger.info("[MutterCapture] started (no dialog, no flash)")

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest.copy() if self._latest is not None else None

    def fps(self) -> float:
        with self._lock:
            dt = max(1e-6, time.time() - self._start_ts)
            return self._frames / dt

    def frames(self) -> int:
        with self._lock:
            return int(self._frames)

    def seconds_since_last_frame(self) -> float:
        with self._lock:
            if self._last_frame_ts <= 0:
                return float('inf')
            return max(0.0, time.time() - self._last_frame_ts)

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
        self._pipeline = None
        if self._loop and self._loop.is_running():
            self._loop.quit()
        try:
            if self._session:
                self._session.Stop()
        except Exception:
            pass
        self._session = None
        logger.info("[MutterCapture] stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *a):
        self.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from PIL import Image
    cap = MutterCapture(crop=(80, 60, 380, 560), rgb=True)
    cap.start()
    time.sleep(1)
    for i in range(10):
        f = cap.get_frame()
        print(f"Frame {i}: {f.shape if f is not None else None}, fps={cap.fps():.1f}")
        if f is not None and i == 5:
            Image.fromarray(f).save("/dev/shm/_mc_test.png")
        time.sleep(0.3)
    cap.stop()
