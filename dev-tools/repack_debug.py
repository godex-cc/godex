# -*- coding: utf-8 -*-
"""Debug repack: print source for index-cbd874f72008.js"""
import hashlib, json, struct, sys
from pathlib import Path

BLOCK = 4 * 1024 * 1024
def integrity(data):
    blocks = [hashlib.sha256(data[i:i+BLOCK]).hexdigest() for i in range(0, len(data), BLOCK)] or [[]]
    return {"algorithm":"SHA256","hash":hashlib.sha256(data).hexdigest(),"blockSize":BLOCK,"blocks":blocks if isinstance(blocks,list) and data else []}

def main():
    loose, ref_path, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    ref = open(ref_path, "rb")
    pre = ref.read(16)
    jsz = struct.unpack("<I", pre[12:16])[0]
    header = json.loads(ref.read(jsz).decode("utf-8"))
    payload_base = 16 + jsz
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
                entry = {"size": size, "unpacked": True}
                if "integrity" in ch:
                    entry["integrity"] = ch["integrity"]
                node_out["files"][name] = entry
                continue
            lp = loose / p
            src = "LOOSE"
            if lp.is_file():
                data = lp.read_bytes()
            else:
                off = int(ch.get("offset", 0))
                ref.seek(payload_base + off)
                data = ref.read(size)
                missing_loose.append(str(p))
                src = "REF"
            if str(p).endswith("index-cbd874f72008.js"):
                print(f"  DEBUG {p} src={src} head={data[:30]!r}")
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
        w.write(struct.pack("<4I", 4, padded+8, padded+4, len(hdr_bytes)))
        w.write(hdr_bytes)
        w.write(b"\0" * pad)
        w.write(bytes(out_buf))
    print(f"packed ok: {len(out_buf)/1e6:.1f} MB, {len(missing_loose)} from ref")

if __name__ == "__main__":
    main()
