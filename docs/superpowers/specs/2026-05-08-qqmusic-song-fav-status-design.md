# QQMusic Song Favorite Status Design

**Date**: 2026-05-08
**Scope**: `plugins/builtin/qqmusic` song-list QQ favorite status query and context-menu behavior
**Strategy**: targeted behavior fix, keep host-side local favorite flow unchanged

## Problem

The QQ Music plugin currently exposes a right-click action for `add_to_qq_favorites` / `remove_from_qq_favorites`, but the menu state is not driven by QQ Music remote favorite status.

Today the online tracks list reuses one `favorite_mids` set for two different concepts:

- local Harmony favorites for cloud tracks
- QQ Music remote song favorites

Because the QQ Music menu item reads that shared local set, it can show the wrong action label. A song that is already favorited on QQ Music may still show `add_to_qq_favorites`, and a local favorite may incorrectly look like a QQ Music favorite.

The requested behavior is:

- query QQ Music song favorite status in batch when a song list is loaded
- cache that status for the current list
- use the cached QQ favorite state to decide whether the context menu shows `收藏到QQ音乐` or `取消收藏到QQ音乐`

## Goals

- Add batch QQ song favorite status querying by `songMid`
- Cache QQ favorite status for the currently loaded online track list
- Drive the QQ Music context-menu label from QQ remote status only
- Update cached QQ favorite state immediately after successful favorite / unfavorite actions
- Preserve existing local favorite behavior and UI wiring

## Non-Goals

- No redesign of local favorites
- No global cross-page QQ favorite cache
- No change to album or playlist favorite status logic
- No change to table-based playlist or artist song views unless they already consume the list-view path
- No additional persistent storage for QQ favorite status

## Current State

Relevant current behavior is split across these files:

- [plugins/builtin/qqmusic/lib/qqmusic_client.py](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/qqmusic_client.py): low-level QQ Music request wrapper, currently has song favorite mutation methods but no song favorite status read method
- [plugins/builtin/qqmusic/lib/qqmusic_service.py](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/qqmusic_service.py): service wrapper that exposes `fav_song` and `unfav_song`
- [plugins/builtin/qqmusic/lib/plugin_online_music_service.py](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/plugin_online_music_service.py): plugin-facing adapter for QQ pages
- [plugins/builtin/qqmusic/lib/online_tracks_list_view.py](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/online_tracks_list_view.py): list model and right-click menu wiring for online songs
- [plugins/builtin/qqmusic/lib/context_menus.py](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/context_menus.py): builds the online track context menu
- [plugins/builtin/qqmusic/lib/online_detail_view.py](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/online_detail_view.py): displays album-style song lists and handles QQ favorite actions

The main defect is in the list-view and menu path:

- `OnlineTracksListView` keeps `_favorite_mids` and uses it for both star rendering and QQ menu behavior
- `OnlineTrackContextMenu.show_menu(...)` receives only one favorite set, so its QQ menu item cannot distinguish local favorites from QQ favorites
- `_on_list_qq_fav_toggle(...)` performs remote mutations but does not update any dedicated QQ status cache in the list

## Recommended Approach

Keep the fix scoped to the QQ plugin and split local-vs-remote favorite state explicitly.

The recommended design is:

1. add a batch song favorite status read API in `QQMusicClient`
2. expose a normalized service method that returns QQ-favorited `songMid` values for a given list
3. pass a dedicated QQ favorite set into `OnlineTracksListView.load_tracks(...)`
4. update `OnlineTrackContextMenu` to choose the QQ menu label from that dedicated QQ set
5. update the cached QQ set after successful remote favorite mutations

This is the smallest change that fixes the bug without disturbing host-side favorite behavior.

## API Design

### `QQMusicClient`

Add a batch read method for song favorite status:

- module: `music.musicasset.SongFavRead`
- method: `IsSongFanByMid`
- request param:
  - `v_songMid: list[str]`

Expected response handling:

- `code == 0`: read `data.m_fan`, where each `songMid` maps to `true` when favorited
- `code == 1000`: treat as "not favorited" for the requested songs, not as a hard error
- empty response, malformed response, or other non-zero codes: treat as query failure and return an empty result

The client method should return a `dict[str, bool]` keyed by `songMid`, because that shape matches the upstream API and makes service-level filtering straightforward.

### `QQMusicService`

Add a helper such as `get_song_fav_status(song_mids: list[str]) -> dict[str, bool]`.

Behavior rules:

- if there is no credential, return an empty mapping
- deduplicate mids before making the request
- ignore empty mids
- on `code == 1000`, return `False` for all requested mids
- on transport or parsing failure, log and return an empty mapping

### `PluginOnlineMusicService`

