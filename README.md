# florida-zygisk — Florida frida-server on Boot

[![Build Status](https://img.shields.io/github/actions/workflow/status/thelok1s/florida-zygisk/build.yml?branch=main&label=Build)](actions/workflows/build.yml)
[![Latest Release](https://img.shields.io/github/v/release/thelok1s/florida-zygisk)](releases/latest)
[![Downloads](https://img.shields.io/github/downloads/thelok1s/florida-zygisk/total)](releases)

A Magisk module that automatically starts **[Florida](https://github.com/Ylarod/Florida)** — an
anti-detection build of frida-server — on boot.

Built on top of the excellent **[magisk-frida](https://github.com/ViRb3/magisk-frida)** module
template by ViRb3.

---

## What this is

| Layer | Source |
|-------|--------|
| Module installer/service scripts | [ViRb3/magisk-frida](https://github.com/ViRb3/magisk-frida) template |
| frida-server binary (patched) | Built from [Ylarod/Florida](https://github.com/Ylarod/Florida) patches applied to [frida/frida](https://github.com/frida/frida) source |

Florida applies source-level patches to frida before compilation, making the server harder to detect
via common heuristics (port, process name, memory maps, etc.).

## How updates work

A GitHub Actions workflow runs every **6 hours** and checks for new releases in both
[frida/frida](https://github.com/frida/frida) and [ViRb3/magisk-frida](https://github.com/ViRb3/magisk-frida).

When a new frida version is detected it **builds Florida from source** — we do not depend on
Florida's own CI releases — and publishes a new module ZIP here.

> **Why build from source?**  
> Florida's upstream CI has been unreliable. By cloning their `patches/` directory and applying
> them ourselves at build time we are independent of their release cadence.

## Supported architectures

`arm` · `arm64` · `x86` · `x86_64`

## Supported root solutions

Magisk ≥ 24 · KernelSU · APatch

## Installation

1. Download the latest `florida-zygisk-*.zip` from the [Releases](releases) page.
2. Flash via Magisk Manager / KSU / APatch.
3. Reboot. The Florida frida-server starts automatically at late-boot.

### Connecting

```bash
PORT=$(adb shell cat /data/local/tmp/frda-port.txt)
adb forward tcp:$PORT tcp:$PORT
frida -H 127.0.0.1:$PORT <target>
frida -U <target_package>
```

### Logs

```bash
adb shell cat /data/local/tmp/florida-zygisk.log
```

## Building locally

```bash
# 1. Build Florida frida-server binaries (requires Android NDK r27c+)
export ANDROID_NDK_ROOT=/path/to/ndk

git clone --recurse-submodules --branch <frida-tag> https://github.com/frida/frida
git clone https://github.com/Ylarod/Florida florida-repo

cd frida
for patch_dir in ../florida-repo/patches/*/; do
    subproject=$(basename "$patch_dir")
    cd subprojects/$subproject
    git am "$patch_dir"*.patch
    cd ../..
done

for arch in android-arm android-arm64 android-x86 android-x86_64; do
    mkdir build-$arch && cd build-$arch
    ../configure --host=$arch
    make subprojects/frida-core/server/frida-server
    cp subprojects/frida-core/server/frida-server ../downloads/frida-server-$arch
    gzip -9 ../downloads/frida-server-$arch
    cd ..
done

# 2. Package into the Magisk module ZIP
FRIDA_VERSION=<tag> RELEASE_TAG=<tag> GITHUB_REPO=you/flordia-zygisk python3 build.py
# Result: build/florida-zygisk-<tag>.zip
```

## Credits

- **[Ylarod/Florida](https://github.com/Ylarod/Florida)** — anti-detection patches and inspiration
- **[ViRb3/magisk-frida](https://github.com/ViRb3/magisk-frida)** — module template and structure
- **[frida/frida](https://github.com/frida/frida)** — the instrumentation toolkit itself
- **[Exo1i/flordia-zygisk](https://github.com/Exo1i/flordia-zygisk)** — original project concept
