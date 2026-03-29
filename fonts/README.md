# Fonts Directory

This directory contains bundled fonts for cross-platform consistency.

## Required Fonts

The application requires the following font files:

### Inter (Western UI Font)
- `Inter/Inter-Regular.ttf`
- `Inter/Inter-Medium.ttf`
- `Inter/Inter-Bold.ttf`

**Source:** https://github.com/rsms/inter/releases
**License:** SIL Open Font License 1.1

### Noto Sans SC (Simplified Chinese)
- `NotoSansSC/NotoSansSC-Regular.ttf`
- `NotoSansSC/NotoSansSC-Medium.ttf`
- `NotoSansSC/NotoSansSC-Bold.ttf`

**Source:** https://fonts.google.com/noto/specimen/Noto+Sans+SC
**License:** SIL Open Font License 1.1

### Noto Color Emoji (Emoji Support)
- `NotoColorEmoji/NotoColorEmoji.ttf`

**Source:** https://github.com/googlefonts/noto-emoji/releases
**License:** SIL Open Font License 1.1

## Download Fonts

Run the download script from the project root:

```bash
./download_fonts.sh
```

This will automatically download all required fonts.

## Manual Download

If the script doesn't work, download manually:

1. **Inter**: Download from https://github.com/rsms/inter/releases
   - Extract and copy Regular, Medium, and Bold TTF files to `fonts/Inter/`

2. **Noto Sans SC**: Download from https://fonts.google.com/noto/specimen/Noto+Sans+SC
   - Extract and copy Regular, Medium, and Bold TTF files to `fonts/NotoSansSC/`

3. **Noto Color Emoji**: Download from https://github.com/googlefonts/noto-emoji/releases
   - Copy `NotoColorEmoji.ttf` to `fonts/NotoColorEmoji/`

## Font Loading

Fonts are loaded automatically by the application through `infrastructure/fonts/font_loader.py`:

1. On startup, `FontLoader` loads all bundled fonts into Qt's font database
2. The application sets the default font family to use bundled fonts
3. All UI components use the bundled fonts consistently

## Build Integration

The `build.py` script automatically includes the `fonts/` directory when building the executable.

## Font Size Optimization

**Note:** `NotoColorEmoji.ttf` is large (~10-20MB). For production builds, consider:
- Using a subset with only commonly used emoji
- Using the non-color variant `NotoEmoji-Regular.ttf` (smaller)

## License Compliance

All fonts use the SIL Open Font License 1.1, which allows:
- Free use in commercial and non-commercial projects
- Bundling with applications
- Modification and redistribution

Include license attribution in your application's About dialog or documentation.
