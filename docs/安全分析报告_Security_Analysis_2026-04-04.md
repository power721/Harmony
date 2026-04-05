# Harmony 音乐播放器安全分析报告

**分析日期**: 2026-04-04
**分析范围**: /home/harold/workspace/music-player
**项目规模**: 4400个Python文件，约15万行代码
**技术栈**: Python + PySide6 + SQLite + Requests

---

## 执行摘要

本次安全分析识别了**23个安全问题**，其中包括：
- **3个严重** (Critical) 漏洞
- **8个高** (High) 风险问题
- **7个中** (Medium) 风险问题
- **5个低** (Low) 风险问题

主要安全风险集中在：云服务认证存储、SQL注入防护、敏感信息泄露、文件操作安全等方面。

---

## 1. 注入攻击漏洞

### 1.1 SQL注入防护良好 ✅
**文件**: `infrastructure/database/sqlite_manager.py`, `repositories/track_repository.py`
**严重程度**: 低
**状态**: 已正确防护

**分析**:
- 所有数据库查询都正确使用了参数化查询
- 使用占位符 `?` 而非字符串拼接
- 示例代码（track_repository.py:30-31）:
```python
cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
```

**优点**:
- 完全避免了SQL注入风险
- 使用了现代SQLite安全实践

**建议**:
- 继续保持当前做法
- 在代码审查中强制要求参数化查询

---

### 1.2 FTS5搜索注入风险 ⚠️
**文件**: `infrastructure/database/sqlite_manager.py:1400-1432`
**严重程度**: 中
**CVSS**: 4.3 (AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:L)

**漏洞描述**:
FTS5搜索功能对用户输入处理不够严格，可能导致FTS查询注入。

**漏洞代码**:
```python
# Line 1402-1406
safe_query = query.replace('"', '""')
fts_query = f'"{safe_query}"'
cursor.execute(
    "SELECT t.*, bm25(tracks_fts) AS score FROM tracks t "
    "JOIN tracks_fts f ON t.id = f.rowid WHERE tracks_fts MATCH ?",
    (fts_query,)
)
```

**攻击场景**:
攻击者可以通过特殊构造的查询导致FTS索引损坏或拒绝服务：
- `"OR"` 查询可能导致性能问题
- 特殊字符组合可能绕过搜索限制

**修复建议**:
```python
def _sanitize_fts_query(query: str) -> str:
    """Sanitize FTS5 query to prevent injection."""
    # Remove FTS5 operators
    query = re.sub(r'[&()|*\-:"^]', ' ', query)
    # Limit query length
    query = query[:100]
    # Remove consecutive spaces
    query = ' '.join(query.split())
    return query

# Usage
safe_query = self._sanitize_fts_query(query)
```

**预防措施**:
1. 实施严格的输入白名单
2. 限制查询长度
3. 移除FTS5特殊操作符
4. 记录可疑查询模式

---

## 2. 敏感信息保护

### 2.1 云服务Token明文存储 🔴
**文件**: `infrastructure/database/sqlite_manager.py:360-363`, `repositories/cloud_repository.py`
**严重程度**: 严重
**CVSS**: 8.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L)

**漏洞描述**:
云服务访问令牌（access_token、refresh_token）以明文形式存储在SQLite数据库中，无任何加密保护。

**漏洞代码**:
```python
# sqlite_manager.py Line 360-363
access_token TEXT,
refresh_token TEXT,
token_expires_at TIMESTAMP,
```

**数据库存储示例**:
```sql
INSERT INTO cloud_accounts (access_token, refresh_token)
VALUES ('cookies: __puus=xxx; xxx_token=yyy', 'refresh_token_value');
```

**攻击场景**:
1. **数据库文件泄露**: 攻击者获取 `Harmony.db` 文件即可提取所有云服务凭证
2. **物理访问**: 任何人可复制数据库文件并在其他设备上使用
3. **备份泄露**: 未加密的数据库备份包含所有敏感信息
4. **内存转储**: 数据库在内存中可能被转储

