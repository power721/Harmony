# Font Bundling Best Practices

## ✅ 推荐方案（已实现）

### 使用 Qt 的 applicationDirPath()

```python
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFontDatabase
from pathlib import Path

class FontLoader:
    def _get_font_dir(self) -> Path:
        """Get fonts directory path."""
        base_path = QCoreApplication.applicationDirPath()
        font_dir = Path(base_path) / "fonts"

        # Development mode fallback
        if not font_dir.exists():
            font_dir = Path(__file__).parent.parent.parent / "fonts"

        return font_dir

    def load_fonts(self):
        font_dir = self._get_font_dir()
        fonts = [
            "Inter/Inter-Regular.ttf",
            "Inter/Inter-Medium.ttf",
            "Inter/Inter-Bold.ttf",
            "NotoSansSC/NotoSansSC-Regular.ttf",
            "NotoSansSC/NotoSansSC-Medium.ttf",
            "NotoSansSC/NotoSansSC-Bold.ttf",
            "NotoColorEmoji/NotoColorEmoji.ttf",
        ]

        for font_path in fonts:
            full_path = font_dir / font_path
            if full_path.exists():
                QFontDatabase.addApplicationFont(str(full_path))
```

### 为什么使用 Qt 的方案？

| 方案 | PyInstaller onefile | PyInstaller onedir | AppImage | 开发模式 |
|-----|---------------------|-------------------|----------|---------|
| `sys._MEIPASS` | ✅ | ❌ | ❌ | ❌ |
| `sys.executable` | ❌ | ❌ | ❌ | ❌ |
| `QCoreApplication.applicationDirPath()` | ✅ | ✅ | ✅ | ⚠️ 需降级 |

**Qt 方案的优势：**
1. ✅ 跨平台一致性
2. ✅ 支持所有打包模式
3. ✅ Qt 原生支持，最可靠
4. ✅ 无需判断打包模式

## ❌ 不推荐的方案

### 方案 1: sys._MEIPASS

```python
# ❌ 只支持 PyInstaller onefile，不支持 onedir 和 AppImage
if getattr(sys, 'frozen', False):
    font_dir = Path(sys._MEIPASS) / 'fonts'
```

**问题：**
- AppImage 不设置 `sys._MEIPASS`
- PyInstaller onedir 模式不使用临时目录

### 方案 2: sys.executable

```python
# ❌ 路径不正确
font_dir = Path(sys.executable).parent / 'fonts'
```

**问题：**
- PyInstaller onefile: `sys.executable` 指向可执行文件，但资源在 `_MEIPASS`
- AppImage: 路径结构不同

### 方案 3: __file__ 相对路径

```python
# ❌ 打包后路径不对
font_dir = Path(__file__).parent.parent / 'fonts'
```

**问题：**
- 打包后 `__file__` 路径改变
- 无法找到资源

## 🎯 字体选择建议

### UI 应用（音乐播放器）

```
西文：Inter / Noto Sans
中文：Noto Sans SC / Noto Sans CJK SC
Emoji：Noto Color Emoji
```

**原因：**
- 比例字体更适合 UI 显示
- 可读性强，美观
- 多字重支持

### 代码编辑器 / 终端

```
西文：JetBrains Mono / Fira Code / Source Code Pro
中文：Noto Sans Mono CJK SC / Source Han Mono
```

**原因：**
- 等宽字体对齐整齐
- 适合显示代码
- 连字支持（部分字体）

## 📦 打包配置

### PyInstaller

```python
# build.py
def collect_data_files():
    datas = []

    # 添加字体目录
    fonts_dir = PROJECT_ROOT / "fonts"
    if fonts_dir.exists():
        datas.append((str(fonts_dir), "fonts"))

    return datas
```

### .gitignore

```gitignore
# 不忽略字体文件
!fonts/
!fonts/**/*.ttf
!fonts/**/*.otf
```

## 🧪 测试验证

### 开发模式测试

```bash
# 应该加载字体
uv run python main.py
# [INFO] Loaded 7/7 bundled fonts
```

### 打包测试

```bash
# 构建并测试
python build.py
./dist/Harmony
# [INFO] Loaded 7/7 bundled fonts

# 验证字体包含
pyi-archive_viewer dist/Harmony | grep font
```

### AppImage 测试

```bash
# 运行 AppImage
./Harmony-x86_64.AppImage
# [INFO] Loaded 7/7 bundled fonts

# 检查挂载目录
ls /tmp/.mount_Harmon*/usr/bin/_internal/fonts/
```

## 🔍 调试技巧

### 打印字体路径

```python
from PySide6.QtCore import QCoreApplication
from pathlib import Path

base_path = QCoreApplication.applicationDirPath()
font_dir = Path(base_path) / "fonts"
print(f"Application dir: {base_path}")
print(f"Font dir: {font_dir}")
print(f"Exists: {font_dir.exists()}")

# 列出字体文件
if font_dir.exists():
    for f in font_dir.rglob("*.ttf"):
        print(f"  {f}")
```

### 检查字体加载

```python
from PySide6.QtGui import QFontDatabase

font_id = QFontDatabase.addApplicationFont("/path/to/font.ttf")
if font_id == -1:
    print("Failed to load font")
else:
    families = QFontDatabase.applicationFontFamilies(font_id)
    print(f"Loaded font families: {families}")
```

## 📚 参考资料

- [PyInstaller Runtime Information](https://pyinstaller.org/en/stable/runtime-information.html)
- [Qt QCoreApplication::applicationDirPath](https://doc.qt.io/qt-6/qcoreapplication.html#applicationDirPath)
- [Noto Fonts](https://fonts.google.com/noto)
- [Inter Font](https://rsms.me/inter/)
