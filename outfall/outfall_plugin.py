"""Outfall UK — main plugin class.

A dock panel that loads every designated UK bathing water onto the map, coloured
by its official annual quality classification or today's short-term pollution-risk
forecast. Data is fetched from the four national regulators asynchronously and
merged into one layer you can filter by nation. Click a site to see its rating,
risk, operator and a link to its official profile.
"""

import os

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QToolButton, QGroupBox, QPlainTextEdit,
    QDialog, QDialogButtonBox,
)
from qgis.core import QgsMessageLog, Qgis
from qgis.gui import QgsCollapsibleGroupBox

from .providers import SOURCES
from .providers.spills import spill_sources
from .sites import SiteStore, MODE_RATING, MODE_RISK
from .spills import SpillStore
from .sources_info import nation_html, spills_html
from ._debug import dbg, add_sink, clear_sinks

REFRESH_MS = 30 * 60 * 1000   # re-fetch every half hour (forecasts update daily)
plugin_dir = os.path.dirname(__file__)


class OutfallPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.store = SiteStore()
        self.spill_store = SpillStore()
        self.sources = {}          # id -> SiteSource instance (bathing waters)
        self.spill_srcs = {}       # id -> StreamSpillSource instance
        self.checks = {}           # id -> QCheckBox
        self.timer = None
        self.cbo_mode = None
        self.chk_spills = None
        self.lbl_status = None
        self.lbl_spills = None
        self.log_view = None
        self._loaded_once = False

    # --- plugin lifecycle ------------------------------------------------
    def initGui(self):
        icon = QIcon(os.path.join(plugin_dir, "icon.svg"))
        self.action = QAction(icon, "Outfall UK", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.toggled.connect(self._toggle_dock)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Outfall UK", self.action)

    def unload(self):
        clear_sinks()
        self.log_view = None
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        for src in list(self.sources.values()) + list(self.spill_srcs.values()):
            try:
                src.stop()
            except Exception as exc:  # noqa: BLE001
                QgsMessageLog.logMessage(
                    f"stop: {exc}", "Outfall UK", Qgis.MessageLevel.Warning)
        self.sources.clear()
        self.spill_srcs.clear()
        self.store.remove_layer()
        self.spill_store.remove_layer()
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("Outfall UK", self.action)
            self.action = None

    def _toggle_dock(self, checked):
        if checked:
            if self.dock is None:
                self.dock = self._build_dock()
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
                self.iface.mainWindow().resizeDocks(
                    [self.dock], [430], Qt.Orientation.Horizontal)
            self.dock.show()
            if not self._loaded_once:
                self._loaded_once = True
                self._load()
        elif self.dock is not None:
            self.dock.hide()

    # --- UI --------------------------------------------------------------
    def _build_dock(self):
        dock = QDockWidget("Outfall UK", self.iface.mainWindow())
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        panel = QWidget()
        layout = QVBoxLayout(panel)

        intro = QLabel(
            "Designated bathing waters across the UK, coloured by their official "
            "water-quality rating — is it safe to swim? Click a site for detail.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Colour by:"))
        self.cbo_mode = QComboBox()
        self.cbo_mode.addItem("Pollution risk (today)", MODE_RISK)
        self.cbo_mode.addItem("Annual rating", MODE_RATING)
        self.cbo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.cbo_mode, 1)
        layout.addLayout(mode_row)

        nat_box = QGroupBox("Nations")
        nat_layout = QVBoxLayout(nat_box)
        for cls in SOURCES:
            row = QHBoxLayout()
            cb = QCheckBox(cls.nation)
            cb.setChecked(True)
            cb.toggled.connect(
                lambda on, cid=cls.id: self._on_nation_toggled(cid, on))
            self.checks[cls.id] = cb
            row.addWidget(cb, 1)
            info = QToolButton()
            info.setText("ⓘ")
            info.setAutoRaise(True)
            info.setToolTip(f"Data sources for {cls.nation}")
            info.clicked.connect(
                lambda _=False, cid=cls.id: self._show_sources(cid))
            row.addWidget(info, 0)
            nat_layout.addLayout(row)
        layout.addWidget(nat_box)

        spill_box = QGroupBox("Live storm overflows (sewage spills)")
        spill_layout = QVBoxLayout(spill_box)
        spill_row = QHBoxLayout()
        self.chk_spills = QCheckBox("Show storm overflows")
        self.chk_spills.toggled.connect(self._on_spills_toggled)
        spill_row.addWidget(self.chk_spills, 1)
        spill_info = QToolButton()
        spill_info.setText("ⓘ")
        spill_info.setAutoRaise(True)
        spill_info.setToolTip("Live storm-overflow data sources")
        spill_info.clicked.connect(lambda _=False: self._show_info(*spills_html()))
        spill_row.addWidget(spill_info, 0)
        spill_layout.addLayout(spill_row)

        self.lbl_spills = QLabel("")
        self.lbl_spills.setWordWrap(True)
        self.lbl_spills.setStyleSheet("color: gray;")
        spill_layout.addWidget(self.lbl_spills)
        layout.addWidget(spill_box)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._load)
        layout.addWidget(self.btn_refresh)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        log_box = QgsCollapsibleGroupBox("Activity Log")
        log_box.setCollapsed(True)
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setMinimumHeight(110)
        self.log_view.setPlaceholderText("Activity appears here while loading.")
        log_layout.addWidget(self.log_view)
        btn_clear = QPushButton("Clear log")
        btn_clear.clicked.connect(self.log_view.clear)
        log_layout.addWidget(btn_clear)
        layout.addWidget(log_box)
        layout.addStretch(1)

        clear_sinks()
        add_sink(self._log_line)

        dock.setWidget(panel)
        return dock

    def _log_line(self, line):
        if self.log_view is not None:
            self.log_view.appendPlainText(line)

    def _show_sources(self, nation_id):
        info = nation_html(nation_id)
        if info is not None:
            self._show_info(*info)

    def _show_info(self, title, body):
        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle(f"Data sources — {title}")
        dlg.setMinimumWidth(430)
        v = QVBoxLayout(dlg)
        lbl = QLabel(body)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setOpenExternalLinks(True)
        v.addWidget(lbl)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        v.addWidget(buttons)
        dlg.exec()

    # --- loading ---------------------------------------------------------
    def _load(self):
        self.store.ensure_layer()
        for cls in SOURCES:
            if not self.checks or self.checks[cls.id].isChecked():
                self._start_source(cls)
        if self.chk_spills is not None and self.chk_spills.isChecked():
            self._load_spills()
        self._ensure_timer()
        self._update_status("Loading…")

    def _load_spills(self):
        self.spill_store.ensure_layer()
        for src in spill_sources():
            prev = self.spill_srcs.pop(src.id, None)
            if prev is not None:
                prev.stop()
            src.sites_update.connect(self._on_spills)
            src.status_changed.connect(self._update_status)
            src.error.connect(self._on_error)
            self.spill_srcs[src.id] = src
            src.start()

    def _start_source(self, cls):
        prev = self.sources.pop(cls.id, None)
        if prev is not None:
            prev.stop()
        src = cls()
        src.sites_update.connect(self._on_sites)
        src.status_changed.connect(self._update_status)
        src.error.connect(self._on_error)
        self.sources[cls.id] = src
        src.start()

    def _ensure_timer(self):
        if self.timer is None:
            self.timer = QTimer()
            self.timer.setInterval(REFRESH_MS)
            self.timer.timeout.connect(self._load)
            self.timer.start()

    def _on_sites(self, source_id, sites):
        self.store.set_sites(source_id, sites)
        self._update_status()

    def _on_spills(self, source_id, spills):
        self.spill_store.set_spills(source_id, spills)
        self._update_status()

    def _on_spills_toggled(self, on):
        if on:
            self._load_spills()
            self._ensure_timer()
        else:
            for src in self.spill_srcs.values():
                src.stop()
            self.spill_srcs.clear()
            self.spill_store.remove_layer()
        self._update_status()

    def _on_error(self, text):
        dbg(f"Error: {text}")
        self._update_status(f"Error: {text}")

    def _on_mode_changed(self):
        self.store.set_mode(self.cbo_mode.currentData())

    def _on_nation_toggled(self, source_id, on):
        cls = next((c for c in SOURCES if c.id == source_id), None)
        # the nation filter applies to the storm-overflow layer too
        if cls is not None:
            self.spill_store.set_nation_visible(cls.nation, on)
        if on:
            if cls is not None:
                self.store.ensure_layer()
                self._start_source(cls)
        else:
            src = self.sources.pop(source_id, None)
            if src is not None:
                src.stop()
            self.store.clear_source(source_id)
        self._update_status()

    def _update_status(self, text=None):
        self._update_spill_status()
        if self.lbl_status is None:
            return
        total = self.store.count()
        poor = self.store.count_where("rating", "Poor")
        risk = self.store.count_where("risk", "Increased risk")
        parts = [f"{total} bathing waters"]
        if poor:
            parts.append(f"{poor} rated Poor")
        if risk:
            parts.append(f"{risk} at increased risk today")
        summary = " · ".join(parts)
        self.lbl_status.setText(f"{text}\n{summary}" if text else summary)

    def _update_spill_status(self):
        if self.lbl_spills is None:
            return
        if self.chk_spills is None or not self.chk_spills.isChecked():
            self.lbl_spills.setText("")
            return
        total = self.spill_store.count()
        now = self.spill_store.count_state("Discharging")
        recent = self.spill_store.count_state("Recently discharged")
        self.lbl_spills.setText(
            f"{total} overflows · {now} discharging now · {recent} recent")