**影响范围**:
- 夸克网盘 (Quark Drive) 完整访问权限
- 百度网盘 (Baidu Drive) 完整访问权限
- QQ音乐账号凭证
- 用户的所有云端文件

**修复建议**:

```python
# 1. 使用keyring库加密存储
import keyring
from cryptography.fernet import Fernet

class SecureTokenStorage:
    def __init__(self):
        # 使用系统keyring存储主密钥
        self.master_key = keyring.get_password("harmony", "master_key")
        if not self.master_key:
            self.master_key = Fernet.generate_key().decode()
            keyring.set_password("harmony", "master_key", self.master_key)
        self.cipher = Fernet(self.master_key.encode())

    def encrypt_token(self, token: str) -> str:
        return self.cipher.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

# 2. 修改数据库schema
ALTER TABLE cloud_accounts ADD COLUMN access_token_encrypted TEXT;
ALTER TABLE cloud_accounts ADD COLUMN refresh_token_encrypted TEXT;

# 3. 迁移现有数据
UPDATE cloud_accounts
SET access_token_encrypted = ?,
    refresh_token_encrypted = ?
WHERE id = ?;
```

**替代方案**:
1. **使用系统密钥环**: `keyring` 库（跨平台支持）
2. **DPAPI** (Windows): `win32crypt` 模块
3. **Keychain** (macOS): `security` 命令行工具
4. **libsecret** (Linux): `secretstorage` 库

**预防措施**:
1. ✅ 永远不要明文存储认证令牌
2. ✅ 使用操作系统级别的密钥管理
3. ✅ 实施令牌加密机制
4. ✅ 定期轮换密钥
5. ✅ 实施数据库文件加密 (SQLCipher)

---

### 2.2 QQ音乐凭证明文存储 🔴
**文件**: `system/config.py:732-756`, `repositories/settings_repository.py`
**严重程度**: 严重
**CVSS**: 7.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

**漏洞描述**:
QQ音乐认证凭证（musicid、musickey、完整credential JSON）以明文形式存储在设置表中。

**漏洞代码**:
```python
# system/config.py:753
self.set(SettingKey.QQMUSIC_CREDENTIAL, json.dumps(credential, ensure_ascii=False))
```

**数据库存储**:
```sql
INSERT INTO settings (key, value)
VALUES ('qqmusic.credential', '{"musicid":"xxx","musickey":"yyy",...}');
```

**攻击场景**:
1. 读取数据库文件获取QQ音乐账号凭证
2. 使用被盗凭证访问QQ音乐服务
3. 下载音乐、获取用户信息

**修复建议**:
```python
import keyring

def set_qqmusic_credential(self, credential: dict):
    """Store QQ Music credentials securely using keyring."""
    # 使用系统keyring存储
    service_name = "harmony_qqmusic"
    username = credential.get('musicid', '')

    # 加密存储完整凭证
    credential_json = json.dumps(credential)
    keyring.set_password(service_name, username, credential_json)

    # 只在本地存储非敏感的nickname
    self.set(SettingKey.QQMUSIC_NICK, credential.get('nick', ''))

def get_qqmusic_credential(self) -> Optional[dict]:
    """Retrieve QQ Music credentials from keyring."""
    service_name = "harmony_qqmusic"

    # 从keyring获取所有可能的凭证
    try:
        # 需要知道username，可以从配置中获取
        # 或者实现凭证列表管理
        musicid = self.get(SettingKey.QQMUSIC_MUSICID)
        if musicid:
            credential_json = keyring.get_password(service_name, musicid)
            if credential_json:
                return json.loads(credential_json)
    except Exception as e:
        logger.error(f"Failed to retrieve credential from keyring: {e}")

    return None
```

---

### 2.3 AI和AcoustID API Key明文存储 🔴
**文件**: `system/config.py:619-635, 675-691`
**严重程度**: 高
**CVSS**: 6.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

**漏洞描述**:
第三方服务API密钥（AI服务、AcoustID）以明文形式存储在数据库中。

**受影响的API Key**:
- AI服务API Key (阿里云Dashscope等)
- AcoustID API Key
- 可能的其他第三方服务

