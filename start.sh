#!/usr/bin/env bash
set -e

echo "[INFO] Starting player..."

# =========================
# 🔍 检测 DBus 是否可用
# =========================
check_dbus() {
    if [[ -n "$DBUS_SESSION_BUS_ADDRESS" ]]; then
        return 0
    fi
    return 1
}

# =========================
# ✅ 使用 systemd DBus（首选）
# =========================
setup_system_dbus() {
    local uid=$(id -u)
    local bus_path="/run/user/$uid/bus"

    if [[ -S "$bus_path" ]]; then
        export DBUS_SESSION_BUS_ADDRESS="unix:path=$bus_path"
        echo "[INFO] Using system DBus: $DBUS_SESSION_BUS_ADDRESS"
        return 0
    fi

    return 1
}

# =========================
# 🧪 fallback: dbus-launch
# =========================
setup_dbus_launch() {
    if command -v dbus-launch >/dev/null 2>&1; then
        echo "[INFO] Starting DBus via dbus-launch..."

        eval "$(dbus-launch --sh-syntax)"

        export DBUS_SESSION_BUS_ADDRESS
        export DBUS_SESSION_BUS_PID

        echo "[INFO] DBus launched: $DBUS_SESSION_BUS_ADDRESS"
        return 0
    fi

    return 1
}

# =========================
# 🚀 初始化 DBus
# =========================
init_dbus() {
    if check_dbus; then
        echo "[INFO] DBus already available"
        return
    fi

    if setup_system_dbus; then
        return
    fi

    if setup_dbus_launch; then
        return
    fi

    echo "[WARN] No DBus available → MPRIS disabled"
}

# =========================
# 🎯 启动程序
# =========================
run_app() {
    echo "[INFO] Launching app..."

    # 👉 关键：确保 uv 继承环境变量
    exec env DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
        uv run main.py
}

# =========================
# 🔥 主流程
# =========================
init_dbus
run_app