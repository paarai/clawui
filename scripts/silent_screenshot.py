#!/usr/bin/env python3
"""Silent screenshot via XDG Desktop Portal - no flash/flicker.

Uses org.freedesktop.portal.Screenshot which captures through
the compositor without any visual indicator.
"""

import os
import time
import urllib.parse

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib


def portal_screenshot(output_path=None, timeout_ms=3000):
    """Take a screenshot via XDG Desktop Portal (no flash).
    
    Returns: path to saved PNG, or None on failure.
    Typical latency: 400-600ms.
    """
    os.environ.setdefault(
        'DBUS_SESSION_BUS_ADDRESS',
        f'unix:path=/run/user/{os.getuid()}/bus'
    )
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    
    result = [None]
    loop = GLib.MainLoop()
    
    def on_response(conn, sender, path, iface, signal, params):
        response, results = params
        if response == 0:
            uri = results.get('uri', '')
            if uri:
                result[0] = urllib.parse.unquote(uri.replace('file://', ''))
        loop.quit()
    
    bus.signal_subscribe(
        None, 'org.freedesktop.portal.Request', 'Response',
        None, None, Gio.DBusSignalFlags.NONE, on_response
    )
    
    bus.call_sync(
        'org.freedesktop.portal.Desktop',
        '/org/freedesktop/portal/desktop',
        'org.freedesktop.portal.Screenshot',
        'Screenshot',
        GLib.Variant('(sa{sv})', ('', {'interactive': GLib.Variant('b', False)})),
        GLib.VariantType('(o)'),
        Gio.DBusCallFlags.NONE, timeout_ms
    )
    
    GLib.timeout_add(timeout_ms, loop.quit)
    loop.run()
    
    if result[0] and output_path:
        import shutil
        shutil.move(result[0], output_path)
        return output_path
    
    return result[0]


def benchmark(rounds=5):
    """Benchmark portal screenshot speed."""
    times = []
    for i in range(rounds):
        t0 = time.time()
        path = portal_screenshot(f'/tmp/portal_bench_{i}.png')
        t1 = time.time()
        ms = (t1 - t0) * 1000
        times.append(ms)
        print(f'  Round {i+1}: {ms:.0f}ms -> {path}')
    
    avg = sum(times) / len(times)
    print(f'\nAvg: {avg:.0f}ms over {rounds} rounds')
    return avg


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'bench':
        benchmark()
    else:
        out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/portal_screenshot.png'
        t0 = time.time()
        path = portal_screenshot(out)
        print(f'{path} ({(time.time()-t0)*1000:.0f}ms)')