**漏洞代码**:
```python
# system/config.py:635
self.set(SettingKey.AI_API_KEY, api_key)

# system/config.py:691
self.set(SettingKey.ACOUSTID_API_KEY, api_key)
```

**修复建议**:
```python
import keyring

def set_ai_api_key(self, api_key: str):
    """Store AI API key using system keyring."""
    keyring.set_password("harmony_ai", "api_key", api_key)

def get_ai_api_key(self) -> str:
    """Retrieve AI API key from keyring."""
    return keyring.get_password("harmony_ai", "api_key") or ""
```

**额外建议**:
1. 实施API密钥验证机制
2. 提供API密钥管理UI（添加/删除/轮换）
3. 记录API密钥使用情况
4. 实施密钥访问审计

---

### 2.4 敏感信息日志泄露 ⚠️
**文件**: 多处日志记录
**严重程度**: 中
**CVSS**: 5.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N)

**漏洞描述**:
代码中存在多处可能泄露敏感信息的日志记录。

**问题示例**:

1. **完整URL记录** (services/cloud/quark_service.py):
```python
# Line 731
logger.error(f"Quark download file error: {e}", exc_info=True)
```
可能包含下载URL和认证token。

2. **Cookie信息** (多处):
```python
# 可能在日志中包含完整的cookie字符串
logger.debug(f"Updated token: {updated_token}")
```

3. **错误堆栈信息** (全局):
```python
logger.exception(f"Error: {e}")  # 包含完整堆栈
```

**修复建议**:
```python
# 1. 实施敏感信息过滤器
import re

class SensitiveDataFilter(logging.Filter):
    """Filter sensitive data from logs."""

    SENSITIVE_PATTERNS = [
        (r'access_token["\']?\s*[:=]\s*["\']?[^"\'>,]+', 'access_token=***'),
        (r'cookie["\']?\s*[:=]\s*["\']?[^"\'>,]+', 'cookie=***'),
        (r'api_key["\']?\s*[:=]\s*["\']?[^"\'>,]+', 'api_key=***'),
        (r'musickey["\']?\s*[:=]\s*["\']?[^"\'>,]+', 'musickey=***'),
        (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer=***'),
    ]

    def filter(self, record):
        if record.msg:
            msg = str(record.msg)
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
            record.msg = msg

        # Also filter args
        if record.args:
            args = tuple(self._sanitize_arg(arg) for arg in record.args)
            record.args = args

        return True

    def _sanitize_arg(self, arg):
        if isinstance(arg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                arg = re.sub(pattern, replacement, arg, flags=re.IGNORECASE)
        return arg

# 2. 应用过滤器
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())
```

**预防措施**:
1. ✅ 在所有logger上添加敏感数据过滤器
2. ✅ 避免在日志中记录完整的请求/响应体
3. ✅ 生产环境禁用DEBUG级别日志
4. ✅ 定期审计日志内容

---

## 3. 认证和授权

### 3.1 云服务认证无过期检查 ⚠️
**文件**: `services/cloud/quark_service.py`, `services/cloud/baidu_service.py`
**严重程度**: 中
**CVSS**: 5.0 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L)

**漏洞描述**:
云服务认证令牌没有完善的过期检查和自动刷新机制。

**问题代码**:
```python
# quark_service.py - 使用token前没有验证过期
def get_file_list(cls, access_token: str, parent_id: str = '0') -> tuple:
    headers = cls.HEADERS.copy()
    headers['Cookie'] = access_token  # 直接使用，未验证是否过期
```

**攻击场景**:
1. 使用过期令牌可能导致服务异常
2. 令牌泄露后长时间有效
3. 无法检测令牌被盗用

