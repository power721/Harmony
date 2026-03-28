# Search History Click Fix

## Issue

点击搜索历史无法搜索，但点击热搜词可以搜索。

## Root Cause

Search history items had the `mousePressEvent` attached to the inner `QLabel`, but the label was wrapped in a parent `QWidget` with a hover style. This caused the parent widget to potentially intercept mouse events.

Hot search items worked because they were simple `QLabel` widgets added directly to the container without a parent wrapper.

## Solution

Moved the `mousePressEvent` and cursor from the inner `QLabel` to the outer `item_widget`, making the entire history item row clickable. This matches the behavior of hot search items and ensures proper event handling.

## Files Modified

- `ui/views/online_music_view.py`: Updated `_add_history_item` method to attach click handler to `item_widget` instead of `label`
