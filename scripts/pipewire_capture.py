#!/usr/bin/env python3
"""PipeWire streaming screen capture via XDG Desktop Portal + GStreamer.

Usage:
  python3 pipewire_capture.py bench

Notes:
- First run will show a portal picker dialog (Select screen/window). User must confirm.
- Requires GNOME Wayland + xdg-desktop-portal + PipeWire + GStreamer pipewiresrc.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import threading
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gio, GLib, Gst


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SC_IFACE = "org.freedesktop.portal.ScreenCast"
REQ_IFACE = "org.freedesktop.portal.Request"


@dataclass
class _PortalReply:
    response: int
    results: dict
    done: bool = True


class _PortalScreenCast:
    def __init__(self) -> None:
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.sender = self.bus.get_unique_name()  # e.g. :1.123
        self.sender_path = self.sender.replace(":", "_").replace(".", "_")
        self.session_handle: Optional[str] = None

    def _request_path(self, token: str) -> str:
        return f"/org/freedesktop/portal/desktop/request/{self.sender_path}/{token}"

    def _wait_request(self, req_path: str, timeout_ms: int = 30000) -> _PortalReply:
        out = {"done": False, "resp": 2, "results": {}}
        loop = GLib.MainLoop()

        def _on_resp(_conn, _sender, _path, _iface, _signal, params):
            response, results = params
            out["done"] = True
            out["resp"] = int(response)
            out["results"] = dict(results) if results is not None else {}
            loop.quit()

        def _on_resp_any(_conn, _sender, _path, _iface, _signal, params):
            if _path != req_path:
                return
            _on_resp(_conn, _sender, _path, _iface, _signal, params)

        sub_id = self.bus.signal_subscribe(
            None,
            REQ_IFACE,
            "Response",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            _on_resp_any,
        )
        try:
            GLib.timeout_add(timeout_ms, loop.quit)
            loop.run()
        finally:
            self.bus.signal_unsubscribe(sub_id)

        return _PortalReply(response=out["resp"], results=out["results"], done=out["done"])

    def _call_request(
        self,
        method: str,
        signature: str,
        args: tuple,
        timeout_ms: int = 30000,
    ) -> _PortalReply:
        token = f"tok_{uuid.uuid4().hex[:12]}"
        req_path = self._request_path(token)

        # Ensure handle_token exists in options
        # All ScreenCast async methods take ... a{sv} options as last argument.
        args = list(args)
        options = dict(args[-1])
        options["handle_token"] = GLib.Variant("s", token)
        args[-1] = options

        out = {"done": False, "resp": 2, "results": {}}
        expected_paths = {req_path}
        loop = GLib.MainLoop()

        def _on_resp(_conn, _sender, _path, _iface, _signal, params):
            if _path not in expected_paths:
                return
            response, results = params
            out["done"] = True
            out["resp"] = int(response)
            out["results"] = dict(results) if results is not None else {}
            loop.quit()

        sub_id = self.bus.signal_subscribe(
            None,
            REQ_IFACE,
            "Response",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            _on_resp,
        )
        try:
            req_obj = self.bus.call_sync(
                PORTAL_BUS,
                PORTAL_PATH,
                SC_IFACE,
                method,
                GLib.Variant(signature, tuple(args)),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                timeout_ms,
                None,
            )
            try:
                expected_paths.add(req_obj.unpack()[0])
            except Exception:
                pass
            GLib.timeout_add(timeout_ms, loop.quit)
            loop.run()
        finally:
            self.bus.signal_unsubscribe(sub_id)

        return _PortalReply(response=out["resp"], results=out["results"], done=out["done"])

    def start(self) -> Tuple[int, int]:
        # 1) CreateSession
        sess_token = f"sess_{uuid.uuid4().hex[:12]}"
        reply = self._call_request(
            "CreateSession",
            "(a{sv})",
            (
                {
                    "session_handle_token": GLib.Variant("s", sess_token),
                },
            ),
        )
        if not reply.done:
            raise RuntimeError("CreateSession timed out waiting for portal response")
        if reply.response != 0:
            raise RuntimeError(f"CreateSession failed: response={reply.response}, results={reply.results}")

        self.session_handle = str(reply.results.get("session_handle", ""))
        if not self.session_handle:
            raise RuntimeError("CreateSession returned empty session_handle")

        # 2) SelectSources (MONITOR = 1, cursor_mode embedded=2)
        reply = self._call_request(
            "SelectSources",
            "(oa{sv})",
            (
                self.session_handle,
                {
                    "types": GLib.Variant("u", 1),
                    "multiple": GLib.Variant("b", False),
                    "cursor_mode": GLib.Variant("u", 2),
                },
            ),
        )
        if reply.response != 0:
            raise RuntimeError(f"SelectSources failed: response={reply.response}")

        # 3) Start (portal picker may appear here)
        reply = self._call_request(
            "Start",
            "(osa{sv})",
            (
                self.session_handle,
                "",  # parent window
                {},
            ),
            timeout_ms=120000,
        )
        if not reply.done:
            raise RuntimeError("Start timed out waiting for portal response (did you confirm picker dialog?)")
        if reply.response != 0:
            raise RuntimeError(
                f"Start failed/cancelled: response={reply.response} (0=success,1=cancelled)"
            )

        streams = reply.results.get("streams")
        if not streams:
            raise RuntimeError("Start returned no streams")

        # streams type is usually a(ssv?) or a(ua{sv}); robustly parse first node id
        node_id = None
        try:
            first = streams[0]
            if isinstance(first, (tuple, list)) and len(first) >= 1:
                node_id = int(first[0])
        except Exception:
            node_id = None
        if node_id is None:
            raise RuntimeError(f"Could not parse stream node id from: {streams!r}")

        # 4) OpenPipeWireRemote -> unix fd
        ret = self.bus.call_sync(
            PORTAL_BUS,
            PORTAL_PATH,
            SC_IFACE,
            "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (self.session_handle, {})),
            GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE,
            30000,
            None,
        )
        fd_index = int(ret.unpack()[0])
        fd_list = ret.get_handle_list()
        fd = fd_list.get(fd_index)
        if fd < 0:
            raise RuntimeError("OpenPipeWireRemote returned invalid fd")

        return fd, node_id


class PipeWireCapture:
    def __init__(self, crop: Optional[Tuple[int, int, int, int]] = None, rgb: bool = True):
        self.crop = crop
        self.rgb = rgb

        self._portal = _PortalScreenCast()
        self._pipeline: Optional[Gst.Pipeline] = None
        self._appsink = None

        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._running = False

        self._frames = 0
        self._start_ts = 0.0
        self._last_frame_ts = 0.0
        self._avg_interval_ms = 0.0

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
            arr = np.frombuffer(mapinfo.data, dtype=np.uint8)
            arr = arr.reshape((height, width, 3)).copy()
            if not self.rgb:
                arr = arr[:, :, ::-1]  # RGB->BGR

            if self.crop is not None:
                l, t, r, b = self.crop
                arr = arr[t:b, l:r, :]

            now = time.time()
            with self._lock:
                self._latest = arr
                self._frames += 1
                if self._last_frame_ts > 0:
                    dt = (now - self._last_frame_ts) * 1000.0
                    if self._avg_interval_ms == 0:
                        self._avg_interval_ms = dt
                    else:
                        self._avg_interval_ms = self._avg_interval_ms * 0.9 + dt * 0.1
                self._last_frame_ts = now
        finally:
            buf.unmap(mapinfo)

        return Gst.FlowReturn.OK

    def start(self):
        if self._running:
            return

        Gst.init(None)
        fd, node_id = self._portal.start()

        fmt = "RGB"
        desc = (
            f"pipewiresrc fd={fd} path={node_id} do-timestamp=true ! "
            f"videoconvert ! video/x-raw,format={fmt} ! "
            "appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false"
        )
        pipeline = Gst.parse_launch(desc)
        sink = pipeline.get_by_name("sink")
        sink.connect("new-sample", self._on_sample)

        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("Failed to set GStreamer pipeline to PLAYING")

        self._pipeline = pipeline
        self._appsink = sink
        self._running = True
        self._start_ts = time.time()

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest is None:
                return None
            return self._latest.copy()

    def fps(self) -> float:
        with self._lock:
            if self._start_ts <= 0:
                return 0.0
            dt = max(1e-6, time.time() - self._start_ts)
            return self._frames / dt

    def avg_interval_ms(self) -> float:
        with self._lock:
            return self._avg_interval_ms

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
        self._pipeline = None
        self._appsink = None


def _bench(seconds: int = 12):
    cap = PipeWireCapture(rgb=True)
    print("[bench] starting portal screencast (first run needs user confirmation)...")
    t0 = time.time()
    cap.start()
    print(f"[bench] started in {(time.time()-t0)*1000:.0f} ms")

    last_cnt = 0
    try:
        t_start = time.time()
        while time.time() - t_start < seconds:
            time.sleep(1.0)
            frame = cap.get_frame()
            has = frame is not None
            f = cap.fps()
            iv = cap.avg_interval_ms()
            print(f"[bench] fps={f:.2f}, avg_frame_interval={iv:.1f} ms, frame_ready={has}")
        print(f"[bench] FINAL fps={cap.fps():.2f}, avg_interval={cap.avg_interval_ms():.1f} ms")
    finally:
        cap.stop()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "bench":
        sec = int(sys.argv[2]) if len(sys.argv) >= 3 else 12
        _bench(sec)
    else:
        print("Usage: python3 pipewire_capture.py bench [seconds]")
