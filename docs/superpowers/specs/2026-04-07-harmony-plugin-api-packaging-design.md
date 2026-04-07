# Harmony Plugin API Packaging Design

## Goal

将 `harmony_plugin_api` 整理为可独立发布的 pip 包 `harmony-plugin-api`，并确保发布内容只包含插件 SDK 的纯接口层，不包含任何 Harmony 宿主实现。

## Scope

本次设计覆盖：

- `harmony_plugin_api` 的发布边界
- 当前仓库内的子包发布结构
- 宿主实现从 SDK 中剥离的迁移方式
- 插件侧 API 使用方式的稳定边界

本次不覆盖：

- 立刻拆独立仓库
- PyPI 发布账号、token、release automation
- 插件市场协议或远程安装协议

## Current State

当前 `harmony_plugin_api` 直接位于主仓库根目录下，没有独立的打包配置。

它原本主要承载纯接口定义：

- manifest / capability 定义
- plugin protocol
- context protocol
- media / lyrics / cover / online models
- registry spec types

但当前分支中又加入了两类不适合独立发布的模块：

- `harmony_plugin_api.ui`
- `harmony_plugin_api.runtime`

这两个模块直接依赖 Harmony 宿主实现，例如：

- `system.theme`
- `ui.dialogs.*`
- `ui.icons`
- `services.online`
- `app.bootstrap`
- `infrastructure.*`

因此现在的 `harmony_plugin_api` 还不是一个真正独立的 SDK，而是“接口定义 + 宿主运行时桥接”的混合体。

## Problems

### 1. 发布边界不干净

如果直接把当前目录发布到 pip，安装方必须同时拥有 Harmony 宿主源码布局，否则 `ui/runtime` 模块会导入失败。

### 2. SDK 和宿主实现耦合

插件 SDK 应该只定义“宿主会提供什么”，不应该自己实现“宿主如何提供”。

### 3. 版本管理不清晰

主项目版本和 SDK 版本需要独立演进。继续共用根 `pyproject.toml` 会让依赖、构建、发布语义混在一起。

## Approaches

### Approach A: 仓库内独立子包发布

在当前仓库新增 `packages/harmony-plugin-api/`，把 SDK 源码与发布配置集中在该目录。

优点：

- 迭代成本最低
- 仍可与宿主代码同仓协同开发
- 版本边界、构建边界明确

缺点：

- 需要增加一套子包构建配置

### Approach B: 根仓库直接多包发布

继续使用根仓库作为构建入口，只把 `harmony_plugin_api` 单独选出来发布。

优点：

- 配置看似更少

缺点：

- 主项目和 SDK 发布边界容易继续缠绕
- 后续做独立版本管理会更痛苦

### Approach C: 立即拆独立仓库

把 SDK 从当前仓库完全拆走，单独维护和发布。

优点：

- 边界最彻底

缺点：

- 当前工作量最大
- 会引入同步开发和 CI 迁移成本

## Recommendation

采用 Approach A。

原因：

- 能最快把 SDK 收敛成可发布形态
- 不阻碍后续再拆独立仓库
- 最符合当前“先发布，再稳定演进”的节奏

## Design

### 1. Package Layout

新增子包目录：

- `packages/harmony-plugin-api/pyproject.toml`
- `packages/harmony-plugin-api/README.md`
- `packages/harmony-plugin-api/src/harmony_plugin_api/`

发布源代码只来自这个子包目录。

根目录下现有 `harmony_plugin_api/` 不再作为最终发布源。实现时可以采用两种过渡方式中的一种：

- 直接迁移到 `packages/.../src/harmony_plugin_api/`
- 或先复制到子包目录，再逐步把主仓库导入切到子包安装路径

优先推荐直接迁移，避免双份源码长期并存。

### 2. SDK Content Boundary

`harmony-plugin-api` 只包含纯 SDK 模块：

