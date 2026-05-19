#!/usr/bin/env python3

import gzip
import json
import logging
import os
import re
import shutil
import zipfile
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

PATH_BASE = Path(__file__).parent.resolve()
PATH_BASE_MODULE: Path = PATH_BASE / "base"
PATH_BUILD: Path = PATH_BASE / "build"
PATH_BUILD_TMP: Path = PATH_BUILD / "tmp"
PATH_DOWNLOADS: Path = PATH_BASE / "downloads"

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

# Architecture name mapping:
#   Florida / frida build arch  →  frida release filename arch
ARCH_MAP = {
    "android-arm": "arm",
    "android-arm64": "arm64",
    "android-x86": "x86",
    "android-x86_64": "x86_64",
}


def generate_version_code(tag: str) -> int:
    """Convert a tag like '17.9.6' or '17.9.6-1' to an integer version code."""
    parts = re.split(r"[-.]", tag)
    return int("".join(f"{int(p):02d}" for p in parts))


def write_module_prop(
    mod_dir: Path, frida_version: str, release_tag: str, github_repo: str
) -> None:
    content = (
        f"id=magisk-hluda\n"
        f"name=florida-zygisk (Florida)\n"
        f"version={release_tag}\n"
        f"versionCode={generate_version_code(release_tag)}\n"
        f"author=Exo1i (module) / Ylarod (Florida) / ViRb3 (template)\n"
        f"updateJson=https://github.com/{github_repo}/releases/latest/download/updater.json\n"
        f"description=Anti-detection Florida frida-server {frida_version} on boot (Magisk/KSU/APatch)\n"
    )
    (mod_dir / "module.prop").write_text(content, encoding="utf-8", newline="\n")
    log.info("Wrote module.prop")


def extract_gz(gz_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    log.info(f"Extracting {gz_path.name}  →  {dest_path.name}")
    with gzip.open(gz_path, "rb") as fin:
        dest_path.write_bytes(fin.read())
    dest_path.chmod(0o755)


def package_zip(mod_dir: Path, out_zip: Path) -> None:
    log.info(f"Creating ZIP: {out_zip.name}")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(mod_dir):
            for fname in files:
                if fname in ("placeholder", ".gitkeep"):
                    continue
                full = Path(root) / fname
                arcname = full.relative_to(mod_dir)
                zf.write(full, arcname=arcname)
    log.info(f"ZIP size: {out_zip.stat().st_size / 1_048_576:.1f} MB")


def write_updater_json(
    build_dir: Path, release_tag: str, frida_version: str, github_repo: str
) -> None:
    data = {
        "version": release_tag,
        "versionCode": generate_version_code(release_tag),
        "zipUrl": (
            f"https://github.com/{github_repo}/releases/download/"
            f"{release_tag}/florida-zygisk-{release_tag}.zip"
        ),
        "changelog": (f"https://github.com/{github_repo}/releases/tag/{release_tag}"),
    }
    out = build_dir / "updater.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="\n")
    log.info("Wrote updater.json")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    frida_version = os.environ.get("FRIDA_VERSION", "0.0.0")
    release_tag = os.environ.get("RELEASE_TAG", frida_version)
    github_repo = os.environ.get("GITHUB_REPO", "unknown/florida-zygisk")

    log.info(f"Building module  frida={frida_version}  tag={release_tag}")

    # Clean / prepare build tree
    if PATH_BUILD_TMP.exists():
        shutil.rmtree(PATH_BUILD_TMP)
    PATH_BUILD.mkdir(parents=True, exist_ok=True)

    # Copy module template
    shutil.copytree(PATH_BASE_MODULE, PATH_BUILD_TMP)

    # Write module.prop (overwrites the placeholder in the template)
    write_module_prop(PATH_BUILD_TMP, frida_version, release_tag, github_repo)

    # Extract florida-server binaries into files/
    files_dir = PATH_BUILD_TMP / "files"
    files_dir.mkdir(exist_ok=True)

    for build_arch, release_arch in ARCH_MAP.items():
        gz = PATH_DOWNLOADS / f"frida-server-{build_arch}.gz"
        if not gz.exists():
            raise FileNotFoundError(
                f"Missing artifact: {gz}\nAvailable: {list(PATH_DOWNLOADS.iterdir())}"
            )
        dest = files_dir / f"frida-server-{release_arch}"
        extract_gz(gz, dest)

    # Create the Magisk module ZIP
    out_zip = PATH_BUILD / f"florida-zygisk-{release_tag}.zip"
    package_zip(PATH_BUILD_TMP, out_zip)
    shutil.rmtree(PATH_BUILD_TMP)

    # Write updater.json for Magisk's auto-update mechanism
    write_updater_json(PATH_BUILD, release_tag, frida_version, github_repo)

    log.info("Done!")


if __name__ == "__main__":
    main()
