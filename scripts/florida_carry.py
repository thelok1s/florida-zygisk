#!/usr/bin/env python3
"""
florida_carry.py — local carry-fixes applied on top of Florida's patches.

Why this exists
---------------
This module builds Florida (anti-detection frida-server) from source by cloning
frida + applying the patches from https://github.com/Ylarod/Florida . Florida's
patches frequently bit-rot against new frida releases, and the *previous* workflow
masked that with `git am --reject || git am --skip`, which silently dropped hunks
and shipped broken/inconsistent binaries (see issue #1: "Failed to spawn: undefined
symbol: main").

This script applies two idempotent, content-anchored repairs so the build stays
correct regardless of whether Florida's patches applied cleanly. Each repair is a
no-op when the intended change is already present (e.g. once Florida fixes upstream).

  1. rpc_obfuscation  — keep Florida's `getRpcStr()` "frida:rpc" string obfuscation
                        self-consistent (definition present whenever it is used).
                        This is what bit-rotted against frida 17.16.x and broke CI.
  2. anti_anti_frida  — make the embed-time `anti-anti-frida.py` invocation robust
                        (env-var path + fail-hard). Without it the agent keeps the
                        `frida_agent_main` symbol while the server looks up `main`,
                        producing "Failed to spawn: undefined symbol: main" (#1).

Run from the frida *source* root (the directory that contains subprojects/frida-core),
e.g.  `cd frida && python3 ../scripts/florida_carry.py`.
"""

import os
import re
import sys
from pathlib import Path


def _frida_root() -> Path:
    # subprojects/frida-core should exist under the frida source root.
    root = Path.cwd()
    if not (root / "subprojects" / "frida-core").is_dir():
        sys.exit(
            f"florida_carry: must run from the frida source root (no "
            f"subprojects/frida-core under {root})"
        )
    return root


# ──────────────────────────────────────────────────────────────────────────────
# 1. rpc.vala — Florida "string_frida_rpc" obfuscation
# ──────────────────────────────────────────────────────────────────────────────

# Mirrors Florida's patches/frida-core/0001-Florida-string_frida_rpc.patch.
# "Wm5KcFpHRTZjbkJq" base64-decodes twice to the literal "frida:rpc".
_GETRPC_METHOD = (
    "\t\tpublic string getRpcStr(bool quote){\n"
    "\t\t\tstring result = (string) GLib.Base64.decode("
    "(string) GLib.Base64.decode(\"Wm5KcFpHRTZjbkJq\"));\n"
    "\t\t\tif(quote){\n"
    "\t\t\t\treturn \"\\\"\" + result + \"\\\"\";\n"
    "\t\t\t}else{\n"
    "\t\t\t\treturn result;\n"
    "\t\t\t}\n"
    "\t\t}\n"
)

# Stable anchors that survive frida reshuffles (constructor body + literal strings).
_RPC_CALL_SITES = [
    ('.add_string_value ("frida:rpc")', '.add_string_value (getRpcStr(false))'),
    ('if (json.index_of ("\\"frida:rpc\\"") == -1)',
     'if (json.index_of (getRpcStr(true)) == -1)'),
    ('if (type == null || type != "frida:rpc")',
     'if (type == null || type != getRpcStr(false))'),
]


def rpc_obfuscation(root: Path) -> None:
    """Ensure Florida's getRpcStr() obfuscation is present AND self-consistent.

    Handles every outcome of the (now strict) patch step:
      * Florida patch fully applied   -> no-op.
      * Florida patch wholly skipped  -> adds definition + call sites.
      * Florida patch partially there -> repairs whichever half is missing.
    """
    rpc = root / "subprojects" / "frida-core" / "lib" / "base" / "rpc.vala"
    if not rpc.exists():
        sys.exit(f"florida_carry: rpc.vala not found at {rpc}")
    src = rpc.read_text()
    orig = src

    # (a) Definition: insert once, right after the RpcClient constructor.
    if "public string getRpcStr" not in src:
        anchor = "\t\t\tObject (peer: peer);\n\t\t}\n"
        if anchor not in src:
            sys.exit(
                "florida_carry: cannot find rpc.vala constructor anchor "
                "('Object (peer: peer);') — frida restructured things; "
                "manual fix needed."
            )
        src = src.replace(anchor, anchor + "\n" + _GETRPC_METHOD, 1)

    # (b) Call sites: replace literal "frida:rpc" usages (idempotent).
    for old, new in _RPC_CALL_SITES:
        src = src.replace(old, new)

    if src != orig:
        rpc.write_text(src)
        print("florida_carry: rpc.vala — ensured getRpcStr obfuscation present")
    else:
        print("florida_carry: rpc.vala — already consistent")


# ──────────────────────────────────────────────────────────────────────────────
# 2. embed-agent.py — robust anti-anti-frida.py invocation
# ──────────────────────────────────────────────────────────────────────────────

