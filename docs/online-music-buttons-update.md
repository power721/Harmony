# 网络音乐播放按钮更新

## 修改日期
2026-03-29（最新更新）

## 背景
之前的网络歌曲详情页只有两个按钮："播放全部"和"全部加到队列"，但实际上它们只播放当前页的歌曲。用户需要更明确的按钮来区分当前页和所有页的操作，以及区分"插入队列"和"添加队列"的操作。

## 解决方案
添加了6个按钮，明确区分当前页和所有页的操作，以及插入队列和添加队列的操作：

### 当前页操作（第一组）

1. **立即播放** - ▶️ 立即播放
   - 播放当前页的歌曲
   - 从当前页第一首开始播放

2. **插入到队列** - 📥 插入到队列 ✨ 新增
   - 将当前页的歌曲插入到当前播放歌曲的下一首
   - 适用于立即接着播放

3. **添加到队列** - ➕ 添加到队列
   - 将当前页的歌曲添加到播放队列末尾
   - 适用于稍后播放

### 全部页操作（第二组）

4. **播放全部** - 播放全部
   - 播放所有页的歌曲（需要后台加载所有页）
   - 从第一首开始播放

5. **全部插入队列** - 📥 全部插入队列 ✨ 新增
   - 将所有页的歌曲插入到当前播放歌曲的下一首
   - 自动加载所有分页数据

6. **全部添加到队列** - ➕ 全部添加到队列
   - 将所有页的歌曲添加到播放队列末尾
   - 自动加载所有分页数据

## 使用场景

### 插入到队列 vs 添加到队列

- **插入到队列**：适合"我想紧接着听这些歌"
  - 插入位置：当前播放歌曲之后
  - 播放顺序：保持原有顺序

- **添加到队列**：适合"我稍后想听这些歌"
  - 添加位置：队列末尾
  - 播放顺序：保持原有顺序

### 当前页 vs 全部页

- **当前页操作**：快速操作，仅处理已加载的歌曲
- **全部页操作**：完整操作，自动加载所有分页数据（可能需要等待）

## 实现细节

### UI 层修改

#### 1. OnlineDetailView 信号
添加了新的信号来区分当前页和所有页的操作：

```python
# 当前页操作
play_all = Signal(list)  # List of OnlineTrack
insert_all_to_queue = Signal(list)
add_all_to_queue = Signal(list)

# 所有页操作
play_all_tracks = Signal(list)  # List of OnlineTrack (all tracks)
insert_all_tracks_to_queue = Signal(list)
add_all_tracks_to_queue = Signal(list)
```

#### 2. 按钮布局
修改 `_create_actions()` 方法，添加6个按钮：

```python
# 立即播放 (current page)
self._play_btn = QPushButton(t("play_now"))

# 插入到队列 (current page) ✨ 新增
self._insert_queue_btn = QPushButton(t("insert_to_queue"))

# 添加到队列 (current page)
self._add_queue_btn = QPushButton(t("add_to_queue"))

# 播放全部 (all pages)
self._play_all_btn = QPushButton(t("play_all"))

# 全部插入队列 (all pages) ✨ 新增
self._insert_all_queue_btn = QPushButton(t("insert_all_to_queue"))

# 全部加到队列 (all pages)
self._add_all_queue_btn = QPushButton(t("add_all_to_queue"))
```

#### 3. 按钮回调
实现区分当前页和所有页的逻辑：

```python
def _on_play_current(self):
    """播放当前页的歌曲"""
    if self._tracks:
        self.play_all.emit(self._tracks)

def _on_insert_current_to_queue(self):
    """插入当前页的歌曲到队列"""
    if self._tracks:
        self.insert_all_to_queue.emit(self._tracks)

def _on_add_current_to_queue(self):
    """添加当前页的歌曲到队列"""
    if self._tracks:
        self.add_all_to_queue.emit(self._tracks)

def _on_play_all(self):
    """播放所有页的歌曲"""
    if self._total_songs <= len(self._tracks):
        # 所有歌曲已加载
        self.play_all_tracks.emit(self._tracks)
    else:
        # 需要后台获取所有歌曲
        self._fetch_all_tracks(callback=lambda tracks: self.play_all_tracks.emit(tracks))

def _on_insert_all_to_queue(self):
    """插入所有页的歌曲到队列"""
    if self._total_songs <= len(self._tracks):
        # 所有歌曲已加载
        self.insert_all_tracks_to_queue.emit(self._tracks)
    else:
        # 需要后台获取所有歌曲
        self._fetch_all_tracks(callback=lambda tracks: self.insert_all_tracks_to_queue.emit(tracks))

def _on_add_all_to_queue(self):
    """添加所有页的歌曲到队列"""
    if self._total_songs <= len(self._tracks):
        # 所有歌曲已加载
        self.add_all_tracks_to_queue.emit(self._tracks)
    else:
        # 需要后台获取所有歌曲
        self._fetch_all_tracks(callback=lambda tracks: self.add_all_tracks_to_queue.emit(tracks))
```

### 后台加载所有歌曲

#### AllTracksWorker 类
新增 `AllTracksWorker` 线程类，用于在后台获取所有页的歌曲：

