# Eyedropper + Tolerance Grouping — Design Spec
_Date: 2026-04-06_

## Problem

PDFs with anti-aliased text or many similar shades can produce dozens of near-identical colors in the sidebar list, making it hard to assign actions. Two features address this:
1. **Tolerance grouping** — merge similar colors into one representative entry
2. **Eyedropper** — click on the PDF preview to identify and select a color in the list

## Goals

- Add a tolerance slider (0–50) that groups colors within Euclidean RGB distance ≤ tolerance into one list entry
- Add a toggleable eyedropper button that lets the user click the PDF preview to auto-select the matching color group in the list
- Preserve existing action assignments when tolerance changes
- No changes to `pdf_editor.py`, `pdf_parser.py`, or `renderer.py`

## Out of Scope

- Perceptual color distance (LAB/ΔE) — Euclidean RGB is sufficient for RISO use
- Eyedropper staying active across multiple clicks — deactivates after one pick
- GUI tests

---

## Architecture & Data Flow

```
Raw colors ──► group_colors(tolerance) ──► representatives ──► color list
                        │
                   groups dict
                  (rep → members)
                        │
              expanded mapping ◄── actions dict (rep → Action)
                        │
                 apply_mapping() ──► export / preview
```

`self._groups: dict[Color, list[Color]]` stores the current grouping (representative → member list). `self._actions` maps representative → Action (unchanged). Before calling `apply_mapping`, the mapping is expanded: every member gets its representative's action. `pdf_editor.py` is untouched.

### New / Changed Files

| File | Change |
|------|--------|
| `src/color_grouper.py` | New — grouping and eyedropper lookup logic |
| `src/main_window.py` | Add `PreviewLabel` subclass, tolerance slider, eyedropper button, grouping wiring |
| `tests/test_color_grouper.py` | New — unit tests for grouper |

---

## UI Layout

### Left Panel

```
COLORS
Tolerance: ──●────── 15     ← QSlider 0–50 + live value label
┌──────────────────────────┐
│ ● #ff0000  [→ black]     │
│ ● #0000ff  [delete]      │
└──────────────────────────┘
Action for selected:
○ Keep → Black
○ Delete
○ Keep as-is
[Apply]
```

- Slider default: **0** (no grouping — identical to current behavior)
- Moving the slider immediately regroups and rebuilds the list
- Existing action assignments transfer to new representatives (closest distance match)

### Toolbar

```
[Open PDF]  |  [Pick Color ◉]  [Export Layer]
```

- **Pick Color** is a checkable `QPushButton` (toggles on/off)
- When active: cursor on preview changes to `Qt.CursorShape.CrossCursor`
- After one successful pick: eyedropper deactivates automatically, cursor resets
- Button is disabled until a PDF is loaded

---

## `color_grouper.py`

### `group_colors(colors: set[Color], tolerance: int) -> dict[Color, list[Color]]`

- `tolerance == 0`: `{c: [c] for c in colors}` — no grouping, zero overhead
- `tolerance > 0`: greedy clustering
  1. Sort colors by (r, g, b) for deterministic output
  2. For each unassigned color, collect all other unassigned colors within Euclidean distance ≤ tolerance
  3. Representative = centroid: `Color(round(mean_r), round(mean_g), round(mean_b))`
  4. Repeat until all colors assigned

Distance formula: `sqrt((r1-r2)² + (g1-g2)² + (b1-b2)²)` in 0–255 space.

Practical reference: tolerance 15 ≈ very similar shades; 50 ≈ same rough hue family.

### `find_group(sampled: Color, groups: dict[Color, list[Color]]) -> Color`

Returns the representative whose group contains the member closest to `sampled`. Used by eyedropper after pixel sampling.

### Action Preservation on Slider Change

When the user moves the slider:
1. Re-run `group_colors` with the new tolerance
2. For each new representative, find the old representative whose members overlap or are closest
3. Transfer that old representative's action to the new one
4. New representatives with no clear match default to `Action.KEEP`

---

## Eyedropper Flow

1. User clicks **Pick Color** button → button enters checked state, `self._preview_label` cursor → `CrossCursor`
2. User clicks on preview → `PreviewLabel` emits `color_picked(QPoint)`
3. `MainWindow._on_color_picked(pos)`:
   - Sample `self._current_pixmap.toImage().pixelColor(pos)` → `QColor` → `Color(r, g, b)`
   - Call `find_group(sampled, self._groups)` → representative
   - Find and select the matching item in `self._color_list`
   - Scroll list to make item visible
   - Deactivate eyedropper: uncheck button, reset cursor

`PreviewLabel` is a small `QLabel` subclass defined inside `main_window.py`:
```python
class PreviewLabel(QLabel):
    color_picked = pyqtSignal(QPoint)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._eyedropper_active = False

    def set_eyedropper(self, active: bool) -> None:
        self._eyedropper_active = active
        cursor = Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)

    def mousePressEvent(self, event):
        if self._eyedropper_active and event.button() == Qt.MouseButton.LeftButton:
            self.color_picked.emit(event.pos())
        super().mousePressEvent(event)
```

`MainWindow` calls `self._preview_label.set_eyedropper(True/False)` to toggle mode.

---

## Error Handling

| Situation | Behavior |
|-----------|---------|
| Click outside pixmap bounds | Ignore — `pixelColor` returns invalid QColor, skip |
| Eyedropper click with no PDF | Button is disabled until PDF is loaded |
| Tolerance change with no PDF | No-op |
| All colors in one group (high tolerance) | Valid — one entry in list, actions work normally |

---

## Testing (`tests/test_color_grouper.py`)

- `tolerance=0` → each color is its own group, representative equals itself
- Two colors within tolerance → one group, representative is their centroid
- Two colors outside tolerance → two separate groups
- Three colors where A≈B and B≈C but A not ≈C → A+B group, C separate (greedy)
- `find_group` returns correct representative for exact member color
- `find_group` returns closest representative for a sampled color not in any group
- Action preservation: action transfers to new representative after tolerance change
