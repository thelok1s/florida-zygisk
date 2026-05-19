#!/system/bin/sh

MODDIR="${0%/*}"
LOG="/data/local/tmp/flordia-zygisk.log"

log() {
    echo "[flordia-zygisk] $*" >> "$LOG"
}

# ── Detect architecture ───────────────────────────────────────────────────────
ABI=$(getprop ro.product.cpu.abi)
case "$ABI" in
    arm64-v8a) ARCH=arm64  ;;
    x86_64)    ARCH=x86_64 ;;
    x86*)      ARCH=x86    ;;
    *)         ARCH=arm    ;;
esac

FRIDA_BIN="$MODDIR/files/frida-server-$ARCH"
PORT=$(( ( RANDOM % 64511 ) + 1024 ))

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [ ! -f "$FRIDA_BIN" ]; then
    log "ERROR: binary not found for arch=$ARCH at $FRIDA_BIN"
    exit 1
fi

chmod 755 "$FRIDA_BIN"

# ── Wait for Android to fully boot ───────────────────────────────────────────
until [ "$(getprop sys.boot_completed)" = "1" ]; do
    sleep 2
done
# Extra grace period so package manager etc. are settled
sleep 3

# ── Kill any existing frida-server instance ───────────────────────────────────
pkill -f "frida-server" 2>/dev/null
sleep 1

# ── Start Florida frida-server ────────────────────────────────────────────────
log "Starting Florida frida-server (arch=$ARCH) …"
nohup "$FRIDA_BIN" --listen "0.0.0.0:$PORT" >> "$LOG" 2>&1 &
SERVER_PID=$!

echo "$PORT" > /data/local/tmp/frda-port.txt

sleep 2
if kill -0 "$SERVER_PID" 2>/dev/null; then
    log "frida-server started (PID=$SERVER_PID)"
else
    log "ERROR: frida-server exited immediately – check $LOG"
fi
