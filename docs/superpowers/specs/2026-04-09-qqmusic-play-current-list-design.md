# QQMusic Play Current List Design

**Goal**

Unify QQ online-song playback so double-click and context-menu `play` always queue the full current song list and start playback from the chosen song, instead of playing only the selected track(s).

**Scope**

- Applies to QQ online song lists hosted by `plugins/builtin/qqmusic/lib/online_music_view.py`
- Includes ranking table, ranking list view, search result table, and any other current-list song table/list entry points already routed through `OnlineMusicView`
- Does not change `insert to queue`, `add to queue`, `download`, or favorite actions

**Design**

- Keep `play_online_tracks(start_index, tracks_data)` as the canonical “play this whole list from here” signal
- Add a small helper in `OnlineMusicView` that emits the current visible track list with a chosen start index
- Route ranking double-click, ranking list activation, and context-menu `play` through that helper
- For context-menu `play`, use the first selected song's position within the current visible list as the start index
- Preserve existing order from `self._current_tracks`

**Behavior Rules**

- Double-click a song in any QQ online current list: queue the whole current list and start from that song
- Right-click `play` on one or more songs: queue the whole current list and start from the first selected song in current-list order
- If the selected song cannot be found in the current list, do nothing
- Multi-select does not create a partial queue for `play`; only queue actions remain partial

**Testing**

- Regression test for ranking list activation emitting `play_online_tracks` with the clicked song index
- Regression test for selected-track play emitting the whole current list from the first selected song
- Existing single-track direct-play tests should be updated to the new whole-list behavior where applicable
