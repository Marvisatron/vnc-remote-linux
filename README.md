# vnc-remote-linux

Drive a remote Linux desktop from an agent over VNC: take screenshots, type
text, click, and run shell commands. The driver talks to the VNC server
directly through [`vncdotool`](https://github.com/sibson/vncdotool) instead of
automating a local viewer, so keystrokes are sent as keysyms and the local
keyboard layout cannot corrupt them.

Runs on Windows, macOS and Linux. Pure Python, nothing to compile.

```
capture  ->  decide  ->  act  ->  capture again
```

## Why not drive the local viewer

A viewer is built for a person at a keyboard. It translates local keycodes
through the local layout, asks the operating system for input and
screen-capture permission, and owns a window that competes with the user's.

Speaking RFB avoids those three constraints:

- keys go out as keysyms (Unicode code points), and the server maps them to its
  own layout;
- no Accessibility, Screen Recording, or input-injection permission is used on
  any platform;
- focus and the real pointer stay where the user put them.

Because the driver runs from a terminal, it also works headless and over SSH.
You need network reachability to the VNC port and nothing else.

## Requirements

- Python 3.9 or newer on the machine running the driver
- A reachable VNC endpoint and its password
- An existing desktop session on the remote host

## Install

```bash
git clone https://github.com/Marvisatron/vnc-remote-linux.git
cd vnc-remote-linux
python scripts/setup.py
```

`setup.py` creates a virtualenv at `~/.venvs/vnc`, installs `vncdotool`, asks
once for the VNC password with input hidden, and prints the interpreter and
driver paths for your platform.

The virtualenv is not decoration. Homebrew Python, Debian, Fedora, and some
python.org Windows builds refuse a system-wide `pip install` under PEP 668 and
require an override flag. A venv avoids that on all three platforms.

## Quick start

```bash
# Windows
PY=%USERPROFILE%\.venvs\vnc\Scripts\python.exe
# macOS / Linux
PY=~/.venvs/vnc/bin/python

DRV=scripts/vncdrv.py

"$PY" "$DRV" --server host.example::5901 capture shot.png
"$PY" "$DRV" --server host.example::5901 run 'uname -a' out.png 4
```

`--server` takes `host::port` with a double colon for an explicit port.

### One connection, many steps

```bash
"$PY" "$DRV" --server host.example::5901 script ops.txt
```

```text
# ops.txt
capture 00-before.png
type cd /opt/work
key return
wait 2
capture 01-after.png
```

## What it can do

| | |
|---|---|
| `capture OUT` | save the framebuffer as PNG |
| `type TEXT` | send text, one keysym per character |
| `key NAME...` | `return`, `tab`, `esc`, `space`, `ctrl-c`, `shift-tab`, … |
| `click X Y` / `dclick` / `move` | pointer |
| `run TEXT OUT [WAIT]` | type, Enter, wait, capture |
| `script FILE` | many operations over one connection |

## Sending files to the remote

RFB has no file-copy primitive. For text files, base64 through the keyboard
needs no extra service on the remote side:

```bash
python scripts/gen_upload_ops.py --remote-dir '~/work' ops.txt a.py b.txt
"$PY" "$DRV" --server host::port script ops.txt
```

The generator chunks at 160 characters per injected line and ends with `md5sum`
for every file, so each transfer is verifiable.

Measured throughput is about 1 KB every 8 seconds at a 5 ms character delay
(10.8 KB in 79 seconds). That covers scripts, configuration, and RTL. Above a
few hundred KB, use the host's own upload channel: FTP, SFTP, or a shared drive.

## Password handling

The password is never passed on a command line, never written into a script,
and never echoed. Resolution order:

```
--passfile PATH   >   $VNC_PASSWORD   >   ~/.vnc_agent_pass
```

`setup.py` creates the last one with owner-only permissions.

## Using it as an agent skill

The repository root is the skill: `SKILL.md` plus `scripts/`. Drop or link the
directory into your agent's skill root.

| Tool | Skill root |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Cursor | `~/.cursor/skills-cursor/` |
| Gemini | `~/.gemini/config/skills/` |
| DeepSeek Harness | `~/.dsh/skills/` |
| neutral | `~/.agents/skills/` |

When several tools share a machine, keep one real copy and link the rest at it,
so the instructions cannot drift apart:

```bash
ln -s ~/.agents/skills/vnc-remote-linux ~/.codex/skills/vnc-remote-linux
```

```powershell
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.codex\skills\vnc-remote-linux" `
         -Target "$env:USERPROFILE\.agents\skills\vnc-remote-linux"
```

## Compatibility

| Platform | Status | Notes |
|---|---|---|
| Linux | supported | pure Python, no native dependencies |
| macOS | supported | no Accessibility or Screen Recording permission used |
| Windows | supported | interpreter lives in `Scripts\python.exe` |

## Limitations

- Needs an existing desktop session on the remote host; it cannot start one.
- Each `capture` transfers a full framebuffer. A 1920x1080 screen is typically
  100 to 200 KB as PNG.
- File transfer by keystroke runs at about 1 KB per 8 seconds, so it suits tens
  of KB rather than megabytes.
- Clipboard transfer is not implemented.

## License

MIT. See [LICENSE](LICENSE).