Add a plugin-facing helper such as `get_song_favorite_mids(song_mids: list[str]) -> set[str]`.

This adapter should:

- call the provider-backed QQ service method when available
- convert the mapping to a `set[str]` containing only mids with `True`
- return an empty set when logged out or unavailable

The plugin-facing layer should expose only the set because the list view only needs membership checks.

## UI Design

### Separate Favorite State

`OnlineTracksModel` and `OnlineTracksListView` should stop using one set for two different meanings.

Target state:

- local favorite mids remain available for existing in-list star rendering and event-bus updates
- QQ favorite mids become a second explicit set used only for QQ remote favorite menu behavior

A minimal shape is:

- `_favorite_mids`: existing local favorite state
- `_qq_favorite_mids`: new QQ remote favorite state

### `load_tracks(...)`

Extend `OnlineTracksListView.load_tracks(...)` and model reset wiring to accept both:

- `favorite_mids`
- `qq_favorite_mids`

For call sites that do not have QQ status data, default `qq_favorite_mids` to an empty set.

### Context Menu

Extend `OnlineTrackContextMenu.show_menu(...)` to accept `qq_favorite_mids`.

QQ menu label rule:

- if every selected track with a valid `mid` is present in `qq_favorite_mids`, show `remove_from_qq_favorites`
- otherwise show `add_to_qq_favorites`

This rule intentionally does not depend on local favorite state.

### Mutation Updates

After `_on_list_qq_fav_toggle(...)` successfully favorites or unfavorites songs, update the in-memory QQ favorite set on the list view immediately.

That avoids stale menu labels until the page is reloaded.

The existing `favorites_collection_changed("fav_songs")` signal should remain, because other QQ pages may depend on it to refresh collection views.

## Data Flow

### List Load

For album-style pages that use `OnlineTracksListView`:

1. `OnlineDetailView` prepares the current page of `OnlineTrack` instances
2. it extracts non-empty `track.mid` values
3. it asks `PluginOnlineMusicService` for the QQ-favorited mids for that page
4. it calls `load_tracks(songs, qq_favorite_mids=...)`
5. the list view caches both local and QQ favorite sets
6. the context menu reads the cached QQ set when shown

### Favorite / Unfavorite

1. user triggers QQ favorite action from the context menu
2. `OnlineDetailView._on_list_qq_fav_toggle(...)` calls `fav_song(...)` or `unfav_song(...)`
3. if at least one mutation succeeds, the list view QQ favorite cache is updated for the affected mids
4. `favorites_collection_changed("fav_songs")` is emitted as it is today

## Error Handling

- Logged out: skip remote status query and use an empty QQ favorite set
- `code == 1000`: interpret as requested songs not favorited
- Partial/invalid `m_fan` payload: use only valid boolean entries and treat missing mids as `False`
- Query failure: log at warning or error level and continue with an empty QQ favorite set
- Mutation failure: do not update cached QQ favorite state for the failed songs

The UI should degrade to the safe default of `add_to_qq_favorites` when status cannot be determined.

## Testing

Add or update focused tests in:

- [tests/test_services/test_qqmusic_client_favorites.py](/home/harold/workspace/music-player/tests/test_services/test_qqmusic_client_favorites.py)
- [tests/test_ui/test_online_tracks_list_view.py](/home/harold/workspace/music-player/tests/test_ui/test_online_tracks_list_view.py)
- any existing QQ detail-view tests that already cover list-view favorite actions

Required coverage:

1. `QQMusicClient` sends `SongFavRead.IsSongFanByMid` with `v_songMid`
2. `QQMusicClient` treats `code == 1000` as "not favorited"
3. plugin/service adapter converts returned mapping to a set of favorited mids
4. `OnlineTrackContextMenu` shows `remove_from_qq_favorites` only when all selected tracks are remotely favorited
5. local favorite mids do not affect the QQ menu label
6. successful QQ favorite / unfavorite actions update the cached QQ favorite mids in the list view

## Risks

- Some list-view call sites may currently assume a single favorite set and need small signature updates
- The album/list distinction in `OnlineDetailView` means only the list-view path should be changed unless table views are intentionally brought into scope later
- If QQ returns status mappings with inconsistent key types, the service layer must normalize them to strings before the UI consumes them

## Acceptance Criteria

- Opening a QQ online list that uses `OnlineTracksListView` performs one batch QQ favorite status query for the current page when logged in
- Right-clicking a remotely favorited song shows `取消收藏到QQ音乐`
- Right-clicking a song not remotely favorited shows `收藏到QQ音乐`
- Local Harmony favorite state does not change the QQ menu label
- After a successful QQ favorite or unfavorite action, reopening the context menu shows the updated label without requiring a page reload
