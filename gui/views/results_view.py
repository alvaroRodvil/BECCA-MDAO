"""
Pestaña de resultados (Results) — capa View.

Muestra un panel de "ficha técnica" organizado en TARJETAS POR DISCIPLINA
(costes, pesos, geometría, propulsión, aerodinámica, estabilidad) y una tabla
de restricciones con BARRA DE MARGEN + semáforo (verde = holgada, ámbar =
activa, rojo = violada).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout,
    QFrame, QScrollArea,
)

from core.results import ResultsDTO
from gui.widgets.margin_bar import MarginBar
from gui.style import (
    BG_CARD, BG_HEADER, BORDER_CARD, BORDER_INPUT, BLUE_DARK,
    BLUE_ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_WHITE,
    TEXT_ON_DARK, GREEN_OK, RED_VIOLATED,
)


# Métricas agrupadas por disciplina: (título, [(etiqueta, ruta, formato)])
DISCIPLINES = [
    ("Pesos", [
        ("MTOW", "cycle.mtow_sum.mtow_calc", "{:.0f} kg"),
        ("Combustible misión", "cycle.miss.w_fuel", "{:.0f} kg"),
        ("OEW (parcial)", "cost.oew_partial", "{:.0f} kg"),
        ("Motor", "cycle.prop.w_engine", "{:.0f} kg"),
        ("Ala", "cycle.weight.w_wing", "{:.0f} kg"),
        ("Fuselaje", "cycle.weight.w_fuse", "{:.0f} kg"),
        ("Cola en V", "cycle.weight.w_vtail", "{:.0f} kg"),
        ("Tren de aterrizaje", "cycle.weight.w_lg", "{:.0f} kg"),
        ("Subsistemas", "cycle.weight.w_systems", "{:.0f} kg"),
    ]),
    ("Geometría", [
        ("Superficie alar S", "wing_area", "{:.2f} m²"),
        ("Envergadura b", "cycle.geom.wingspan", "{:.2f} m"),
        ("Alargamiento AR", "aspect_ratio", "{:.2f}"),
        ("Estrechamiento λ", "taper_ratio", "{:.3f}"),
        ("Cuerda raíz", "cycle.geom.root_chord", "{:.3f} m"),
        ("Cuerda punta", "cycle.geom.tip_chord", "{:.3f} m"),
        ("MAC", "cycle.geom.mac", "{:.3f} m"),
        ("Coef. cola V_HT", "v_ht", "{:.3f}"),
        ("Superficie cola V", "cycle.geom.s_vtail", "{:.3f} m²"),
        ("Ángulo en V", "cycle.geom.v_angle", "{:.1f} °"),
        ("Vol. tanque alar", "cycle.geom.vol_wing_tank", "{:.4f} m³"),
        ("Vol. tanque fuselaje", "cycle.geom.vol_fuse_tank", "{:.4f} m³"),
    ]),
    ("Propulsión", [
        ("Empuje SL", "t_sl", "{:.0f} N"),
        ("Empuje disponible", "cycle.prop.t_avail", "{:.0f} N"),
        ("Empuje crucero", "cycle.prop.t_avail_cruise", "{:.0f} N"),
        ("TSFC", "cycle.prop.tsfc_avail", "{:.2f} mg/(N·s)", 1e6),
        ("T/W (despegue)",
         lambda d: d.get("t_sl") / (d.get("cycle.mtow_sum.mtow_calc") * 9.81),
         "{:.3f}"),
        ("W/S (carga alar)",
         lambda d: d.get("cycle.mtow_sum.mtow_calc") * 9.81 / d.get("wing_area"),
         "{:.1f} N/m²"),
    ]),
    ("Aerodinámica", [
        ("L/D crucero", "cycle.aero.L_D", "{:.2f}"),
        ("L/D máx", "cycle.aero.L_D_max", "{:.2f}"),
        ("CL crucero", "cycle.aero.CL_cruise", "{:.3f}"),
        ("CD0", "cycle.aero.cd0", "{:.4f}"),
        ("CD inducida", "cycle.aero.cd_induced", "{:.4f}"),
        ("CD onda", "cycle.aero.cd_wave", "{:.4f}"),
        ("Factor de Oswald e", "cycle.aero.e_oswald", "{:.3f}"),
        ("M_dd", "cycle.aero.M_dd", "{:.3f}"),
    ]),
    ("Estabilidad", [
        ("SM (full)", "stab.sm_full", "{:.3f}"),
        ("SM (empty)", "stab.sm_empty", "{:.3f}"),
        ("SM (aft-crítico)", "stab.sm_aft", "{:.3f}"),
        ("CG %MAC (full)", "stab.cg_full_pct_mac", "{:.3f}"),
        ("CG %MAC (empty)", "stab.cg_empty_pct_mac", "{:.3f}"),
        ("Brazo cola l_h", "stab.l_h_actual", "{:.3f} m"),
        ("Cn_β", "stab.cn_beta", "{:.4f} /rad"),
    ]),
    ("Costes", [
        ("Coste unitario", "cost.unit_cost_mUSD", "{:.2f} M$"),
        ("Coste RDT&E", "cost.rdte_mUSD", "{:.1f} M$"),
    ]),
]

_STATUS_COLORS = {
    "ok":       (GREEN_OK,      "#ECFDF5"),
    "active":   ("#1E6FD9",     "#EEF4FF"),   # activa = buena señal → azul
    "violated": (RED_VIOLATED,  "#FEF2F2"),
}
_STATUS_TEXT = {"ok": "Holgada", "active": "Activa", "violated": "VIOLADA"}

_DISC_CARD_QSS = f"""
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


