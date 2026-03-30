# Queue Source Display Feature

## Overview
This feature adds visual indicators for track sources in the playback queue, making it easy to identify where each track originates from.

## Implementation Details

### Changes Made
1. **Enhanced Queue Item Display**
   - Added source indicator below the artist/album line
   - Increased font sizes for better readability:
     - Title: 13px → 15px
     - Artist/Album: 11px → 13px
     - Source: 11px
   - Increased item height: 72px → 82px

2. **Source Types Displayed**
   - 本地文件 (Local File) - for local tracks
   - QQ音乐 (QQ Music) - for QQ Music online tracks
   - 夸克网盘 (Quark Cloud) - for Quark cloud storage tracks
   - 百度网盘 (Baidu Cloud) - for Baidu cloud storage tracks

### Technical Implementation

#### Modified Files
- `ui/views/queue_view.py` - QueueItemDelegate.paint() method
- `tests/test_queue_delegate.py` - Updated test expectations

#### Code Changes
The `QueueItemDelegate.paint()` method now:
1. Extracts the `source` field from track data
2. Converts it to `TrackSource` enum
3. Maps to localized text using existing i18n keys
4. Renders the source text in a third line below artist/album

#### Font Size Adjustments
```python
# Title font
font.setPixelSize(15)  # was 13

# Artist/Album font
font.setPixelSize(13)  # was 11

# Source font
font.setPixelSize(11)
```

#### Layout Changes
```python
# Item height
def sizeHint(self, option, index):
    return QSize(0, 82)  # was 72

# Cover art position
cover_rect = QRect(x + 2, rect.top() + 9, ...)  # was + 4

# Title position
title_rect = QRect(x, rect.top() + 10, ...)  # was + 14

# Artist/Album position
info_rect = QRect(x, rect.top() + 32, ...)  # was + 38

# Source position
source_rect = QRect(x, rect.top() + 52, ...)  # new
```

### Internationalization
The feature uses existing translation keys:
- `source_local` - "本地文件" / "Local File"
- `source_qq` - "QQ音乐" / "QQ Music"
- `source_quark` - "夸克网盘" / "Quark Cloud"
- `source_baidu` - "百度网盘" / "Baidu Cloud"

These keys were already present in `translations/zh.json` and `translations/en.json`.

### Testing
All existing tests were updated to accommodate the new item height:
- `test_size_hint` - Updated expected size from 72 to 82
- `test_paint_does_not_crash` - Updated pixmap height from 72 to 82
- All 1055 tests pass successfully

## User Benefits
1. **Clear Source Identification** - Users can immediately see where each track comes from
2. **Better Readability** - Larger fonts make text easier to read
3. **Consistent Design** - Maintains the existing visual style while adding information
4. **Internationalized** - Works with both English and Chinese interfaces

## Future Enhancements
Potential improvements could include:
- Color-coded source badges
- Icons for each source type
- Filter by source in queue view
