#!/usr/bin/env python3
"""Turn local files into a vncdrv.py ops script that recreates them on the
remote host, byte-exactly.

Why base64: the remote shell is often tcsh and the injection path mangles `$`,
backslashes and quotes. Base64's alphabet is [A-Za-z0-9+/=], i.e. nothing the
shell, or tcsh history expansion, will touch.

Why 160-character chunks: injected lines longer than roughly 200 characters have
been observed to arrive truncated — the tail of the command silently never runs.
Chunking also keeps each op line short enough to read back on screen.

Usage:
    gen_upload_ops.py --remote-dir '~/work' OUT_OPS FILE [FILE ...]

Then:
    vncdrv.py --server host::port script OUT_OPS

The generated script ends with `md5sum` for every file. Compare those against
the digests printed here; never trust the transfer without that check.
"""
import argparse
import base64
import hashlib
import pathlib

CHUNK = 160


def emit(remote_dir: str, files: list[str]) -> tuple[str, list[tuple]]:
    lines = [
        f"typeline mkdir -p {remote_dir}",
        f"typeline cd {remote_dir}",
    ]
    manifest = []
    for path in files:
        p = pathlib.Path(path)
        data = p.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        manifest.append((p.name, len(data), hashlib.md5(data).hexdigest(),
                         hashlib.sha256(data).hexdigest()))
        lines.append(f"typeline rm -f {p.name}.b64")
        for i in range(0, len(b64), CHUNK):
            lines.append(f"typeline echo '{b64[i:i + CHUNK]}' >> {p.name}.b64")
        lines.append(f"typeline base64 -d {p.name}.b64 > {p.name}")
        lines.append(f"typeline rm -f {p.name}.b64")
    for name, _, _, _ in manifest:
        lines.append(f"typeline md5sum {name}")
    lines.append("capture /tmp/upload_check.png")
    return "\n".join(lines) + "\n", manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote-dir", required=True)
    ap.add_argument("out")
    ap.add_argument("files", nargs="+")
    ns = ap.parse_args()
    text, manifest = emit(ns.remote_dir, ns.files)
    pathlib.Path(ns.out).write_text(text, encoding="utf-8")
    total = sum(m[1] for m in manifest)
    print(f"{len(text.splitlines())} ops, {len(text)} chars, {total} source bytes\n")
    print(f"{'file':28s} {'bytes':>7s}  md5")
    for name, n, md5, _ in manifest:
        print(f"{name:28s} {n:7d}  {md5}")


if __name__ == "__main__":
    main()