```python
class AllTracksWorker(QThread):
    """Background worker for fetching all tracks from all pages."""

    all_tracks_loaded = Signal(list)  # List of OnlineTrack

    def __init__(self, service: OnlineMusicService, detail_type: str, mid: str,
                 total_songs: int, page_size: int = 30):
        super().__init__()
        self._service = service
        self._detail_type = detail_type
        self._mid = mid
        self._total_songs = total_songs
        self._page_size = page_size

    def run(self):
        """Fetch all tracks from all pages."""
        # 循环获取所有页的数据
        # 支持三种类型：artist, album, playlist
```

#### 数据解析
正确解析歌曲数据为 `OnlineTrack` 对象：

```python
def _parse_songs(self, songs: List[Dict]) -> List[OnlineTrack]:
    """Parse song data into OnlineTrack objects."""
    tracks = []
    for song in songs:
        # 解析歌手信息为 OnlineSinger 对象列表
        singers = []
        for s in song.get("singer", []):
            singers.append(OnlineSinger(
                mid=s.get("mid", ""),
                name=s.get("name", "")
            ))

        # 解析专辑信息为 AlbumInfo 对象
        album_data = song.get("album", {})
        album = None
        if album_data or song.get("albummid"):
            album = AlbumInfo(
                mid=album_data.get("mid", song.get("albummid", "")),
                name=album_data.get("name", song.get("albumname", "")),
            )

        # 创建 OnlineTrack 对象
        track = OnlineTrack(
            mid=song.get("mid", ""),
            id=song.get("id"),
            title=song.get("name", song.get("title", "")),
            singer=singers,
            album=album,
            duration=song.get("duration", 0),
            pay_play=song.get("pay_play", 0)
        )
        tracks.append(track)
    return tracks
```

#### 加载状态处理
在加载所有歌曲时，禁用按钮并显示加载状态：

```python
def _fetch_all_tracks(self, callback):
    # 显示加载状态
    self._play_all_btn.setEnabled(False)
    self._insert_all_queue_btn.setEnabled(False)
    self._add_all_queue_btn.setEnabled(False)
    self._play_all_btn.setText(t("loading"))
    self._insert_all_queue_btn.setText(t("loading"))
    self._add_all_queue_btn.setText(t("loading"))

    # 启动后台线程
    self._all_tracks_worker = AllTracksWorker(...)
    self._all_tracks_worker.all_tracks_loaded.connect(
        lambda tracks: self._on_all_tracks_loaded(tracks, callback)
    )
    self._all_tracks_worker.start()

def _on_all_tracks_loaded(self, tracks, callback):
    """Handle all tracks loaded."""
    # Restore button state
    self._play_all_btn.setEnabled(True)
    self._insert_all_queue_btn.setEnabled(True)
    self._add_all_queue_btn.setEnabled(True)
    self._play_all_btn.setText(t("play_all"))
    self._insert_all_queue_btn.setText(t("insert_all_to_queue"))
    self._add_all_queue_btn.setText(t("add_all_to_queue"))

    # Call callback with all tracks
    callback(tracks)
```

### 翻译更新
在 `translations/zh.json` 和 `translations/en.json` 中添加新的翻译键：

```json
{
  "play_now": "▶️ 立即播放",
  "play_all": "播放全部",
  "insert_to_queue": "📥 插入到队列",
  "insert_all_to_queue": "📥 全部插入队列",
  "add_to_queue": "➕ 添加到队列",
  "add_all_to_queue": "➕ 全部添加到队列"
}
```

### 信号连接
在 `OnlineMusicView` 中连接新的信号：

```python
# 连接当前页操作
self._detail_view.play_all.connect(self._on_play_all_from_detail)
self._detail_view.insert_all_to_queue.connect(self._on_insert_all_to_queue_from_detail)
self._detail_view.add_all_to_queue.connect(self._on_add_all_to_queue_from_detail)

# 连接所有页操作
self._detail_view.play_all_tracks.connect(self._on_play_all_from_detail)
self._detail_view.insert_all_tracks_to_queue.connect(self._on_insert_all_to_queue_from_detail)
self._detail_view.add_all_tracks_to_queue.connect(self._on_add_all_to_queue_from_detail)
```

## 用户体验改进

1. **明确的按钮语义** - 用户可以清楚知道每个按钮的作用范围和位置
2. **插入队列功能** - 新增插入队列功能，用户可以选择立即接着播放或稍后播放
3. **加载状态提示** - 在获取所有歌曲时显示"加载中..."状态
4. **按钮禁用** - 加载过程中禁用相关按钮，防止重复操作
5. **后台加载** - 不阻塞UI线程，用户可以继续浏览其他内容
6. **图标区分** - 使用emoji图标帮助用户快速识别功能

## 按钮顺序

从左到右：

1. 立即播放（主要操作，使用 primaryBtn 样式）
2. 插入到队列（当前页）
3. 添加到队列（当前页）
4. 播放全部（全部页）
5. 全部插入队列（全部页）
6. 全部添加到队列（全部页）

## 测试
所有现有测试通过，没有引入回归问题。

## 相关文件
- `ui/views/online_detail_view.py` - 主要实现文件
- `ui/views/online_music_view.py` - 信号连接
- `translations/zh.json` - 翻译文件
- `domain/online_music.py` - 领域模型定义

## Bug 修复
修复了 `AllTracksWorker._parse_songs()` 方法中的数据解析问题：
- 正确将歌手数据解析为 `List[OnlineSinger]` 对象
- 使用 `AlbumInfo` 而不是 `OnlineAlbum` 来表示专辑信息
- 正确设置 `OnlineTrack` 的所有字段
