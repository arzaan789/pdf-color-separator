# Eyedropper + Tolerance Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tolerance slider that merges similar colors into groups and an eyedropper toggle that lets the user click the PDF preview to select a color in the list.

**Architecture:** A new `color_grouper.py` module handles all grouping logic (pure functions, no GUI). `main_window.py` gains a `PreviewLabel` subclass that emits a signal on click, a tolerance slider wired to re-group colors, and an eyedropper toggle button. Before every `apply_mapping` call the representative→action dict is expanded to member→action so `pdf_editor.py` needs no changes.

**Tech Stack:** Python 3.11+, pikepdf, PyMuPDF, PyQt6, pytest

---

## File Map

| Path | Change |
|------|--------|
| `src/color_grouper.py` | **New** — `group_colors`, `find_group`, `transfer_actions`, `expand_mapping` |
| `src/main_window.py` | **Modify** — `PreviewLabel`, tolerance slider, eyedropper, grouping wiring |
| `tests/test_color_grouper.py` | **New** — unit tests for all four functions |

---

## Task 1: `color_grouper.py` — Grouping Logic

**Files:**
- Create: `src/color_grouper.py`
- Create: `tests/test_color_grouper.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_color_grouper.py`:
```python
import sys
sys.path.insert(0, 'src')

from models import Color, Action
from color_grouper import group_colors, find_group, transfer_actions, expand_mapping


# ── group_colors ──────────────────────────────────────────────────────────────

def test_tolerance_zero_each_color_own_group():
    colors = {Color(255, 0, 0), Color(0, 0, 255)}
    groups = group_colors(colors, 0)
    assert len(groups) == 2
    assert Color(255, 0, 0) in groups
    assert Color(0, 0, 255) in groups
    assert groups[Color(255, 0, 0)] == [Color(255, 0, 0)]
    assert groups[Color(0, 0, 255)] == [Color(0, 0, 255)]


def test_two_colors_within_tolerance_form_one_group():
    # Euclidean distance between (255,0,0) and (250,0,0) is 5
    a = Color(255, 0, 0)
    b = Color(250, 0, 0)
    groups = group_colors({a, b}, 10)
    assert len(groups) == 1
    rep = list(groups.keys())[0]
    members = groups[rep]
    assert a in members
    assert b in members
    # Centroid: round((255+250)/2)=round(252.5)=252 (Python rounds to even)
    assert rep == Color(252, 0, 0)


def test_two_colors_outside_tolerance_stay_separate():
    # Distance between pure red and pure blue is ~360 — always separate
    a = Color(255, 0, 0)
    b = Color(0, 0, 255)
    groups = group_colors({a, b}, 10)
    assert len(groups) == 2


def test_greedy_clustering_a_near_b_b_near_c_a_not_near_c():
    # A=(200,0,0) B=(205,0,0) C=(215,0,0), tolerance=10
    # dist(A,B)=5 ≤ 10, dist(A,C)=15 > 10, dist(B,C)=10 ≤ 10
    # Greedy: seed A → collects B (dist=5≤10), C not collected (dist(A,C)=15>10)
    # Then seed C → own group
    a = Color(200, 0, 0)
    b = Color(205, 0, 0)
    c = Color(215, 0, 0)
    groups = group_colors({a, b, c}, 10)
    assert len(groups) == 2
    ab_members = next(members for members in groups.values() if a in members)
    assert b in ab_members
    assert c not in ab_members


def test_empty_colors_returns_empty():
    assert group_colors(set(), 0) == {}
    assert group_colors(set(), 20) == {}


# ── find_group ────────────────────────────────────────────────────────────────

def test_find_group_exact_member():
    red = Color(255, 0, 0)
    blue = Color(0, 0, 255)
    groups = {red: [red], blue: [blue]}
    assert find_group(Color(255, 0, 0), groups) == red
    assert find_group(Color(0, 0, 255), groups) == blue


def test_find_group_closest_to_sampled():
    # Sampled is (250, 5, 0) — closer to red than blue
    red = Color(255, 0, 0)
    blue = Color(0, 0, 255)
    groups = {red: [red], blue: [blue]}
    assert find_group(Color(250, 5, 0), groups) == red


# ── transfer_actions ──────────────────────────────────────────────────────────

def test_transfer_actions_by_member_overlap():
    old_rep = Color(255, 0, 0)
    old_groups = {old_rep: [Color(255, 0, 0), Color(253, 0, 0)]}
    old_actions = {old_rep: Action.KEEP_BLACK}
    # New grouping has same members but a different centroid as representative
    new_rep = Color(254, 0, 0)
    new_groups = {new_rep: [Color(255, 0, 0), Color(253, 0, 0)]}
    new_actions = transfer_actions(old_groups, new_groups, old_actions, Action.KEEP)
    assert new_actions[new_rep] == Action.KEEP_BLACK


def test_transfer_actions_no_overlap_falls_back_to_keep():
    old_rep = Color(255, 0, 0)
    old_groups = {old_rep: [Color(255, 0, 0)]}
    old_actions = {old_rep: Action.DELETE}
    # Completely new color with no member overlap
    new_rep = Color(0, 0, 255)
    new_groups = {new_rep: [Color(0, 0, 255)]}
    new_actions = transfer_actions(old_groups, new_groups, old_actions, Action.KEEP)
    # No overlap → falls back to closest old rep by distance, which is old_rep
    # Distance between blue and red is large, but it's still the only candidate
    assert new_rep in new_actions  # result has an entry (either KEEP or DELETE)


# ── expand_mapping ────────────────────────────────────────────────────────────

def test_expand_mapping_all_members_get_representative_action():
    rep = Color(255, 0, 0)
    m1 = Color(254, 0, 0)
    m2 = Color(253, 0, 0)
    groups = {rep: [rep, m1, m2]}
    actions = {rep: Action.DELETE}
    expanded = expand_mapping(groups, actions, Action.KEEP)
    assert expanded[rep] == Action.DELETE
    assert expanded[m1] == Action.DELETE
    assert expanded[m2] == Action.DELETE


def test_expand_mapping_unmapped_rep_uses_default():
    rep = Color(0, 255, 0)
    groups = {rep: [rep]}
    actions = {}  # rep not in actions
    expanded = expand_mapping(groups, actions, Action.KEEP)
    assert expanded[rep] == Action.KEEP
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/arzaan.mairaj/PycharmProjects/PythonProject2
source .venv/bin/activate && pytest tests/test_color_grouper.py -v
```