class ResultsView(QWidget):
    goto_plots_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._summary_labels: dict[str, QLabel] = {}
        self._summary_fmt: dict[str, tuple] = {}
        self._summary_fns: dict[str, object] = {}   # key → callable(dto) | None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # ── Banner headline ──
        self._banner = QFrame()
        self._banner.setFixedHeight(80)
        self._banner.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {BG_HEADER}, stop:1 {BLUE_ACCENT});"
            f" border-radius: 12px; }}"
        )
        blay = QHBoxLayout(self._banner)
        blay.setContentsMargins(24, 12, 16, 12)
        blay.setSpacing(12)

        text_block = QWidget()
        text_block.setStyleSheet("background: transparent;")
        tlay = QVBoxLayout(text_block)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(4)

        self.headline = QLabel("Aún no se ha ejecutado ninguna optimización.")
        hf = QFont("Helvetica Neue", 17, QFont.Weight.Bold)
        self.headline.setFont(hf)
        self.headline.setStyleSheet(f"color: {TEXT_WHITE}; background: transparent;")
        tlay.addWidget(self.headline)

        self.subline = QLabel("")
        self.subline.setStyleSheet(
            f"color: {TEXT_ON_DARK}; font-size: 12px; background: transparent;")
        tlay.addWidget(self.subline)

        blay.addWidget(text_block, 1)

        self.plots_btn = QPushButton("Ver gráficas")
        self.plots_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plots_btn.setEnabled(False)
        self.plots_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.18); color: #FFFFFF;
                font-size: 13px; font-weight: 700;
                border-radius: 8px; padding: 8px 18px;
                border: 1px solid rgba(255,255,255,0.4);
            }
            QPushButton:hover:!disabled {
                background: rgba(255,255,255,0.30);
            }
            QPushButton:disabled {
                color: rgba(255,255,255,0.35);
                border-color: rgba(255,255,255,0.15);
            }
        """)
        self.plots_btn.clicked.connect(self.goto_plots_requested.emit)
        blay.addWidget(self.plots_btn)

        layout.addWidget(self._banner)

        # ── Scroll body ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body_widget = QWidget()
        scroll.setWidget(body_widget)
        layout.addWidget(scroll, 1)

        body = QVBoxLayout(body_widget)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        # ── Resumen por disciplina (grid de tarjetas) ──
        body.addWidget(self._section_label("Resumen por disciplina"))
        disc_grid_widget = QWidget()
        disc_grid = QGridLayout(disc_grid_widget)
        disc_grid.setContentsMargins(0, 0, 0, 0)
        disc_grid.setHorizontalSpacing(14)
        disc_grid.setVerticalSpacing(14)
        n_cols = 3
        for i, (title, rows) in enumerate(DISCIPLINES):
            r, c = divmod(i, n_cols)
            disc_grid.addWidget(self._make_discipline_card(title, rows), r, c)
        for c in range(n_cols):
            disc_grid.setColumnStretch(c, 1)
        body.addWidget(disc_grid_widget)

        # ── Restricciones ──
        body.addWidget(self._section_label("Restricciones"))
        cons_box = QFrame()
        cons_box.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_CARD};"
            f" border-radius: 10px; }}")
        cl = QVBoxLayout(cons_box)
        cl.setContentsMargins(10, 10, 10, 10)
        self.cons_table = QTableWidget(0, 5)
        self.cons_table.setAlternatingRowColors(True)
        self.cons_table.setHorizontalHeaderLabels(
            ["Restricción", "Valor", "Límites", "Margen", "Estado"])
        self.cons_table.verticalHeader().setVisible(False)
        self.cons_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hh = self.cons_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.cons_table.verticalHeader().setDefaultSectionSize(40)
        self.cons_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cl.addWidget(self.cons_table)
        body.addWidget(cons_box)
        body.addStretch(1)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {BLUE_DARK}; font-size: 16px; font-weight: 800;"
            f" background: transparent; padding: 2px 2px;")
        return lbl

    def _make_discipline_card(self, title: str, rows) -> QGroupBox:
        """Tarjeta de disciplina con filas etiqueta → valor, al estilo del
        formulario de la página de Misión (valor en caja tipo input)."""
        box = QGroupBox(title)
        box.setStyleSheet(_DISC_CARD_QSS)
        form = QFormLayout(box)
        form.setContentsMargins(14, 8, 14, 12)
        form.setSpacing(8)
        form.setHorizontalSpacing(14)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for row in rows:
            label, path_or_fn, fmt = row[0], row[1], row[2]
            factor = row[3] if len(row) > 3 else 1.0
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-weight: 500;"
                f" background: transparent;")
            form.addRow(name_lbl, self._make_value_box(label, path_or_fn, fmt, factor))
        return box

    def _make_value_box(self, key: str, path_or_fn, fmt: str,
                        factor: float = 1.0) -> QLabel:
        """Caja de valor de solo lectura. `path_or_fn` puede ser una ruta DTO
        (str) o un callable(dto) → float para valores derivados."""
        val_lbl = QLabel("—")
        val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setMinimumWidth(110)
        val_lbl.setStyleSheet(
            f"QLabel {{ background: {BG_CARD}; border: 1px solid {BORDER_INPUT};"
            f" border-radius: 6px; padding: 5px 8px; min-height: 24px;"
            f" color: {BLUE_DARK}; font-weight: 700; }}")
        store_key = path_or_fn if isinstance(path_or_fn, str) else key
        self._summary_labels[store_key] = val_lbl
        self._summary_fmt[store_key] = (fmt, factor)
        self._summary_fns[store_key] = (None if isinstance(path_or_fn, str)
                                        else path_or_fn)
        return val_lbl

    # ------------------------------------------------------------- API
    def show_results(self, dto: ResultsDTO):
        self.plots_btn.setEnabled(True)
        mtow = dto.mtow
        cost = dto.unit_cost
        self.headline.setText(
            f"MTOW {mtow:.0f} kg   ·   Coste unitario {cost:.2f} M$")

        if dto.success and dto.all_constraints_ok:
            self.subline.setText(
                "✔  Diseño óptimo factible — todas las restricciones satisfechas.")
            self._banner.setStyleSheet(
                f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 #15803D, stop:1 #22C55E); border-radius: 12px; }}"
            )
        else:
            self.subline.setText(
                f"⚠  Solución NO factible o no convergida — {dto.message}")
            self._banner.setStyleSheet(
                f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 #B91C1C, stop:1 #EF4444); border-radius: 12px; }}"
            )

        for key, lbl in self._summary_labels.items():
            entry = self._summary_fmt.get(key, ("{:.3f}", 1.0))
            fmt, factor = entry if isinstance(entry, tuple) else (entry, 1.0)
            fn = self._summary_fns.get(key)
            try:
                v = fn(dto) if fn is not None else dto.get(key)
            except Exception:
                v = float("nan")
            lbl.setText("—" if v != v else fmt.format(v * factor))  # v!=v => NaN

        self._fill_constraints(dto)

    # Constraints que no se muestran en la tabla (activos en el optimizador
    # pero redundantes o demasiado técnicos para el panel de resultados).
    _HIDDEN_CONSTRAINTS = {"perf.cruise_margin"}

    def _fill_constraints(self, dto: ResultsDTO):
        t = self.cons_table
        visible = [c for c in dto.feasibility
                   if c.name not in self._HIDDEN_CONSTRAINTS]
        t.setRowCount(len(visible))
        for r, c in enumerate(visible):
            # Nombre
            t.setItem(r, 0, QTableWidgetItem(c.label))

            # Valor (valores numéricamemnte nulos se muestran como 0)
            val_str = "0" if abs(c.value) < 1e-6 else f"{c.value:.4g}"
            val_item = QTableWidgetItem(val_str)
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(r, 1, val_item)

            # Límites
            lim = []
            if c.lower is not None:
                lim.append(f"≥ {c.lower:g}")
            if c.upper is not None:
                lim.append(f"≤ {c.upper:g}")
            lim_item = QTableWidgetItem("  ".join(lim))
            lim_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(r, 2, lim_item)

            # Barra de margen
            t.setCellWidget(r, 3, MarginBar(c))

            # Badge de estado
            fg_color, bg_color = _STATUS_COLORS.get(
                c.status, (TEXT_PRIMARY, BG_CARD))
            status_text = _STATUS_TEXT.get(c.status, c.status)
            status_item = QTableWidgetItem(f"  {status_text}  ")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor(fg_color))
            status_item.setBackground(QColor(bg_color))
            sf = QFont()
            sf.setBold(True)
            sf.setPointSize(10)
            status_item.setFont(sf)
            t.setItem(r, 4, status_item)

        t.resizeColumnsToContents()
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h = t.horizontalHeader().height() + 2 * t.frameWidth()
        for r in range(t.rowCount()):
            h += t.rowHeight(r)
        t.setFixedHeight(h)
