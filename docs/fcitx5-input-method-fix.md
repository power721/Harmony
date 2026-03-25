# Linux 下 fcitx5 中文输入法修复

## 问题

在 Linux 系统上，PySide6 应用默认无法使用 fcitx5 输入法切换中文。

## 原因

1. PySide6 自带的 Qt 插件目录缺少 fcitx5 输入法插件
2. 系统的 fcitx5-frontend-qt6 插件编译于 Qt 6.4.2
3. PySide6 使用不同版本的 Qt（如 6.11.0），版本不匹配导致符号错误：
   ```
   undefined symbol: _ZN22QWindowSystemInterface22handleExtendedKeyEventE..., version Qt_6_PRIVATE_API
   ```

## 解决方案

### 方案一：编译 fcitx5 插件（推荐）

运行提供的脚本编译匹配 PySide6 Qt 版本的 fcitx5 插件：

```bash
chmod +x scripts/build_fcitx5_qt6.sh
./scripts/build_fcitx5_qt6.sh
```

脚本会：
1. 安装编译依赖
2. 使用 aqtinstall 安装匹配的 Qt SDK
3. 从源码编译 fcitx5-qt6 插件
4. 安装到 PySide6 插件目录

### 方案二：使用 ibus 兼容模式

如果不想编译，可以安装 ibus 并配置 fcitx5 的 ibus 支持：

```bash
# 安装 ibus
sudo apt install ibus

# 设置环境变量
export QT_IM_MODULE=ibus
export GTK_IM_MODULE=ibus
export XMODIFIERS=@im=ibus

# 运行应用
python main.py
```

注意：此方案需要 fcitx5 支持 ibus 协议，可能需要额外配置。

### 方案三：降级 PySide6（不推荐）

降级 PySide6 到匹配系统 Qt 插件的版本：

```bash
pip install PySide6==6.4.2
```

缺点：失去新功能和 bug 修复。

## 验证

编译安装后，运行以下命令验证插件是否正确加载：

```bash
QT_DEBUG_PLUGINS=1 python main.py 2>&1 | grep -i fcitx
```

应该看到类似输出：
```
qt.core.library: ".../libfcitx5platforminputcontextplugin.so" loaded library
```

## 环境要求

- Linux Mint 22 / Ubuntu 24.04 (Noble)
- fcitx5-frontend-qt6 >= 5.1.4
- Python 3.11+

## 相关文件

- `main.py`: 设置输入法环境变量
- `scripts/build_fcitx5_qt6.sh`: fcitx5 插件编译脚本
