# 在线音乐状态持久化

## 功能概述

Harmony 音乐播放器现在支持保存和恢复在线音乐页面的状态。当用户关闭应用并重新打开时，会自动恢复到之前的页面状态。

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
   - 详情 mid：歌手/专辑/歌单的唯一标识符
   - 详情数据：名称、封面 URL、歌手名称（专辑）、创建者（歌单）等
   - 配置键：
     - `online_music.detail_type`
     - `online_music.detail_mid`
     - `online_music.detail_data`

## 使用场景

### 场景 1：搜索后查看详情

1. 用户搜索"周杰伦"
2. 点击某个歌手进入歌手详情页
3. 关闭应用
4. 重新打开应用后，自动恢复到周杰伦的歌手详情页

### 场景 2：浏览排行榜

1. 用户在排行榜页面
2. 关闭应用
3. 重新打开应用后，停留在排行榜页面

### 场景 3：搜索结果页

1. 用户搜索"Taylor Swift"
2. 浏览搜索结果
3. 关闭应用
4. 重新打开应用后，自动恢复到搜索结果页面，关键词保持不变

### 场景 4：我的收藏 - 收藏的歌曲

1. 用户点击"我的收藏"卡片中的"收藏的歌曲"
2. 查看收藏的歌曲列表
3. 关闭应用
4. 重新打开应用后，自动恢复到收藏的歌曲列表页面

### 场景 5：我的收藏 - 创建的歌单

1. 用户点击"我的收藏"卡片中的"创建的歌单"
2. 查看创建的歌单列表
3. 关闭应用
4. 重新打开应用后，自动恢复到创建的歌单列表页面

### 场景 6：推荐 - 猜你喜欢

1. 用户点击"猜你喜欢"推荐卡片
2. 查看推荐的歌单列表
3. 关闭应用
4. 重新打开应用后，自动恢复到推荐的歌单列表页面

## 技术实现

### 状态标志

使用 `_is_restoring_state` 标志来跟踪是否正在恢复详情页状态：
- 在构造函数中检查配置，如果是详情页则设置为 `True`
- 阻止在恢复详情页时加载收藏和推荐区域
- 在用户点击返回按钮时重置为 `False`

### 配置管理

在 `system/config.py` 中添加了新的配置键和方法：

```python
# 配置键
ONLINE_MUSIC_KEYWORD = "online_music.keyword"
ONLINE_MUSIC_PAGE_TYPE = "online_music.page_type"
ONLINE_MUSIC_DETAIL_TYPE = "online_music.detail_type"
ONLINE_MUSIC_DETAIL_MID = "online_music.detail_mid"
ONLINE_MUSIC_DETAIL_DATA = "online_music.detail_data"
```

### 视图状态保存

`OnlineMusicView.save_state()` 方法：
- 保存当前搜索关键词
- 判断当前页面类型（排行榜/搜索结果/详情页）
- 检查是否在查看"我的收藏"或"推荐"内容（通过返回按钮可见性和收藏推荐区域隐藏状态判断）
- 保存详情页的状态信息，包括歌单列表和专辑列表

### 视图状态恢复

`OnlineMusicView.restore_state()` 方法：
- 读取保存的关键词并恢复到搜索框
- 根据页面类型恢复相应的页面：
  - 搜索页面：重新执行搜索
  - 详情页面：隐藏首页推荐区域，恢复详情页内容
    - `artist`/`album`/`playlist`：恢复到对应详情页
    - `fav_songs`：恢复收藏的歌曲列表（需要先加载收藏数据）
    - `playlists`/`albums`：恢复歌单列表或专辑列表
  - 排行榜：保持默认状态

### 详情页状态管理

`OnlineDetailView.get_state()` 和 `restore_state()` 方法：
- 获取当前详情页的类型、mid、名称等信息
- 根据保存的状态恢复到歌手/专辑/歌单详情页

### 主窗口集成

在 `MainWindow` 中：
- `_save_view_state()` 中调用 `OnlineMusicView.save_state()`
- `_restore_view_state()` 中延迟调用 `OnlineMusicView.restore_state()`，确保 UI 已准备好

### 返回按钮处理

`OnlineMusicView._on_back_from_detail()` 方法：
- 重置 `_is_restoring_state` 标志
- 如果收藏和推荐未加载，则加载它们
- 如果已加载，则显示它们

## 注意事项

1. **首页隐藏**：恢复到详情页时，会自动隐藏首页的收藏和推荐区域，避免界面混乱。

2. **延迟加载**：从详情页返回时，如果收藏和推荐未加载（因为恢复状态时阻止了加载），会自动加载它们。

3. **收藏歌曲恢复**：恢复"收藏的歌曲"视图时，需要先加载收藏数据，使用延迟调用确保数据加载完成后再显示。

4. **数据一致性**：保存的状态数据存储在数据库的 settings 表中，与应用其他配置统一管理。

5. **延迟恢复**：状态恢复使用 `QTimer.singleShot(200, ...)` 延迟执行，确保 UI 组件完全初始化后再恢复状态。

6. **容错处理**：如果保存的数据无效或缺失，会安全地回退到默认页面（排行榜）。

7. **提前设置标志**：在构造函数中就根据配置设置 `_is_restoring_state` 标志，确保在 UI 初始化时就能正确阻止收藏和推荐的加载。

8. **导航状态检测**：通过检查返回按钮的可见性和收藏推荐区域的隐藏状态，判断是否在查看"我的收藏"或"推荐"内容。

## 测试

相关测试位于 `tests/test_online_music_state.py`，覆盖：
- 关键词保存和加载
- 页面类型保存和加载
- 详情类型、mid、数据的保存和加载
- 完整场景测试

运行测试：
```bash
uv run pytest tests/test_online_music_state.py -v
```
