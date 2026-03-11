# 构建指南

本目录包含用于构建 Harmony 音乐播放器可执行文件的跨平台脚本。

## 快速开始

### 自动检测平台构建

```bash
# Linux / macOS
./build.sh

# Windows (PowerShell)
.\build_windows.ps1

# Windows (CMD)
build_windows.bat

# 使用 Python 脚本（所有平台）
python build.py
```

### Conda 环境注意事项

如果在 Conda 环境中运行，可能会遇到 PyInstaller 兼容性问题。构建脚本已自动处理这些问题。

如果仍有问题，可以尝试：

```bash
# 方法 1：升级 PyInstaller 到最新版本
pip install --upgrade pyinstaller

# 方法 2：设置环境变量
PYINSTALLER_NO_CONDA=1 python build.py
```

## 构建脚本说明

| 脚本 | 平台 | 说明 |
|------|------|------|
| `build.py` | 跨平台 | Python 统一构建脚本，支持所有平台 |
| `build.sh` | Linux/macOS | 自动检测平台并调用对应脚本 |
| `build_linux.sh` | Linux | 构建可执行文件，支持创建 AppImage/DEB |
| `build_macos.sh` | macOS | 构建 .app 包和 DMG 安装包 |
| `build_windows.bat` | Windows | CMD 批处理脚本 |
| `build_windows.ps1` | Windows | PowerShell 脚本（推荐） |

## 前置要求

### 通用要求
- Python 3.8+
- pip
- 项目依赖 (`pip install -r requirements.txt`)
- PyInstaller (`pip install pyinstaller`)

### Linux 额外要求
```bash
# Ubuntu/Debian
sudo apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libpulse0 \
    libxcb1 \
    libxkbcommon-x11-0

# 可选：创建 AppImage
# 下载 appimagetool: https://github.com/AppImage/AppImageKit/releases
```

### macOS 额外要求
- Xcode Command Line Tools: `xcode-select --install`
- 可选：开发者证书（用于签名和公证）

### Windows 额外要求
- Visual C++ Build Tools（通常已随 Python 安装）
- 可选：Inno Setup（创建安装程序）
- 可选：7-Zip（创建便携版 ZIP）

## 构建选项

### Python 脚本 (`build.py`)

```bash
# 构建当前平台
python build.py

# 指定平台
python build.py linux
python build.py macos
python build.py windows

# 构建为目录模式（而非单文件）
python build.py --dir

# 不清理旧构建
python build.py --no-clean

# 调试模式
python build.py --debug

# 构建所有平台
python build.py --all
```

### Linux 脚本 (`build_linux.sh`)

```bash
# 基础构建
./build_linux.sh

# 创建 AppImage
./build_linux.sh --appimage

# 创建 DEB 包
./build_linux.sh --deb

# 创建所有格式
./build_linux.sh --all
```

### macOS 脚本 (`build_macos.sh`)

```bash
# 基础构建
./build_macos.sh

# 创建 DMG
./build_macos.sh --dmg

# 签名应用
./build_macos.sh --sign

# 公证应用（需要 Apple Developer 账户）
./build_macos.sh --notarize

# 创建 DMG 并签名
./build_macos.sh --all
```

### Windows PowerShell (`build_windows.ps1`)

```powershell
# 基础构建
.\build_windows.ps1

# 创建安装程序
.\build_windows.ps1 -Installer

# 创建便携版 ZIP
.\build_windows.ps1 -Zip

# 创建所有格式
.\build_windows.ps1 -Installer -Zip

# 不清理旧构建
.\build_windows.ps1 -Clean:$false

# 调试模式
.\build_windows.ps1 -Debug
```

## 输出目录

构建完成后，输出文件位于 `dist/` 目录：

```
dist/
├── Harmony              # Linux 可执行文件
├── Harmony-x.x.x-x86_64.AppImage  # Linux AppImage
├── Harmony.app/         # macOS 应用包
├── Harmony-x.x.x.dmg    # macOS DMG 安装包
├── Harmony.exe          # Windows 可执行文件
├── Harmony-x.x.x-portable.zip  # Windows 便携版
└── Harmony-x.x.x-setup.exe     # Windows 安装程序
```

## GitHub Actions CI/CD

项目包含 GitHub Actions 配置 (`.github/workflows/build.yml`)，支持：

- **自动构建**：推送标签时自动构建所有平台
- **手动触发**：可在 Actions 页面手动触发构建
- **PR 构建**：Pull Request 时自动构建测试

### 发布流程

1. 创建版本标签：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions 自动构建并创建 Release

3. 下载构建产物或从 Release 页面获取

## 图标文件

构建时会自动查找以下位置的图标：

```
icons/
├── icon.ico    # Windows
├── icon.icns   # macOS
└── icon.png    # Linux
```

如需自定义图标，请将图标文件放入上述位置。

## 故障排除

### PyInstaller 找不到模块

添加隐藏导入到 `build.py` 的 `hidden_imports` 列表。

### Linux 上缺少库

确保安装了所有系统依赖。查看错误信息，安装缺少的库。

### macOS 上无法打开应用

如果是未签名的应用，需要在"系统偏好设置 > 安全性与隐私"中允许打开。

### Windows 上被杀毒软件拦截

这是 PyInstaller 打包程序的常见问题。可以：
1. 添加白名单
2. 使用代码签名证书签名可执行文件

### 构建文件过大

PyInstaller 默认包含所有依赖。可以：
1. 使用 `--exclude-module` 排除不需要的模块
2. 使用目录模式 (`--onedir`) 而非单文件模式
3. 考虑使用 UPX 压缩（`pip install pyinstaller[encryption]`）

## 高级配置

### 自定义 PyInstaller 选项

编辑 `build.py` 文件中的 `build_executable()` 函数，添加自定义选项。

### 添加额外的数据文件

在 `build.py` 的 `collect_data_files()` 函数中添加：

```python
datas.append(("path/to/source", "destination/in/app"))
```

### 环境变量

- `HARMONY_VERSION`: 覆盖版本号
- `HARMONY_DEBUG`: 启用调试模式
