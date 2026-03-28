# QQ音乐主页推荐修复 - 最终版本

## 问题

用户报告："看不到推荐，只有4个card"

## 根本原因分析

### 原因1: `get_home_feed()` 解析逻辑错误

**错误理解**:
最初认为 `get_home_feed()` 应该返回歌曲列表

**正确理解**:
根据QQ音乐API设计（参考Node.js代码），`get_home_feed()` 返回的是**推荐卡片**列表，包括：
- 歌单卡片 (type=500)
- 榜单卡片 (type=1000)
- 猜你喜欢卡片 (type=700)
- 单曲卡片 (type=200) - 仅"大家都在听"部分
- 特殊功能卡片 (type=900)

**API响应结构**:
```json
{
  "v_shelf": [
    {
      "id": 301,
      "v_niche": [
        {
          "v_card": [
            {
              "type": 700,
              "title": "猜你喜欢",
              "id": 99,
              ...
            }
          ]
        }
      ]
    }
  ]
}
```

### 原因2: 凭证检查错误

`_has_qqmusic_credential()` 方法只检查配置文件，未检查已初始化的 `qqmusic_service.credential`，导致即使有凭证也返回 False。

## 修复方案

### 修复1: 更新 `get_home_feed()` 方法

**文件**: `services/cloud/qqmusic/qqmusic_service.py:862-922`

**修改**:
```python
def get_home_feed(self) -> List[Dict[str, Any]]:
    """获取主页推荐卡片数据（歌单、榜单等）."""
    result = self.client.get_home_feed()

    if isinstance(result, dict) and 'v_shelf' in result:
        cards = []
        for shelf in result['v_shelf']:
            for niche in shelf.get('v_niche', []):
                for card in niche.get('v_card', []):
                    card_type = card.get('type')
                    # Skip special cards (type=-1)
                    if card_type == -1:
                        continue

                    cards.append({
                        'id': card.get('id'),
                        'title': card.get('title', ''),
                        'subtitle': card.get('subtitle', ''),
                        'cover': card.get('cover', ''),
                        'type': card_type,
                        'jumptype': card.get('jumptype'),
                    })
        return cards
    return []
```

### 修复2: 更新凭证检查方法

**文件**: `services/online/online_music_service.py:51-63`

**修改**:
```python
def _has_qqmusic_credential(self) -> bool:
    """Check if QQ Music credential is available."""
    # Check if qqmusic_service has credential
    if self._qqmusic and self._qqmusic.credential:
        return True

    # Check config if available
    if not self._config:
        return False

    credential = self._config.get_qqmusic_credential()
    return credential is not None
```

### 修复3: 更新推荐解析逻辑

**文件**: `ui/views/online_music_view.py:1577-1595`

**修改**:
```python
elif recommend_type == 'home_feed':
    # Home feed returns recommendation cards (playlists, rankings, songs)
    # Each card has type: 200=song, 500=playlist, 700=guess, 1000=ranking
    playlist_id = first_item.get('id')
```

### 修复4: 添加日志和显示调用

**文件**: `ui/views/online_music_view.py`

添加详细日志跟踪推荐加载过程，并显式调用 `show()` 显示推荐区域。

## 测试结果

| API | 修复前 | 修复后 | 说明 |
|-----|-------|--------|------|
| get_home_feed | 0 | **83** | 推荐卡片（歌单、榜单等） |
| get_guess_recommend | 5 | 5 | 猜你喜欢歌曲 |
| get_radar_recommend | 10 | 10 | 雷达推荐歌曲 |
| get_recommend_songlist | 25 | 25 | 推荐歌单 |
| get_recommend_newsong | 65 | 65 | 新歌推荐 |

## UI显示结构

```
┌─────────────────────────────────────┐
│  我的收藏 (4个卡片)                  │
│  [我喜欢] [创建的歌单] [收藏歌单] [收藏专辑] │
├─────────────────────────────────────┤
│  推荐 (5个卡片)                      │
│  [主页推荐] [猜你喜欢] [雷达] [歌单] [新歌] │
│                                     │
│  点击"主页推荐"卡片会显示：          │
│  - 83个推荐卡片（歌单、榜单、单曲等）│
└─────────────────────────────────────┘
```

## 卡片类型说明

| Type | 说明 | 示例 |
|------|------|------|
| 200 | 单曲卡片 | "大家都在听"中的歌曲 |
| 500 | 歌单推荐 | "每日30首"、"百万收藏" |
| 700 | 功能入口 | "猜你喜欢" |
| 900 | 特殊功能 | "雷达模式"、"排行榜" |
| 1000 | 榜单 | "热歌榜"、"欧美榜" |
| -1 | 设置卡片 | "偏好设置"（跳过） |

## 关键文件

- `services/cloud/qqmusic/qqmusic_service.py:862-922` - 推荐API服务层
- `services/online/online_music_service.py:51-63` - 凭证检查
- `ui/views/online_music_view.py:1532-1600` - 推荐解析和显示
- `ui/widgets/recommend_card.py` - 推荐卡片组件

## 验证方法

```bash
uv run python -c "
from services.cloud.qqmusic import QQMusicService

service = QQMusicService()
cards = service.get_home_feed()

print(f'Found {len(cards)} cards')
for card in cards[:5]:
    print(f'  [{card[\"type\"]}] {card[\"title\"]} (ID: {card[\"id\"]})')
"
```

预期输出：
```
Found 83 cards
  [700] 猜你喜欢 (ID: 99)
  [500] 每日30首 (ID: 0)
  [900] 雷达模式 (ID: 22000)
  ...
```
