"""
Pestaña de ejecución (Run) — capa View.

Layout:
  ┌──────────────────────────────────────────────┐
  │  Botón ejecutar  │  Barra de progreso        │
  ├──────────────────────────────────────────────┤
  │  Estado                                      │
  ├──────────────────────────────────────────────┤  ╮
  │  Log del solver   │  N2 interactivo          │  │ QScrollArea
  ├───────────────────────────────────────────── ┤  │ global
  │  Arquitectura MDAO — diagrama XDSM (imagen)  │  │ (scroll vertical)
  └──────────────────────────────────────────────┘  ╯
"""

from __future__ import annotations

import os

from PySide6.QtCore import Signal, Qt, QUrl, QSize
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit,
    QProgressBar, QLabel, QSplitter, QFrame, QGroupBox, QScrollArea,
)
from PySide6.QtPdf import QPdfDocument

from gui.style import (
    BG_CARD, BORDER_CARD, BLUE_PRIMARY, BLUE_DARK, BLUE_ACCENT,
    TEXT_WHITE, TEXT_SECONDARY, GREEN_OK, RED_VIOLATED,
)

_XDSM_PDF = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "docs", "xdsm_ucav.pdf")
)


class _XdsmPdfWidget(QWidget):
    """Renderiza la primera página del PDF XDSM a ancho completo como QPixmap.

    La altura se calcula automáticamente a partir del aspect ratio del documento,
    de modo que la imagen siempre ocupa el ancho disponible sin barras de scroll
    propias. El scroll lo gestiona el QScrollArea externo de RunView.
    """

    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        self._doc = QPdfDocument(self)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        self._aspect: float = 0.0   # height / width del PDF
        self._last_w: int = 0

        if os.path.exists(pdf_path):
            self._doc.load(pdf_path)
            if self._doc.pageCount() > 0:
                ps = self._doc.pagePointSize(0)
                if ps.width() > 0:
                    self._aspect = ps.height() / ps.width()
        else:
            self._label.setText(f"No se encontró:\n{pdf_path}")
            self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        self._render()

    def _render(self):
        if self._aspect <= 0 or self._doc.pageCount() == 0:
            return
        w = self.width()
        if w <= 10:
            return
        dpr = self.devicePixelRatio()
        phys_w = int(w * dpr)
        if phys_w == self._last_w:
            return
        self._last_w = phys_w
        phys_h = max(1, int(phys_w * self._aspect))
        img = self._doc.render(0, QSize(phys_w, phys_h))
        if not img.isNull():
            px = QPixmap.fromImage(img)
            px.setDevicePixelRatio(dpr)
            self._label.setPixmap(px)
        h_logical = max(1, int(w * self._aspect))
        self.setMinimumHeight(h_logical)
        self.setMaximumHeight(h_logical)


