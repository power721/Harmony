# Font Bundling - FAQ

## Q: 如果字体文件不存在，程序能正常工作吗？

**A: 可以！** 程序会优雅降级到使用系统字体。

### 工作原理

1. **字体加载器** (`FontLoader`) 在启动时尝试加载打包的字体
2. 如果字体文件不存在，会记录调试日志并继续运行
3. Qt 会自动使用系统默认字体作为后备

### 日志输出

**有字体文件时：**
```
[INFO] Loaded 7/7 bundled fonts
[DEBUG] Loaded font: Inter from /path/to/fonts/Inter/Inter-Regular.ttf
...
```

**没有字体文件时：**
```
[INFO] No bundled fonts found, using system fonts
[DEBUG] Font file not found: /path/to/fonts/Inter/Inter-Regular.ttf
...
```

### 应用行为差异

| 场景 | 有打包字体 | 无打包字体（系统字体） |
|------|-----------|---------------------|
| 西文字符 | Inter 字体 | 系统默认 sans-serif |
| 中文字符 | Noto Sans SC | 系统默认 CJK 字体 |
| Emoji | Noto Color Emoji | 系统默认 emoji 字体 |
| 跨平台一致性 | ✅ 完全一致 | ❌ 各平台不同 |
| 视觉效果 | 最佳 | 取决于系统字体 |

### 开发和生产环境

#### 开发环境
```bash
# 方式 1: 使用打包字体
./download_fonts.sh
uv run python main.py

# 方式 2: 使用系统字体（快速测试）
uv run python main.py  # 无需下载字体
```

#### 生产环境（PyInstaller 打包）
```bash
# 打包时会自动包含 fonts/ 目录
python build.py

# 生成的可执行文件包含所有字体
./dist/Harmony  # 字体已打包
```

### GitHub Actions CI/CD

在 GitHub Actions 中，字体文件已提交到 git 仓库，因此：
- ✅ 自动构建时包含所有字体
- ✅ 无需在 CI 中下载字体
- ✅ 构建产物跨平台一致

### 建议

- **开发阶段**: 可以下载字体获得最佳效果，也可以不下载快速测试
- **生产构建**: 必须包含字体文件（已通过 git 管理）
- **测试覆盖**: 两种场景都应该测试

### 代码实现细节

`FontLoader` 的错误处理策略：

```python
def load_fonts(self) -> None:
    """Load bundled fonts into application font database.

    If font files are not found, the application will fall back to
    system fonts. This allows the app to work in development without
    downloading fonts, though the appearance may vary across platforms.
    """
    # 检查文件存在性
    if full_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(full_path))
        if font_id != -1:
            # 成功加载
            logger.debug(f"Loaded font: {family}")
        else:
            # 加载失败（文件损坏等）
            logger.warning(f"Failed to load font: {full_path}")
    else:
        # 文件不存在，使用系统字体
        logger.debug(f"Font file not found: {full_path}")

    # 汇总结果
    if loaded_count > 0:
        logger.info(f"Loaded {loaded_count}/{len(fonts_to_load)} bundled fonts")
    else:
        logger.info("No bundled fonts found, using system fonts")
```

这种设计确保了：
1. **零配置启动** - 开发者无需下载字体即可运行
2. **优雅降级** - 缺少字体时自动使用系统字体
3. **最佳体验** - 有字体时获得一致的跨平台显示
4. **清晰日志** - 用户和开发者了解当前使用的字体来源