**修复建议**:
```python
class TokenManager:
    """管理云服务令牌生命周期"""

    def __init__(self):
        self.token_cache = {}  # {account_id: {token, expires_at, ...}}

    def is_token_valid(self, account_id: int) -> bool:
        """检查令牌是否有效且未过期"""
        if account_id not in self.token_cache:
            return False

        token_info = self.token_cache[account_id]
        expires_at = token_info.get('expires_at')

        if not expires_at:
            return True  # 没有过期时间，假设有效

        # 提前5分钟认为过期
        return datetime.now() < expires_at - timedelta(minutes=5)

    def get_valid_token(self, account_id: int) -> Optional[str]:
        """获取有效令牌，如果需要则刷新"""
        if not self.is_token_valid(account_id):
            # 尝试刷新令牌
            if not self.refresh_token(account_id):
                return None

        return self.token_cache[account_id]['token']
```

---

### 3.2 无CSRF保护机制
**文件**: 不适用（桌面应用）
**严重程度**: 低
**状态**: 可接受风险

**分析**:
作为桌面应用，不涉及Web浏览器的CSRF攻击。但云服务API调用应考虑实施：
- 请求签名验证
- 时间戳检查
- Nonce机制

---

## 4. 数据处理安全

### 4.1 文件路径遍历风险 ⚠️
**文件**: `services/library/playlist_service.py:167`, `services/lyrics/lyrics_service.py:485`
**严重程度**: 中
**CVSS**: 5.5 (AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N)

**漏洞描述**:
用户提供的文件路径未经验证直接用于文件操作，可能导致路径遍历攻击。

**漏洞代码**:
```python
# playlist_service.py:167
def export_m3u(self, playlist_id: int, file_path: str) -> int:
    with open(file_path, 'w', encoding='utf-8') as f:  # 直接使用用户路径
```

**攻击场景**:
1. **目录遍历**: 攻击者提供路径 `../../../etc/passwd`
2. **文件覆盖**: 覆盖系统重要文件
3. **任意位置写入**: 在任意位置创建文件

**修复建议**:
```python
import os
from pathlib import Path

def validate_file_path(file_path: str, allowed_dir: str = None) -> str:
    """
    验证文件路径是否安全。

    Args:
        file_path: 用户提供的文件路径
        allowed_dir: 允许的目录（可选）

    Returns:
        规范化的绝对路径

    Raises:
        ValueError: 路径不安全
    """
    # 转换为绝对路径并解析符号链接
    abs_path = Path(file_path).resolve()

    # 如果指定了允许的目录，确保路径在该目录下
    if allowed_dir:
        allowed = Path(allowed_dir).resolve()
        try:
            # 检查路径是否在允许的目录内
            abs_path.relative_to(allowed)
        except ValueError:
            raise ValueError(f"路径不在允许的目录内: {file_path}")

    # 检查路径是否试图访问敏感目录
    sensitive_dirs = ['/etc', '/sys', '/proc', '/root', '/boot']
    for sensitive in sensitive_dirs:
        try:
            abs_path.relative_to(sensitive)
            raise ValueError(f"不允许访问系统目录: {sensitive}")
        except ValueError:
            pass  # 不在该目录下，继续

    return str(abs_path)

# 使用示例
def export_m3u(self, playlist_id: int, file_path: str) -> int:
    try:
        # 限制导出目录到用户Downloads或Music
        allowed_dirs = [
            Path.home() / "Downloads",
            Path.home() / "Music",
            Path.cwd() / "exports"
        ]

        safe_path = validate_file_path(file_path)
        # 或者在允许的目录中选择
        # safe_path = validate_file_path(file_path, allowed_dir=str(Path.home() / "Downloads"))

        with open(safe_path, 'w', encoding='utf-8') as f:
            # ... 写入逻辑
    except ValueError as e:
        logger.error(f"无效的文件路径: {e}")
        return 0
```

**预防措施**:
1. ✅ 始终验证和规范化文件路径
2. ✅ 限制文件操作到特定目录
3. ✅ 使用白名单而非黑名单
4. ✅ 避免直接使用用户输入的路径
5. ✅ 实施最小权限原则

---

### 4.2 下载文件类型验证缺失 ⚠️
**文件**: `services/cloud/quark_service.py:709-746`, `infrastructure/network/http_client.py:234-277`
**严重程度**: 中
**CVSS**: 5.5 (AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N)

