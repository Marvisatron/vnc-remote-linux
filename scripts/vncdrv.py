#!/usr/bin/env python3
"""vncdrv.py: drive a remote Linux desktop over the RFB protocol.

Speaks VNC directly with vncdotool instead of automating a local viewer, so
keystrokes are sent as keysyms (Unicode code points) and the server maps them
itself. That bypasses viewer-side keyboard-layout mangling entirely, needs no
OS-level input or screen-capture permission on any platform, and never steals
the pointer.

Subcommands
-----------
  capture OUT
  type TEXT
  key NAME [NAME ...]        NAME in lowercase: return enter tab esc space
                             ctrl-c  ctrl-u  shift-tab ...
  click X Y [BUTTON]
  dclick X Y
  move X Y
  run TEXT OUT [WAIT]        type, Return, sleep WAIT s, capture OUT
  script FILE                many ops over ONE connection

`script` file format, one op per line, `#` comments and blank lines ignored:

  capture /tmp/00.png
  type cd /opt/work
  key return
  wait 2
  capture /tmp/01.png

Password resolution order: --passfile PATH  ->  $VNC_PASSWORD  ->  default file
~/.vnc_agent_pass. The value is never echoed, never placed on a command line,
and never written to output.

Server: --server host::port  or  $VNC_SERVER.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

DEFAULT_PASSFILE = os.path.expanduser("~/.vnc_agent_pass")


def read_password(passfile: str) -> str:
    path = os.path.expanduser(passfile)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    env = os.environ.get("VNC_PASSWORD")
    if env:
        return env
    sys.exit(f"no VNC password: {path} missing and $VNC_PASSWORD unset")


def parse_server(argv_server: str | None) -> str:
    server = argv_server or os.environ.get("VNC_SERVER")
    if not server:
        sys.exit("no server: pass --server host::port or set $VNC_SERVER")
    return server


def connect(server: str, password: str, timeout: float):
    from vncdotool import api

    return api.connect(server, password=password, timeout=timeout)


# ---------------------------------------------------------------- primitives

def do_capture(client, out: str, settle: float = 0.0) -> None:
    if settle:
        time.sleep(settle)
    client.captureScreen(out)
    print(f"capture {out}")


def do_type(client, text: str, delay: float) -> None:
    for ch in text:
        client.keyPress(ch)
        time.sleep(delay)
    print(f"type {text!r}")


def do_key(client, names: list[str], delay: float) -> None:
    for name in names:
        client.keyPress(name)
        time.sleep(delay)
    print(f"key {names}")


def do_click(client, x: int, y: int, button: int, hover: float) -> None:
    client.mouseMove(x, y)
    time.sleep(hover)
    client.mousePress(button)
    print(f"click {x},{y} button={button}")


def do_dclick(client, x: int, y: int, hover: float, gap: float) -> None:
    client.mouseMove(x, y)
    time.sleep(hover)
    client.mousePress(1)
    time.sleep(gap)
    client.mousePress(1)
    print(f"dclick {x},{y}")


def do_move(client, x: int, y: int) -> None:
    client.mouseMove(x, y)
    print(f"move {x},{y}")


# ---------------------------------------------------------------- script mode

def run_script(client, path: str, delay: float, hover: float) -> None:
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        op = parts[0]
        arg = parts[1] if len(parts) > 1 else ""
        try:
            if op == "capture":
                do_capture(client, arg)
            elif op == "type":
                do_type(client, arg, delay)
            elif op == "typeline":
                do_type(client, arg, delay)
                time.sleep(0.15)
                client.keyPress("return")
                print("  + return")
            elif op == "key":
                do_key(client, arg.split(), delay)
            elif op == "click":
                x, y = (int(v) for v in arg.split()[:2])
                do_click(client, x, y, 1, hover)
            elif op == "dclick":
                x, y = (int(v) for v in arg.split()[:2])
                do_dclick(client, x, y, hover, 0.09)
            elif op == "move":
                x, y = (int(v) for v in arg.split()[:2])
                do_move(client, x, y)
            elif op == "wait":
                time.sleep(float(arg))
                print(f"wait {arg}")
            else:
                sys.exit(f"{path}:{lineno}: unknown op {op!r}")
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"{path}:{lineno}: {op} failed: {exc}")


# ---------------------------------------------------------------- entry point

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", help="host::port (double colon for explicit port)")
    ap.add_argument("--passfile", default=DEFAULT_PASSFILE)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--delay", type=float, default=0.010, help="per-character delay")
    ap.add_argument("--hover", type=float, default=0.12, help="move->press delay")
    ap.add_argument("command", choices=[
        "capture", "type", "key", "click", "dclick", "move", "run", "script"])
    ap.add_argument("args", nargs="*")
    ns = ap.parse_args()

    if not ns.args:
        ap.error("missing arguments for " + ns.command)

    server = parse_server(ns.server)
    client = connect(server, read_password(ns.passfile), ns.timeout)
    try:
        cmd, a = ns.command, ns.args
        if cmd == "capture":
            do_capture(client, a[0])
        elif cmd == "type":
            do_type(client, a[0], ns.delay)
        elif cmd == "key":
            do_key(client, a, ns.delay)
        elif cmd == "click":
            do_click(client, int(a[0]), int(a[1]), int(a[2]) if len(a) > 2 else 1, ns.hover)
        elif cmd == "dclick":
            do_dclick(client, int(a[0]), int(a[1]), ns.hover, 0.09)
        elif cmd == "move":
            do_move(client, int(a[0]), int(a[1]))
        elif cmd == "run":
            wait = float(a[2]) if len(a) > 2 else 3.0
            do_type(client, a[0], ns.delay)
            time.sleep(0.15)
            client.keyPress("return")
            print("+ return")
            do_capture(client, a[1], settle=wait)
        elif cmd == "script":
            run_script(client, a[0], ns.delay, ns.hover)
    finally:
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
