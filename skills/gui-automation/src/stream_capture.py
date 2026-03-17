"""High-FPS streaming screen capture via Mutter ScreenCast D-Bus API.

Provides a zero-dialog, low-latency capture backend for GNOME/Wayland.
Falls back gracefully to portal screenshot when Mutter is unavailable.

Usage:
    from clawui.stream_capture import StreamCapture
    cap = StreamCapture(crop=(left, top, right, bottom))
    cap.start()
    frame = cap.get_frame()  # numpy RGB array
    cap.stop()
"""

from __future__ import annotations
import os
import time
import threading
import logging
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger("clawui.stream_capture")

try:
    import gi
    gi.require_version("Gio", "2.0")
    gi.require_version("Gst", "1.0")
    from gi.repository import Gio, GLib, Gst
    _GI_AVAILABLE = True
except Exception:
    _GI_AVAILABLE = False

MUTTER_SC_BUS = "org.gnome.Mutter.ScreenCast"
MUTTER_SC_PATH = "/org/gnome/Mutter/ScreenCast"
MUTTER_SC_IFACE = "org.gnome.Mutter.ScreenCast"
MUTTER_SESSION_IFACE = "org.gnome.Mutter.ScreenCast.Session"
MUTTER_STREAM_IFACE = "org.gnome.Mutter.ScreenCast.Stream"