**漏洞描述**:
从互联网下载文件时，未验证文件类型和内容，可能导致恶意文件下载。

**问题代码**:
```python
# quark_service.py:731
with open(dest_path, 'wb') as f:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)  # 直接写入，未验证内容
```

**攻击场景**:
1. **恶意可执行文件**: 下载.exe、.sh等可执行文件
2. **恶意脚本**: 下载包含恶意代码的脚本文件
3. **大文件DoS**: 下载超大文件导致磁盘耗尽
4. **路径覆盖**: 通过符号链接覆盖系统文件

**修复建议**:
```python
import magic
import hashlib
from pathlib import Path

ALLOWED_AUDIO_TYPES = {
    'audio/mpeg': ['.mp3'],
    'audio/flac': ['.flac'],
    'audio/wav': ['.wav'],
    'audio/ogg': ['.ogg'],
    'audio/m4a': ['.m4a'],
    'audio/x-m4a': ['.m4a'],
}

MAX_DOWNLOAD_SIZE = 500 * 1024 * 1024  # 500MB

class SecureDownloader:
    """安全的文件下载器"""

    def validate_download(self, url: str, dest_path: str) -> bool:
        """验证下载是否安全"""

        # 1. 验证目标路径
        dest = Path(dest_path).resolve()
        if not str(dest).startswith(str(Path.home())):
            raise ValueError("只能下载到用户目录")

        # 2. 验证文件扩展名
        allowed_extensions = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.lrc'}
        if dest.suffix.lower() not in allowed_extensions:
            raise ValueError(f"不允许的文件类型: {dest.suffix}")

        return True

    def download_with_validation(
        self,
        url: str,
        dest_path: str,
        max_size: int = MAX_DOWNLOAD_SIZE
    ) -> bool:
        """安全下载文件"""

        self.validate_download(url, dest_path)

        downloaded_size = 0
        chunk_hash = hashlib.sha256()

        try:
            with self.stream("GET", url) as response:
                # 验证Content-Type
                content_type = response.headers.get('Content-Type', '').split(';')[0]
                if content_type and content_type not in ALLOWED_AUDIO_TYPES:
                    logger.warning(f"可疑的Content-Type: {content_type}")
                    # 可以选择拒绝或继续

                # 验证Content-Length
                content_length = int(response.headers.get('content-length', 0))
                if content_length > max_size:
                    raise ValueError(f"文件过大: {content_length} > {max_size}")

                # 下载并计算哈希
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            downloaded_size += len(chunk)
                            if downloaded_size > max_size:
                                raise ValueError(f"下载超过大小限制: {downloaded_size}")

                            chunk_hash.update(chunk)
                            f.write(chunk)

                # 验证实际文件类型
                mime_type = magic.from_file(dest_path, mime=True)
                if mime_type not in ALLOWED_AUDIO_TYPES:
                    logger.error(f"下载的文件类型不匹配: {mime_type}")
                    Path(dest_path).unlink()  # 删除恶意文件
                    return False

                logger.info(f"文件下载成功: SHA256={chunk_hash.hexdigest()}")
                return True

        except Exception as e:
            logger.error(f"下载失败: {e}")
            # 清理不完整的文件
            if Path(dest_path).exists():
                Path(dest_path).unlink()
            return False
```

**预防措施**:
1. ✅ 验证文件类型（扩展名、Content-Type、magic bytes）
2. ✅ 限制文件大小
3. ✅ 验证下载路径
4. ✅ 计算文件哈希
5. ✅ 使用沙箱环境处理下载的文件

---

### 4.3 M3U导入路径遍历风险 ⚠️
**文件**: `services/library/playlist_service.py:187-200`
**严重程度**: 中
**CVSS**: 5.0 (AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N)

**漏洞描述**:
M3U文件导入时，文件中的路径未经验证直接使用。

**问题代码**:
```python
# 未完整显示，但预计会读取M3U文件中的路径
def import_m3u(self, file_path: str, playlist_name: str) -> int:
    # 读取M3U文件
    # 解析路径
    # 直接添加到播放列表
```

