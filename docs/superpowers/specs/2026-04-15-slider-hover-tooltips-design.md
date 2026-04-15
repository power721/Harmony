# Slider Hover Tooltips Design

## Goal

Add hover tooltips to playback sliders so the progress slider previews the target time and the volume slider shows the current percentage.

## Scope

- Extend the shared `ClickableSlider` widget with optional hover tooltip formatting.
- Wire the main player controls progress slider to display the hovered seek time.
- Wire the main player controls volume slider to display `NN%`.
- Preserve existing click-to-seek and drag behavior.

## Design

### Shared Slider Behavior

`ClickableSlider` will gain an optional formatter callback that receives the slider value under the cursor and returns tooltip text. When a formatter is configured, the slider enables mouse tracking, shows a tooltip on hover/move, and hides it on leave.

### Progress Slider

`PlayerControls` will configure the progress slider formatter after widget creation. The formatter will map slider values from `0..1000` to the current effective duration and return the formatted playback time via `format_time`. If no duration is available yet, it will return an empty string so no tooltip is shown.

### Volume Slider

`PlayerControls` will configure the volume slider formatter to return `f"{value}%"`.

## Risks

- Hover logic must not interfere with handle dragging or existing click-to-seek behavior.
- Progress tooltip output depends on duration fallback logic, so it should reuse the same effective-duration helper already used by seek handling.

## Testing

- Add unit-style UI tests for `ClickableSlider` formatter plumbing and tooltip text generation.
- Add focused `PlayerControls` tests for progress time formatting and volume percentage formatting without constructing the full window stack.