class StreamCapture:
    """High-FPS screen capture using Mutter's native ScreenCast + GStreamer."""

    def __init__(
        self,
        crop: Optional[Tuple[int, int, int, int]] = None,
        rgb: bool = True,
        max_buffers: int = 1,
    ):
        self.crop = crop
        self.rgb = rgb
        self.max_buffers = max_buffers

        self._pipeline = None
        self._appsink = None
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._running = False
        self._frames = 0
        self._start_ts = 0.0
        self._last_frame_ts = 0.0
        self._avg_interval_ms = 0.0
        self._session_path: Optional[str] = None
        self._stream_path: Optional[str] = None
        self._bus = None
        self._glib_loop = None
        self._glib_thread = None

    def _on_sample(self, sink):
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK

        buf = sample.get_buffer()
        caps = sample.get_caps()
        st = caps.get_structure(0)
        width = st.get_value("width")
        height = st.get_value("height")

        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK

        try:
            arr = np.frombuffer(mapinfo.data, dtype=np.uint8).reshape((height, width, 3)).copy()
            if not self.rgb:
                arr = arr[:, :, ::-1]
            if self.crop:
                left, t, r, b = self.crop
                arr = arr[t:b, left:r, :]

            now = time.time()
            with self._lock:
                self._latest = arr
                self._frames += 1
                if self._frames == 1 and self._start_ts > 0:
                    logger.info("First frame after %.1f ms", (now - self._start_ts) * 1000.0)
                if self._last_frame_ts > 0:
                    dt = (now - self._last_frame_ts) * 1000.0
                    self._avg_interval_ms = self._avg_interval_ms * 0.9 + dt * 0.1 if self._avg_interval_ms else dt
                self._last_frame_ts = now
        finally:
            buf.unmap(mapinfo)

        return Gst.FlowReturn.OK

    def _on_bus_message(self, bus, msg):
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            logger.error("Gst ERROR from %s: %s (%s)", msg.src.get_name() if msg.src else "?", err, dbg)
        elif t == Gst.MessageType.WARNING:
            warn, dbg = msg.parse_warning()
            logger.warning("Gst WARNING from %s: %s (%s)", msg.src.get_name() if msg.src else "?", warn, dbg)
        elif t == Gst.MessageType.EOS:
            logger.warning("Gst EOS received")
        elif t == Gst.MessageType.STATE_CHANGED and msg.src == self._pipeline:
            old, new, pending = msg.parse_state_changed()
            logger.info("Pipeline state: %s -> %s (pending=%s)", old.value_nick, new.value_nick, pending.value_nick)

    def _ensure_glib_loop(self):
        if self._glib_loop and self._glib_loop.is_running():
            return
        self._glib_loop = GLib.MainLoop()
        self._glib_thread = threading.Thread(target=self._glib_loop.run, daemon=True, name="stream-capture-glib")
        self._glib_thread.start()

    def _create_mutter_session(self, bus) -> int:
        ret = bus.call_sync(
            MUTTER_SC_BUS, MUTTER_SC_PATH, MUTTER_SC_IFACE,
            "CreateSession",
            GLib.Variant("(a{sv})", ({},)),
            GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 5000, None,
        )
        session_path = ret.unpack()[0]
        self._session_path = session_path
        logger.info("Mutter session: %s", session_path)

        ret = bus.call_sync(
            MUTTER_SC_BUS, session_path, MUTTER_SESSION_IFACE,
            "RecordMonitor",
            GLib.Variant("(sa{sv})", ("", {"cursor-mode": GLib.Variant("u", 0)})),
            GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 5000, None,
        )
        stream_path = ret.unpack()[0]
        self._stream_path = stream_path
        logger.info("Mutter stream: %s", stream_path)

        node_out = {"id": 0}

        wait_loop = GLib.MainLoop()

        def on_pw_stream(conn, sender, path, iface, signal, params):
            if path == stream_path:
                node_out["id"] = int(params[0])
                if wait_loop.is_running():
                    wait_loop.quit()

        sub_id = bus.signal_subscribe(
            MUTTER_SC_BUS, MUTTER_STREAM_IFACE, "PipeWireStreamAdded",
            stream_path, None, Gio.DBusSignalFlags.NONE, on_pw_stream,
        )

        bus.call_sync(
            MUTTER_SC_BUS, session_path, MUTTER_SESSION_IFACE,
            "Start", None, None, Gio.DBusCallFlags.NONE, 5000, None,
        )

        def on_timeout():
            if wait_loop.is_running():
                wait_loop.quit()
            return False

        timeout_id = GLib.timeout_add(5000, on_timeout)
        try:
            wait_loop.run()
        finally:
            try:
                GLib.source_remove(timeout_id)
            except Exception:
                pass
            bus.signal_unsubscribe(sub_id)

        if node_out["id"] == 0:
            raise RuntimeError("PipeWireStreamAdded signal not received")

        logger.info("PipeWire node_id=%s", node_out["id"])
        return node_out["id"]

    def start(self, retries: int = 3, retry_delay: float = 2.0):
        if self._running:
            return
        if not _GI_AVAILABLE:
            raise RuntimeError("GI (PyGObject + Gst) not available")

        Gst.init(None)
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                node_id = self._create_mutter_session(self._bus)
                last_err = None
                break
            except Exception as e:
                last_err = e
                logger.warning("Attempt %s/%s failed: %s", attempt, retries, e)
                if attempt < retries:
                    time.sleep(retry_delay)

        if last_err is not None:
            raise last_err

        desc = (
            f"pipewiresrc path={node_id} do-timestamp=true keepalive-time=33 "
            f"always-copy=true min-buffers=16 ! "
            f"videoconvert ! video/x-raw,format=RGB ! "
            f"appsink name=sink emit-signals=true max-buffers={self.max_buffers} drop=true sync=false"
        )
        logger.info("Pipeline desc: %s", desc)
        pipeline = Gst.parse_launch(desc)
        sink = pipeline.get_by_name("sink")
        sink.connect("new-sample", self._on_sample)

        gst_bus = pipeline.get_bus()
        gst_bus.add_signal_watch()
        gst_bus.connect("message", self._on_bus_message)

        self._pipeline = pipeline
        self._appsink = sink
        self._start_ts = time.time()
        self._ensure_glib_loop()

        ret = pipeline.set_state(Gst.State.PLAYING)
        logger.info("Pipeline set_state(PLAYING) => %s", ret.value_nick)
        if ret == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("GStreamer pipeline failed to start")

        self._running = True
        logger.info("StreamCapture started (node=%s)", node_id)

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest.copy() if self._latest is not None else None

    def fps(self) -> float:
        with self._lock:
            dt = max(1e-6, time.time() - self._start_ts) if self._start_ts > 0 else 1e-6
            return self._frames / dt

    def avg_interval_ms(self) -> float:
        with self._lock:
            return self._avg_interval_ms

    def stop(self):
        if not self._running:
            return
        self._running = False

        if self._pipeline:
            try:
                bus = self._pipeline.get_bus()
                if bus:
                    bus.remove_signal_watch()
            except Exception:
                pass
            self._pipeline.set_state(Gst.State.NULL)
        self._pipeline = None
        self._appsink = None

        if self._bus and self._session_path:
            try:
                self._bus.call_sync(
                    MUTTER_SC_BUS,
                    self._session_path,
                    MUTTER_SESSION_IFACE,
                    "Stop",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
            except Exception:
                pass

        if self._glib_loop and self._glib_loop.is_running():
            self._glib_loop.quit()

        self._session_path = None
        self._stream_path = None
        self._bus = None
        logger.info("StreamCapture stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