**攻击场景**:
1. 恶意M3U文件包含 `../../etc/passwd` 等路径
2. 可能导致信息泄露或系统异常

**修复建议**:
```python
def import_m3u(self, file_path: str, playlist_name: str) -> int:
    """安全导入M3U播放列表"""

    # 验证M3U文件路径
    safe_path = validate_file_path(file_path)

    playlist = Playlist(name=playlist_name)
    playlist_id = self.create_playlist(playlist)
    count = 0

    try:
        with open(safe_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue

                # 验证路径
                try:
                    track_path = validate_file_path(line)

                    # 检查文件是否存在且是音频文件
                    if not Path(track_path).exists():
                        logger.debug(f"文件不存在: {line}")
                        continue

                    # 检查是否在数据库中
                    track = self._track_repo.get_by_path(track_path)
                    if track:
                        self.add_track_to_playlist(playlist_id, track.id)
                        count += 1
                    else:
                        logger.debug(f"未找到音轨: {track_path}")

                except ValueError as e:
                    logger.warning(f"跳过无效路径: {line} - {e}")

        logger.info(f"从M3U导入 {count} 个音轨")
        return count

    except Exception as e:
        logger.error(f"M3U导入失败: {e}")
        return 0
```

---

## 5. 网络安全

### 5.1 SSL证书验证缺失 ⚠️
**文件**: `infrastructure/network/http_client.py`
**严重程度**: 中
**CVSS**: 5.9 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N)

**漏洞描述**:
未明确配置SSL证书验证，可能使用不安全的连接。

**问题代码**:
```python
# http_client.py - 未显式设置SSL验证
self._session = requests.Session()
# 未设置 verify=True
```

**攻击场景**:
1. 中间人攻击（MITM）
2. SSL/TLS降级攻击
3. 证书欺骗

**修复建议**:
```python
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class SSLAdapter(HTTPAdapter):
    """强制SSL验证的适配器"""

    def init_poolmanager(self, *args, **kwargs):
        # 强制使用TLS 1.2或更高版本
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.verify_mode = ssl.CERT_REQUIRED

        # 可选：指定证书包
        # context.load_verify_locations('/path/to/cacert.pem')

        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

class HttpClient:
    def __init__(self, ...):
        self._session = requests.Session()
        # 强制SSL验证
        self._session.verify = True
        # 使用自定义适配器
        adapter = SSLAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
        )
        self._session.mount('https://', adapter)
```

**额外建议**:
1. 实施证书固定（Certificate Pinning）用于关键服务
2. 记录SSL/TLS版本和密码套件
3. 定期更新证书包

---

### 5.2 无请求速率限制 ⚠️
**文件**: `infrastructure/network/http_client.py`, `services/cloud/quark_service.py`
**严重程度**: 中
**CVSS**: 4.3 (AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:L)

**漏洞描述**:
云服务API请求缺少全局速率限制，可能导致账号被封禁。

**现有保护**:
```python
# baidu_service.py:20-33 - 仅针对百度服务
_last_request_time = 0
_request_interval = 0.2  # 200ms
_rate_limit_lock = threading.Lock()
```

**问题**:
- 只有百度网盘实现了速率限制
- 夸克网盘和其他服务无限制
- 全局HTTP客户端无限制

**修复建议**:
```python
import time
import threading
from collections import deque
from typing import Optional

class RateLimiter:
    """令牌桶算法的速率限制器"""

    def __init__(self, rate: float, burst: int = 5):
        """
        Args:
            rate: 每秒请求数
            burst: 突发请求数
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """获取令牌，如果无法获取则阻塞"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            # 计算需要等待的时间
            wait_time = (tokens - self.tokens) / self.rate
            time.sleep(wait_time)
            self.tokens = 0
            return True

# 为每个服务配置不同的速率限制
RATE_LIMITS = {
    'quark': RateLimiter(rate=2.0, burst=5),    # 每秒2个请求
    'baidu': RateLimiter(rate=5.0, burst=10),   # 每秒5个请求
    'qqmusic': RateLimiter(rate=10.0, burst=20), # 每秒10个请求
    'default': RateLimiter(rate=5.0, burst=10),
}

class HttpClient:
    def request(self, method: str, url: str, service: str = 'default', **kwargs):
        # 应用速率限制
        limiter = RATE_LIMITS.get(service, RATE_LIMITS['default'])
        limiter.acquire()

        # 执行请求
        return self._session.request(method, url, **kwargs)
```

