# Font Bundling System

## Overview

Harmony bundles fonts with the application to ensure consistent cross-platform display. This eliminates dependency on system-installed fonts and guarantees the same visual experience on Linux, macOS, and Windows.

## Architecture

### Components

1. **Font Files** (`fonts/` directory)
   - `Inter/` - Western UI font (Regular, Medium, Bold)
   - `NotoSansSC/` - Simplified Chinese font (Regular, Medium, Bold)
   - `NotoColorEmoji/` - Emoji font

2. **Font Loader** (`infrastructure/fonts/`)
   - `font_loader.py` - Singleton class that loads fonts into Qt's font database
   - `__init__.py` - Module exports

3. **Build Integration** (`build.py`)
   - Includes `fonts/` directory in PyInstaller bundle

### Loading Flow

```
main.py
  └─> FontLoader.instance().load_fonts()
       └─> QFontDatabase.addApplicationFont()
            └─> Fonts available to Qt
                 └─> QApplication.setFont()
                      └─> All widgets use bundled fonts
```

## Implementation Details

### FontLoader Class

**Location:** `infrastructure/fonts/font_loader.py`

**Responsibilities:**
- Load font files from disk
- Add fonts to Qt's application font database
- Handle both development and PyInstaller bundle modes
- Provide singleton access

**Key Methods:**

```python
FontLoader.instance().load_fonts()  # Load all bundled fonts
FontLoader.instance().is_loaded()   # Check if fonts loaded
FontLoader.instance().get_loaded_font_count()  # Number of fonts loaded
```

### Font Family Configuration

**Primary Font Stack:**
1. **Inter** - Western characters, numbers, symbols
2. **Noto Sans SC** - Simplified Chinese characters
3. **Noto Color Emoji** - Emoji characters

**Usage in Code:**

```python
from PySide6.QtGui import QFont

font = QFont()
font.setFamilies(["Inter", "Noto Sans SC", "Noto Color Emoji"])
widget.setFont(font)
```

Qt will automatically fall through the font stack:
1. Try Inter first
2. If character not found, try Noto Sans SC
3. If still not found, try Noto Color Emoji
4. Finally fall back to system default

### Path Resolution

**Development Mode:**
```python
Path(__file__).parent.parent.parent / 'fonts'
# Resolves to: /path/to/project/fonts/
```

**PyInstaller Bundle:**
```python
Path(sys._MEIPASS) / 'fonts'
# Resolves to: /tmp/_MEIxxxxxx/fonts/
```

## Font Selection Rationale

### Inter (Western UI)
- **Type:** Sans-serif proportional font
- **Strengths:** Excellent legibility, designed for screens, multiple weights
- **Coverage:** Latin, Cyrillic, Greek alphabets
- **Size:** ~300KB per weight

### Noto Sans SC (Chinese)
- **Type:** Sans-serif CJK font
- **Strengths:** Google's unified CJK design, excellent screen rendering
- **Coverage:** Simplified Chinese characters
- **Size:** ~7MB per weight

### Noto Color Emoji (Emoji)
- **Type:** Color bitmap font
- **Strengths:** Full emoji coverage, color rendering
- **Coverage:** All Unicode emoji characters
- **Size:** ~10-20MB (large!)

## Performance Considerations

### Font File Sizes

```
Inter-Regular.ttf:      ~300KB
Inter-Medium.ttf:       ~300KB
Inter-Bold.ttf:         ~300KB
NotoSansSC-Regular.ttf: ~7MB
NotoSansSC-Medium.ttf:  ~7MB
NotoSansSC-Bold.ttf:    ~7MB
NotoColorEmoji.ttf:     ~10-20MB
-----------------------------------
Total:                  ~32-42MB
```

### Optimization Options

1. **Subset Noto Color Emoji**
   - Use fonttools to create subset with only needed emoji
   - Example: Keep music notes, hearts, common symbols
   - Can reduce from 20MB to 1-2MB

   ```bash
   pip install fonttools
   pyftsubset NotoColorEmoji.ttf \
     --output-file=NotoColorEmoji-subset.ttf \
     --unicodes=U+1F3B5,U+1F3B6,U+266B,U+2764 \
     --layout-features='*'
   ```

2. **Use Variable Fonts**
   - Inter supports variable font format
   - Single file for all weights
   - Reduces Inter from 900KB to ~400KB

3. **Use Non-Color Emoji**
   - `NotoEmoji-Regular.ttf` (monochrome)
   - Size: ~2MB vs 20MB
   - Trade-off: No color emoji

## Build Integration

### PyInstaller Configuration

**In `build.py`:**

```python
def collect_data_files() -> list:
    datas = []
    # ... other data files ...

    # Add fonts directory
    fonts_dir = PROJECT_ROOT / "fonts"
    if fonts_dir.exists():
        datas.append((str(fonts_dir), "fonts"))

    return datas
```

This ensures fonts are included in the built executable.

### Verification

Check if fonts are bundled:

```bash
# Build the application
python build.py

# Verify fonts in dist (onedir mode)
ls dist/Harmony/fonts/

# Test built application
dist/Harmony/Harmony
```

## Testing

### Verify Font Loading

1. **Check console output:**
   ```
   [INFO] Loading fonts from: /path/to/fonts
   [INFO] Loaded 7 fonts successfully
   ```

2. **Test font rendering:**
   - Open application
   - Navigate to lyrics view (Chinese text)
   - Verify emoji display (if applicable)

3. **Test on clean system:**
   - Use VM or container without Inter/Noto fonts installed
   - Verify application still displays correctly

### Common Issues

**Fonts not loading:**
```
Warning: Font file not found: /path/to/fonts/Inter/Inter-Regular.ttf
```
- Run `./download_fonts.sh`
- Check fonts directory structure

**Wrong font displayed:**
- Check `setFamilies()` order
- Verify font files exist
- Check font names match file metadata

## Adding New Fonts

To add a new font:

1. **Download font file** (TTF or OTF format)

2. **Add to fonts directory:**
   ```
   fonts/NewFont/NewFont-Regular.ttf
   ```

3. **Update FontLoader:**
   ```python
   fonts_to_load = [
       # ... existing fonts ...
       ("NewFont/NewFont-Regular.ttf", "NewFont"),
   ]
   ```

4. **Update font family stack:**
   ```python
   font.setFamilies(["NewFont", "Inter", ...])
   ```

5. **Update documentation**

## License Compliance

All bundled fonts must be licensed for embedding and distribution.

**SIL Open Font License 1.1:**
- ✅ Free to bundle with applications
- ✅ Free to distribute
- ✅ No attribution required in UI
- ⚠️ Must include license text if redistributing font files separately

**Include in About Dialog:**
```
This application uses the following fonts:
- Inter (SIL Open Font License)
- Noto Sans SC (SIL Open Font License)
- Noto Color Emoji (SIL Open Font License)
```

## Future Improvements

1. **Font settings UI**
   - Allow users to customize font family
   - Allow users to adjust font size
   - Add font preview

2. **Lazy loading**
   - Load emoji font only when needed
   - Reduce startup time

3. **Font subsetting**
   - Create minimal emoji subset
   - Reduce bundle size by 15-18MB

4. **Variable font support**
   - Use Inter variable font
   - Reduce Inter bundle size by ~60%
