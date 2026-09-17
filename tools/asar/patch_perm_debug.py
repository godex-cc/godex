# -*- coding: utf-8 -*-
"""Patch permissions-mode-dropdown chunk inside app.asar with a debug capture.

Injects right after the disable-state computation in the PermissionsModeDropdown
component:  N=ue||ae||!de,fe;   ->   ... + try{window.__permDebugAll=...}catch{}
Writes app.asar.permdebug (does NOT touch the live asar). Self-check included.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ASAR = Path(r"D:\Odyssey\GodexDesktop\app\resources\app.asar")
OUT = ASAR.with_suffix(".asar.permdebug2")
CHUNK_REL = ("webview", "assets", "permissions-mode-dropdown-8266f079a0d0.js")

ANCHOR = b"K=Nt?sn:`text-tertiary`,q,J;"
INJECT = (
    b"K=Nt?sn:`text-tertiary`,q,J;"
    b"(function(){try{(window.__permDebug2=window.__permDebug2||[]).push({"
    b"st:st,jt:jt,kt:kt,ceLen:Ce.length,b:B==null?null:B,mt:mt,"
    b"rt:rt,dt:dt,W:W,ut:ut,vt:vt==null?null:vt,it:it,ot:ot==null?null:ot,de:De,"
    b"cid:n==null?null:n,host:r,"
    b"cfg:JSON.stringify({req:O==null?null:O.requirements,cfg:O==null?null:O.resolvedConfig,pending:O==null?null:O.isConfigDataPending}).slice(0,500)"
    b"})}catch(__pd){(window.__permDebug2=window.__permDebug2||[]).push({err:String(__pd)})}})();"
)


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def read_header(f):
    f.seek(4)
    header_size = struct.unpack("<I", f.read(4))[0]
    f.seek(16)
    raw = f.read(header_size)
    header, _ = json.JSONDecoder().raw_decode(raw.decode("utf-8", errors="replace"))
    return header, 8 + header_size


def node_for(header, rel):
    n = header["files"]
    for part in rel[:-1]:
        n = n[part]["files"]
    return rel[-1], n


def extract_file(f, header, data_offset, rel):
    name, parent = node_for(header, rel)
    child = parent[name]
    f.seek(data_offset + int(child["offset"]))
    return f.read(int(child["size"]))


def main():
    src = open(ASAR, "rb")
    header, data_offset = read_header(src)
    chunk = extract_file(src, header, data_offset, CHUNK_REL)
    print(f"chunk {sha(chunk)} len={len(chunk)}")
    if chunk.count(ANCHOR) != 1:
        sys.exit(f"anchor count = {chunk.count(ANCHOR)}, expected 1")
    if b"__permDebug2" in chunk:
        sys.exit("chunk already carries __permDebug2 (previous patch?)")
    patched_chunk = chunk.replace(ANCHOR, INJECT, 1)
    # sanity: balanced-ish (same paren/brace balance delta as anchor replacement)
    print(f"patched chunk {sha(patched_chunk)} len={len(patched_chunk)}")

    patched = {CHUNK_REL: patched_chunk}
    orig = {}

    def collect(node, rel):
        for name, child in node.items():
            r = rel + (name,)
            if "files" in child:
                collect(child["files"], r)
            elif child.get("unpacked"):
                continue
            elif "offset" in child:
                orig[r] = (int(child["offset"]), int(child["size"]))

    collect(header["files"], ())

    cursor = 0
    nf = 0

    def plan(node, rel):
        nonlocal cursor, nf
        for name, child in node.items():
            r = rel + (name,)
            if "files" in child:
                plan(child["files"], r)
            elif child.get("unpacked"):
                continue
            elif "offset" in child:
                blob = patched.get(r)
                size = len(blob) if blob is not None else orig[r][1]
                child["offset"] = str(cursor)
                child["size"] = size
                cursor += size
                nf += 1

    plan(header["files"], ())

    jb = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_len = len(jb)
    json_padded = (json_len + 3) // 4 * 4
    b2 = 4 + json_padded
    b1 = b2 + 4
    dst = open(OUT, "wb")
    dst.write(struct.pack("<4I", 4, b1, b2, json_len) + jb + b"\x00" * (json_padded - json_len))
    data_start = 8 + b1
    assert dst.tell() == data_start, (dst.tell(), data_start)

    def emit(node, rel):
        for name, child in node.items():
            r = rel + (name,)
            if "files" in child:
                emit(child["files"], r)
            elif child.get("unpacked"):
                continue
            elif "offset" in child:
                blob = patched.get(r)
                if blob is None:
                    off, size = orig[r]
                    src.seek(data_offset + off)
                    blob = src.read(size)
                    if len(blob) != size:
                        sys.exit(f"short read at {r}")
                dst.write(blob)

    emit(header["files"], ())
    if dst.tell() != data_start + cursor:
        sys.exit(f"data size mismatch: wrote {dst.tell() - data_start}, planned {cursor}")
    dst.close()
    src.close()
    print(f"repacked {OUT}: {nf} files, {cursor} data bytes")

    # self-check
    vf = open(OUT, "rb")
    vheader, vdata = read_header(vf)
    got = extract_file(vf, vheader, vdata, CHUNK_REL)
    print(f"self-check chunk: {'OK' if got == patched_chunk else 'MISMATCH'} ({len(got)} bytes)")
    # spot-check one untouched file
    other = ("webview", "assets", "app-initial-d9bed9d614d8.js")
    got2 = extract_file(vf, vheader, vdata, other)
    orig2 = extract_file(open(ASAR, "rb"), header, data_offset, other)
    print(f"self-check app-initial: {'OK' if got2 == orig2 else 'MISMATCH'} ({len(got2)} bytes)")
    vf.close()


if __name__ == "__main__":
    main()
