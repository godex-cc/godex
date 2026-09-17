# -*- coding: utf-8 -*-
"""Build the portable Windows zip: Godex-<version>-win32-x64.zip.

Stages a clean copy of app/ (dev backups, stray asar copies and logs excluded,
hardlinks used when possible), adds the portable launcher, the BYOK tool and a
first-run README, then zips it and writes a sha256 manifest next to the zip.

Excludes (guards also fire if the cruft ever comes back):
  app.asar.*            except app.asar itself and app.asar.unpacked/
  Godex.exe.pre-*       version-branding backups
  owl-app.ini.vendor-backup
  debug.log
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]          # GodexDesktop/
APP = ROOT / "app"
PKG = ROOT / "packaging"
VERSION = (PKG / "VERSION").read_text(encoding="utf-8").strip()
STAGE = PKG / "stage" / f"Godex-{VERSION}-win32-x64"
ZIP_PATH = PKG / "dist" / f"Godex-{VERSION}-win32-x64.zip"


def excluded(rel: Path, is_dir: bool) -> bool:
    name = rel.name
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "resources" and parts[1] == "app.asar.unpacked":
        return False                                   # native modules: keep
    if name == "app.asar":
        return False
    if len(parts) >= 2 and parts[0] == "resources" and parts[1].startswith("app.asar."):
        return True                                    # asar copies/backups
    if name.startswith("Godex.exe.pre-"):
        return True
    if name.endswith(".godex-bak") or ".pre-" in name:
        return True                                    # dev backup copies (any file)
    if name in ("owl-app.ini.vendor-backup", "debug.log"):
        return True
    return False


def stage_tree():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    dst_app = STAGE / "app"
    n_files = 0
    for dirpath, dirnames, filenames in os.walk(APP):
        rel_dir = Path(dirpath).relative_to(APP)
        dirnames[:] = [d for d in dirnames
                       if not excluded(rel_dir / d, True)]
        out_dir = dst_app / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        for fn in filenames:
            rel = rel_dir / fn
            if excluded(rel, False):
                continue
            src = Path(dirpath) / fn
            dst = out_dir / fn
            try:
                os.link(src, dst)                      # same volume: instant
            except OSError:
                shutil.copy2(src, dst)
            n_files += 1
    for extra in ("win/启动 Godex.cmd", "win/README.txt"):
        src = PKG / extra
        shutil.copy2(src, STAGE / src.name)
        n_files += 1
    shutil.copy2(ROOT / "godex-byok.py", STAGE / "godex-byok.py")
    n_files += 1
    return n_files


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


MUST_HAVE = [
    "app/Godex.exe",
    "app/chrome.dll",
    "app/resources/app.asar",
    "app/resources/godex",                             # engine (required!)
    "app/resources/Godex.exe",                         # engine godex.exe (required!)
    "app/resources/godex-code-mode-host.exe",
    "app/resources/godex-command-runner.exe",
    "app/resources/rg.exe",
    "app/resources/app.asar.unpacked/node_modules/better-sqlite3",
    "app/resources/native/windows-updater.node",
    "app/owl-shell-runtime.json",
    "启动 Godex.cmd",
    "godex-byok.py",
]


def main():
    n = stage_tree()
    print(f"staged {n} files -> {STAGE}")
    for rel in MUST_HAVE:
        if not (STAGE / rel.replace("/", os.sep)).exists():
            raise SystemExit(f"missing critical payload entry: {rel}")
    for bad in ("app/resources/app.asar.dbg", "app/Godex.exe.pre-verstring"):
        if (STAGE / bad.replace("/", os.sep)).exists():
            raise SystemExit(f"excluded file leaked into stage: {bad}")

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dirpath, dirnames, filenames in os.walk(STAGE):
            for fn in sorted(filenames):
                full = Path(dirpath) / fn
                arc = full.relative_to(STAGE.parent).as_posix()
                z.write(full, arc)

    manifest = {
        "artifact": ZIP_PATH.name,
        "version": VERSION,
        "platform": "win32-x64",
        "bytes": ZIP_PATH.stat().st_size,
        "sha256": sha256(ZIP_PATH),
        "stagedFiles": n,
        "criticalEntries": MUST_HAVE,
    }
    out_manifest = ZIP_PATH.with_suffix(".zip.manifest.json")
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH) as z:
        bad = z.testzip()
        assert bad is None, f"corrupt entry: {bad}"
        names = [nm.replace("\\", "/") for nm in z.namelist()]
    prefix = f"Godex-{VERSION}-win32-x64/"
    for rel in MUST_HAVE:
        arc = prefix + rel.replace(os.sep, "/")
        if (STAGE / rel.replace("/", os.sep)).is_dir():
            assert any(nm.startswith(arc + "/") for nm in names), f"zip missing dir {arc}"
        else:
            assert arc in names, f"zip missing {arc}"
    print(f"zip OK: {ZIP_PATH.name} {manifest['bytes']:,} bytes sha256={manifest['sha256'][:16]}...")
    print(f"manifest: {out_manifest}")


if __name__ == "__main__":
    main()
