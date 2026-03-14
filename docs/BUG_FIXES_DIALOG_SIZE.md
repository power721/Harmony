# 错误修复和对话框尺寸改进

## 修复的错误

### 1. AttributeError: 'int' object has no attribute 'get'

**问题位置：** `ui/windows/main_window.py:985`

**原因分析：**
`_on_track_changed` 方法中的代码假设 `track_item` 要么是 `PlaylistItem` 对象，要么是字典，但实际运行时它可能是一个 `int`（track_id）。当代码尝试对 `int` 调用 `.get()` 方法时，会抛出 `AttributeError`。

**修复方案：**
添加了对 `int` 类型的处理：

```python
# 修复前
if isinstance(track_item, PlaylistItem):
    # 处理 PlaylistItem
else:
    track_dict = track_item
    track_id = track_dict.get("id")  # ❌ 如果 track_item 是 int 会失败

# 修复后
if isinstance(track_item, PlaylistItem):
    # 处理 PlaylistItem
elif isinstance(track_item, int):
    # 处理 int 类型的 track_id ✓
    track_id = track_item
    track_dict = None
else:
    # 处理 dict
```

## 对话框尺寸改进

### 用户反馈：
- "对话框再大一些"

### 实施的改进：

#### 1. 对话框整体尺寸
**之前：**
```python
self.setMinimumSize(600, 500)
```

**之后：**
```python
self.setMinimumSize(800, 700)
self.resize(900, 750)  # 设置更大的默认尺寸
```

**改进效果：**
- 最小宽度：600px → 800px (+33%)
- 最小高度：500px → 700px (+40%)
- 默认尺寸：900x750px（更大的初始显示）

#### 2. 封面预览区域
**之前：**
```python
self.cover_label.setMinimumSize(300, 300)
self.cover_label.setMaximumSize(300, 300)
scroll_area.setMaximumHeight(320)
```

**之后：**
```python
self.cover_label.setMinimumSize(500, 500)
self.cover_label.setMaximumSize(500, 500)
scroll_area.setMaximumHeight(550)
```

**改进效果：**
- 封面预览：300x300 → 500x500 (+67%)
- 滚动区域：320px → 550px (+72%)

#### 3. 封面图片缩放
更新了两处封面图片的缩放尺寸：

**之前：**
```python
scaled_pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
```

**之后：**
```python
scaled_pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
```

**影响的方法：**
- `_on_cover_downloaded` - 新下载的封面
- `_display_existing_cover` - 已存在的封面

## 测试验证

### 单元测试
- **所有191个测试通过** ✓
- **8个新功能测试通过** ✓
- **没有回归问题** ✓

### 功能测试
- **track_id 处理** ✓
  - int 类型的 track_id 正确处理
  - dict 类型的 track_item 正常工作
  - PlaylistItem 类型不受影响

- **对话框尺寸** ✓
  - 更大的显示区域
  - 更好的封面预览效果
  - 响应式布局保持正常

## 用户体验改进

### 错误修复
- ✅ 消除了 `AttributeError` 异常
- ✅ 提高了应用程序稳定性
- ✅ 支持更多类型的 track_item 输入

### 视觉改进
- ✅ 更大的对话框尺寸（900x750px）
- ✅ 更大的封面预览（500x500px）
- ✅ 更好的封面细节可见性
- ✅ 保持响应式布局和滚动功能

## 兼容性

修复保持了向后兼容性：
- ✅ 现有的 PlaylistItem 处理不受影响
- ✅ 现有的 dict 处理不受影响
- ✅ 新增 int 处理提供额外支持
- ✅ 所有现有功能正常工作
