# QQMusic Nick Profile Link Design

## Overview

This document defines a small QQ Music UI adjustment in the online music page header. When the user is logged in and a QQ Music nickname is available, only the `nick` portion in the right-side login status should render as a clickable text link. Clicking that link should open the QQ Music profile page at `https://y.qq.com/n/ryqq_v2/profile/`.

The existing layout, login button behavior, and non-login states should remain unchanged.

## Goals

- Keep the current QQ Music page header layout intact.
- Render only the nickname text as a clickable link when `nick` exists.
- Open `https://y.qq.com/n/ryqq_v2/profile/` in the system browser when the nickname link is clicked.
- Preserve current behavior for:
  - logged-in state without a nickname
  - logged-out state
  - login and logout button text updates

## Non-Goals

- No changes to QQ Music login flow or credential storage.
- No changes to the target URL based on user identity.
- No redesign of the header or replacement of the status area with a new widget type.
- No changes to recommendation loading, favorites loading, or other QQ Music page behaviors.

## Current State

`plugins/builtin/qqmusic/lib/online_music_view.py` updates the right-side login status through `_update_login_status()` and `_refresh_login_status()`.

When login credentials exist:

- If plugin-scoped `nick` exists, the status label is set to plain text in the form `已登录为 {nick}`.
- If `nick` does not exist, the status label falls back to the generic logged-in text.

The status widget is currently treated as a plain text label.

## Recommended Approach

Keep the existing status label and switch the nickname rendering to rich text with an inline anchor.

Why this approach:

- It is the smallest possible change.
- It preserves the current layout and widget hierarchy.
- It keeps the clickable region limited to the nickname itself, matching the requirement exactly.
- It avoids introducing extra spacing and alignment risk from splitting the text into separate widgets.

## Behavior Design

### Logged In With Nick

Display the login status as:

- plain leading text from the existing translation key for `qqmusic_logged_in_as`
- a trailing clickable nickname anchor

Only the nickname should be clickable.

Click action:

- Open `https://y.qq.com/n/ryqq_v2/profile/` through Qt desktop URL handling.

### Logged In Without Nick

Keep the existing generic logged-in text with no link.

### Logged Out

Keep the existing not-logged-in text with no link.

## UI and Interaction Details

- The visible text should continue reading naturally as `已登录为 nick`.
- The nickname should look like a text link, not like a button.
- The label should allow external link handling through explicit signal wiring or equivalent controlled URL opening.
- The implementation should avoid making the entire label clickable.

## Implementation Notes

### OnlineMusicView

Update the login status rendering path in both `_update_login_status()` and `_refresh_login_status()` so they use one shared formatting rule:

- when `nick` exists, set rich text containing a single anchor around the escaped nickname
- when `nick` does not exist, keep the existing plain text path

If the view does not already configure the login status label for rich text links, add the minimal label setup needed during UI initialization:

- enable rich text / browser interaction as needed
- connect the link activation handler to open the fixed QQ Music profile URL

### Safety

- Escape the nickname before inserting it into rich text.
- Use a fixed destination URL instead of interpolating user data into the target.

## Testing

Add or extend UI-focused tests in `tests/test_ui/test_online_music_view_async.py`.

Required coverage:

- `_update_login_status()` with a stored nickname renders a link that targets `https://y.qq.com/n/ryqq_v2/profile/`
- `_refresh_login_status()` with a stored nickname renders the same link form
- existing behavior remains unchanged when nickname is empty

Tests do not need to open the browser. Verifying the rendered label text and link target is sufficient for this change.

## Risks and Mitigations

### Rich Text Rendering Risk

Risk:

- Switching from plain text to rich text could accidentally make more of the label interactive than intended.

Mitigation:

- Only wrap the nickname in the anchor.
- Keep the non-nickname prefix outside the anchor.

### Nickname Content Risk

Risk:

- Nicknames may contain characters that break HTML rendering.

Mitigation:

- HTML-escape the nickname before composing the label text.

## Acceptance Criteria

- On the QQ Music page, when logged in with a nickname, only the nickname text is clickable.
- Clicking the nickname opens `https://y.qq.com/n/ryqq_v2/profile/`.
- Logged-in without nickname still shows the normal non-link status text.
- Logged-out state remains unchanged.
- A UI test covers rich-text link rendering for the nickname state.
