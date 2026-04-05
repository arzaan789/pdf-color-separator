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


class MainWindow(QMainWindow):
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

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

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

    def _apply_action(self) -> None:
        selected = self._color_list.selectedItems()
        if not selected:
            return
        if self._radio_keep_black.isChecked():
            action = Action.KEEP_BLACK
        elif self._radio_delete.isChecked():
            action = Action.DELETE
        else:
            action = Action.KEEP
        for item in selected:
            color: Color = item.data(Qt.ItemDataRole.UserRole)
            self._actions[color] = action
        self._refresh_color_labels()
        self._refresh_preview()

    def _prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._update_page_nav()
            self._refresh_preview()

    def _next_page(self) -> None:
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            self._update_page_nav()
            self._refresh_preview()

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
        self._btn_pick.setChecked(False)
        self._preview_label.set_eyedropper(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_color_list(self) -> None:
        self._color_list.clear()
        for color in self._colors:
            item = QListWidgetItem(self._item_text(color))
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(color.r, color.g, color.b))
            item.setIcon(QIcon(swatch))
            item.setData(Qt.ItemDataRole.UserRole, color)
            self._color_list.addItem(item)

    def _item_text(self, color: Color) -> str:
        labels = {Action.KEEP: "keep", Action.KEEP_BLACK: "→ black", Action.DELETE: "delete"}
        return f"{color}  [{labels[self._actions[color]]}]"

    def _refresh_color_labels(self) -> None:
        for i in range(self._color_list.count()):
            item = self._color_list.item(i)
            color: Color = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self._item_text(color))

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

    def _update_page_nav(self) -> None:
        self._page_label.setText(f"Page {self._current_page + 1} / {self._total_pages}")
        self._btn_prev.setEnabled(self._current_page > 0)
        self._btn_next.setEnabled(self._current_page < self._total_pages - 1)
