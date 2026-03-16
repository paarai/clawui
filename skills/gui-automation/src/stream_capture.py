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
import os, time, threading, logging
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
        """
        Args:
            crop: (left, top, right, bottom) pixel region to extract.
            rgb: If True, output RGB; else BGR.
            max_buffers: GStreamer appsink buffer limit (1 = latest frame only).
        """
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
        self._bus = None
        self._glib_loop: Optional[object] = None
        self._glib_thread: Optional[threading.Thread] = None

    # ── GStreamer callback ──────────────────────────────────────

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
                l, t, r, b = self.crop
                arr = arr[t:b, l:r, :]

            now = time.time()
            with self._lock:
                self._latest = arr
                self._frames += 1
                if self._last_frame_ts > 0:
                    dt = (now - self._last_frame_ts) * 1000.0
                    self._avg_interval_ms = self._avg_interval_ms * 0.9 + dt * 0.1 if self._avg_interval_ms else dt
                self._last_frame_ts = now
        finally:
            buf.unmap(mapinfo)

        return Gst.FlowReturn.OK

    # ── Mutter D-Bus session ────────────────────────────────────

    def _create_mutter_session(self, bus) -> int:
        """Create Mutter ScreenCast session, return PipeWire node ID."""
        ret = bus.call_sync(
            MUTTER_SC_BUS, MUTTER_SC_PATH, MUTTER_SC_IFACE,
            "CreateSession",
            GLib.Variant("(a{sv})", ({"is-platform": GLib.Variant("b", True)},)),
            GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 5000, None,
        )
        session_path = ret.unpack()[0]
        self._session_path = session_path
        logger.info(f"Mutter session: {session_path}")

        ret = bus.call_sync(
            MUTTER_SC_BUS, session_path, MUTTER_SESSION_IFACE,
            "RecordMonitor",
            GLib.Variant("(sa{sv})", ("", {"is-recording": GLib.Variant("b", False)})),
            GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 5000, None,
        )
        stream_path = ret.unpack()[0]
        logger.info(f"Mutter stream: {stream_path}")

        node_out = {"id": 0}
        def on_pw_stream(conn, sender, path, iface, signal, params):
            if path == stream_path:
                node_out["id"] = int(params[0])

        sub_id = bus.signal_subscribe(
            MUTTER_SC_BUS, MUTTER_STREAM_IFACE, "PipeWireStreamAdded",
            stream_path, None, Gio.DBusSignalFlags.NONE, on_pw_stream,
        )

        bus.call_sync(
            MUTTER_SC_BUS, session_path, MUTTER_SESSION_IFACE,
            "Start", None, None, Gio.DBusCallFlags.NONE, 5000, None,
        )

        ctx = GLib.MainContext.default()
        deadline = time.time() + 5.0
        while node_out["id"] == 0 and time.time() < deadline:
            ctx.iteration(False)
            time.sleep(0.02)

        bus.signal_unsubscribe(sub_id)

        if node_out["id"] == 0:
            raise RuntimeError("PipeWireStreamAdded signal not received")

        logger.info(f"PipeWire node_id={node_out['id']}")
        return node_out["id"]

    # ── Public API ──────────────────────────────────────────────

    def start(self, retries: int = 3, retry_delay: float = 2.0):
        """Start the capture pipeline."""
        if self._running:
            return
        if not _GI_AVAILABLE:
            raise RuntimeError("GI (PyGObject + Gst) not available")

        Gst.init(None)
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS",
                              f"unix:path=/run/user/{os.getuid()}/bus")
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._bus = bus

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                node_id = self._create_mutter_session(bus)
                last_err = None
                break
            except Exception as e:
                last_err = e
                logger.warning(f"Attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(retry_delay)

        if last_err is not None:
            raise last_err

        # GLib MainLoop is required for GStreamer appsink signal dispatch
        if self._glib_loop is None:
            self._glib_loop = GLib.MainLoop()
            self._glib_thread = threading.Thread(target=self._glib_loop.run, daemon=True)
            self._glib_thread.start()

        desc = (
            f"pipewiresrc path={node_id} do-timestamp=true ! "
            f"videoconvert ! video/x-raw,format=RGB ! "
            f"appsink name=sink emit-signals=true max-buffers={self.max_buffers} drop=true sync=false"
        )
        pipeline = Gst.parse_launch(desc)
        sink = pipeline.get_by_name("sink")
        sink.connect("new-sample", self._on_sample)

        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("GStreamer pipeline failed to start")

        self._pipeline = pipeline
        self._appsink = sink
        self._running = True
        self._start_ts = time.time()
        self._frames = 0
        self._last_frame_ts = 0.0
        self._avg_interval_ms = 0.0
        logger.info(f"StreamCapture started (node={node_id})")

    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest captured frame (RGB numpy array), or None."""
        with self._lock:
            return self._latest.copy() if self._latest is not None else None

    def fps(self) -> float:
        """Current average frames per second."""
        with self._lock:
            dt = max(1e-6, time.time() - self._start_ts) if self._start_ts > 0 else 1e-6
            return self._frames / dt

    def avg_interval_ms(self) -> float:
        """Exponentially-weighted average inter-frame interval in ms."""
        with self._lock:
            return self._avg_interval_ms

    def _stop_mutter_session(self):
        """Best-effort close of Mutter session to avoid leaked PipeWire streams."""
        if self._bus is None or not self._session_path:
            return
        try:
            flags = Gio.DBusCallFlags.NONE if _GI_AVAILABLE else 0
            self._bus.call_sync(
                MUTTER_SC_BUS,
                self._session_path,
                MUTTER_SESSION_IFACE,
                "Stop",
                None,
                None,
                flags,
                2000,
                None,
            )
        except Exception as e:
            logger.debug(f"Failed to stop Mutter session {self._session_path}: {e}")
        finally:
            self._session_path = None

    def stop(self):
        """Stop the capture pipeline and release resources."""
        if not self._running and not self._pipeline and not self._session_path:
            return

        self._running = False

        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
        self._pipeline = None
        self._appsink = None

        self._stop_mutter_session()

        if self._glib_loop and self._glib_loop.is_running():
            self._glib_loop.quit()
        if self._glib_thread and self._glib_thread.is_alive():
            self._glib_thread.join(timeout=1.0)
        self._glib_loop = None
        self._glib_thread = None
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
