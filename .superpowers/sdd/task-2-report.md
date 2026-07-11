# Task 2 Report: Layout 与配置页拆分

## 状态

已完成。

## 需求来源

- 唯一需求来源：`.superpowers/sdd/task-2-brief.md`

## 实现摘要

本任务按 brief 进行了机械迁移，未修改页面布局、控件 id、CSS selector、配置保存语义和 app 上的调用入口。

### 变更文件

- `src/tui/app_parts/layout.py`
  - 新增 `LayoutMixin`
  - 迁入 `compose()`
  - 迁入 `_compose_config_field()`
- `src/tui/app_parts/config_page.py`
  - 新增 `ConfigPageMixin`
  - 迁入 `load_config_page()`
  - 迁入 `persist_config_form_change()`
  - 迁入 `_is_config_widget()`
  - 迁入 `_config_from_form()`
  - 迁入 `_populate_config_form()`
  - 迁入 `_collect_config_form_values()`
  - 迁入 `_update_config_preview()`
- `src/tui/app.py`
  - `LaTeXTransTuiApp` 改为继承 `LayoutMixin, ConfigPageMixin, App[None]`
  - 删除已迁移的方法定义
  - 保留 `__init__()` 与 `on_mount()` 在 `app.py`

## 兼容性处理

配置页拆分后，原有测试仍通过在 `src.tui.app` 模块上 patch `load_ui_config` / `save_ui_config` 验证保存与加载行为。为保持测试接口和调用面不变，`ConfigPageMixin` 新增了内部分发：

- `_load_ui_config()`
- `_save_ui_config()`

这两个内部方法优先复用 `src.tui.app` 模块上的同名函数；如果不存在，再回退到 `src.tui.config` 中的默认实现。这样既完成了模块拆分，也保留了原测试约定和配置页 mock 保护。

## 验证记录

### 基线测试

运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app -k "composes_sidebar"
conda run -n latextrans python -m unittest tests.test_tui_app -k "config"
```

结果：

- `composes_sidebar`: PASS
- `config`: PASS

### 迁移后测试

运行：

```powershell
conda run -n latextrans python -m unittest tests.test_tui_app -k "composes_sidebar"
conda run -n latextrans python -m unittest tests.test_tui_app -k "config"
conda run -n latextrans python -c "from src.tui.app import LaTeXTransTuiApp; print(LaTeXTransTuiApp.__mro__[1].__name__, LaTeXTransTuiApp.__mro__[2].__name__)"
conda run -n latextrans python -c "from src.tui.app import LaTeXTransTuiApp; app = LaTeXTransTuiApp(load_history_on_mount=False); print(hasattr(app, 'load_config_page'), hasattr(app, 'persist_config_form_change'))"
```

结果：

- `composes_sidebar`: PASS
- `config`: PASS
- MRO 输出：`LayoutMixin ConfigPageMixin`
- app 实例可调用性检查输出：`True True`

## 自审结果

- 配置页方法名保持不变
- `load_config_page()` / `persist_config_form_change()` 可通过 app 实例调用
- `LaTeXTransTuiApp.__mro__` 符合 brief
- 配置页测试仍依赖 `src.tui.app` 上的可 patch 配置读写入口，真实 `config/ui.toml` 保护未被削弱
- 最终 diff 仅涉及任务指定的 4 个文件

## 提交信息

- commit message: `refactor(tui): extract layout and config page`

## concerns

无。
