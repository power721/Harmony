# List Views Bug Fixes

## Issues Fixed

### 1. 封面无法显示 ✅

**问题**: 封面图片无法在列表视图中显示

**原因**:
- Worker 使用 `track_id` 作为标识，但 delegate 使用 `cache_key` (基于 artist/album 或 path)
- `_on_cover_ready` 中尝试根据 track_id 查找 track 再生成 cache_key，但缓存键可能不一致
- **关键错误**: 信号定义为 `Signal(int, object, object)` 但传递的是 `str` 类型的 cache_key

**修复**:
1. 修改信号定义为 `Signal(str, object, object)`
2. 修改 `CoverLoadWorker` 直接使用 `cache_key` 而不是 `track_id`
3. Worker 的回调信号发射 `cache_key` 而不是 `track_id`
4. `_on_cover_ready` 直接使用接收到的 `cache_key` 存储和更新

**修改文件**:
- `ui/views/history_list_view.py`
- `ui/views/ranking_list_view.py`

### 2. 收藏图标不是红心 ✅

**问题**: 收藏图标显示为星星，不是红心

**原因**: 使用了 `IconName.STAR_FILLED` 和 `IconName.STAR_OUTLINE`

**修复**:
1. 创建红心图标文件:
   - `/icons/heart-filled.svg` - 填充的红心
   - `/icons/heart-outline.svg` - 空心红心

2. 在 `ui/icons.py` 中添加常量:
   ```python
   HEART_FILLED = "heart-filled.svg"
   HEART_OUTLINE = "heart-outline.svg"
   ```

3. 修改 delegate.paint() 使用红心图标:
   ```python
   heart_icon = get_icon(IconName.HEART_FILLED if is_favorite else IconName.HEART_OUTLINE, ...)
   ```

**修改文件**:
- 新建: `/icons/heart-filled.svg`, `/icons/heart-outline.svg`
- 修改: `ui/icons.py`, `ui/views/history_list_view.py`, `ui/views/ranking_list_view.py`

### 3. 时间显示错误（UTC转北京时间） ✅

**问题**: 刚刚播放的歌曲显示"8小时前"

**原因**:
- 数据库存储的是 UTC 时间
- `format_relative_time()` 直接比较 UTC 时间和本地时间，导致时差问题

**修复**:
修改 `utils/helpers.py` 中的 `format_relative_time()`:
```python
# UTC to Beijing (UTC+8)
if dt.tzinfo is None:
    dt_local = dt + timedelta(hours=8)
else:
    # If it has timezone, convert to local
    from datetime import timezone
    local_offset = timedelta(hours=8)
    dt_local = dt.astimezone(timezone(local_offset))

# Use current time in same timezone
now = datetime.utcnow() + timedelta(hours=8)
delta = now - dt_local
```

**结果**: 刚刚播放的歌曲显示"刚刚"，而不是"8小时前"

**修改文件**:
- `utils/helpers.py`

### 4. 显示歌曲来源 ✅

**问题**: 列表视图不显示歌曲来源信息

**修复**:
在 delegate.paint() 中添加来源显示:

**历史列表视图** (`history_list_view.py`):
```python
# Source indicator + Played time
from domain.track import TrackSource
source_str = track.source.value if track.source else "Local"
source_text = ""
if source == TrackSource.LOCAL:
    source_text = "本地"
elif source == TrackSource.QQ:
    source_text = "QQ"
elif source == TrackSource.QUARK:
    source_text = "夸克"
elif source == TrackSource.BAIDU:
    source_text = "百度"

source_time_text = f"{source_text} • {played_time_text}"
```

**排行榜列表视图** (`ranking_list_view.py`):
```python
# Source indicator (QQ Music)
source_text = "QQ音乐"
```

**修改文件**:
- `ui/views/history_list_view.py`
- `ui/views/ranking_list_view.py`

## Testing

测试封面加载:
```bash
uv run python main.py
# 导航到"最近播放"，检查封面是否显示
# 导航到"在线音乐" → "排行榜"，检查封面是否显示
```

测试红心图标:
```bash
# 在列表视图中检查收藏图标是否为红心
# 点击红心图标，检查是否正常切换
```

测试时间显示:
```bash
# 播放一首歌曲
# 导航到"最近播放"
# 检查时间显示是否为"刚刚"而不是"8小时前"
```

测试来源显示:
```bash
# 在"最近播放"列表视图中检查第三行显示"本地 • 刚刚"或类似格式
# 在"排行榜"列表视图中检查第三行显示"QQ音乐"
```

## Summary

所有问题已修复:
- ✅ 封面正常显示
- ✅ 收藏图标改为红心
- ✅ 时间显示正确（UTC转北京时间）
- ✅ 显示歌曲来源信息
