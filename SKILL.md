---
name: vnc-remote-linux
description: "Drive a remote Linux desktop over VNC from an agent: screenshot, type text, click, and run shell commands by speaking the RFB protocol directly with vncdotool, instead of automating a local VNC viewer. Runs on Windows, macOS and Linux. Use when a remote machine is reachable only as a graphical desktop (no SSH), or when automating the local viewer is inconvenient, blocked by OS permissions, or corrupts keystrokes through its keyboard layout. Skip when SSH/scp is available — a shell over SSH is always cheaper than pixels."
version: 2.0.0
license: MIT
triggers:
  - "VNC"
  - "远程桌面"
  - "服务器桌面"
  - "vncdotool"
  - "RFB"
  - "远程 Linux"
  - "VNC 上敲命令"
  - "no SSH access"
---

# Drive a remote Linux desktop over VNC

Talk to the **VNC server** directly instead of driving a local VNC viewer.
The viewer is a human interface; RFB is a machine one.

You get four primitives — screenshot, type, click, key — and from those, shell
access to the remote machine.

## When to use this

- The remote host is reachable only as a graphical desktop (no SSH/SFTP).
- You have a VNC endpoint and its password, and nothing else.
- You want to send exact keystrokes without depending on the local keyboard
  layout, and without taking over the user's real mouse and keyboard.

Do **not** use it when SSH exists. A shell over SSH is faster, cheaper and far
more reliable than moving pixels around.

## Why go through RFB rather than the viewer

A VNC viewer is built for a person at a keyboard. It translates local keycodes
through the local layout, needs OS input permissions, and owns a real window.
Speaking RFB sidesteps all three:

- keys are sent as **keysyms** (Unicode code points) and the server maps them
  to its own layout, so the local layout cannot corrupt them;
- no OS-level input or screen-capture permission is involved, on any platform;
- nothing steals focus or moves the user's pointer.

The cost is that you only get what RFB offers: framebuffer, keyboard, pointer,
clipboard. There is no file-copy primitive — see "Transferring files in".

## Install

Requires Python 3.9 or newer on the machine that will run the driver
(the *controller*, not the remote host).

```bash
python scripts/setup.py
```

That creates a virtualenv at `~/.venvs/vnc`, installs `vncdotool` into it, and
prompts once for the VNC password. It prints the exact interpreter and driver
paths for the current OS when it finishes.

A virtualenv is used deliberately: several systems (Homebrew, Debian, Fedora,
and Python installed from python.org on Windows in some configurations) refuse
system-wide `pip install` and need `--break-system-packages` or an equivalent
override. None of that is necessary here.

Manual equivalent, if you prefer:

| Platform | Create | Activate | Interpreter |
|---|---|---|---|
| Windows | `py -m venv .venv` | `.venv\Scripts\activate` | `.venv\Scripts\python.exe` |
| macOS / Linux | `python3 -m venv .venv` | `. .venv/bin/activate` | `.venv/bin/python` |

then `pip install vncdotool`.

## Keep the password out of band

Never put the VNC password on a command line, in a script, in a project file,
or in a chat message. A command line is visible to other users through the
process list; a repository outlives the engagement.

`setup.py` writes it to a file readable only by you. The driver reads that file
at runtime and never echoes it. Precedence:

```
--passfile PATH   >   $VNC_PASSWORD   >   ~/.vnc_agent_pass
```

The environment variable exists for CI and for throwaway sessions; the file is
the better default. Delete it when the engagement ends.

## Driving it

```bash
# Windows
PY  = %USERPROFILE%\.venvs\vnc\Scripts\python.exe
# macOS / Linux
PY  = ~/.venvs/vnc/bin/python

DRV = <path to>/scripts/vncdrv.py

"$PY" "$DRV" --server host.example::5901 capture shot.png
"$PY" "$DRV" --server host.example::5901 type 'ls -la /opt'
"$PY" "$DRV" --server host.example::5901 key return
"$PY" "$DRV" --server host.example::5901 click 79 222
"$PY" "$DRV" --server host.example::5901 run 'uname -a' out.png 4
```

`--server` takes `host::port` with a **double** colon when specifying a port
explicitly (`host:1` is display-number syntax and means something else).
`VNC_SERVER` sets a default.

Subcommands:

| Command | Meaning |
|---|---|
| `capture OUT` | save the framebuffer as PNG |
| `type TEXT` | send the text, one keysym per character |
| `key NAME...` | send named keys, lowercase: `return`, `tab`, `esc`, `space`, `ctrl-c`, `shift-tab` |
| `click X Y [BTN]` | move, settle, press |
| `dclick X Y` | two presses ~90 ms apart |
| `move X Y` | move only |
| `run TEXT OUT [WAIT]` | type, press Return, wait WAIT seconds, capture — the fastest loop |
| `script FILE` | many operations over **one** connection |

For anything beyond a couple of steps use `script`, so the sequence shares one
connection instead of reconnecting per action:

```text
# ops.txt — one op per line; blank lines and # comments are ignored
capture 00-before.png
type cd /opt/work
key return
wait 2
capture 01-after.png
```

## The loop that works

```
capture  ->  decide  ->  act  ->  capture again
```

**Do not skip the second capture.** A command that returned success is not
evidence that the remote changed. The screenshot is the proof, and it is also
the artefact you hand back to the user.

The framebuffer size reported by `capture` is the true remote resolution, not
the viewer window size. Click coordinates live in that space.

Reading a screenshot is worth doing carefully: crop only after you have looked
at the whole frame, because a window may have moved or scrolled, and a crop that
lands on empty space looks exactly like "the command printed nothing".

## Typing rules

These follow from the vncdotool API:

- Key names are **lowercase**: `return`, `enter`, `tab`, `esc`, `space`,
  `ctrl`, `shift`, `alt`. Combined keys are hyphenated: `ctrl-c`, `shift-tab`.
- A character that is not a known key name falls through to its Unicode keysym,
  which is why arbitrary printable text works.
- There is **no** `typeText` method on `VNCDoToolClient`; the driver loops
  `keyPress` one character at a time, 8–12 ms apart.
- Leave ~100 ms between `mouseMove` and `mousePress`; the pointer position has
  to land before the press is meaningful.
- Double-click is two `mousePress` calls about 90 ms apart at one position.

## The remote shell

The remote is a Linux desktop, and its shell is whatever the account uses —
commonly `bash`, sometimes `tcsh` or `zsh`. The driver injects characters, not
a shell session, so quoting is your responsibility.

Two habits that hold regardless of shell:

- Prefer single quotes around anything containing `$`, `!`, `\`, or `*`.
- Prefer command forms that need no subshell or pipeline when a simpler one
  exists (`unzip -Z1 file.zip` lists names; `unzip -l | awk '{print $4}'` does
  not need to).

Long injected lines are the one real constraint: keep a single logical line
short, and split work across several `type` operations when it grows. If a
command that should produce output produces none, re-issue it in smaller pieces
before drawing a conclusion.

Non-ASCII filenames cannot be typed — there is no input method in an injected
keystroke. Address them with an ASCII glob (`*Application*.pdf`) or by attribute
(`find . -size +1000k`), or copy them to an ASCII name first.

## Transferring files in

RFB has no file-copy primitive. For source files up to a few tens of KB, send
them as base64: the alphabet is `[A-Za-z0-9+/=]`, which no shell will
misinterpret.

```bash
python scripts/gen_upload_ops.py --remote-dir '~/work' ops.txt a.py b.txt
```

then feed the generated script to the driver:

```bash
"$PY" "$DRV" --server host::port script ops.txt
```

Per file it emits `rm -f f.b64`, then `echo '<160 chars>' >> f.b64` repeated,
then `base64 -d f.b64 > f`, then `md5sum f` for every file.

Two rules:

- **Chunk small.** 160 characters per injected line keeps each operation short
  enough to be reliable and to read back on screen.
- **Verify with a digest.** Compare the remote `md5sum` against the digest the
  generator printed. A matching line count is weak; a matching md5 is not.

Throughput is roughly 1 KB per 8 seconds at a 5 ms character delay. That is
fine for scripts and RTL, hopeless for megabytes — above a few hundred KB use
whatever upload channel the host provides (FTP, SFTP, a shared drive) and keep
this method for text you cannot otherwise get across.

## Verification discipline

- One action, then look. Batching unverified steps compounds mistakes.
- Distinguish "ran and produced nothing" from "never ran": wrap a command as
  `echo START; cmd; echo END` and check that both markers appear.
- Prefer read-only probes first: `ls`, `head`, `wc -l`, `grep -c`.
- Capture after every state change and keep the images as evidence.
- When a result matters, verify the *input* to the step as well as the output.
  A tool that reports success is not proof that it used the file you think it
  did.

## Safety

- Password: 0600 file or environment variable. Never argv, never a repository.
- Write inside the account's own home. Reading shared public directories is
  usually fine; do not enumerate other users' private directories.
- Do not change login, security, shell startup files, or shared tool
  directories in order to "make something work".
- Ask before anything destructive or outward-facing: deleting, installing,
  publishing, overwriting, sending mail.

## Compatibility

| Platform | Status | Notes |
|---|---|---|
| Linux | supported | driver is pure Python |
| macOS | supported | no Accessibility or Screen Recording permission needed |
| Windows | supported | use `%USERPROFILE%\.venvs\vnc\Scripts\python.exe` |

`vncdotool` is pure Python on top of Twisted, so there is nothing to compile.
The driver uses only `argparse`, `os`, `sys` and `time` from the standard
library, plus `vncdotool`.

## Files

| Path | Purpose |
|---|---|
| `scripts/setup.py` | create the venv, install vncdotool, store the password |
| `scripts/vncdrv.py` | the driver |
| `scripts/gen_upload_ops.py` | turn local files into a base64 upload script |
