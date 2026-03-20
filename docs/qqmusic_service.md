# QQ音乐服务实现

## 概述

已完成QQ音乐API的Python实现，用于在Harmony音乐播放器中搜索和播放QQ音乐。

## 实现状态

### ✅ 已完成

1. **加密解密模块** (`services/cloud/qqmusic/crypto.py`)
   - SHA1签名生成算法
   - TripleDES解密（用于QRC歌词）
   - zlib解压缩支持
   - MD5和Hash33算法

2. **通用工具模块** (`services/cloud/qqmusic/common.py`)
   - GUID和搜索ID生成
   - 音质映射
   - 搜索类型枚举
   - API配置常量

3. **API客户端** (`services/cloud/qqmusic/client.py`)
   - 搜索接口
   - 歌曲URL获取（支持多种音质降级）
   - 歌词获取（支持翻译和逐字歌词）
   - 专辑、歌单、歌手信息获取
   - 排行榜获取

4. **服务层** (`services/cloud/qqmusic/qqmusic_service.py`)
   - 高级接口封装
   - 简化的搜索和播放URL获取

### ⚠️ 当前限制

**需要登录凭证**

QQ音乐API现在需要登录凭证才能使用搜索和歌词功能。无凭证调用会返回错误码2000。

**可用功能（无需登录）**
- ✅ 专辑封面URL生成（直接URL，无网络请求）
- ✅ 歌手图片URL生成（直接URL，无网络请求）

**需要登录的功能**
- ❌ 歌曲搜索
- ❌ 歌词下载
- ❌ 播放URL获取
- ❌ 专辑/歌单详细信息

详见：[QQ音乐登录凭证配置](qqmusic_credentials.md)

### 凭证格式

```python
credential = {
    'musicid': 'QQ号或uin',
    'musickey': '登录后获取的key',
    'login_type': 2  # 登录类型
}
```

## 使用方式

### 基本使用

```python
from services.cloud.qqmusic import QQMusicService

# 无凭证（某些功能可能受限）
service = QQMusicService()

# 搜索歌曲
tracks = service.search_tracks("周杰伦 晴天", page_size=10)

# 获取播放URL
url = service.get_playback_url(song_mid='003OUlho2HcRHC', quality='flac')

# 获取歌词
lyrics = service.get_lyrics(song_mid='003OUlho2HcRHC')
```

### 使用凭证

```python
credential = {
    'musicid': 'your_uin',
    'musickey': 'your_key',
    'login_type': 2
}

service = QQMusicService(credential)
```

## API接口

### QQMusicClient

低级API客户端，直接与QQ音乐服务器通信。

- `search(keyword, search_type, page_num, page_size)` - 搜索
- `get_song_url(song_mid, quality)` - 获取播放URL
- `get_song_detail(song_mid)` - 获取歌曲详情
- `get_lyric(song_mid, qrc, trans, roma)` - 获取歌词
- `get_album(album_mid)` - 获取专辑信息
- `get_playlist(playlist_id)` - 获取歌单信息
- `get_singer(singer_mid)` - 获取歌手信息
- `get_top_lists()` - 获取排行榜

### QQMusicService

高级服务层，提供更友好的接口。

- `search_tracks(keyword, page, page_size)` - 搜索歌曲
- `get_playback_url(song_mid, quality)` - 获取播放URL
- `get_lyrics(song_mid)` - 获取歌词
- `get_album_info(album_mid)` - 获取专辑信息
- `get_playlist_info(playlist_id)` - 获取歌单信息
- `get_singer_info(singer_mid)` - 获取歌手信息
- `get_top_lists()` - 获取排行榜

## 音质支持

支持以下音质（自动降级）：
- `master` - 臻品母带 24Bit 192kHz
- `atmos` / `atmos_2` - 臻品全景声
- `atmos_51` - 臻品音质
- `flac` - FLAC 无损
- `320` - MP3 320kbps
- `128` - MP3 128kbps

## 依赖

已添加到 `requirements.txt`：
```
pycryptodome>=3.19.0
```

## 测试

创建了测试脚本：
- `test_qqmusic_simple.py` - 基本功能测试
- `test_qqmusic_final.py` - API调用测试

## 文件结构

```
services/cloud/qqmusic/
├── __init__.py           # 包导出
├── crypto.py             # 加密解密工具
├── common.py             # 通用常量和工具
├── client.py             # API客户端
└── qqmusic_service.py    # 服务层
```

## 下一步

### 获取登录凭证

要使用完整的QQ音乐API功能，需要：

1. **手动获取凭证**
   - 使用浏览器登录QQ音乐网页版
   - 从开发者工具中获取cookie
   - 提取 `uin` 和 `qqmusic_key`

2. **使用现有工具**
   - 参考 [tooplick/qq-music-download](https://github.com/tooplick/qq-music-download)
   - 该项目可以获取登录凭证

3. **实现登录功能** (可选)
   - 可以在Harmony中添加QQ音乐登录界面
   - 实现二维码登录或账号密码登录

### 集成到UI

1. 在搜索界面添加"搜索QQ音乐"选项
2. 在播放列表中显示QQ音乐来源
3. 实现歌词显示（包括逐字歌词）

## 注意事项

1. **版权限制**：仅用于个人学习，禁止商业用途
2. **API变更**：QQ音乐API可能随时变更，需要及时更新
3. **登录状态**：凭证有时效性，需要定期刷新
4. **速率限制**：避免过于频繁的请求

## 参考资料

- 原始API项目：https://github.com/ygkth/qq-music-api
- API文档：https://doc.ygking.top
- 凭证获取工具：https://github.com/tooplick/qq-music-download
