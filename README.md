# florida-zygisk — Florida frida-server module

[![Build Status](https://img.shields.io/github/actions/workflow/status/thelok1s/florida-zygisk/build.yml?branch=main&label=Build)](actions/workflows/build.yml)
[![Latest Release](https://img.shields.io/github/v/release/thelok1s/florida-zygisk)](releases/latest)
[![Downloads](https://img.shields.io/github/downloads/thelok1s/florida-zygisk/total)](releases)

A Magisk / KSU / APatch module that automatically starts **[Florida](https://github.com/Ylarod/Florida)** —
an anti-detection build of frida-server — on boot.

Built on top of the **[magisk-frida](https://github.com/ViRb3/magisk-frida)** module template by ViRb3.

---

## About project

| Layer | Source |
|-------|--------|
| Module installer / service scripts | [ViRb3/magisk-frida](https://github.com/ViRb3/magisk-frida) template |
| frida-server binary (patched) | Built from [Ylarod/Florida](https://github.com/Ylarod/Florida) patches applied to [frida/frida](https://github.com/frida/frida) source |

Florida applies source-level patches to frida before compilation, making the server harder to detect
via common heuristics (port, process name, memory maps, etc.).

## How updates work

A GitHub Actions workflow runs **every week** and checks for a new frida release. When one is
detected it **builds Florida from source** and publishes a new module ZIP here.

> **Why build from source?**  
> Florida's upstream CI has been unreliable. By cloning their `patches/` directory and applying
> them ourselves we are independent of their release cadence.

## Requirements

* Architectures: `arm` · `arm64` · `x86` · `x86_64`
* Magisk ≥ 24 · KernelSU · APatch

## Installation

1. Download the latest `florida-zygisk-*.zip` from the [Releases](releases) page.
2. Flash via Magisk Manager / KSU / APatch.
3. Reboot. The Florida frida-server starts automatically at late-boot.

## Status & port

The module description shown in the module manager updates at runtime:

| State | Description field |
|-------|-------------------|
| Running | `Running on port <PORT> (PID=<PID>) - tap Action to toggle` |
| Stopped | `Stopped - tap Action to restart` |
| Error | `ERROR: <reason> - check log` |

You can also read the port from the log:

```bash
adb shell grep "frida-server started" /data/local/tmp/florida-zygisk.log | tail -1
# or read the description directly
adb shell grep "^description=" /data/adb/modules/florida-zygisk/module.prop
```

## Toggle (KSU Action button)

In KernelSU, the module manager shows an **Action** button next to florida-zygisk.
Tapping it toggles the server:

- **Running → tap →** server stops, description updates to `Stopped`
- **Stopped → tap →** server starts on a new random port, description updates with port & PID

## Connecting

Once the server is running, forward the port and connect:

```bash
# Get the current port
PORT=$(adb shell grep "^description=" /data/adb/modules/florida-zygisk/module.prop \
        | grep -oE '[0-9]{4,5}' | head -1)

adb forward tcp:$PORT tcp:$PORT
frida -H 127.0.0.1:$PORT <target>
```

## Logs

```bash
adb shell cat /data/local/tmp/florida-zygisk.log
```

## Building locally

```bash
# 1. Build Florida frida-server binaries (requires Android NDK r29+)
export ANDROID_NDK_ROOT=/path/to/ndk

git clone --recurse-submodules --branch <frida-tag> https://github.com/frida/frida
git clone https://github.com/Ylarod/Florida florida-repo

cd frida
FRIDA_ROOT="$(pwd)"
for patch_dir in ../florida-repo/patches/*/; do
    subproject=$(basename "$patch_dir")
    cd "$FRIDA_ROOT/subprojects/$subproject"
    git am "$patch_dir"*.patch
    cd "$FRIDA_ROOT"
done

for arch in android-arm android-arm64 android-x86 android-x86_64; do
    mkdir -p ../build-$arch && cd ../build-$arch
    ../frida/configure --host=$arch
    make subprojects/frida-core/server/frida-server
    cp subprojects/frida-core/server/frida-server ../downloads/frida-server-$arch
    gzip -9 ../downloads/frida-server-$arch
    cd ..
done

# 2. Package into the Magisk module ZIP
FRIDA_VERSION=<tag> RELEASE_TAG=<tag> GITHUB_REPO=thelok1s/florida-zygisk python3 build.py
# Result: build/florida-zygisk-<tag>.zip
```

## Credits

- **[Ylarod/Florida](https://github.com/Ylarod/Florida)** — anti-detection patches and inspiration
- **[ViRb3/magisk-frida](https://github.com/ViRb3/magisk-frida)** — module template and structure
- **[frida/frida](https://github.com/frida/frida)** — the instrumentation toolkit itself

## License

See [LICENSE](LICENSE)