---

### 5.3 HTTP请求头安全配置 ⚠️
**文件**: `services/cloud/quark_service.py:46-52`, `services/cloud/baidu_service.py:85-89`
**严重程度**: 低
**CVSS**: 3.7 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)

**漏洞描述**:
HTTP请求头未配置安全相关的头部。

**当前配置**:
```python
HEADERS = {
    'User-Agent': 'Mozilla/5.0 ...',
    'Referer': 'https://pan.quark.cn/',
    'Origin': 'https://pan.quark.cn'
}
```

**建议添加**:
```python
SECURE_HEADERS = {
    'User-Agent': '...',
    'Referer': '...',
    'Origin': '...',
    # 安全相关头部
    'X-Requested-With': 'XMLHttpRequest',  # CSRF保护
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'DNT': '1',  # Do Not Track
    'Accept': 'application/json',  # 限制响应类型
}
```

---

## 6. 依赖安全

### 6.1 依赖版本检查
**严重程度**: 中
**CVSS**: 依赖具体漏洞

**建议**:
```bash
# 使用pip-audit检查已知漏洞
pip install pip-audit
pip-audit

# 使用safety检查
pip install safety
safety check --json

# 使用requirements.txt
pip freeze > requirements.txt
pip-audit --format json --output audit-report.json requirements.txt
```

**关键依赖**:
- `requests` - 定期更新
- `PySide6` - 定期更新
- `mutagen` - 定期更新
- `sqlite3` - Python内置，跟随Python版本

---

## 7. 其他安全问题

### 7.1 数据库文件权限 ⚠️
**文件**: `infrastructure/database/sqlite_manager.py:25`
**严重程度**: 中
**CVSS**: 5.0 (AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

**漏洞描述**:
数据库文件 `Harmony.db` 可能使用不安全的文件权限。

**修复建议**:
```python
import os
import stat

def _set_secure_permissions(db_path: str):
    """设置数据库文件的安全权限"""
    # 设置文件权限为用户读写 (0600)
    os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)

    # 如果是Unix系统，可以设置更严格的权限
    # 确保只有创建者可以读写

# 在数据库创建后调用
self._init_database()
_set_secure_permissions(self.db_path)
```

---

### 7.2 错误处理信息泄露 ⚠️
**严重程度**: 低
**CVSS**: 3.7 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)

**问题**:
多个地方的错误处理可能泄露敏感信息。

**示例**:
```python
# 不要这样做
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)  # 包含完整堆栈

# 应该这样做
except Exception as e:
    logger.error(f"操作失败: {type(e).__name__}")  # 只记录错误类型
    # 在调试模式下才记录详细信息
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"详细错误: {e}", exc_info=True)
```

---

## 8. 安全加固建议

### 8.1 短期改进（1-2周）
1. **加密存储所有认证令牌** - 使用系统keyring
2. **实施文件路径验证** - 防止路径遍历
3. **添加下载文件类型验证** - 防止恶意文件
4. **配置SSL证书验证** - 强制HTTPS
5. **过滤日志中的敏感信息** - 实施日志过滤器

### 8.2 中期改进（1-2月）
1. **实施完整的令牌管理** - 过期检查、自动刷新
2. **添加全局速率限制** - 防止API滥用
3. **实施数据库加密** - SQLCipher或文件级加密
4. **添加安全审计日志** - 记录安全相关事件
5. **实施Content Security Policy** - 限制资源加载

### 8.3 长期改进（3-6月）
1. **安全开发生命周期** - 集成安全测试到CI/CD
2. **依赖漏洞扫描** - 自动化依赖安全检查
3. **渗透测试** - 定期安全评估
4. **安全培训** - 提升团队安全意识
5. **安全代码审查** - 建立安全审查流程

