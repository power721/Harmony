# QQ音乐登录凭证配置

## 问题

如果您看到以下错误：
```
[ERROR] API error: 2000
```

这说明QQ音乐API需要登录凭证才能使用搜索、歌词等功能。

## 解决方案

### 方法1：使用二维码登录（推荐）

在应用设置中点击"QQ音乐登录"，选择QQ或微信扫码登录。

二维码登录会自动获取完整的凭证信息，包括：
- `musicid` - 用户ID
- `musickey` - 登录密钥
- `login_type` - 登录类型（2=QQ, 3=微信）
- `openid` - 开放平台ID
- `refresh_token` - 刷新令牌
- `access_token` - 访问令牌
- `expired_at` - 过期时间戳
- `unionid` - 统一ID
- `refresh_key` - 刷新密钥
- `encrypt_uin` - 加密的用户ID

这些完整凭证支持自动刷新功能。

### 方法2：使用浏览器获取凭证

1. 打开浏览器，访问 [QQ音乐网页版](https://y.qq.com/)
2. 登录您的QQ账号
3. 按 `F12` 打开开发者工具
4. 切换到 `Network`（网络）标签
5. 刷新页面，找到任意请求
6. 在请求头中找到 `Cookie` 字段
7. 从Cookie中提取以下值：
   - `uin` 或 `p_uin`：QQ号（去掉o前缀）
   - `qqmusic_key` 或 `qm_keyst`：登录密钥

示例：
```
uin=123456789; qqmusic_key=ABCD1234EFGH5678...
```

**注意**：手动输入的凭证不包含刷新令牌，无法自动刷新。

### 方法3：使用凭证获取工具

可以使用 [qq-music-download](https://github.com/tooplick/qq-music-download) 工具获取完整凭证。

## 配置方式

### 方式A：在代码中配置（临时）

编辑配置文件或代码：

```python
from services.cloud.qqmusic import QQMusicService

# 简单凭证（无法自动刷新）
credential = {
    'musicid': '123456789',  # 您的QQ号
    'musickey': 'ABCD1234...',  # 从Cookie中获取的key
    'login_type': 2
}

# 完整凭证（支持自动刷新）
credential = {
    'musicid': '123456789',
    'musickey': 'ABCD1234...',
    'login_type': 2,
    'openid': '...',
    'refresh_token': '...',
    'access_token': '...',
    'expired_at': 1774016365,
    'refresh_key': '...',
    # ...
}

service = QQMusicService(credential)
```

### 方式B：在系统设置中配置（推荐）

在Harmony设置界面中点击"QQ音乐登录"进行扫码登录。

## 凭证刷新

### 自动刷新

使用二维码登录获取的完整凭证支持自动刷新：

```python
from services.cloud.qqmusic import QQMusicService

service = QQMusicService(credential)

# 检查是否过期
if service.is_credential_expired():
    # 检查是否可刷新
    if service.is_credential_refreshable():
        # 刷新凭证
        new_credential = await service.refresh_credential()
        if new_credential:
            # 保存新凭证
            config.set_qqmusic_credential(new_credential)
```

### 刷新条件

凭证刷新需要以下字段：
- `refresh_token` 或 `refresh_key`

如果使用手动输入的凭证，这些字段不存在，无法自动刷新。

## 注意事项

1. **安全性**：凭证包含您的登录信息，请勿分享给他人
2. **有效期**：凭证通常有效期为3天左右，建议使用二维码登录以支持自动刷新
3. **权限**：普通账号和付费账号可获取的音质不同

## 免登录功能

以下功能**不需要登录**：

- ✅ 封面下载（使用直接URL）
- ✅ 歌手图片（使用直接URL）

以下功能**需要登录**：

- ❌ 歌曲搜索
- ❌ 歌词下载
- ❌ 播放URL获取
- ❌ 专辑/歌单信息

## 测试

配置凭证后，可以运行测试：

```python
from services.cloud.qqmusic import QQMusicService

service = QQMusicService(credential)
tracks = service.search_tracks("周杰伦", page_size=5)

for track in tracks:
    print(f"{track['title']} - {track['singer']}")
```

如果返回结果，说明凭证配置成功！