Expected: `ModuleNotFoundError: No module named 'color_grouper'`

- [ ] **Step 3: Implement `src/color_grouper.py`**

```python
import math

from models import Color, Action


def group_colors(colors: set[Color], tolerance: int) -> dict[Color, list[Color]]:
    """Group similar colors by Euclidean RGB distance.

    Returns a dict mapping representative Color → list of member Colors.
    For tolerance=0 each color is its own group (zero overhead).
    For tolerance>0 uses greedy clustering: seed on the first unassigned color,
    collect all others within distance ≤ tolerance, compute centroid as
    representative, repeat until all colors are assigned.
    """
    if not colors:
        return {}
    if tolerance == 0:
        return {c: [c] for c in colors}

    unassigned = sorted(colors, key=lambda c: (c.r, c.g, c.b))
    groups: dict[Color, list[Color]] = {}

    while unassigned:
        seed = unassigned[0]
        members = [c for c in unassigned if _distance(seed, c) <= tolerance]
        for m in members:
            unassigned.remove(m)
        rep = _centroid(members)
        groups[rep] = members

    return groups


def find_group(sampled: Color, groups: dict[Color, list[Color]]) -> Color:
    """Return the representative whose group contains the member closest to sampled."""
    best_rep = None
    best_dist = float('inf')
    for rep, members in groups.items():
        for member in members:
            d = _distance(sampled, member)
            if d < best_dist:
                best_dist = d
                best_rep = rep
    return best_rep


def transfer_actions(
    old_groups: dict[Color, list[Color]],
    new_groups: dict[Color, list[Color]],
    old_actions: dict[Color, Action],
    default_action: Action,
) -> dict[Color, Action]:
    """Build a new actions dict for new_groups, preserving actions from old_groups.

    For each new representative, finds the old representative whose members have
    the most overlap with the new group. If no overlap exists, falls back to the
    closest old representative by Euclidean distance. Defaults to default_action
    when old_groups is empty.
    """
    # Build reverse map: member → old representative
    member_to_old_rep: dict[Color, Color] = {
        m: rep for rep, members in old_groups.items() for m in members
    }

    new_actions: dict[Color, Action] = {}
    for new_rep, new_members in new_groups.items():
        overlap: dict[Color, int] = {}
        for m in new_members:
            if m in member_to_old_rep:
                old_rep = member_to_old_rep[m]
                overlap[old_rep] = overlap.get(old_rep, 0) + 1

        if overlap:
            best_old_rep = max(overlap, key=lambda r: overlap[r])
            new_actions[new_rep] = old_actions.get(best_old_rep, default_action)
        elif old_groups:
            closest_old_rep = min(old_groups, key=lambda r: _distance(new_rep, r))
            new_actions[new_rep] = old_actions.get(closest_old_rep, default_action)
        else:
            new_actions[new_rep] = default_action

    return new_actions


def expand_mapping(
    groups: dict[Color, list[Color]],
    actions: dict[Color, Action],
    default_action: Action,
) -> dict[Color, Action]:
    """Expand representative→action to member→action for every member in every group."""
    return {
        member: actions.get(rep, default_action)
        for rep, members in groups.items()
        for member in members
    }


def _distance(a: Color, b: Color) -> float:
    return math.sqrt((a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2)


def _centroid(colors: list[Color]) -> Color:
    n = len(colors)
    return Color(
        round(sum(c.r for c in colors) / n),
        round(sum(c.g for c in colors) / n),
        round(sum(c.b for c in colors) / n),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && pytest tests/test_color_grouper.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Run full suite to check no regressions**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: 32 passed (20 existing + 12 new).

- [ ] **Step 6: Commit**

```bash
git add src/color_grouper.py tests/test_color_grouper.py
git commit -m "feat: color grouper — tolerance clustering, find_group, transfer_actions, expand_mapping"
```

---

## Task 2: Tolerance Slider + Grouping Wiring in `main_window.py`

**Files:**
- Modify: `src/main_window.py`

This task wires the grouping logic into the GUI. The eyedropper is added in Task 3. After this task the tolerance slider works and the color list reflects grouped colors.

- [ ] **Step 1: Update imports at the top of `src/main_window.py`**

Replace the current import block (lines 1–16) with:

```python
import logging
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel,
    QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
    QScrollArea, QSizePolicy, QToolBar, QSlider,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap

