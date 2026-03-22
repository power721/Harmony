# QQ Music Search Completion

## Overview

QQ音乐搜索自动补全功能，在用户输入搜索关键词时提供实时建议。

## Implementation

### API Layer

**File**: `services/cloud/qqmusic/client.py`

```python
def complete(self, keyword: str) -> Dict:
    """
    搜索词补全建议.

    Args:
        keyword: 关键词.

    Returns:
        搜索建议字典
    """
    params = {
        'search_id': get_search_id(),
        'query': keyword,
        'num_per_page': 0,
        'page_idx': 0,
    }

    return self._make_request('music.smartboxCgi.SmartBoxCgi', 'GetSmartBoxResult', params)
```

### Service Layer

**File**: `services/cloud/qqmusic/qqmusic_service.py`

```python
def complete(self, keyword: str) -> List[Dict[str, Any]]:
    """
    搜索词补全建议.

    Args:
        keyword: 关键词.

    Returns:
        搜索建议列表，每个建议包含 hint 和 type 键
    """
```

### UI Layer

**File**: `ui/views/online_music_view.py`

- `CustomQCompleter`: 自定义补全列表组件，提供更好的视觉效果
- `CompletionWorker`: 后台线程处理补全请求
- Auto-completion triggered 300ms after user stops typing
- Only available when logged in to QQ Music

## Usage

1. **Login to QQ Music**: Search completion requires QQ Music login
2. **Type in search box**: Start typing a keyword
3. **Select suggestion**: Click on a suggestion or press Enter to search

## API Response Format

```json
{
  "items": [
    {
      "hint": "周杰伦",
      "type": 0,
      "docid": "17675977119827593594",
      "pic_url": "https://...",
      "score": 3899628.5
    },
    {
      "hint": "周杰伦 新歌",
      "type": 0,
      "docid": "14926957171818164292",
      "pic_url": "https://...",
      "score": 2099.07
    }
  ],
  "search_id": "189126226307799042",
  "total_num": 442
}
```

### Key Fields

- `hint`: 建议的搜索文本（这是显示给用户的）
- `type`: 建议类型（0 = 搜索建议）
- `docid`: 文档ID
- `pic_url`: 相关图片URL
- `score`: 相关性评分

## Requirements

- QQ Music account with valid credential
- Network connectivity to QQ Music servers

## Notes

- Completion API requires authenticated requests (credential needed)
- Minimum 1 character input triggers completion
- 300ms debounce delay to avoid excessive API calls
- Uses `Qt.MatchContains` filter mode to show any suggestion containing the typed text