class RunView(QWidget):
    run_requested = Signal()
    goto_results_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._n2_path: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # ── Top control bar ──────────────────────────────────────────
        top_card = QFrame()
        top_card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_CARD};"
            f" border-radius: 10px; }}"
        )
        bar = QHBoxLayout(top_card)
        bar.setContentsMargins(16, 12, 16, 12)
        bar.setSpacing(14)

        self.run_btn = QPushButton("Ejecutar optimización MDAO")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setMinimumWidth(280)
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BLUE_PRIMARY}, stop:1 {BLUE_ACCENT});
                color: {TEXT_WHITE}; font-size: 14px; font-weight: 700;
                border-radius: 8px; padding: 10px 28px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BLUE_ACCENT}, stop:1 {BLUE_PRIMARY});
            }}
            QPushButton:pressed {{ background: {BLUE_DARK}; }}
            QPushButton:disabled {{ background: #C4CAD4; color: #8896A8; }}
        """)
        self.run_btn.clicked.connect(self.run_requested.emit)
        bar.addWidget(self.run_btn)

        self.results_btn = QPushButton("Ver resultados")
        self.results_btn.setMinimumHeight(40)
        self.results_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.results_btn.setEnabled(False)
        self.results_btn.setStyleSheet("""
            QPushButton {
                background: #16A34A; color: #FFFFFF;
                font-size: 14px; font-weight: 700;
                border-radius: 8px; padding: 10px 22px;
                border: none;
            }
            QPushButton:hover:!disabled { background: #22C55E; }
            QPushButton:pressed { background: #15803D; }
            QPushButton:disabled { background: #C4CAD4; color: #F8FAFC; border: none; }
        """)
        self.results_btn.clicked.connect(self.goto_results_requested.emit)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        bar.addWidget(self.progress, 1)
        bar.addWidget(self.results_btn)
        layout.addWidget(top_card)

        # ── Estado ───────────────────────────────────────────────────
        self.status = QLabel("Listo.")
        self.status.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: 600; font-size: 13px;"
            f" padding: 2px 8px; background: transparent;"
        )
        layout.addWidget(self.status)

        # ── Scroll area global (log/N2 + XDSM) ───────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(10)

        # ── Log (estrecho) | N2 ──────────────────────────────────────
        hsplit = QSplitter(Qt.Orientation.Horizontal)
        hsplit.setHandleWidth(6)
        hsplit.setMinimumHeight(620)   # altura mínima para log/N2

        log_card = QGroupBox("Log del solver")
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(10, 8, 10, 10)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setObjectName("logConsole")
        self.log_edit.setReadOnly(True)
        self.log_edit.setFont(QFont("Menlo", 10))
        self.log_edit.setMaximumBlockCount(5000)
        log_lay.addWidget(self.log_edit)
        hsplit.addWidget(log_card)

        n2_card = QGroupBox("N2 interactivo — dependencias de variables")
        n2_lay = QVBoxLayout(n2_card)
        n2_lay.setContentsMargins(6, 8, 6, 8)
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.n2_view = QWebEngineView()
            n2_lay.addWidget(self.n2_view)
            self._n2_available = True
        except ImportError:
            lbl = QLabel(
                "QtWebEngine no disponible.\n"
                "Instala PySide6-WebEngine para ver el N2 aquí."
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
            n2_lay.addWidget(lbl)
            self._n2_available = False

        hsplit.addWidget(n2_card)
        log_card.setFixedWidth(400)
        hsplit.setStretchFactor(0, 0)
        hsplit.setStretchFactor(1, 1)
        iv.addWidget(hsplit)

        # ── XDSM (ancho completo, altura automática por aspect ratio) ─
        xdsm_card = QGroupBox("Arquitectura MDAO — diagrama XDSM")
        xdsm_lay = QVBoxLayout(xdsm_card)
        xdsm_lay.setContentsMargins(6, 8, 6, 8)
        self._xdsm_widget = _XdsmPdfWidget(_XDSM_PDF, parent=xdsm_card)
        xdsm_lay.addWidget(self._xdsm_widget)
        iv.addWidget(xdsm_card)

        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        self._show_n2_placeholder()

    # ── N2 ───────────────────────────────────────────────────────────
    def _show_n2_placeholder(self):
        if not self._n2_available:
            return
        html = (
            "<html><body style='background:#F0F2F5;display:flex;"
            "align-items:center;justify-content:center;height:100%;margin:0'>"
            "<p style='font-family:sans-serif;font-size:16px;color:#64748B;"
            "text-align:center'>Ejecuta una optimización para cargar<br>"
            "el N2 interactivo de OpenMDAO.</p></body></html>"
        )
        self.n2_view.setHtml(html)

    def load_n2(self, path: str):
        """Carga el HTML del N2 generado por OpenMDAO tras la optimización."""
        if not self._n2_available or not path or not os.path.exists(path):
            return
        if self._n2_path and self._n2_path != path:
            try:
                os.remove(self._n2_path)
            except OSError:
                pass
        self._n2_path = path
        self.n2_view.load(QUrl.fromLocalFile(path))

    # ── API pública ───────────────────────────────────────────────────
    def set_results_ready(self, ready: bool):
        self.results_btn.setEnabled(ready)

    def set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        if running:
            self.progress.setRange(0, 0)
            self.log_edit.clear()
            self.status.setText("Optimizando…")
            self.status.setStyleSheet(
                f"color: {BLUE_PRIMARY}; font-weight: 600; font-size: 13px;"
                f" padding: 2px 8px; background: transparent;"
            )
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

    def append_log(self, text: str):
        self.log_edit.moveCursor(self.log_edit.textCursor().MoveOperation.End)
        self.log_edit.insertPlainText(text)
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_status(self, text: str, ok: bool = True):
        color = GREEN_OK if ok else RED_VIOLATED
        self.status.setText(text)
        self.status.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: 13px;"
            f" padding: 2px 8px; background: transparent;"
        )

    def plot_convergence(self, history: dict, objective_label: str):
        """Mantiene compatibilidad con el controlador (no-op)."""
        pass
