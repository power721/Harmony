# 在线音乐状态持久化

## 功能概述

Harmony 音乐播放器现在支持保存和恢复在线音乐页面的状态。当用户关闭应用并重新打开时，会自动恢复到之前的页面状态。

**重要特性**：不保存完整数据，只保存必要标识，恢复时重新获取数据。

## 保存的状态信息

以下状态会被持久化保存：

1. **搜索关键词**
   - 当前搜索框中的关键词
   - 配置键：`online_music.keyword`

2. **页面类型**
   - 当前所在页面的类型
   - 可能的值：
     - `top_list` - 排行榜页面（默认）
     - `search` - 搜索结果页面
     - `detail` - 详情页面
   - 配置键：`online_music.page_type`

3. **详情页面信息**
   - 详情类型：
     - `artist` - 歌手详情
     - `album` - 专辑详情
     - `playlist` - 歌单详情
     - `fav_songs` - 收藏的歌曲
     - `playlists` - 歌单列表（创建的歌单/收藏的歌单）
     - `albums` - 专辑列表（收藏的专辑）
     - `recommend_guess` - 猜你喜欢
     - `recommend_radar` - 雷达推荐
     - `recommend_home_feed` - 首页推荐
     - `recommend_newsong` - 新歌推荐
     - `recommend_songlist` - 推荐歌单
   - 详情 mid：歌手/专辑/歌单的唯一标识符
   - 详情数据：仅保存必要信息（推荐类型、标题等），不保存完整数据
   - 配置键：
     - `online_music.detail_type`
     - `online_music.detail_mid`
     - `online_music.detail_data`

## 使用场景

支持所有在线音乐页面的状态保存和恢复，包括：
- 搜索结果页面
- 歌手/专辑/歌单详情页
- 我的收藏（收藏的歌曲、创建的歌单、收藏的歌单、收藏的专辑）
- 推荐内容（猜你喜欢、雷达推荐、推荐歌单、新歌推荐、首页推荐）

## 技术实现

### 核心原则：不保存完整数据

**为什么？**
- 避免数据冗余和存储浪费
- 确保数据一致性（恢复时获取最新数据）
- 简化实现逻辑

**如何实现？**
- 只保存标识信息：推荐类型、标题等
- 恢复时从已加载的数据中获取

### 状态标志

使用 `_is_restoring_state` 标志来跟踪是否正在恢复详情页状态，阻止不必要的UI更新。

### 推荐恢复机制

从已加载的 `_recommendations` 字典中获取推荐数据，使用智能延迟策略确保数据就绪。

## 测试

运行测试：
```bash
uv run pytest tests/test_online_music_state.py -v
```