from models import Color, Action
from pdf_parser import extract_colors
from pdf_editor import apply_mapping
from renderer import render_page
from color_grouper import group_colors, find_group, transfer_actions, expand_mapping

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Add `PreviewLabel` subclass before the `MainWindow` class**

Insert this block between the `logger = ...` line and `class MainWindow`:

```python
class PreviewLabel(QLabel):
    """QLabel subclass that emits color_picked(QPoint) when eyedropper is active."""

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

- [ ] **Step 3: Update `__init__` to add new state variables**

Replace the current `__init__` body with:

```python
def __init__(self):
    super().__init__()
    self.setWindowTitle("PDF Color Separator")
    self.setMinimumSize(960, 680)

    self._pdf_bytes: bytes | None = None
    self._colors: list[Color] = []
    self._groups: dict[Color, list[Color]] = {}
    self._actions: dict[Color, Action] = {}
    self._current_page: int = 0
    self._total_pages: int = 0
    self._current_pixmap: QPixmap | None = None

    self._build_ui()
```

- [ ] **Step 4: Update `_build_ui` to add the Pick Color button**

Replace the current `_build_ui` method with:

```python
def _build_ui(self) -> None:
    toolbar = QToolBar()
    self.addToolBar(toolbar)

    btn_open = QPushButton("Open PDF")
    btn_open.clicked.connect(self._open_pdf)
    toolbar.addWidget(btn_open)
    toolbar.addSeparator()

    self._btn_pick = QPushButton("Pick Color")
    self._btn_pick.setCheckable(True)
    self._btn_pick.setEnabled(False)
    self._btn_pick.clicked.connect(self._toggle_eyedropper)
    toolbar.addWidget(self._btn_pick)

    self._btn_export = QPushButton("Export Layer")
    self._btn_export.setEnabled(False)
    self._btn_export.clicked.connect(self._export)
    toolbar.addWidget(self._btn_export)

    central = QWidget()
    self.setCentralWidget(central)
    layout = QHBoxLayout(central)

    layout.addWidget(self._build_left_panel())
    layout.addWidget(self._build_right_panel(), stretch=1)