- `__init__.py`
- `manifest.py`
- `plugin.py`
- `context.py`
- `media.py`
- `lyrics.py`
- `cover.py`
- `online.py`
- `registry_types.py`

这些模块只允许依赖：

- Python 标准库
- `typing`
- `dataclasses`
- `pathlib`

不允许依赖 Harmony 宿主包，也不要求 Qt / requests / PySide6。

### 3. Host Runtime Boundary

下列能力不属于 SDK 发布内容：

- `ThemeManager`
- `MessageDialog`
- `DialogTitleBar`
- icon 获取
- Bootstrap / EventBus
- 在线服务创建
- cache / HTTP / playlist 工具

它们应移动到宿主侧模块，例如：

- `system/plugins/plugin_sdk_runtime.py`
- 或 `system/plugins/sdk_bridge/*.py`

宿主负责把这些实现注入 `PluginContext`。

### 4. Context Contract

`PluginContext` 继续作为插件唯一稳定入口。

插件使用边界为：

- `context.settings`
- `context.storage`
- `context.ui`
- `context.services`
- `context.http`
- `context.events`

其中 `context.ui.theme` / `context.ui.dialogs` 在 SDK 中只保留 `Protocol` 定义，不提供实现模块。

也就是说：

- 可以有 `PluginThemeBridge` / `PluginDialogBridge` 协议
- 不能再有 `harmony_plugin_api.ui` 这种宿主实现模块

### 5. Plugin Import Rules

发布后的规则应收敛为：

- 插件可以 import `harmony_plugin_api.*`
- 插件可以 import 自己包内模块
- 插件可以 import 允许的第三方依赖或标准库
- 插件不能 import Harmony 宿主源码包

当前运行时导入守卫和安装时审计应继续存在，但判定依据应该面向“宿主包禁止”，而不是依赖 SDK 中的宿主实现模块。

### 6. Versioning

SDK 采用独立版本号，例如 `0.1.0`。

插件 manifest 中的 `api_version` 仍作为插件协议级版本；
pip 包版本则作为 SDK 发行版本。两者不要求完全一致，但宿主需要定义兼容关系。

首个版本先保持简单：

- `api_version = "1"` 不变
- pip 包发布 `0.1.0`

### 7. Migration Plan

迁移分三步：

#### Step 1

把 SDK 纯接口模块迁到子包目录，建立独立 `pyproject.toml`，保证可以单独构建 wheel/sdist。

#### Step 2

把 `harmony_plugin_api.ui` / `runtime` 中的宿主实现移动到主项目宿主桥接层。

同时修改：

- `system/plugins/host_services.py`
- QQ 插件中的桥接引用

使插件只通过 `context` 获取宿主能力，而不是 import SDK 内的宿主实现。

#### Step 3

增加验证：

- 子包可构建
- wheel 可安装并可导入
- SDK 中不存在对宿主包的直接依赖
- 现有插件与宿主集成仍通过测试

## Risks

### 1. 双份源码漂移

如果根目录和子包目录长期同时维护 `harmony_plugin_api`，很容易漂移。

设计要求尽快收敛为单一发布源。

### 2. 插件侧仍残留对 SDK 宿主实现模块的依赖

如果仍保留 `harmony_plugin_api.ui/runtime`，未来外部插件会继续错误依赖这些模块。

设计上应直接删除或停用它们，而不是长期保留。

### 3. 主项目导入路径切换带来回归

主项目内大量地方已经 import `harmony_plugin_api.*`。迁移时需要保证：

- 开发环境仍能正常导入
- 测试环境导入解析稳定

## Testing

至少要覆盖：

- 子包构建测试
- wheel 安装后导入测试
- SDK 源码静态扫描，确认无宿主依赖
- 插件导入审计测试
- `PluginContext` 宿主桥接测试

## Result

完成后，`harmony-plugin-api` 将成为一个真正独立、可发布、仅含纯接口定义的 pip 包；
Harmony 宿主实现继续留在主项目中，通过 `PluginContext` 向插件暴露能力。