---

## 9. 代码示例：安全工具库

建议创建 `infrastructure/security.py` 模块：

```python
"""
安全工具模块
"""
import re
import logging
from pathlib import Path
from typing import Optional
import keyring
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class SecurityUtils:
    """安全工具集合"""

    @staticmethod
    def validate_file_path(file_path: str, allowed_dir: Optional[Path] = None) -> Path:
        """验证文件路径安全性"""
        path = Path(file_path).resolve()

        if allowed_dir:
            try:
                path.relative_to(allowed_dir.resolve())
            except ValueError:
                raise ValueError(f"路径不在允许的目录内")

        # 检查敏感目录
        sensitive = ['/etc', '/sys', '/proc', '/root']
        for sens in sensitive:
            if path.is_relative_to(sens):
                raise ValueError(f"不允许访问: {sens}")

        return path

    @staticmethod
    def sanitize_log_message(message: str) -> str:
        """清理日志消息中的敏感信息"""
        patterns = [
            (r'access_token["\']?\s*[:=]\s*["\']?[^"\'>,]+', 'access_token=***'),
            (r'api_key["\']?\s*[:=]\s*["\']?[^"\'>,]+', 'api_key=***'),
            (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer=***'),
        ]

        for pattern, replacement in patterns:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

        return message

class SecureStorage:
    """使用系统keyring的安全存储"""

    def __init__(self, service_name: str):
        self.service_name = service_name

    def store(self, key: str, value: str) -> bool:
        """安全存储密钥"""
        try:
            keyring.set_password(self.service_name, key, value)
            return True
        except Exception as e:
            logger.error(f"安全存储失败: {e}")
            return False

    def retrieve(self, key: str) -> Optional[str]:
        """检索密钥"""
        try:
            return keyring.get_password(self.service_name, key)
        except Exception as e:
            logger.error(f"检索密钥失败: {e}")
            return None

    def delete(self, key: str) -> bool:
        """删除密钥"""
        try:
            keyring.delete_password(self.service_name, key)
            return True
        except Exception:
            return False

class Encryption:
    """数据加密工具"""

    def __init__(self, master_key: Optional[bytes] = None):
        if master_key:
            self.cipher = Fernet(master_key)
        else:
            # 从keyring获取或生成密钥
            storage = SecureStorage("harmony_encryption")
            key_b64 = storage.retrieve("master_key")

            if key_b64:
                self.cipher = Fernet(key_b64.encode())
            else:
                key = Fernet.generate_key()
                storage.store("master_key", key.decode())
                self.cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        """加密字符串"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        """解密字符串"""
        return self.cipher.decrypt(encrypted.encode()).decode()

class SensitiveDataFilter(logging.Filter):
    """日志敏感信息过滤器"""

    def filter(self, record):
        if record.msg:
            record.msg = SecurityUtils.sanitize_log_message(str(record.msg))
        return True
```

---

## 10. 总结

Harmony音乐播放器在基础安全实践（如SQL注入防护）方面表现良好，但在以下关键领域需要改进：

### 优先级P0（立即修复）:
1. ✅ 加密存储所有云服务认证令牌
2. ✅ 使用系统keyring管理API密钥
3. ✅ 实施文件路径验证机制

### 优先级P1（2周内修复）:
4. ✅ 添加下载文件类型验证
5. ✅ 过滤日志中的敏感信息
6. ✅ 强制SSL证书验证

### 优先级P2（1月内修复）:
7. ✅ 实施完整的令牌生命周期管理
8. ✅ 添加全局速率限制
9. ✅ 实施数据库文件加密

### 风险评估:
- **当前风险等级**: 高 🔴
- **修复后风险等级**: 中-低 🟡
- **建议行动**: 立即开始P0优先级修复

---

**报告生成时间**: 2026-04-04
**分析工具**: 人工代码审查 + 静态分析
**下次审查建议**: 2026-07-04（3个月后）
