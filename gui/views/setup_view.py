"""
Pestaña de configuración (Setup) — capa View.

El usuario define aquí:
  - Requisitos de misión + envelope táctico  (MissionConfig)
  - Parámetros fijos de la aeronave           (AircraftParams) + tamaño de flota
  - Bounds y activación de las variables de diseño   (tabla)
  - Límites y activación de las restricciones        (tabla)

`load_config(cfg)` vuelca una FullConfig en los widgets;
`read_config(base)` devuelve una FullConfig nueva con lo editado.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QLocale
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QDoubleSpinBox, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QPushButton, QFrame, QStackedWidget, QButtonGroup,
    QStyledItemDelegate, QLineEdit,
)
from PySide6.QtGui import QDoubleValidator

from core.config import FullConfig, PRESETS
from gui.style import (
    BLUE_PRIMARY, BLUE_DARK, BLUE_LIGHT, TEXT_SECONDARY, TEXT_WHITE,
    BG_CARD, BORDER_CARD,
)

# Pasos del asistente de configuración (stepper)
STEPS = ["Misión", "Diseño", "Restricciones"]

CONS_CATEGORIES = [
    ("Prestaciones", ("perf.",)),
    ("Estabilidad y control", ("stab.",)),
    ("Aerodinámica", ("cycle.aero.",)),
    ("Geometría y combustible", ("cycle.geom.", "fuel_vol.")),
]


def _cons_category(name: str) -> str:
    for title, prefixes in CONS_CATEGORIES:
        if any(name.startswith(p) for p in prefixes):
            return title
    return CONS_CATEGORIES[-1][0]

_STEP_QSS = f"""
QPushButton {{
    background: transparent; border: none; color: {TEXT_SECONDARY};
    font-weight: 700; font-size: 14px; padding: 8px 18px;
    border-radius: 18px;
}}
QPushButton:hover:!checked {{ color: {BLUE_DARK}; }}
QPushButton:checked {{ background: {BLUE_PRIMARY}; color: {TEXT_WHITE}; }}
"""

_RUN_BTN_QSS = """
QPushButton { background-color: #16A34A; color: #FFFFFF; }
QPushButton:hover { background-color: #22C55E; }
QPushButton:pressed { background-color: #15803D; }
"""

_CONS_CAT_QSS = f"""
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_CARD};
    border-radius: 10px;
    margin-top: 0px;
    padding: 34px 12px 12px 12px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 12px 14px 0px 14px;
    color: {BLUE_DARK};
    font-weight: 800;
    font-size: 14px;
}}
"""


# (campo, etiqueta, min, max, step, decimales)
MISSION_FIELDS = [
    ("h_cruise_m", "Altitud crucero [m]", 3000.0, 18000.0, 250.0, 0),
    ("m_cruise", "Mach crucero", 0.40, 0.92, 0.01, 2),
    ("h_combat_m", "Altitud combate [m]", 3000.0, 15000.0, 250.0, 0),
    ("m_combat", "Mach combate", 0.40, 0.95, 0.01, 2),
    ("n_combat", "Factor de carga combate [g]", 1.0, 7.0, 0.1, 1),
    ("range_km", "Alcance total [km]", 500.0, 8000.0, 100.0, 0),
    ("payload_kg", "Carga lanzable [kg]", 50.0, 2000.0, 25.0, 0),
    ("loiter_min", "Loiter ISR [min]", 0.0, 240.0, 5.0, 0),
]

AIRCRAFT_FIELDS = [
    ("t_c_ratio", "Espesor relativo t/c", 0.03, 0.18, 0.005, 3),
    ("sweep_angle_deg", "Flecha c/4 [°]", 0.0, 60.0, 1.0, 1),
    ("fuselage_length_m", "Longitud fuselaje [m]", 5.0, 15.0, 0.5, 1),
    ("fuselage_diameter_m", "Diámetro fuselaje [m]", 0.8, 2.5, 0.1, 2),
    ("w_avionics_kg", "Aviónica [kg]", 50.0, 600.0, 10.0, 0),
]


# Separador decimal con punto (no coma) en spinboxes y validadores.
_DOT_LOCALE = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


def _spin(minv, maxv, step, decimals) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setLocale(_DOT_LOCALE)
    sb.setRange(minv, maxv)
    sb.setSingleStep(step)
    sb.setDecimals(decimals)
    sb.setKeyboardTracking(False)
    return sb


def _num_item(value, editable=True) -> QTableWidgetItem:
    txt = "" if value is None else f"{value:g}"
    item = QTableWidgetItem(txt)
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _parse(text):
    text = text.strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


class _NumericDelegate(QStyledItemDelegate):
    """Delegado que sólo permite introducir números decimales (y signo/punto)."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        validator = QDoubleValidator(editor)
        validator.setLocale(_DOT_LOCALE)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        editor.setValidator(validator)
        return editor


