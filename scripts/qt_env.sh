#!/usr/bin/env bash

# ==========================================
# Qt Runtime Environment (CI + Local Safe)
# ==========================================

# 1️⃣ 检测是否有显示环境
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    echo "[QtEnv] No display detected → using offscreen"
    export QT_QPA_PLATFORM=offscreen
else
    echo "[QtEnv] Display detected → using system default"
fi

# 2️⃣ fallback（极端情况）
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

# 3️⃣ Qt plugin debug（CI 开启）
if [ "$CI" = "true" ]; then
    export QT_DEBUG_PLUGINS=1
fi

# 4️⃣ 禁止 Qt 用系统插件（避免污染）
export QT_PLUGIN_PATH=""

# 5️⃣ 强制软件渲染（避免 GPU 问题）
export QT_OPENGL=software

# 6️⃣ 修复 QtMultimedia（某些环境必须）
export QT_MEDIA_BACKEND=ffmpeg

# 7️⃣ 避免 XDG 报错
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-root}"
mkdir -p "$XDG_RUNTIME_DIR"

echo "[QtEnv] QT_QPA_PLATFORM=$QT_QPA_PLATFORM"