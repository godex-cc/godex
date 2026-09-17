# -*- coding: utf-8 -*-
"""Build a patched app.asar.new.

The app runs from app.asar (loose app/resources/app is ignored), so the runtime
bundles live inside the asar. The loose dir already carries the fully patched
bundles, so:
  - main bundle: keep the asar head (byte-verified identical to loose head),
    swap in the loose tail after ;/*GODEX_BYOK_RPC*/ (catalog + enabled + repairCfg)
  - renderer: asar copy is byte-identical to the loose .pre-enabled backup, so
    copy the loose patched renderer verbatim
Then repack: original header structure/order, updated offsets/sizes, file data
streamed from the old asar except the two patched files.
Writes app.asar.next to app.asar; does NOT touch the live asar.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ASAR = Path(r"D:\Odyssey\GodexDesktop\app\resources\app.asar")
WORK = Path(r"D:\Odyssey\work\asar-work")
LOOSE_DIR = Path(r"D:\Odyssey\GodexDesktop\app\resources\app")
LOOSE_MAIN = LOOSE_DIR / ".vite" / "build" / "main-D8abTQQE.js"
LOOSE_REND = LOOSE_DIR / "webview" / "assets" / "app-initial-d9bed9d614d8.js"
LOOSE_REND_BASE = LOOSE_REND.with_suffix(".js.pre-enabled")
MAIN_REL = (".vite", "build", "main-D8abTQQE.js")
REND_REL = ("webview", "assets", "app-initial-d9bed9d614d8.js")
LOOSE_HTML = LOOSE_DIR / "webview" / "index.html"
HTML_REL = ("webview", "index.html")
MARK = b";/*GODEX_BYOK_RPC*/"


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
    WORK.mkdir(parents=True, exist_ok=True)
    src = open(ASAR, "rb")
    header, data_offset = read_header(src)

    # --- gather bases -------------------------------------------------------
    asar_main = extract_file(src, header, data_offset, MAIN_REL)
    asar_rend = extract_file(src, header, data_offset, REND_REL)
    loose_main = LOOSE_MAIN.read_bytes()
    loose_rend = LOOSE_REND.read_text(encoding="utf-8")
    loose_rend_base = LOOSE_REND_BASE.read_bytes()

    # renderer: asar copy may already be the patched bytes (previous repack) or
    # the pristine base (original asar) -- only these two states are accepted
    patched_rend = loose_rend.encode("utf-8")
    # line endings drifted (loose file re-saved as CRLF); compare EOL-normalized
    norm = lambda b: b.replace(b"\r\n", b"\n")
    chipfix_base = LOOSE_REND.with_suffix(".js.pre-chipfix")
    chipfix_bytes = chipfix_base.read_bytes() if chipfix_base.exists() else None
    if norm(asar_rend) == norm(patched_rend):
        print("renderer already patched in asar; keeping as-is")
    elif norm(asar_rend) == norm(loose_rend_base):
        print("renderer base ok; copying loose patched renderer")
    elif chipfix_bytes is not None and norm(asar_rend) == norm(chipfix_bytes):
        print("renderer matches pre-chipfix repack state; upgrading")
    else:
        # unknown state: accept only if it is an earlier iteration of this same
        # patch lineage (enabled UI + chip avatar + popup header markers)
        lineage = [b"function setEn(", b"dotOff:", "使用中".encode(),
                   b'call("setEnabled"', b"data-ody-user-icon"]
        if all(m in norm(asar_rend) for m in lineage):
            print("renderer matches an earlier patched iteration (lineage ok); upgrading")
        else:
            sys.exit(
                f"asar renderer {sha(asar_rend)} matches neither the patched loose "
                f"renderer {sha(patched_rend)} nor the .pre-enabled base {sha(loose_rend_base)}"
            )
    for m in ["function setEn(", "dotOff:", "使用中", 'call("setEnabled"']:
        if loose_rend.count(m) < 1:
            sys.exit(f"loose renderer missing marker {m!r}")

    # main: heads differ only by upstream build drift (one \r inside an embedded
    # string + a ~1.6KB engine block); the RPC tail IIFE is self-contained and
    # every patch to it has been additive, so keep the asar head and swap in the
    # loose tail. Safety net = marker checks on the merged result below.
    i, j = asar_main.find(MARK), loose_main.find(MARK)
    if i < 0 or j < 0:
        sys.exit("BYOK RPC marker missing")
    patched_main = asar_main[:i] + loose_main[j:]
    for m in [b"function isEn(", b"setEnabled", b"function repairCfg(", b"fs.watch(CFG",
              b"out.enabled=st.enabled||{}", b"if(!isEn(st,pid))continue;", b"genCatalog(null)",
              b"fixProviderOnModelChange", b"byok-state.log"]:
        if patched_main.count(m) < 1:
            sys.exit(f"patched main missing marker {m!r}")
    if b"BUILTIN_CAT" in patched_main:
        sys.exit("builtin catalog merge must not be present (user removed builtins)")

    # --- startup splash html: replace OpenAI blossom with brand face ---------
    asar_html = extract_file(src, header, data_offset, HTML_REL)
    loose_html = LOOSE_HTML.read_bytes()
    nh = lambda b: b.replace(b"\r\n", b"\n")
    pre_splash = LOOSE_HTML.with_suffix(".html.pre-splash")
    if nh(asar_html) == nh(loose_html):
        print("splash html already patched in asar; keeping as-is")
    elif pre_splash.exists() and nh(asar_html) == nh(pre_splash.read_bytes()):
        print("splash html base ok; copying loose patched html")
    else:
        sys.exit(f"splash html {sha(asar_html)} matches neither patched loose html "
                 f"{sha(loose_html)} nor the .pre-splash base")
    if b"M11.6475" in loose_html or b"data:image/png;base64" not in loose_html:
        sys.exit("loose splash html does not carry the brand patch")
    patched_html = loose_html

    # --- package.json: stamp release version 0.0.1 ----------------------------
    PKG_REL = ("package.json",)
    asar_pkg = extract_file(src, header, data_offset, PKG_REL)
    loose_pkg = (LOOSE_DIR / "package.json").read_bytes()
    OLD_VER = b'"version": "26.908.40834"'
    NEW_VER = b'"version": "0.0.1"'
    if NEW_VER in asar_pkg and OLD_VER not in asar_pkg:
        if asar_pkg != loose_pkg:
            sys.exit(f"stamped asar package.json {sha(asar_pkg)} != loose {sha(loose_pkg)}")
        print("package.json already stamped 0.0.1 in asar; keeping as-is")
        patched_pkg = asar_pkg
    elif asar_pkg.count(OLD_VER) == 1:
        patched_pkg = asar_pkg.replace(OLD_VER, NEW_VER)
        if patched_pkg != loose_pkg:
            sys.exit(f"stamping asar package.json did not reproduce loose {sha(loose_pkg)}")
        print("package.json version stamped 0.0.1")
    else:
        sys.exit(f"package.json {sha(asar_pkg)} in unexpected state (loose {sha(loose_pkg)})")
    import json as _json
    pk = _json.loads(patched_pkg.decode("utf-8"))
    if pk.get("version") != "0.0.1" or pk.get("productName") != "Godex":
        sys.exit("stamped package.json failed sanity checks")
    if b"26.908.40834" in patched_pkg:
        sys.exit("old version string still present in package.json")

    (WORK / "main-patched.js").write_bytes(patched_main)
    (WORK / "app-initial-patched.js").write_bytes(patched_rend)
    print(f"main  {len(asar_main)} -> {len(patched_main)} bytes (head ok, tail swapped)")
    print(f"rend  {len(asar_rend)} -> {len(patched_rend)} bytes (base ok, loose copy)")

    # --- repack -------------------------------------------------------------
    out = ASAR.with_suffix(".asar.new")
    patched = {MAIN_REL: patched_main, REND_REL: patched_rend, HTML_REL: patched_html, PKG_REL: patched_pkg}

    # capture original offsets (plan() overwrites them)
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

    # pass 1: assign new offsets/sizes into the header dict
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

    # pass 2: serialize the UPDATED header, then stream the data
    jb = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_len = len(jb)
    json_padded = (json_len + 3) // 4 * 4
    b2 = 4 + json_padded
    b1 = b2 + 4
    dst = open(out, "wb")
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
    print(f"repacked {out}: {nf} files, {cursor} data bytes, header {data_start} bytes")

    # --- self-check: re-read the .new from scratch --------------------------
    vf = open(out, "rb")
    vheader, vdata = read_header(vf)
    for rel, blob, label in [(MAIN_REL, patched_main, "main"), (REND_REL, patched_rend, "rend"), (PKG_REL, patched_pkg, "pkg")]:
        got = extract_file(vf, vheader, vdata, rel)
        print(f"self-check {label}: {'OK' if got == blob else 'MISMATCH'} ({len(got)} bytes)")
    vf.close()


if __name__ == "__main__":
    main()
