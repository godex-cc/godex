# -*- coding: utf-8 -*-
"""Generate the cross-platform icon set for Godex from the brand source PNG.

Inputs : assets/godex-brand-ico.png (512x512 RGBA white-disc terminal face)
Outputs: packaging/icons/
  godex.icns            macOS bundle icon (PNG-compressed ICNS, ic07..ic14)
  godex.png             Linux/general 512x512
  godex-{16,32,48,64,128,256}.png  Linux hicolor set
  godex-win.ico         Windows multi-size ico (16..256)

Pure Pillow; no external icon tools. Deterministic output (no timestamps).
"""
from pathlib import Path
import struct

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]        # GodexDesktop/
SRC = ROOT / "assets" / "godex-brand-ico.png"
OUT = ROOT / "packaging" / "icons"

SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]


def resized(img, size):
    return img.resize((size, size), Image.LANCZOS)


def write_icns(img, path):
    """Minimal ICNS writer. PNG data is accepted by macOS for the modern
    icon types (ic07=128, ic08=256, ic09=512, ic10=1024(@2x 512),
    ic11=32(@2x 16), ic12=64(@2x 32), ic13=256(@2x 128), ic14=512(@2x 256))."""
    entries = [
        ("ic07", 128), ("ic08", 256), ("ic09", 512), ("ic10", 1024),
        ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512),
    ]
    chunks = b""
    seen = set()
    for otype, size in entries:
        if size in seen:
            continue  # ic13/ic14 reuse sizes of ic08/ic09 at @2x semantics
        seen.add(size)
        png = resized(img, size)
        buf = path.with_suffix(".tmp.png")
        png.save(buf, "PNG", optimize=False)
        data = buf.read_bytes()
        buf.unlink()
        chunks += otype.encode("ascii") + struct.pack(">I", len(data) + 8) + data
    total = 8 + len(chunks)
    path.write_bytes(b"icns" + struct.pack(">I", total) + chunks)
    return total


def verify_icns(path):
    b = path.read_bytes()
    assert b[:4] == b"icns", "bad magic"
    total = struct.unpack(">I", b[4:8])[0]
    assert total == len(b), f"size mismatch {total} != {len(b)}"
    off, kinds = 8, []
    while off < len(b):
        otype = b[off:off + 4].decode("ascii")
        ln = struct.unpack(">I", b[off + 4:off + 8])[0]
        assert b[off + 8:off + 12] == b"\x89PNG", f"{otype} chunk not PNG"
        kinds.append((otype, ln))
        off += ln
    return kinds


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert("RGBA")
    assert src.width == 512 and src.height == 512, f"source must be 512, got {src.size}"

    for s in (16, 32, 48, 64, 128, 256):
        resized(src, s).save(OUT / f"godex-{s}.png", "PNG")
    resized(src, 512).save(OUT / "godex.png", "PNG")

    ico_path = OUT / "godex-win.ico"
    src.save(ico_path, format="ICO",
             sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    total = write_icns(src, OUT / "godex.icns")
    kinds = verify_icns(OUT / "godex.icns")
    print(f"icns OK: {total} bytes, chunks: {[k for k, _ in kinds]}")
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name:20s} {p.stat().st_size:>9d}")


if __name__ == "__main__":
    main()
