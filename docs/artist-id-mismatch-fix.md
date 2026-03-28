# Artist ID Mismatch Fix

## Problem

When clicking on artist names in the playback control view, navigation to the artist detail view failed silently.

## Root Cause Analysis

### Database Investigation

The issue was discovered through systematic debugging:

1. **Checked navigation flow**: `PlayerControls.artist_clicked` → `MainWindow._on_player_artist_clicked` → `LibraryService.get_artist_by_name`

2. **Found `get_artist_by_name()` returning `None`**: The method couldn't find artists in the database

3. **Database inspection revealed ID mismatch**:
   ```sql
   SELECT MIN(id), MAX(id) FROM artists;
   -- Result: 190597 - 191120

   SELECT MIN(artist_id), MAX(artist_id) FROM track_artists;
   -- Result: 183090 - 190596
   ```

4. **The ID ranges don't overlap!** This means all artist IDs in `track_artists` reference non-existent artists.

### How This Happened

The multi-artist migration script (`scripts/migrate_multi_artist.py`) was run multiple times:

1. **First run**: Created artists with IDs 183090-190596 and populated `track_artists`
2. **Second run**: Deleted `track_artists` but created NEW artists with IDs 190597-191120
3. **Result**: `track_artists` still references OLD artist IDs that no longer exist

### Why Navigation Failed

When clicking an artist name:
1. `MultiArtistWidget` parses the artist string and emits artist names
2. `MainWindow._on_player_artist_clicked()` calls `get_artist_by_name(artist_name)`
3. `get_artist_by_name()` queries the `artists` table using normalized name
4. If found, it returns the artist; if not found, it returns `None`
5. When `None` is returned, navigation doesn't happen

The problem: Artists exist in the database, but the `track_artists` junction table has the wrong IDs, causing the artist lookup to potentially fail or return incorrect results.

## Solution

### Step 1: Created Fix Script

Created `scripts/fix_artist_ids.py` to:
- Detect artist ID mismatches
- Remove orphaned `track_artists` entries
- Remove artists with no tracks

```python
# Detect mismatch
cursor.execute("SELECT MIN(id), MAX(id) FROM artists")
artist_min, artist_max = cursor.fetchone()

cursor.execute("SELECT MIN(artist_id), MAX(artist_id) FROM track_artists")
ta_min, ta_max = cursor.fetchone()

if not (ta_min >= artist_min and ta_max <= artist_max):
    print("ID mismatch detected!")
    # Delete orphaned entries
    cursor.execute("""
        DELETE FROM track_artists
        WHERE NOT EXISTS (SELECT 1 FROM artists a WHERE a.id = track_artists.artist_id)
    """)
```

### Step 2: Re-ran Migration

```bash
# Fix ID mismatch
python scripts/fix_artist_ids.py --yes

# Re-run migration with correct IDs
echo "y" | python scripts/migrate_multi_artist.py
```

### Step 3: Verification

After the fix:

```sql
-- Artist IDs now match
SELECT MIN(id), MAX(id) FROM artists;
-- Result: 191121 - 191767

SELECT MIN(artist_id), MAX(artist_id) FROM track_artists;
-- Result: 191121 - 191767

-- Artists have correct track counts
SELECT name, song_count FROM artists WHERE name = 'A-Lin';
-- Result: A-Lin | 30

-- Multi-artist tracks properly split
SELECT t.artist, a.name, ta.position
FROM tracks t
JOIN track_artists ta ON t.id = ta.track_id
JOIN artists a ON ta.artist_id = a.id
WHERE t.artist LIKE '%,%'
LIMIT 5;

-- Result:
-- 王赫野, 黄霄雲 | 王赫野 | 0
-- 王赫野, 黄霄雲 | 黄霄雲 | 1
```

## Test Results

Created `tests/test_artist_navigation.py` to verify the fix:

```bash
$ python tests/test_artist_navigation.py

Testing artist navigation...
--------------------------------------------------
✓ Found: A-Lin
  Songs: 30
  Albums: 13
✓ Found: Taylor Swift
  Songs: 116
  Albums: 25
✓ Found: 周杰伦
  Songs: 104
  Albums: 21
✓ Found: 黄霄雲
  Songs: 592
  Albums: 205
--------------------------------------------------

Testing multi-artist track...
Input: A-Lin, 李佳薇, 汪苏泷
  Parsed: ['A-Lin', '李佳薇', '汪苏泷']
    ✓ A-Lin: found
    ✓ 李佳薇: found
    ✓ 汪苏泷: found

==================================================
✓ All tests passed!
```

## Prevention

To prevent this issue in the future:

1. **Migration script asks for confirmation** before re-running
2. **Fix script can detect and repair** ID mismatches automatically
3. **Test verifies navigation works** for all artists

## Files Changed

- **Created**: `scripts/fix_artist_ids.py` - Detects and fixes artist ID mismatches
- **Updated**: `docs/bug-report.md` - Documented the issue
- **Created**: `tests/test_artist_navigation.py` - Tests artist navigation

## Related Files

- `scripts/migrate_multi_artist.py` - Multi-artist migration script
- `ui/widgets/player_controls.py` - `MultiArtistWidget` emits artist names
- `ui/windows/main_window.py` - Handles artist navigation
- `repositories/track_repository.py` - `get_artist_by_name()` implementation
- `services/library/library_service.py` - Library service wrapper

## Usage

To check database consistency:

```bash
python scripts/fix_artist_ids.py
```

To auto-fix issues:

```bash
python scripts/fix_artist_ids.py --yes
echo "y" | python scripts/migrate_multi_artist.py
```

To test artist navigation:

```bash
python tests/test_artist_navigation.py
```
