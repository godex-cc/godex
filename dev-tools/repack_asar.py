# -*- coding: utf-8 -*-
"""Repack app.asar from the patched loose dir.

Strategy: load the reference asar's header; for every entry take payload from
the loose dir (falling back to the old asar bytes if absent there); emit a new
archive with recomputed offsets/sizes/integrity. Files flagged `unpacked` in
the reference keep that flag (their real bytes stay in app.asar.unpacked).

Usage: python repack_asar.py <loose_dir> <ref_asar> <out_asar>
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

BLOCK = 4 * 1024 * 1024


def integrity(data: bytes) -> dict:
    blocks = [hashlib.sha256(data[i:i + BLOCK]).hexdigest()
              for i in range(0, len(data), BLOCK)] or [[]]
    # @electron/asar uses lowercase hex of sha256; zero-block files hash empty
    return {
        "algorithm": "SHA256",
        "hash": hashlib.sha256(data).hexdigest(),
        "blockSize": BLOCK,
        "blocks": blocks if isinstance(blocks, list) and data else [],
    }


def main():
    loose, ref_path, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    ref = open(ref_path, "rb")
    pre = ref.read(16)
    jsz = struct.unpack("<I", pre[12:16])[0]
    header = json.loads(ref.read(jsz).decode("utf-8"))
    # header JSON is 4-byte padded in the current archive geometry; offsets are
    # relative to the padded end (16 + aligned jsz), not the raw json size.
    payload_base = 16 + ((jsz + 3) & ~3)

    def walk(node, rel):
        out = {}
        for name, ch in node.get("files", {}).items():
            p = rel / name
            if "files" in ch:
                out[name] = {"files": walk(ch["files_part"] if False else ch, p)[1]["files"]} \
                    if False else None
            # handled below uniformly
        # simpler recursive build
        return None

    new_header = {"files": {}}
    out_buf = bytearray()
    missing_loose = []

    def emit(node_ref, node_out, rel):
        for name, ch in node_ref.get("files", {}).items():
            p = rel / name
            if "files" in ch:
                sub = {"files": {}}
                emit(ch, sub, p)
                if sub["files"]:
                    node_out["files"][name] = sub
                continue
            size = ch.get("size", 0)
            if ch.get("unpacked"):
                target = Path(str(loose / p) ) # informational
                entry = {"size": size, "unpacked": True}
                if "integrity" in ch:
                    entry["integrity"] = ch["integrity"]
                node_out["files"][name] = entry
                continue
            lp = loose / p
            if lp.is_file():
                data = lp.read_bytes()
            else:
                off = int(ch.get("offset", 0))
                ref.seek(payload_base + off)
                data = ref.read(size)
                missing_loose.append(str(p))
            entry = {"size": len(data)}
            entry["offset"] = str(len(out_buf))
            if "integrity" in ch:
                entry["integrity"] = integrity(data)
            out_buf.extend(data)
            node_out["files"][name] = entry

    emit(header, new_header, Path("."))
    ref.close()

    hdr_bytes = json.dumps(new_header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    pad = (4 - len(hdr_bytes) % 4) % 4
    padded = len(hdr_bytes) + pad
    with open(out_path, "wb") as w:
        # framing mirrors the reference archive exactly: (4, n+8, n+4, n)
        w.write(struct.pack("<4I", 4, padded + 8, padded + 4, len(hdr_bytes)))
        w.write(hdr_bytes)
        w.write(b"\0" * pad)
        w.write(bytes(out_buf))
    print(f"packed ok: {len(out_buf)/1e6:.1f} MB payload, {len(missing_loose)} files from ref only")
    if missing_loose:
        print("e.g.", missing_loose[:5])


if __name__ == "__main__":
    main()
