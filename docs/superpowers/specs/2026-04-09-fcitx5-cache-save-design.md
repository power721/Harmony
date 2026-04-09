# 2026-04-09 fcitx5 cache save design

## Goal
- Make the Linux GitHub Actions workflow save the built fcitx5 Qt6 plugin cache immediately after a successful build instead of relying on post-job cache persistence.

## Scope
- Update the Linux build workflow in `.github/workflows/build.yml`.
- Keep the existing cache key format based on Qt version and runner OS.
- Improve readability by separating restore, build/restore decision, and save responsibilities.

## Design
- Replace the single `actions/cache@v4` step with explicit `actions/cache/restore@v4` and `actions/cache/save@v4` steps.
- Gate the plugin build on the restore step output so a cache hit skips compilation.
- Save the cache only when there was a miss and the plugin file was produced.
- Preserve the existing cache directory `~/.cache/fcitx5-qt6-plugin` so the build script and restore path stay aligned.

## Verification
- Add a regression test in `tests/test_release_build.py` that inspects `.github/workflows/build.yml` and asserts the Linux workflow uses restore/save cache actions for fcitx5.
- Run the targeted pytest case after the workflow edit.