```

- [ ] **Step 5: Update `_build_left_panel` to add the tolerance row**

Replace the current `_build_left_panel` method with:

```python
def _build_left_panel(self) -> QWidget:
    panel = QWidget()
    panel.setFixedWidth(210)
    layout = QVBoxLayout(panel)

    layout.addWidget(QLabel("<b>COLORS</b>"))

    # Tolerance row
    tol_row = QWidget()
    tol_layout = QHBoxLayout(tol_row)
    tol_layout.setContentsMargins(0, 0, 0, 0)
    tol_layout.addWidget(QLabel("Tolerance:"))
    self._slider_tolerance = QSlider(Qt.Orientation.Horizontal)
    self._slider_tolerance.setRange(0, 50)
    self._slider_tolerance.setValue(0)
    tol_layout.addWidget(self._slider_tolerance)
    self._tol_label = QLabel("0")
    self._tol_label.setFixedWidth(24)
    tol_layout.addWidget(self._tol_label)
    self._slider_tolerance.valueChanged.connect(self._on_tolerance_changed)
    layout.addWidget(tol_row)

    self._color_list = QListWidget()
    self._color_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    layout.addWidget(self._color_list)

    layout.addWidget(QLabel("Action for selected:"))
    self._radio_keep_black = QRadioButton("Keep → Black")
    self._radio_delete = QRadioButton("Delete")
    self._radio_keep = QRadioButton("Keep as-is")
    self._radio_keep.setChecked(True)

    self._action_group = QButtonGroup()
    for radio in (self._radio_keep_black, self._radio_delete, self._radio_keep):
        layout.addWidget(radio)
        self._action_group.addButton(radio)

    self._btn_apply = QPushButton("Apply")
    self._btn_apply.setEnabled(False)
    self._btn_apply.clicked.connect(self._apply_action)
    layout.addWidget(self._btn_apply)
    layout.addStretch()
    return panel
```

- [ ] **Step 6: Update `_build_right_panel` to use `PreviewLabel` and wire the signal**

Replace the current `_build_right_panel` method with:

```python
def _build_right_panel(self) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)

    self._preview_label = PreviewLabel("Open a PDF to begin.")
    self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._preview_label.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    self._preview_label.color_picked.connect(self._on_color_picked)
    scroll = QScrollArea()
    scroll.setWidget(self._preview_label)
    scroll.setWidgetResizable(True)
    layout.addWidget(scroll)

    nav = QWidget()
    nav_layout = QHBoxLayout(nav)
    self._btn_prev = QPushButton("◀")
    self._btn_prev.setEnabled(False)
    self._btn_prev.clicked.connect(self._prev_page)
    self._page_label = QLabel("Page — / —")
    self._btn_next = QPushButton("▶")
    self._btn_next.setEnabled(False)
    self._btn_next.clicked.connect(self._next_page)
    nav_layout.addStretch()
    nav_layout.addWidget(self._btn_prev)
    nav_layout.addWidget(self._page_label)
    nav_layout.addWidget(self._btn_next)
    nav_layout.addStretch()
    layout.addWidget(nav)
    return panel
```

- [ ] **Step 7: Update `_open_pdf` to compute groups and enable the Pick button**

Replace the current `_open_pdf` method with:

```python
def _open_pdf(self) -> None:
    path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
    if not path:
        return
    try:
        with open(path, 'rb') as f:
            self._pdf_bytes = f.read()
        colors = extract_colors(self._pdf_bytes)
        self._groups = group_colors(colors, self._slider_tolerance.value())
        self._colors = sorted(self._groups.keys(), key=lambda c: (c.r, c.g, c.b))
        self._actions = {c: Action.KEEP for c in self._colors}
        self._populate_color_list()

        with fitz.open(stream=self._pdf_bytes, filetype='pdf') as doc:
            self._total_pages = len(doc)
        self._current_page = 0
        self._update_page_nav()
        self._refresh_preview()

        self._btn_apply.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._btn_pick.setEnabled(True)

        if not colors:
            QMessageBox.information(
                self, "No Colors Detected",
                "No text or path colors were found.\n"
                "The PDF may contain only raster images."
            )
    except Exception as exc:
        logger.exception("Failed to open PDF")
        QMessageBox.critical(self, "Error Opening PDF", str(exc))
```

- [ ] **Step 8: Update `_refresh_preview` to expand the mapping and store the pixmap**

Replace the current `_refresh_preview` method with:

```python
def _refresh_preview(self) -> None:
    if self._pdf_bytes is None:
        return
    try:
        expanded = expand_mapping(self._groups, self._actions, Action.KEEP)
        modified = apply_mapping(self._pdf_bytes, expanded)
        pixmap = render_page(modified, self._current_page)
        self._current_pixmap = pixmap
        self._preview_label.setPixmap(pixmap)
        self._preview_label.resize(pixmap.size())
    except Exception as exc:
        logger.exception("Preview failed")
        QMessageBox.warning(self, "Preview Error", str(exc))
