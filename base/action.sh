#!/system/bin/sh
MODDIR="${0%/*}"
LOG="/data/local/tmp/florida-zygisk.log"

update_desc() {
    sed -i "s|^description=.*|description=$1|" "$MODDIR/module.prop"
}

if pgrep -f "frida-server" > /dev/null 2>&1; then
    echo "Stopping frida-server..."
    pkill -f "frida-server" 2>/dev/null
    sleep 1
    update_desc "Stopped - tap Action to restart"
    echo "Server stopped."
else
    ABI=$(getprop ro.product.cpu.abi)
    case "$ABI" in
        arm64-v8a) ARCH=arm64  ;;
        x86_64)    ARCH=x86_64 ;;
        x86*)      ARCH=x86    ;;
        *)         ARCH=arm    ;;
    esac
    FRIDA_BIN="$MODDIR/files/frida-server-$ARCH"
    if [ ! -f "$FRIDA_BIN" ]; then
        echo "ERROR: binary not found at $FRIDA_BIN"
        exit 1
    fi
    chmod 755 "$FRIDA_BIN"
    PORT=$(( ( RANDOM % 64511 ) + 1024 ))
    nohup "$FRIDA_BIN" --listen "0.0.0.0:$PORT" >> "$LOG" 2>&1 &
    SERVER_PID=$!
    sleep 2
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        update_desc "Frida running on port $PORT (PID=$SERVER_PID)"
        echo "Server started on port $PORT (PID=$SERVER_PID)"
    else
        echo "ERROR: frida-server failed to start – check $LOG"
        exit 1
    fi
fi
