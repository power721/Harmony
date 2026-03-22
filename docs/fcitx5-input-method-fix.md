# Linux 下 fcitx5 中文输入法修复

## 问题

在 Linux 系统上，PySide6 应用默认无法使用 fcitx5 输入法切换中文。

## 原因

1. PySide6 自带的 Qt 插件目录缺少 fcitx5 输入法插件
2. 系统的 fcitx5-frontend-qt6 插件编译于 Qt 6.4.2
3. PySide6 6.6.0 使用 Qt 6.6.0，版本不匹配导致符号错误
4. PySide6 6.4.2 需要 Python < 3.12，而系统只有 Python 3.12

## 解决方案

创建 Python 3.11 的 conda 环境，安装 PySide6 6.4.2，复制系统 fcitx5 插件。

### 步骤

```bash
# 1. 创建 Python 3.11 环境
conda create -n harmony python=3.11 -y

# 2. 激活环境
conda activate harmony

# 3. 安装依赖（会安装 PySide6 6.6.0）
pip install -r requirements.txt

# 4. 降级 PySide6 到 6.4.2（匹配系统 fcitx5 插件）
pip install PySide6==6.4.2

# 5. 复制系统 fcitx5 插件到 PySide6
cp /usr/lib/x86_64-linux-gnu/qt6/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so \
   ~/Miniforge3/envs/harmony/lib/python3.11/site-packages/PySide6/Qt/plugins/platforminputcontexts/
```

### 运行应用

```bash
conda activate harmony
python main.py
```

## 注意事项

- 不要运行 `pip install -r requirements.txt`，否则会升级 PySide6 到 6.6.0
- 如需更新其他依赖，手动指定版本，避免升级 PySide6：
  ```bash
  pip install <package> --no-deps  # 不更新依赖
  ```
- 或在 requirements.txt 中锁定 PySide6 版本为 6.4.2

## 环境要求

- Ubuntu 24.04 (Noble)
- fcitx5-frontend-qt6 >= 5.1.4
- conda/Miniforge
- Python 3.11

## 相关文件

- `main.py`: 设置 `QT_IM_MODULE=fcitx5` 环境变量