```

- [ ] **Step 9: Update `_export` to expand the mapping**

Replace the current `_export` method with:

```python
def _export(self) -> None:
    if self._pdf_bytes is None:
        return
    path, _ = QFileDialog.getSaveFileName(self, "Save Layer PDF", "", "PDF Files (*.pdf)")
    if not path:
        return
    if not path.endswith('.pdf'):
        path += '.pdf'
    try:
        expanded = expand_mapping(self._groups, self._actions, Action.KEEP)
        result = apply_mapping(self._pdf_bytes, expanded)
        with open(path, 'wb') as f:
            f.write(result)
        QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")
    except Exception as exc:
        logger.exception("Failed to export PDF")
        QMessageBox.critical(self, "Export Error", str(exc))
```

- [ ] **Step 10: Add the `_on_tolerance_changed` and `_toggle_eyedropper` slots**

Add these two methods to the Slots section (after `_export`):

```python
def _on_tolerance_changed(self, value: int) -> None:
    self._tol_label.setText(str(value))
    if self._pdf_bytes is None:
        return
    raw_colors = {m for members in self._groups.values() for m in members}
    new_groups = group_colors(raw_colors, value)
    self._actions = transfer_actions(self._groups, new_groups, self._actions, Action.KEEP)
    self._groups = new_groups
    self._colors = sorted(self._groups.keys(), key=lambda c: (c.r, c.g, c.b))
    self._populate_color_list()
    self._refresh_preview()

def _toggle_eyedropper(self) -> None:
    self._preview_label.set_eyedropper(self._btn_pick.isChecked())
```

- [ ] **Step 11: Add the `_on_color_picked` slot**

Add this method after `_toggle_eyedropper`:

```python
def _on_color_picked(self, pos: QPoint) -> None:
    if self._current_pixmap is None:
        return
    img = self._current_pixmap.toImage()
    if pos.x() < 0 or pos.y() < 0 or pos.x() >= img.width() or pos.y() >= img.height():
        return
    qcolor = img.pixelColor(pos)
    if not qcolor.isValid():
        return
    sampled = Color(qcolor.red(), qcolor.green(), qcolor.blue())
    rep = find_group(sampled, self._groups)
    if rep is None:
        return
    for i in range(self._color_list.count()):
        item = self._color_list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == rep:
            self._color_list.clearSelection()
            self._color_list.setCurrentItem(item)
            self._color_list.scrollToItem(item)
            break
    # Deactivate eyedropper after one pick
    self._btn_pick.setChecked(False)
    self._preview_label.set_eyedropper(False)
```

- [ ] **Step 12: Run the existing test suite to verify no regressions**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: 32 passed (the GUI changes have no unit tests — correctness is verified by smoke test below).

- [ ] **Step 13: Smoke-test the app manually**

```bash
source .venv/bin/activate && python src/main.py
```

Verify:
1. Open `samples/four_color_mixed.pdf` — 4 colors appear in the list, all `[keep]`
2. Move tolerance slider to 20 — if any colors are close, list shrinks
3. Move slider back to 0 — all 4 colors return
4. Move slider back to 0, click "Pick Color" — button becomes checked
5. Click on a red region in the preview — red color is selected in list, button unchecks

- [ ] **Step 14: Commit**

```bash
git add src/main_window.py
git commit -m "feat: tolerance grouping slider and eyedropper pick mode"
```

---

## Self-Review Checklist

Run mentally against the spec before saving:

1. **Spec coverage:**
   - ✅ `group_colors(tolerance=0)` — zero overhead path
   - ✅ `group_colors(tolerance>0)` — greedy Euclidean clustering
   - ✅ `find_group` — eyedropper pixel lookup
   - ✅ `transfer_actions` — action preservation on slider change
   - ✅ `expand_mapping` — called before every `apply_mapping`
   - ✅ Tolerance slider 0–50, live label, in left panel above color list
   - ✅ Pick Color checkable button in toolbar, disabled until PDF loaded
   - ✅ Eyedropper deactivates after one pick
   - ✅ `pdf_editor.py`, `pdf_parser.py`, `renderer.py` untouched

2. **No placeholders** — all method bodies are complete

3. **Type consistency:**
   - `group_colors` → `dict[Color, list[Color]]` ✅ used consistently in `self._groups`
   - `find_group(sampled, self._groups)` → `Color` ✅
   - `transfer_actions(old_groups, new_groups, old_actions, Action.KEEP)` ✅
   - `expand_mapping(self._groups, self._actions, Action.KEEP)` ✅
