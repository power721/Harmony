# QQ音乐推荐功能调查结果

## 问题描述

用户报告"看不到推荐，只有4个card"。

## 问题分析

### 发现的问题

1. **`get_home_feed()` 数据解析错误**
   - API返回结构：`v_shelf[].v_niche[].v_card[]`（type=200是歌曲）
   - 原代码尝试从：`v_shelf[0]['item_list']` 提取（不存在）
   - 结果：返回空列表

2. **推荐区域默认隐藏**
   - `_recommend_section` 初始化时调用 `hide()`
   - 数据加载后没有显式调用 `show()`
   - 虽然 `load_recommendations()` 内部会调用 `show()`，但显式调用更清晰

### 数据流程

```
QQMusicClient.get_home_feed()
  ↓ 返回原始API响应
QQMusicService.get_home_feed()
  ↓ 解析嵌套结构，提取type=200的卡片
OnlineMusicView._on_recommend_ready()
  ↓ 接收歌曲列表
OnlineMusicView._display_recommendations()
  ↓ 创建推荐卡片数据
RecommendSection.load_recommendations()
  ↓ 显示推荐卡片
用户看到5个推荐卡片
```

## 修复方案

### 1. 修复数据解析逻辑

**文件**: `services/cloud/qqmusic/qqmusic_service.py:862-918`

**修改前**:
```python
# 尝试从 v_shelf[0]['item_list'] 提取
for shelf in shelves:
    items = shelf.get('item_list', [])
    if items:
        return items
```

**修改后**:
```python
# 遍历 v_shelf[].v_niche[].v_card[]，提取type=200的歌曲卡片
for shelf in result['v_shelf']:
    for niche in shelf.get('v_niche', []):
        for card in niche.get('v_card', []):
            if card.get('type') == 200:  # 歌曲卡片
                song = {
                    'id': card.get('id'),
                    'songid': card.get('id'),
                    'title': card.get('title', ''),
                    'subtitle': card.get('subtitle', ''),
                    'singer': card.get('subtitle', ''),  # 歌手名
                    'cover': card.get('cover', ''),
                    'time': card.get('time', 0),
                    'mid': card.get('subid', ''),
                }
                songs.append(song)
```

### 2. 显式显示推荐区域

**文件**: `ui/views/online_music_view.py:1337-1339`

**修改前**:
```python
if cards:
    self._recommend_section.load_recommendations(cards)
```

**修改后**:
```python
if cards:
    self._recommend_section.load_recommendations(cards)
    # Show recommendations section after loading
    self._recommend_section.show()
```

## 验证结果

### API数据统计

| 推荐类型 | 数量 | 数据结构 |
|---------|------|---------|
| home_feed | 36首 | 简化歌曲结构（singer是字符串） |
| guess_recommend | 5首 | 完整歌曲结构（singer是列表） |
| radar_recommend | 10首 | 嵌套结构（Track字段） |
| recommend_songlist | 25个 | 嵌套结构（Playlist字段） |
| recommend_newsong | 65首 | 完整歌曲结构（singer是列表） |

### 示例数据

**home_feed 第一首歌**:
```json
{
  "id": 5665622,
  "songid": 5665622,
  "title": "晴",
  "subtitle": "汪苏泷",
  "singer": "汪苏泷",
  "cover": "https://y.gtimg.cn/music/photo_new/T002R150x150M000...",
  "mid": "k0022vbocvs"
}
```

## 推荐区域 vs 收藏区域

用户看到的界面结构：

```
┌─────────────────────────────────────┐
│  我的收藏 (4个卡片)                  │  ← favorites_section
│  [我喜欢] [创建的歌单] [收藏歌单] [收藏专辑] │
├─────────────────────────────────────┤
│  推荐 (5个卡片)                      │  ← recommend_section
│  [主页推荐] [猜你喜欢] [雷达] [歌单] [新歌] │
└─────────────────────────────────────┘
```

- **收藏区域**: 显示4个卡片（我喜欢、创建的歌单、收藏歌单、收藏专辑）
- **推荐区域**: 显示5个卡片（主页推荐、猜你喜欢、雷达推荐、推荐歌单、新歌）

修复后，两个区域都会正确显示。

## 相关文件

- `services/cloud/qqmusic/client.py:666-673` - API客户端
- `services/cloud/qqmusic/qqmusic_service.py:862-918` - 服务层解析
- `ui/views/online_music_view.py:1313-1339` - UI显示逻辑
- `ui/widgets/recommend_card.py` - 推荐卡片组件

## 测试方法

```python
from services.cloud.qqmusic import QQMusicService

service = QQMusicService()

# 测试所有推荐API
print('home_feed:', len(service.get_home_feed()))      # 36
print('guess:', len(service.get_guess_recommend()))     # 5
print('radar:', len(service.get_radar_recommend()))     # 10
print('songlist:', len(service.get_recommend_songlist())) # 25
print('newsong:', len(service.get_recommend_newsong()))   # 65
```
