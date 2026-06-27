"""
Pestaña de gráficas (Plots) — capa View.

Navegación por categorías (árbol) a la izquierda + un único lienzo matplotlib a
la derecha. Las gráficas "instant" se calculan al vuelo; las de tipo "study"
(tornado, Pareto) requieren un cálculo costoso que se lanza con un botón y se
ejecuta en segundo plano (StudyWorker) con barra de progreso. Los resultados de
estudio se cachean hasta la siguiente optimización.
"""

from __future__ import annotations

import traceback

from PySide6.QtCore import Qt, QThread, QSize, QEvent, QTimer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QToolButton, QLabel, QFrame, QComboBox, QProgressBar,
    QScrollArea,
)
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

from core.config import FullConfig
from core.results import ResultsDTO
from core import studies as st
from gui.widgets.mpl_canvas import MplWidget
from gui.study_worker import StudyWorker
from gui.plots import CATEGORIES, CHART_INFO
from gui.style import BLUE_DARK, BLUE_LIGHT, BORDER_CARD, BG_CARD


class CompactToolbar(NavigationToolbar2QT):
    toolitems = [t for t in NavigationToolbar2QT.toolitems
                 if t[0] in ("Home", "Pan", "Zoom", "Save")]


def _computer_modern_family() -> str:
    import os
    import matplotlib
    from PySide6.QtGui import QFontDatabase
    try:
        path = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "cmr10.ttf")
        fid = QFontDatabase.addApplicationFont(path)
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            return fams[0]
    except Exception:
        pass
    return "serif"


class PlotsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dto: ResultsDTO | None = None
        self._config: FullConfig | None = None
        self._current = None                 # (key, label, fn, kind)
        self._study_cache: dict = {}         # key -> resultado del estudio
        self._thread: QThread | None = None
        self._worker: StudyWorker | None = None
        self._pending = None                 # (key, fn) del estudio en curso
        self._build_ui()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # --- Árbol de categorías (colapsable) ---
        self.left = QFrame()
        self.left.setMaximumWidth(300)
        self.left.setMinimumWidth(240)
        left_lay = QVBoxLayout(self.left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        self.head_widget = QWidget()
        head = QHBoxLayout(self.head_widget)
        head.setContentsMargins(4, 2, 0, 2)
        self.title_lbl = QLabel("Gráficas")
        self.title_lbl.setStyleSheet(f"color:{BLUE_DARK}; font-size:16px; font-weight:800;")
        head.addWidget(self.title_lbl)
        head.addStretch(1)
        self.toggle_btn = self._mini_button("☰", "Ocultar el índice de gráficas",
                                            self._toggle_tree)
        head.addWidget(self.toggle_btn)
        left_lay.addWidget(self.head_widget)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(10)
        self.tree.setRootIsDecorated(False)
        self.tree.setStyleSheet(self._tree_qss())
        self._leaf_items: list[QTreeWidgetItem] = []
        from PySide6.QtGui import QColor, QBrush
        for cat_name, charts in CATEGORIES:
            parent = QTreeWidgetItem([cat_name])
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)        # cabecera no seleccionable
            f = parent.font(0)
            f.setBold(True)
            f.setPointSizeF(f.pointSizeF() + 0.5)
            parent.setFont(0, f)
            parent.setBackground(0, QBrush(QColor(BLUE_LIGHT)))
            parent.setForeground(0, QBrush(QColor(BLUE_DARK)))
            self.tree.addTopLevelItem(parent)
            for (key, label, fn, kind) in charts:
                child = QTreeWidgetItem([label])
                child.setData(0, Qt.ItemDataRole.UserRole, (key, label, fn, kind))
                parent.addChild(child)
                self._leaf_items.append(child)
            parent.setExpanded(True)
        self.tree.currentItemChanged.connect(self._on_select)
        left_lay.addWidget(self.tree, 1)

        self.collapsed_bar = QWidget()
        cb = QVBoxLayout(self.collapsed_bar)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(10)
        cb.addStretch(1)
        self.prev_btn = self._mini_button("▲", "Gráfica anterior",
                                          lambda: self._select_relative(-1))
        self.toggle_btn2 = self._mini_button("☰", "Mostrar el índice de gráficas",
                                             self._toggle_tree)
        self.next_btn = self._mini_button("▼", "Gráfica siguiente",
                                          lambda: self._select_relative(1))
        for b in (self.prev_btn, self.toggle_btn2, self.next_btn):
            cb.addWidget(b, alignment=Qt.AlignmentFlag.AlignHCenter)
        cb.addStretch(1)
        self.collapsed_bar.hide()
        left_lay.addWidget(self.collapsed_bar, 1)

        layout.addWidget(self.left)

        # --- Lado derecho ---
        right = QVBoxLayout()
        right.setSpacing(8)

        # Barra superior: toolbar matplotlib anclada a la derecha
        strip = QHBoxLayout()
        strip.setContentsMargins(0, 0, 0, 0)
        strip.addStretch(1)

        # Barra de control de estudios (oculta para gráficas instant)
        self.study_bar = QFrame()
        self.study_bar.setStyleSheet(
            f"QFrame {{ background:{BG_CARD}; border:1px solid {BORDER_CARD};"
            f" border-radius:8px; }}")
        sb = QHBoxLayout(self.study_bar)
        sb.setContentsMargins(12, 8, 12, 8)
        self.study_label = QLabel("")
        sb.addWidget(self.study_label)
        self.param_combo = QComboBox()
        for k, (lab, unit, _f) in st.PARETO_PARAMS.items():
            self.param_combo.addItem(f"{lab} [{unit}]", k)
        sb.addWidget(self.param_combo)
        self.compute_btn = QPushButton("Calcular")
        self.compute_btn.clicked.connect(self._on_compute)
        sb.addWidget(self.compute_btn)
        self.study_progress = QProgressBar()
        self.study_progress.setRange(0, 1)
        self.study_progress.setValue(0)
        sb.addWidget(self.study_progress, 1)

        # Lienzo principal (sin toolbar embebida)
        self.canvas = MplWidget(figsize=(7.5, 5.0), toolbar=False)

        # Toolbar matplotlib compacta, anclada arriba a la derecha
        self.toolbar = CompactToolbar(self.canvas.canvas, self)
        self.toolbar.setIconSize(QSize(18, 18))
        self.toolbar.setStyleSheet(
            "QToolBar { background: transparent; border: none; spacing: 1px; }"
            "QToolButton { border: none; padding: 4px; border-radius: 6px; }"
            f"QToolButton:hover {{ background: {BLUE_LIGHT}; }}"
            f"QToolButton:checked {{ background: {BLUE_LIGHT}; }}")
        if hasattr(self.toolbar, "locLabel"):
            loc = self.toolbar.locLabel
            loc.setVisible(False)
            loc_act = next((a for a in self.toolbar.actions()
                            if self.toolbar.widgetForAction(a) is loc), None)
            if loc_act is not None:
                self.toolbar.removeAction(loc_act)
        strip.addWidget(self.toolbar)
        right.addLayout(strip)
        right.addWidget(self.study_bar)
        self.study_bar.hide()

        self.eq_button = QPushButton("Ecuaciones fundamentales        ▼")
        self.eq_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cm_family = _computer_modern_family()
        self.eq_button.setStyleSheet(
            f"QPushButton {{ text-align:left; padding:8px 14px;"
            f" font-family:'{cm_family}'; font-size:17px; font-weight:bold;"
            f" color:{BLUE_DARK}; background:{BLUE_LIGHT}; border:1px solid {BORDER_CARD};"
            f" border-radius:8px; }}"
            f"QPushButton:hover {{ background:#DCE9FB; }}")
        self.eq_button.clicked.connect(self._toggle_equations_scroll)

        self.eq_canvas = MplWidget(figsize=(7.5, 2.3), toolbar=False)
        self.eq_canvas.setFixedHeight(240)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(8)
        iv.addWidget(self.canvas)
        iv.addWidget(self.eq_button)
        iv.addWidget(self.eq_canvas)
        self.scroll.setWidget(inner)
        right.addWidget(self.scroll, 1)

        layout.addLayout(right, 1)

        self.canvas.canvas.installEventFilter(self)
        self.eq_canvas.canvas.installEventFilter(self)
        self.scroll.verticalScrollBar().valueChanged.connect(self._update_eq_arrow)

        self._has_eq = False
        self.eq_button.setVisible(False)
        self.eq_canvas.setVisible(False)
        self._placeholder("Ejecuta una optimización para generar las gráficas.")

    # ---------------------------------------------- layout dinámico
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_chart_height()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_chart_height)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and hasattr(self, "scroll"):
            bar = self.scroll.verticalScrollBar()
            bar.setValue(bar.value() - event.angleDelta().y())
            return True
        return super().eventFilter(obj, event)

    def _fit_chart_height(self):
        if not hasattr(self, "scroll"):
            return
        vh = self.scroll.viewport().height()
        reserve = self.eq_button.sizeHint().height() + 10 if getattr(self, "_has_eq", True) else 0
        self.canvas.setMinimumHeight(max(260, vh - reserve))

    def _configure_eq_area(self, key):
        from gui.plots import equations_canvas_height
        self._has_eq = key in CHART_INFO
        self.eq_button.setVisible(self._has_eq)
        if self._has_eq:
            self.eq_canvas.setFixedHeight(equations_canvas_height(key))
        self.eq_canvas.setVisible(self._has_eq)
        self._fit_chart_height()

    # ------------------------------------------------- helpers de UI
    def _mini_button(self, text, tip, slot):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QToolButton {{ border:1px solid {BORDER_CARD}; border-radius:7px;"
            f" padding:6px 9px; font-size:15px; color:{BLUE_DARK}; background:{BG_CARD}; }}"
            f"QToolButton:hover {{ background:{BLUE_LIGHT}; }}")
        b.clicked.connect(slot)
        return b

    def _tree_qss(self) -> str:
        return f"""
        QTreeWidget {{ border:none; background:transparent; outline:0; }}
        QTreeWidget::item {{
            padding:9px 8px; margin:2px 2px; border-radius:6px;
        }}
        QTreeWidget::item:hover {{ background:#EAF1FC; }}
        QTreeWidget::item:selected {{ background:{BLUE_LIGHT}; color:{BLUE_DARK}; }}
        """

    def _toggle_tree(self):
        self._tree_collapsed = not getattr(self, "_tree_collapsed", False)
        if self._tree_collapsed:                          # colapsa a barra fina
            self.tree.hide()
            self.head_widget.hide()
            self.collapsed_bar.show()
            self.left.setFixedWidth(48)
        else:                                             # restaura el panel
            self.tree.show()
            self.head_widget.show()
            self.collapsed_bar.hide()
            self.left.setMinimumWidth(240)
            self.left.setMaximumWidth(300)
        self._fit_chart_height()

    def _select_relative(self, delta):
        """Selecciona la gráfica anterior/siguiente en el índice (flechas de la
        barra colapsada)."""
        items = getattr(self, "_leaf_items", [])
        if not items:
            return
        cur = self.tree.currentItem()
        idx = items.index(cur) if cur in items else -1
        new = max(0, min(len(items) - 1, idx + delta))
        if new != idx:
            self.tree.setCurrentItem(items[new])

    def _toggle_equations_scroll(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(0 if bar.value() >= bar.maximum() - 2 else bar.maximum())

    def _update_eq_arrow(self, _value=0):
        bar = self.scroll.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 2 and bar.maximum() > 0
        self.eq_button.setText("Ecuaciones fundamentales        "
                               + ("▲" if at_bottom else "▼"))

    def _draw_equations(self, key):
        from gui.plots import draw_equations
        try:
            draw_equations(self.eq_canvas.fig, key)
        except Exception:
            self.eq_canvas.fig.clear()
        self.eq_canvas.draw()

    def _placeholder(self, text):
        from gui import plot_style as ps
        ps.placeholder(self.canvas.fig, text)
        self.canvas.draw()

    # ------------------------------------------------------------- API
    def show_results(self, dto: ResultsDTO, config: FullConfig):
        self._dto = dto
        self._config = config
        self._study_cache.clear()
        top = self.tree.topLevelItem(0)
        if top and top.childCount():
            self.tree.setCurrentItem(top.child(0))
        else:
            self._redraw()

    # ----------------------------------------------------- selección
    def _on_select(self, current: QTreeWidgetItem, _prev=None):
        if current is None:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return                            # cabecera de categoría
        self._current = data
        self._redraw()

    def _redraw(self):
        if self._dto is None or self._current is None:
            return
        key, label, fn, kind = self._current

        self.scroll.verticalScrollBar().setValue(0)
        self.eq_button.setText("Ecuaciones fundamentales        ▼")
        self._configure_eq_area(key)
        QTimer.singleShot(0, self._fit_chart_height)

        if kind == "instant":
            self.study_bar.hide()
            self._draw_instant(fn)
            if self._has_eq:
                self._draw_equations(key)
        else:                                 # study:tornado / study:pareto
            self._setup_study_bar(kind)
            if key in self._study_cache:
                self._draw_study(fn, self._study_cache[key])
            else:
                self._placeholder(
                    f"Pulsa «Calcular» para generar:\n{label}\n\n"
                    "(re-ejecuta el MDAO; puede tardar unos segundos)")
            if self._has_eq:
                self._draw_equations(key)

    def _draw_instant(self, fn):
        self.canvas.fig.set_layout_engine("constrained")
        try:
            fn(self.canvas.fig, self._dto, self._config)
        except Exception:
            self._placeholder("No se pudo dibujar:\n" + traceback.format_exc(limit=2))
        self.canvas.draw()

    def _draw_study(self, fn, result):
        self.canvas.fig.set_layout_engine("constrained")
        try:
            fn(self.canvas.fig, result)
        except Exception:
            self._placeholder("No se pudo dibujar:\n" + traceback.format_exc(limit=2))
        self.canvas.draw()

    # ------------------------------------------------------- estudios
    def _setup_study_bar(self, kind):
        is_pareto = kind == "study:pareto"
        self.param_combo.setVisible(is_pareto)
        self.study_label.setText("Barrido de requisito:" if is_pareto
                                 else "Sensibilidad ±10 % alrededor del óptimo")
        self.study_bar.show()

    def _on_compute(self):
        if self._dto is None or self._current is None or self._thread is not None:
            return
        key, label, fn, kind = self._current
        dto, cfg = self._dto, self._config

        if kind == "study:tornado":
            job = lambda progress: st.tornado_sensitivity(dto, cfg, progress=progress)
        elif kind == "study:pareto":
            param = self.param_combo.currentData()
            job = lambda progress: st.pareto_front(cfg, param=param, progress=progress)
        else:
            return

        self.compute_btn.setEnabled(False)
        self.study_progress.setRange(0, 0)   # indeterminado hasta el primer progreso

        self._pending = (key, fn)

        self._thread = QThread()
        self._worker = StudyWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_study_progress)
        self._worker.finished.connect(self._on_study_done)
        self._worker.failed.connect(self._on_study_failed)
        self._thread.start()

    def _on_study_progress(self, done, total):
        self.study_progress.setRange(0, total)
        self.study_progress.setValue(done)

    def _on_study_done(self, result):
        key, fn = self._pending if self._pending else (None, None)
        if key is not None:
            self._study_cache[key] = result
        self._teardown_thread()
        self.compute_btn.setEnabled(True)
        self.study_progress.setRange(0, 1)
        self.study_progress.setValue(1)
        if key is not None and self._current and self._current[0] == key:
            self._draw_study(fn, result)
            if key in CHART_INFO:
                self._draw_equations(key)

    def _on_study_failed(self, tb):
        self._teardown_thread()
        self.compute_btn.setEnabled(True)
        self.study_progress.setRange(0, 1)
        self.study_progress.setValue(0)
        self._placeholder("El estudio falló:\n" + tb)

    def _teardown_thread(self):
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
