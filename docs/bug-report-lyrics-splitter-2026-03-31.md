# Bug Report: 歌词面板拖动消失问题修复

**日期**: 2026-03-31
**问题**: 歌词左边的分割线可以拖动，现在拖动导致歌词消失
**严重程度**: 中等
**状态**: 已修复

---

## 问题描述

用户在拖动歌词面板左侧的分割线（QSplitter handle）时，如果拖动幅度过大，歌词面板会完全消失。这是因为 QSplitter 默认允许子部件被折叠到 0 宽度。

## 根本原因

在 `ui/windows/main_window.py` 中，歌词面板被添加到 QSplitter 中时，没有设置最小宽度限制：

```python
# 旧代码
self._lyrics_panel = self._create_lyrics_panel()
self._splitter.addWidget(self._lyrics_panel)

# 没有设置最小宽度或禁止折叠
self._splitter.setStretchFactor(0, 2)
self._splitter.setStretchFactor(1, 1)
self._splitter.setSizes([600, 400])
```

QSplitter 的默认行为：
- `childrenCollapsible` 默认为 `True`，允许子部件被折叠到 0 宽度
- 当用户拖动分割线到最左侧时，歌词面板宽度变为 0
- 宽度为 0 时，面板视觉上"消失"，用户无法再次拖动分割线

## 解决方案

在 `ui/windows/main_window.py` 第 411-423 行添加了以下修复：

```python
# 修复后的代码
self._stacked_widget.setMinimumWidth(200)  # 左侧面板最小宽度
self._splitter.addWidget(self._stacked_widget)

# Lyrics panel
self._lyrics_panel = self._create_lyrics_panel()
self._lyrics_panel.setMinimumWidth(250)  # Prevent lyrics panel from collapsing
self._splitter.addWidget(self._lyrics_panel)

# Set splitter proportions
self._splitter.setStretchFactor(0, 2)  # Library gets 2/3
self._splitter.setStretchFactor(1, 1)  # Lyrics gets 1/3
self._splitter.setSizes([600, 400])  # Initial sizes
self._splitter.setChildrenCollapsible(False)  # 禁止完全折叠
```

### 修复内容

1. **设置最小宽度**:
   - `stacked_widget.setMinimumWidth(200)` - 确保左侧面板至少 200px 宽
   - `lyrics_panel.setMinimumWidth(250)` - 确保歌词面板至少 250px 宽

2. **禁止完全折叠**:
   - `splitter.setChildrenCollapsible(False)` - 防止任何子面板被完全折叠到 0 宽度

## 技术细节

### QSplitter 行为

- 默认情况下，`QSplitter` 允许用户将子部件拖动到 0 宽度
- 这会导致部件"消失"，且难以恢复（无法拖动宽度为 0 的分割线）
- 解决方法：
  1. 在子部件上设置 `minimumWidth`
  2. 在 QSplitter 上设置 `setChildrenCollapsible(False)`

### 为什么选择 250px 最小宽度？

- 歌词面板需要足够宽度显示文本内容
- 250px 可以容纳平均 15-20 个中文字符
- 不会占用过多空间，同时保证可读性
- 与左侧面板的 200px 最小宽度形成合理的比例

## 测试验证

### 手动测试步骤

1. 启动应用程序: `uv run python main.py`
2. 播放一首歌曲，确保歌词显示
3. 尝试拖动歌词面板左侧的分割线向左拖动
4. **预期结果**: 分割线在达到最小宽度时停止，歌词面板不会消失
5. 尝试向右拖动分割线
6. **预期结果**: 歌词面板可以正常调整大小

### 测试结果

✅ 歌词面板现在有最小宽度限制（250px）
✅ 左侧面板有最小宽度限制（200px）
✅ 分割线无法将面板折叠到 0 宽度
✅ 歌词面板始终保持可见

## 影响范围

### 修改文件

- `ui/windows/main_window.py` - 添加最小宽度和禁止折叠设置

### 影响功能

- 歌词面板显示
- 分割线拖动行为
- 窗口布局管理

### 向后兼容性

✅ 完全兼容 - 只是添加了约束，没有改变现有功能

## 相关代码

### 参考文档

- Qt Documentation: [QSplitter Class](https://doc.qt.io/qt-6/qsplitter.html)
- Qt Documentation: [QWidget::minimumWidth Property](https://doc.qt.io/qt-6/qwidget.html#minimumWidth-prop)

### 相关文件

- `ui/windows/components/lyrics_panel.py` - 歌词面板组件
- `ui/widgets/lyrics_widget_pro.py` - 歌词显示组件

## 总结

这是一个典型的 UI 布局边界条件问题。通过设置最小宽度和禁止折叠，确保了用户界面在任何操作下都保持可用状态。修复简单但有效，不需要复杂的逻辑或状态管理。
