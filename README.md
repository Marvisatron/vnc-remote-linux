# vnc-remote-linux

An agent skill for driving a remote Linux desktop over VNC — screenshot, type,
click, and run shell commands — by talking to the **VNC server directly** with
[`vncdotool`](https://github.com/sibson/vncdotool) instead of automating a local
VNC viewer.

Works on **Windows, macOS and Linux**. Pure Python, nothing to compile.

```
capture  ->  decide  ->  act  ->  capture again
```

## Why not just drive the VNC viewer

A viewer is built for a person at a keyboard. It translates local keycodes
through the local keyboard layout, needs OS-level input and screen permissions,
and owns a real window that competes with the user's.

Speaking RFB avoids all three:

- keys go out as **keysyms** (Unicode code points); the server maps them to its
  own layout, so your local layout cannot corrupt them;
- no Accessibility, Screen Recording, or input-injection permission is involved
  on any platform;
- nothing takes focus and nothing moves the user's pointer.

Everything is driven from a terminal, so it also works headless and over SSH —
you only need network reachability to the VNC port.

## Requirements

- Python 3.9+ on the machine running the driver
- A reachable VNC endpoint and its password
- The remote host must already have a running desktop session

## Install

```bash
git clone https://github.com/Marvisatron/vnc-remote-linux.git
cd vnc-remote-linux
python scripts/setup.py
```

`setup.py` creates a virtualenv at `~/.venvs/vnc`, installs `vncdotool`, asks
once for the VNC password (hidden input), and prints the exact interpreter and
driver paths for your OS.

Why a virtualenv: several systems refuse system-wide `pip install` and require
an override flag. The venv makes that unnecessary everywhere.

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

`--server` uses `host::port` with a **double** colon for an explicit port.

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

RFB has no file-copy primitive. For text files up to a few tens of KB, base64
through the keyboard is reliable and needs no extra service:

```bash
python scripts/gen_upload_ops.py --remote-dir '~/work' ops.txt a.py b.txt
"$PY" "$DRV" --server host::port script ops.txt
```

It chunks at 160 characters per injected line and finishes with `md5sum` for
every file, so the transfer is verifiable.

## Password handling

The password is never passed on a command line, never written into a script,
and never echoed. Resolution order:

```
--passfile PATH   >   $VNC_PASSWORD   >   ~/.vnc_agent_pass
```

`setup.py` creates the last one with owner-only permissions.

## Using it as an agent skill

The repository root *is* the skill: `SKILL.md` plus `scripts/`. Drop or link the
directory into your agent's skill root.

| Tool | Skill root |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Cursor | `~/.cursor/skills-cursor/` |
| Gemini | `~/.gemini/config/skills/` |
| DeepSeek Harness | `~/.dsh/skills/` |
| neutral | `~/.agents/skills/` |

When several tools share a machine, keep one real copy and symlink the rest at
it, so the instructions cannot drift apart:

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
| Linux | supported | pure Python, no native deps |
| macOS | supported | no Accessibility / Screen Recording permission needed |
| Windows | supported | interpreter lives in `Scripts\python.exe` |

## Limitations

- Needs an existing desktop session on the remote host; it will not create one.
- Bandwidth is a screen image per `capture`; large resolutions are slower.
- File transfer by keystroke is practical for tens of KB, not megabytes.
- Clipboard transfer is not implemented.

## License

MIT — see [LICENSE](LICENSE).
