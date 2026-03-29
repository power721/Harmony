# 睡眠定时器Bug修复报告

## 问题描述

用户报告无法打开睡眠定时器对话框,出现样式表解析错误:
```
[WARNING] root - Qt: Could not parse stylesheet of object SleepTimerDialog
```

## 根本原因

1. **不存在的CSS Token**: 样式表中使用了`%highlight_pressed%`token,但ThemeManager中不存在此token
2. **对话框尺寸问题**: 对话框只设置了宽度,没有设置高度,可能导致显示异常
3. **ThemeManager初始化**: 对话框在初始化时过早调用`ThemeManager.instance()`

## 已完成的修复

### 1. 移除无效的CSS Token

**文件**: `ui/dialogs/sleep_timer_dialog.py`

**修改前**:
```css
QPushButton:pressed {
    background-color: %highlight_pressed%;
}
```

**修改后**:
```css
QPushButton:pressed {
    background-color: %selection%;
}
```

使用存在的`%selection%` token替代不存在的`%highlight_pressed%` token。

### 2. 修复对话框尺寸

**文件**: `ui/dialogs/sleep_timer_dialog.py`

**修改前**:
```python
self.setFixedWidth(400)
```

**修改后**:
```python
self.setFixedSize(400, 450)  # 设置宽度和高度
```

### 3. 优化ThemeManager调用

**文件**: `ui/dialogs/sleep_timer_dialog.py`

**修改前**:
```python
def __init__(self, sleep_timer_service, parent=None):
    super().__init__(parent)
    self._sleep_timer = sleep_timer_service
    self._theme = ThemeManager.instance()  # 过早调用
    ...
    self._theme.register_widget(self)
```

**修改后**:
```python
def __init__(self, sleep_timer_service, parent=None):
    super().__init__(parent)
    self._sleep_timer = sleep_timer_service
    ...
    # 在需要时调用
    ThemeManager.instance().register_widget(self)
```

### 4. 添加调试日志

**文件**: `ui/widgets/player_controls.py`

添加了详细的调试日志,帮助追踪对话框打开过程:
```python
def _show_sleep_timer(self):
    """Show sleep timer dialog."""
    try:
        from ui.dialogs.sleep_timer_dialog import SleepTimerDialog
        from app.bootstrap import Bootstrap

        logger.info("Opening sleep timer dialog")
        sleep_timer_service = Bootstrap.instance().sleep_timer_service
        logger.info(f"Sleep timer service obtained: {sleep_timer_service}")
        dialog = SleepTimerDialog(sleep_timer_service, self)
        logger.info(f"Dialog created: {dialog}")
        result = dialog.exec_()
        logger.info(f"Dialog closed with result: {result}")
    except Exception as e:
        logger.error(f"Failed to open sleep timer dialog: {e}", exc_info=True)
```

## 测试结果

### 日志输出

应用程序启动正常,无样式表解析错误:
```
[INFO] system.theme - ThemeManager initialized with theme: Dark
[INFO] system.theme - Global stylesheet applied
```

点击闹钟按钮后,对话框创建成功:
```
[INFO] ui.widgets.player_controls - Opening sleep timer dialog
[INFO] ui.widgets.player_controls - Sleep timer service obtained: <services.playback.sleep_timer_service.SleepTimerService object>
[INFO] ui.widgets.player_controls - Dialog created: <ui.dialogs.sleep_timer_dialog.SleepTimerDialog object>
```

### 功能验证

- ✅ 应用程序启动无错误
- ✅ 无样式表解析警告
- ✅ 对话框成功创建
- ✅ 服务正确注入
- ⏳ 等待用户确认对话框是否正常显示

## 下一步

用户需要:
1. 重新启动应用程序
2. 点击播放控制区域的闹钟图标 ⏰
3. 确认对话框是否正常显示

如果对话框仍然无法显示,请提供:
- 控制台输出
- 是否有任何错误消息
- 点击按钮后的行为描述

## 相关文件

- `ui/dialogs/sleep_timer_dialog.py` - 对话框实现
- `ui/widgets/player_controls.py` - 闹钟按钮和事件处理
- `services/playback/sleep_timer_service.py` - 核心服务
- `translations/en.json` - 英文翻译
- `translations/zh.json` - 中文翻译
