# Repository Guidelines

## Project Structure & Module Organization
Harmony is a Python desktop music player built on PySide6 with a layered architecture.
- `app/` and `main.py`: application bootstrap and startup wiring.
- `domain/`: pure data/domain models (no UI or infrastructure imports).
- `services/`: business logic (playback, library, lyrics, cloud, metadata).
- `repositories/`: database access and persistence adapters.
- `infrastructure/`: technical integrations (audio backends, DB manager, HTTP, caches, fonts).
- `ui/`: windows, dialogs, widgets, views, and controllers.
- `system/`: cross-cutting runtime concerns (config, theme, i18n, event bus, hotkeys).
- `tests/`: pytest suite split by layer (`test_domain/`, `test_services/`, `test_ui/`, etc.).
- `docs/`, `icons/`, `fonts/`, `translations/`: documentation and static assets.

## Build, Test, and Development Commands
Use `uv` for local development.
- `uv sync` installs dependencies from `pyproject.toml`/`uv.lock`.
- `uv run python main.py` launches the app.
- `uv run pytest tests/` runs the full test suite.
- `uv run pytest tests/test_ui/ -m "not slow"` runs faster UI-focused checks.
- `uv run ruff check .` runs lint checks (install with `uv sync --extra dev` if needed).
- `./build.sh` runs platform-detected packaging; use `python build.py <linux|macos|windows>` for explicit targets.
- GitHub Actions use [release.sh](release.sh) to build Linux AppImage.

## Coding Style & Naming Conventions
- Follow PEP 8, 4-space indentation, and type annotations.
- Prefer `@dataclass` for domain entities.
- Keep layer boundaries strict: UI depends on services/domain; domain stays independent.
- File and module names use `snake_case`; classes use `PascalCase`; tests use `test_*.py`.
- Keep logging consistent with project format: `[LEVEL] logger - message`.

## Testing Guidelines
Pytest configuration is in `pytest.ini` (`--strict-markers`, `--tb=short`, verbose mode).
- Naming: `test_*.py`, classes `Test*`, functions `test_*`.
- Markers: `unit`, `integration`, `slow`.
- Prefer focused tests near the affected layer (example: queue logic changes go under `tests/test_services/` and/or `tests/test_repositories/`).

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects (often concise Chinese phrases), e.g. `修复进度条`, `优化打包`.
- Keep commit titles brief and action-oriented; split unrelated changes.
- PRs should include: problem summary, scope, test commands run, and screenshots/GIFs for UI changes.
- Target `main`/`master`; GitHub Actions will run build validation on PRs.