# The robust block we want in place of Florida's fragile one. Indented to sit at
# the same level as Florida's insertion (12 spaces, sibling of the agent if/else).
_CARRY_BLOCK = '''            # --- florida-zygisk carry: robust anti-anti-frida invocation ---
            import os as _carry_os, sys as _carry_sys
            _carry_script = _carry_os.environ.get("FLORIDA_ANTI_ANTI_FRIDA")
            if not _carry_script:
                _carry_script = _carry_os.path.join(
                    _carry_os.path.dirname(_carry_os.path.realpath(_carry_sys.argv[0])),
                    "anti-anti-frida.py")
            _carry_rc = _carry_os.system(
                "python3 " + _carry_script + " " + str(priv_dir / f"frida-agent-{flavor}.so"))
            if _carry_rc != 0:
                raise SystemExit(
                    "florida-zygisk: anti-anti-frida.py failed (rc=%d); agent symbol "
                    "rename did not happen -> would cause: Failed to spawn, undefined symbol main"
                    % _carry_rc)
            print("anti-anti-frida finished (florida-zygisk carry)")
            # --- end carry ---
'''

# Florida's 0010-exec-anti-anti-frida.py.patch adds exactly this (fragile) block.
_FLORIDA_BLOCK_RE = re.compile(
    r'            import os\n'
    r'            custom_script=str\(output_dir\).*?'
    r'print\("anti-anti-frida error\. Code:?", return_code\)\n'
    r'[ \t]*\n',
    re.S,
)

_CARRY_MARKER = "# --- florida-zygisk carry: robust anti-anti-frida invocation ---"


def anti_anti_frida(root: Path) -> None:
    """Make embed-agent.py run anti-anti-frida.py reliably and fail hard on error."""
    eap = root / "subprojects" / "frida-core" / "src" / "embed-agent.py"
    if not eap.exists():
        sys.exit(f"florida_carry: embed-agent.py not found at {eap}")
    src = eap.read_text()
    orig = src

    # Already carried (idempotent refresh).
    if _CARRY_MARKER in src:
        src = re.sub(
            re.escape(_CARRY_MARKER) + r".*?# --- end carry ---\n",
            _CARRY_BLOCK,
            src,
            count=1,
            flags=re.S,
        )
    elif _FLORIDA_BLOCK_RE.search(src):
        # Florida's 0010 applied — replace its fragile block with ours.
        src = _FLORIDA_BLOCK_RE.sub(_CARRY_BLOCK, src, count=1)
    elif "anti-anti-frida" in src:
        # 0010 applied but in an unrecognised shape — don't guess, surface it.
        print("florida_carry: embed-agent.py has an unrecognised anti-anti-frida "
              "block — leaving untouched (review manually)")
    else:
        # 0010 didn't apply at all — insert our block at the 12-space level,
        # right before the Linux/Android branch's `embedded_assets += [...]`.
        # Target that specific occurrence by anchoring on the unique
        # `frida-agent-{flavor}.so` line that precedes it.
        marker = 'embedded_agent = priv_dir / f"frida-agent-{flavor}.so"'
        midx = src.find(marker)
        eidx = src.find("embedded_assets += [embedded_agent]", midx) if midx != -1 else -1
        if midx != -1 and eidx != -1:
            # Walk back to the start of the `embedded_assets` line.
            lstart = src.rfind("\n", 0, eidx) + 1
            src = src[:lstart] + _CARRY_BLOCK + src[lstart:]
        else:
            print("florida_carry: embed-agent.py — no insertion anchor for "
                  "anti-anti-frida; skipping (post-build verify will catch a "
                  "missing rename)")

    if src != orig:
        eap.write_text(src)
        print("florida_carry: embed-agent.py — installed robust anti-anti-frida hook")
    else:
        print("florida_carry: embed-agent.py — already robust")


def main() -> None:
    root = _frida_root()
    rpc_obfuscation(root)
    anti_anti_frida(root)
    _assert_consistent(root)
    print("florida_carry: done")


def _assert_consistent(root: Path) -> None:
    """Fail fast (before the long compile) if a carry-repaired file is still
    self-inconsistent. This is the cheap, early gate; the workflow's post-build
    'Verify Florida patches took effect' step is the final binary-level gate."""
    rpc = root / "subprojects" / "frida-core" / "lib" / "base" / "rpc.vala"
    if rpc.exists():
        src = rpc.read_text()
        if "getRpcStr(" in src and "public string getRpcStr" not in src:
            sys.exit("florida_carry: FATAL — getRpcStr used but not defined in rpc.vala")
    eap = root / "subprojects" / "frida-core" / "src" / "embed-agent.py"
    if eap.exists() and "custom_script=str(output_dir)" in eap.read_text():
        sys.exit("florida_carry: FATAL — fragile anti-anti-frida path still in embed-agent.py")
    print("florida_carry: consistency check OK")


if __name__ == "__main__":
    main()
