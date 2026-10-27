#!/usr/bin/env python3
"""setup.py - one-time preparation for vnc-remote-linux. Works on Windows, macOS and Linux.

Creates a virtual environment, installs vncdotool into it, and stores the VNC
password in a file outside the project so it never appears in a command line,
a script, a shell history, or a repository.

    python scripts/setup.py

Options:

    --venv PATH          where to put the virtualenv (default ~/.venvs/vnc)
    --passfile PATH      where to store the password (default ~/.vnc_agent_pass)
    --skip-password      only do the venv, leave the password file alone

Re-running is safe: an existing virtualenv is reused and an existing password
file is left untouched.
"""
from __future__ import annotations

import argparse
import getpass
import os
import pathlib
import stat
import subprocess
import sys


def venv_python(venv: pathlib.Path) -> pathlib.Path:
    """The interpreter inside a virtualenv, which differs between platforms."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venv", default=str(pathlib.Path.home() / ".venvs" / "vnc"))
    ap.add_argument("--passfile", default=str(pathlib.Path.home() / ".vnc_agent_pass"))
    ap.add_argument("--skip-password", action="store_true")
    ns = ap.parse_args()

    venv = pathlib.Path(ns.venv).expanduser()
    py = venv_python(venv)

    # ---------------------------------------------------------------- venv
    if not py.exists():
        print(f"creating virtualenv: {venv}")
        run([sys.executable, "-m", "venv", str(venv)])
    else:
        print(f"virtualenv already present: {venv}")

    # A venv is used because several distributions (Homebrew, Debian, Fedora)
    # refuse system-wide pip installs under PEP 668.
    run([str(py), "-m", "pip", "install", "--quiet",
         "--disable-pip-version-check", "vncdotool"])

    # Verify the API the driver depends on actually exists in this install,
    # rather than assuming it. Kept quiet: only the verdict is printed.
    probe = (
        "from vncdotool.client import VNCDoToolClient as C\n"
        "need = ['keyPress', 'captureScreen', 'mouseMove', 'mousePress']\n"
        "missing = [n for n in need if not hasattr(C, n)]\n"
        "assert not missing, 'missing methods: %s' % missing\n"
        "print('vncdotool API check: ok')\n"
    )
    result = subprocess.run([str(py), "-c", probe],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("vncdotool install did not provide the expected API:")
        print(result.stderr.strip() or result.stdout.strip())
        return 1
    print(result.stdout.strip())

    # ------------------------------------------------------------ password
    passfile = pathlib.Path(ns.passfile).expanduser()
    print()
    if ns.skip_password:
        print(f"skipping password file: {passfile}")
    elif passfile.exists() and passfile.stat().st_size > 0:
        print(f"password file already present, left untouched: {passfile}")
    else:
        try:
            pw = getpass.getpass("VNC password (input hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("\naborted; no password written")
            return 1
        if not pw:
            print("empty password; nothing written")
            return 1
        passfile.parent.mkdir(parents=True, exist_ok=True)
        passfile.write_text(pw, encoding="utf-8")
        del pw
        # 0600 where the OS supports it. On Windows the file inherits the
        # profile directory ACL, which is per-user already.
        try:
            passfile.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        print(f"saved {passfile} ({passfile.stat().st_size} bytes)")

    # ------------------------------------------------------------- summary
    here = pathlib.Path(__file__).resolve().parent
    driver = here / "vncdrv.py"
    print()
    print("=" * 62)
    print("Ready. Run the driver with this interpreter:")
    print()
    print(f'  PYTHON = "{py}"')
    print(f'  DRIVER = "{driver}"')
    print()
    print("Example:")
    print(f'  "{py}" "{driver}" --server HOST::PORT capture shot.png')
    print()
    print("Windows (PowerShell) uses the same form, with quotes as shown.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
