# 实时可视化设计：波形与频谱（Now Playing）

## 1. 背景与目标

本设计为 Harmony 增加“实时音频可视化”能力，首期范围如下：

- 展示位置：`NowPlayingWindow`
- 可视化类型：`waveform`（波形）与 `spectrum`（频谱）
- 数据形态：实时帧（非预计算整首）
- 后端范围：仅 `mpv` 后端支持（`qt` 后端退化为不支持）

目标是以最小侵入方式接入当前分层架构，优先交付稳定 MVP，并为后续深度定制（自定义 FFT、瀑布图、粒子效果）预留接口。

## 2. 方案对比与选型

### 方案 A（推荐）：基于 mpv 现有能力输出可视化帧

- 思路：利用 mpv/ffmpeg 侧现有音频分析与可视化能力，后端输出可视化帧数据（或可供绘制的频带/采样点），Qt 侧负责渲染。
- 优点：
  - 实现速度快，MVP 风险低
  - 分析正确性和性能更稳定
  - 与现有 mpv 后端衔接自然
- 缺点：
  - 与 mpv 绑定较深
  - 视觉风格可塑性受后端输出形式影响

### 方案 B：Python 侧实时采样 + FFT + 自绘

- 思路：获取 PCM 后在 Python 线程内做 FFT，再由 `QWidget` 绘制。
- 优点：视觉可控性最高。
- 缺点：复杂度高，性能与线程同步风险显著增加。

### 方案 C：旁路预分析 + 定时刷新

- 思路：外部预分析后按时间索引推送可视化结果。
- 优点：实现路径清晰。
- 缺点：实时性与同步精度不足，不符合本期目标。

**选型结论**：首期采用方案 A。

## 3. 架构设计

保持现有分层边界：`ui -> services/playback -> infrastructure/audio`。

新增与改动：

1. `infrastructure/audio/audio_backend.py`
- 增加能力接口：`supports_visualizer() -> bool`
- 增加信号：`visualizer_frame = Signal(object)`

2. `infrastructure/audio/mpv_backend.py`
- 实现 `supports_visualizer() == True`
- 在播放态推送实时帧，暂停/停止时停更或降频

3. `infrastructure/audio/qt_backend.py`
- 实现 `supports_visualizer() == False`
- 不推送可视化帧

4. `infrastructure/audio/audio_engine.py`
- 新增 `visualizer_frame` 信号，透传后端帧到 UI 层

5. `ui/widgets/audio_visualizer_widget.py`（新增）
- 提供 `set_mode()` 与 `update_frame()`
- 在 `paintEvent` 渲染频谱柱或波形线

6. `ui/windows/now_playing_window.py`
- 接入 `AudioVisualizerWidget`
- 连接 `engine.visualizer_frame`
- 根据 `supports_visualizer()` 自动显示/隐藏

## 4. 数据协议与渲染策略

统一帧协议（dict）：

```python
{
  "mode": "spectrum" | "waveform",
  "bins": list[float],      # spectrum 时使用，归一化到 [0,1]
  "samples": list[float],   # waveform 时使用，归一化到 [-1,1]
  "timestamp_ms": int
}
```

约束：
- UI 只保留“最后一帧”（last-value-wins），不积压队列
- 目标刷新上限 30 FPS
- 非法帧（缺字段、空列表、数值越界）在 Widget 层容错并丢弃

## 5. 组件职责

### 5.1 AudioBackend（抽象层）

- 定义能力与信号，不承担具体绘图逻辑。
- 任何后端都可选择支持/不支持可视化。

### 5.2 MpvAudioBackend（实现层）

- 负责从 mpv 路径产出可视化帧。
- 必须满足：
  - 播放时稳定推送
  - 停止、切歌、cleanup 时正确释放资源
  - 推送异常不影响核心播放

### 5.3 PlayerEngine（编排层）

- 仅透传可视化信号，不做二次分析。
- 保持 UI 与后端解耦，便于后续扩展。

### 5.4 AudioVisualizerWidget（UI 渲染层）

- 仅关注“最后一帧 + 当前模式”的绘制。
- 渲染策略：
  - `spectrum`：柱状 + 轻量渐变/圆角（低成本）
  - `waveform`：中心线 + 折线（抗锯齿）
- 不在 UI 线程做 FFT 或重计算。

## 6. 交互与用户体验

- 默认模式：`spectrum`
- 模式切换：预留按钮或上下文菜单（首期可先仅内部接口）
- 后端不支持时：可视化区域自动隐藏，不显示错误弹窗
- 暂停时：画面冻结或渐隐到静态（二选一，首期建议冻结）

## 7. 异常处理与降级策略

1. mpv 可视化初始化失败：
- 记录 warning
- 将能力视为不支持
- 播放功能保持正常

2. 帧数据异常：
- 后端层尽量规范化
- Widget 层再次兜底，异常帧丢弃

3. 生命周期问题：
- `NowPlayingWindow` 关闭时主动断开连接
- `PlayerEngine` 销毁时停止透传
- `MpvAudioBackend.cleanup()` 保证计时器/观察器清理

## 8. 测试设计

### 8.1 基础设施层

- `tests/test_infrastructure/test_mpv_backend.py`
  - `supports_visualizer()` 返回 True
  - 播放/暂停/停止触发推送启停符合预期

- `tests/test_infrastructure/test_audio_engine.py`
  - 后端帧能透传到 engine
  - cleanup 后不再继续透传

### 8.2 UI 层

- `tests/test_ui/test_audio_visualizer_widget.py`（新增）
  - `set_mode()` 生效
  - 合法/非法帧输入不崩溃
  - 空数据时可安全绘制

- `tests/test_ui/test_now_playing_window_*.py`
  - mpv 支持时可视化区域显示并接收帧
  - qt 后端时区域隐藏

## 9. 实施边界（本期不做）

- 不实现整首静态波形预计算
- 不实现瀑布谱、3D、粒子等重渲染效果
- 不在 qt 后端补齐实时分析链路

## 10. 风险与缓解

1. 风险：mpv 某些环境下可视化数据源不可用
- 缓解：快速降级为 `supports_visualizer=False`

2. 风险：高刷新率导致 UI 抖动
- 缓解：30 FPS 限制 + 仅保存最后一帧

3. 风险：切歌时短暂空帧闪烁
- 缓解：允许短暂空帧，保持实时性优先，不回放历史帧

## 11. 验收标准

- 在 mpv 后端播放音频时，Now Playing 页面能实时看到频谱或波形变化
- 暂停/停止后可视化行为符合设计（冻结或停更）
- qt 后端下无异常日志轰炸，无崩溃，可视化区域自动隐藏
- 所有新增测试通过

## 12. 后续扩展点

- 增加 UI 模式切换控件与用户配置持久化
- 在不改 UI API 的前提下，将后端数据源替换为自研 FFT 管线
- 增加主题联动（颜色、渐变、透明度）