class SetupView(QWidget):
    preset_selected = Signal(str)
    goto_run_requested = Signal()        # paso 3 → "Ejecución" (solo navega)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mission_spins: dict[str, QDoubleSpinBox] = {}
        self._aircraft_spins: dict[str, QDoubleSpinBox] = {}
        self._q_prod_spin: QDoubleSpinBox | None = None
        self._cons_tables: list[QTableWidget] = []
        self._build_ui()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(12)

        # --- Stepper (cabecera de pasos) ---
        outer.addWidget(self._build_stepper())

        # --- Páginas del asistente (QStackedWidget) ---
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step_mission())
        self._stack.addWidget(self._build_step_design())
        self._stack.addWidget(self._build_step_constraints())
        outer.addWidget(self._stack, 1)

        # --- Navegación Atrás / Siguiente ---
        outer.addWidget(self._build_nav_bar())

        self._go_to_step(0)

    # ----------------------------------------------------- stepper / nav
    def _build_stepper(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_CARD};"
            f" border-radius: 10px; }}")
        bar = QHBoxLayout(card)
        bar.setContentsMargins(16, 8, 16, 8)
        bar.setSpacing(8)
        bar.addStretch(1)

        self._step_group = QButtonGroup(self)
        self._step_group.setExclusive(True)
        self._step_buttons: list[QPushButton] = []
        for i, name in enumerate(STEPS):
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet(
                    f"color: {BORDER_CARD}; font-size: 18px; font-weight: 800;"
                    f" background: transparent;")
                bar.addWidget(sep)
            b = QPushButton(f"{i + 1}.  {name}")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_STEP_QSS)
            b.clicked.connect(lambda _=False, idx=i: self._go_to_step(idx))
            self._step_group.addButton(b)
            self._step_buttons.append(b)
            bar.addWidget(b)
        bar.addStretch(1)
        return card

    def _build_nav_bar(self) -> QWidget:
        w = QWidget()
        nav = QHBoxLayout(w)
        nav.setContentsMargins(0, 0, 0, 0)

        self._back_btn = QPushButton("‹  Atrás")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_CARD}; color: {BLUE_DARK};"
            f" border: 1px solid {BORDER_CARD}; }}"
            f"QPushButton:hover {{ background: {BLUE_LIGHT}; }}"
            f"QPushButton:disabled {{ color: {TEXT_SECONDARY};"
            f" border-color: {BORDER_CARD}; background: {BG_CARD}; }}")
        self._back_btn.clicked.connect(
            lambda: self._go_to_step(self._stack.currentIndex() - 1))
        nav.addWidget(self._back_btn)

        nav.addStretch(1)

        self._next_btn = QPushButton("Siguiente  ›")
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._on_next_clicked)
        nav.addWidget(self._next_btn)
        return w

    def _on_next_clicked(self):
        idx = self._stack.currentIndex()
        if idx < len(STEPS) - 1:
            self._go_to_step(idx + 1)
        else:
            self.goto_run_requested.emit()      # último paso → ir a Ejecución

    def _go_to_step(self, idx: int):
        idx = max(0, min(idx, len(STEPS) - 1))
        self._stack.setCurrentIndex(idx)
        self._step_buttons[idx].setChecked(True)
        self._back_btn.setEnabled(idx > 0)
        last = idx == len(STEPS) - 1
        self._next_btn.setText("Ejecución  ▶" if last else "Siguiente  ›")
        self._next_btn.setStyleSheet(_RUN_BTN_QSS if last else "")

    # ----------------------------------------------------- páginas (pasos)
    def _step_page(self) -> tuple[QScrollArea, QVBoxLayout]:
        """Crea una página con scroll y devuelve (scroll, layout interior)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        return scroll, lay

    def _build_step_mission(self) -> QWidget:
        scroll, lay = self._step_page()

        # Barra de presets
        preset_card = QFrame()
        preset_card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_CARD};"
            f" border-radius: 10px; }}")
        pbar = QHBoxLayout(preset_card)
        pbar.setContentsMargins(16, 10, 16, 10)
        pbar.setSpacing(12)
        plabel = QLabel("Preset de misión")
        plabel.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: 600; font-size: 13px;"
            f" background: transparent;")
        pbar.addWidget(plabel)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.activated.connect(
            lambda _i: self.preset_selected.emit(self.preset_combo.currentText()))
        self.preset_combo.setMinimumWidth(260)
        pbar.addWidget(self.preset_combo)
        pbar.addStretch(1)
        lay.addWidget(preset_card)

        lay.addWidget(self._build_form_group(
            "Requisitos de misión", MISSION_FIELDS, self._mission_spins))
        lay.addStretch(1)
        return scroll

    def _build_step_design(self) -> QWidget:
        scroll, lay = self._step_page()
        cols = QHBoxLayout()
        cols.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(self._build_aircraft_group())
        left.addStretch(1)
        cols.addLayout(left, 0)
        cols.addWidget(self._build_dv_group(), 1)
        lay.addLayout(cols)
        lay.addStretch(1)
        return scroll

    def _build_step_constraints(self) -> QWidget:
        scroll, lay = self._step_page()
        self._cons_tables = []
        self._cons_table_by_cat: dict[str, QTableWidget] = {}

        cols = QHBoxLayout()
        cols.setSpacing(14)
        left_col = QVBoxLayout()
        left_col.setSpacing(14)
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        for i, (title, _prefixes) in enumerate(CONS_CATEGORIES):
            box = QGroupBox(title)
            box.setStyleSheet(_CONS_CAT_QSS)
            vlay = QVBoxLayout(box)
            vlay.setContentsMargins(10, 4, 10, 10)
            table = self._make_constraint_table()
            self._cons_tables.append(table)
            self._cons_table_by_cat[title] = table
            vlay.addWidget(table)
            (left_col if i in (0, 3) else right_col).addWidget(box)

        left_col.addStretch(1)
        right_col.addStretch(1)
        cols.addLayout(left_col, 1)
        cols.addLayout(right_col, 1)
        lay.addLayout(cols)
        return scroll

    def _make_constraint_table(self) -> QTableWidget:
        t = QTableWidget(0, 4)
        t.setAlternatingRowColors(True)
        t.setHorizontalHeaderLabels(
            ["Activa", "Restricción", "Lím. inferior", "Lím. superior"])
        t.verticalHeader().setVisible(False)
        hh = t.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        t.setColumnWidth(0, 60)
        t.setColumnWidth(2, 120)
        t.setColumnWidth(3, 120)
        t.verticalHeader().setDefaultSectionSize(32)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _nd = _NumericDelegate(t)
        t.setItemDelegateForColumn(2, _nd)
        t.setItemDelegateForColumn(3, _nd)
        return t

    def _build_form_group(self, title, fields, store) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(14, 8, 14, 14)
        form.setSpacing(10)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for name, label, mn, mx, step, dec in fields:
            sb = _spin(mn, mx, step, dec)
            store[name] = sb
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 500;")
            form.addRow(lbl, sb)
        return box

    def _build_aircraft_group(self) -> QGroupBox:
        box = QGroupBox("Aeronave (parámetros fijos)")
        form = QFormLayout(box)
        form.setContentsMargins(14, 8, 14, 14)
        form.setSpacing(10)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for name, label, mn, mx, step, dec in AIRCRAFT_FIELDS:
            sb = _spin(mn, mx, step, dec)
            self._aircraft_spins[name] = sb
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 500;")
            form.addRow(lbl, sb)
        self._q_prod_spin = _spin(10.0, 2000.0, 10.0, 0)
        ql = QLabel("Tamaño de flota Q")
        ql.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 500;")
        form.addRow(ql, self._q_prod_spin)
        return box

    def _build_dv_group(self) -> QGroupBox:
        box = QGroupBox("Variables de diseño (bounds)")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        self.dv_table = QTableWidget(0, 4)
        self.dv_table.setAlternatingRowColors(True)
        self.dv_table.setHorizontalHeaderLabels(
            ["Activa", "Variable", "Mínimo", "Máximo"])
        self.dv_table.verticalHeader().setVisible(False)
        hh = self.dv_table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setDefaultSectionSize(100)
        self.dv_table.verticalHeader().setDefaultSectionSize(32)
        self.dv_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _nd = _NumericDelegate(self.dv_table)
        self.dv_table.setItemDelegateForColumn(2, _nd)
        self.dv_table.setItemDelegateForColumn(3, _nd)
        lay.addWidget(self.dv_table)
        return box

    @staticmethod
    def _fit_table_height(t: QTableWidget):
        """Fija la altura de la tabla para mostrar TODAS las filas sin scroll
        interno (el scroll de la página se encarga del desbordamiento)."""
        h = t.horizontalHeader().height() + 2 * t.frameWidth()
        for r in range(t.rowCount()):
            h += t.rowHeight(r)
        t.setFixedHeight(h)

    # ---------------------------------------------------- carga / lectura
    def load_config(self, cfg: FullConfig):
        m = cfg.mission
        for name, sb in self._mission_spins.items():
            sb.setValue(float(getattr(m, name)))
        ac = cfg.aircraft
        for name, sb in self._aircraft_spins.items():
            sb.setValue(float(getattr(ac, name)))
        if self._q_prod_spin is not None:
            self._q_prod_spin.setValue(float(cfg.cost.q_prod))

        self._fill_dv_table(cfg)
        self._fill_cons_table(cfg)

    def _fill_dv_table(self, cfg: FullConfig):
        t = self.dv_table
        t.setRowCount(len(cfg.design_vars))
        for r, dv in enumerate(cfg.design_vars):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if dv.enabled else Qt.CheckState.Unchecked)
            t.setItem(r, 0, chk)
            name_item = _num_item(None, editable=False)
            name_item.setText(dv.label or dv.name)
            name_item.setData(Qt.ItemDataRole.UserRole, dv.name)
            t.setItem(r, 1, name_item)
            t.setItem(r, 2, _num_item(dv.lower))
            t.setItem(r, 3, _num_item(dv.upper))
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._fit_table_height(t)

    def _fill_cons_table(self, cfg: FullConfig):
        grouped: dict[str, list] = {title: [] for title, _ in CONS_CATEGORIES}
        for c in cfg.constraints:
            grouped[_cons_category(c.name)].append(c)

        for title, cons in grouped.items():
            t = self._cons_table_by_cat[title]
            t.setRowCount(len(cons))
            for r, c in enumerate(cons):
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(
                    Qt.CheckState.Checked if c.enabled else Qt.CheckState.Unchecked)
                t.setItem(r, 0, chk)
                name_item = _num_item(None, editable=False)
                name_item.setText(c.label or c.name)
                name_item.setData(Qt.ItemDataRole.UserRole, c.name)
                t.setItem(r, 1, name_item)
                t.setItem(r, 2, _num_item(c.lower))
                t.setItem(r, 3, _num_item(c.upper))
            self._fit_table_height(t)

    def read_config(self, base: FullConfig) -> FullConfig:
        """Construye una FullConfig a partir de `base` aplicando lo editado."""
        cfg = base.copy()

        for name, sb in self._mission_spins.items():
            setattr(cfg.mission, name, sb.value())
        for name, sb in self._aircraft_spins.items():
            setattr(cfg.aircraft, name, sb.value())
        if self._q_prod_spin is not None:
            cfg.cost.q_prod = self._q_prod_spin.value()

        dv_by_name = {dv.name: dv for dv in cfg.design_vars}
        for r in range(self.dv_table.rowCount()):
            name = self.dv_table.item(r, 1).data(Qt.ItemDataRole.UserRole)
            dv = dv_by_name.get(name)
            if dv is None:
                continue
            dv.enabled = self.dv_table.item(r, 0).checkState() == Qt.CheckState.Checked
            lo = _parse(self.dv_table.item(r, 2).text())
            hi = _parse(self.dv_table.item(r, 3).text())
            if lo is not None:
                dv.lower = lo
            if hi is not None:
                dv.upper = hi

        cons_by_name = {c.name: c for c in cfg.constraints}
        for t in self._cons_tables:
            for r in range(t.rowCount()):
                name = t.item(r, 1).data(Qt.ItemDataRole.UserRole)
                c = cons_by_name.get(name)
                if c is None:
                    continue
                c.enabled = t.item(r, 0).checkState() == Qt.CheckState.Checked
                c.lower = _parse(t.item(r, 2).text())
                c.upper = _parse(t.item(r, 3).text())

        return cfg

    def validate(self, cfg: FullConfig) -> list[str]:
        """Comprobaciones básicas de coherencia; devuelve lista de errores."""
        errors: list[str] = []
        for dv in cfg.design_vars:
            if dv.enabled and dv.lower >= dv.upper:
                errors.append(f"DV '{dv.label or dv.name}': mínimo ≥ máximo.")
        for c in cfg.constraints:
            if c.enabled and c.lower is not None and c.upper is not None \
                    and c.lower > c.upper:
                errors.append(f"Restricción '{c.label or c.name}': inferior > superior.")
        if not any(dv.enabled for dv in cfg.design_vars):
            errors.append("No hay ninguna variable de diseño activa.")
        return errors
