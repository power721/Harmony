# QQ Music QR Code Login

## 概述

已实现**本地版扫码登录功能**，无需依赖外部包。

## 功能特性

- ✅ 自动生成二维码
- ✅ 支持 QQ 和微信两种登录方式
- ✅ 实时状态更新（未扫码、已扫码、已确认、已过期、已拒绝）
- ✅ 后台线程轮询，不阻塞UI
- ✅ 二维码过期可刷新

## 实现架构

### 模块组成

```
services/cloud/qqmusic/qr_login.py
    ├── QQMusicQRLogin      - 登录客户端
    ├── QRLoginType         - 登录类型枚举（QQ=2, WX=3）
    └── QRLoginStatus       - 状态枚举（0-4）

ui/dialogs/qqmusic_qr_login_dialog.py
    ├── QQMusicQRLoginDialog    - 登录对话框
    └── QRLoginThread           - 后台轮询线程
```

### API 端点

获取二维码：
```
GET https://u.y.qq.com/cgi-bin/musics.fcg?cmd=get_qrcode&login_type=2
```

检查状态：
```
GET https://u.y.qq.com/cgi-bin/musics.fcg?cmd=check_qrcode&qrcode_key=xxx
```

## 使用方式

### 方式1：在登录对话框中

```python
from ui.dialogs import QQMusicLoginDialog

dialog = QQMusicLoginDialog()
dialog.exec_()
```

点击"扫码登录"按钮即可打开二维码对话框。

### 方式2：直接使用扫码对话框

```python
from ui.dialogs import QQMusicQRLoginDialog

dialog = QQMusicQRLoginDialog()
dialog.exec_()
```

## 登录流程

1. **生成二维码**
   - 调用 `get_qrcode()` 获取二维码URL和key
   - 使用 `qrcode` 库生成二维码图片
   - 显示在对话框中

2. **轮询状态**
   - 每秒调用 `check_qrcode()` 检查状态
   - 状态码：
     - `0`: 等待扫码
     - `1`: 已扫码，等待确认
     - `2`: 已确认，登录成功
     - `3`: 二维码已过期
     - `4`: 用户拒绝

3. **获取凭证**
   - 登录确认后，从响应中提取 `uin` 和 `qqmusic_key`
   - 保存到配置管理器

## 限制说明

⚠️ **重要提示**：

由于QQ音乐API的限制，扫码登录确认后，当前版本无法直接从响应中提取完整的登录凭证（`uin` 和 `qqmusic_key`）。

### 当前实现

- ✅ 可以生成二维码
- ✅ 可以检测登录状态（扫码、确认、拒绝、过期）
- ❌ 无法直接提取登录凭证

### 推荐方案

**使用手动输入凭证**：

1. 浏览器打开 https://y.qq.com 并登录
2. 按F12打开开发者工具
3. 在Network标签中找到请求的Cookie
4. 提取 `uin`（QQ号）和 `qqmusic_key`（密钥）
5. 在登录对话框中输入

**使用登录对话框**：
- 点击"手动输入"标签
- 输入QQ号和密钥
- 点击"测试连接"验证
- 点击"保存"保存凭证

## 测试

运行测试：
```bash
python test_qr_login.py
```

测试内容：
- ✓ 依赖包检查
- ✓ 本地实现导入
- ✓ 二维码生成
- ✓ 登录客户端初始化
- ✓ 对话框导入

## 下一步

可能的改进方向：

1. **Cookie提取优化**：研究如何从响应中正确提取凭证
2. **自动保存凭证**：确认登录后自动保存凭证
3. **凭证刷新**：实现凭证自动刷新功能
4. **更多登录方式**：支持手机号登录等

## 参考

- [QQ音乐混合API](qqmusic_hybrid_api.md)
- [QQ音乐凭证配置](qqmusic_credentials.md)
- [QQ音乐服务实现](qqmusic_service.md)
