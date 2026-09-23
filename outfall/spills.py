"""Live storm-overflow layer: merge outfalls from every water company and render
them by discharge state, like the SAS Live Sewage Map.

Keeps records keyed by source (company) and rebuilds a memory layer whenever a
company loads, refreshes, or is switched off. Individual states can be shown or
hidden (the panel's filter) without refetching.
"""

import os

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProject, QgsMarkerSymbol, QgsSvgMarkerSymbolLayer,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsMessageLog, Qgis,
)

LAYER_NAME = "Outfall UK — Storm Overflows"
_DROP_SVG = os.path.join(os.path.dirname(__file__), "drop.svg")

# Discharge state -> colour, in legend order (mirrors the SAS Live Sewage Map).
STATE_COLORS = [
    ("Discharging", "#d7191c"),          # red — spilling now
    ("Recently discharged", "#fdae61"),  # orange — stopped in last 48h
    ("Not discharging", "#1a9641"),      # green — monitored, dry
    ("Offline", "#9e9e9e"),              # grey — monitor offline
    ("No Data", "#4d4d4d"),              # dark grey — status unknown
]

_FIELDS = [
    ("name", QVariant.String),
    ("company", QVariant.String),
    ("state", QVariant.String),
    ("water", QVariant.String),
    ("started", QVariant.String),
]
_ALIASES = {
    "name": "Overflow", "company": "Company", "state": "Status",
    "water": "Receiving water", "started": "Latest spill start",
}
_MAP_TIP = (
    '<b>💧 [% "name" %]</b><br/>'
    'Status: [% "state" %]<br/>'
    'Company: [% "company" %]'
    '[% CASE WHEN "water" != \'\' THEN \'<br/>Into: \' || "water" '
    'ELSE \'\' END %]'
)


class SpillStore:
    def __init__(self):
        self._layer = None
        self._by_company = {}   # source id -> list of spill dicts
        self._visible = {state for state, _c in STATE_COLORS}

    # --- layer lifecycle -------------------------------------------------
    def ensure_layer(self):
        if self._layer_valid():
            return self._layer
        fields = QgsFields()
        for name, qtype in _FIELDS:
            fields.append(QgsField(name, qtype))
        layer = QgsVectorLayer("Point?crs=EPSG:4326", LAYER_NAME, "memory")
        layer.dataProvider().addAttributes(fields.toList())
        layer.updateFields()
        for name, alias in _ALIASES.items():
            idx = layer.fields().indexOf(name)
            if idx >= 0:
                layer.setFieldAlias(idx, alias)
        layer.setMapTipTemplate(_MAP_TIP)
        self._layer = layer
        self._style()
        QgsProject.instance().addMapLayer(layer)
        self._rebuild()
        return layer

    def _layer_valid(self):
        try:
            return self._layer is not None and self._layer.isValid()
        except RuntimeError:
            return False

    def layer(self):
        return self._layer if self._layer_valid() else None

    def remove_layer(self):
        if self._layer_valid():
            QgsProject.instance().removeMapLayer(self._layer.id())
        self._layer = None
        self._by_company.clear()

    # --- data ------------------------------------------------------------
    def set_spills(self, source_id, spills):
        self._by_company[source_id] = list(spills)
        self._rebuild()

    def clear_all(self):
        self._by_company.clear()
        self._rebuild()

    def _all(self):
        for spills in self._by_company.values():
            for s in spills:
                yield s

    def count(self):
        return sum(len(v) for v in self._by_company.values())

    def count_state(self, state):
        return sum(1 for s in self._all() if s.get("state") == state)

    def _rebuild(self):
        if not self._layer_valid():
            return
        dp = self._layer.dataProvider()
        existing = [f.id() for f in self._layer.getFeatures()]
        if existing:
            dp.deleteFeatures(existing)
        feats = []
        for s in self._all():
            feat = QgsFeature(self._layer.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(float(s["lon"]), float(s["lat"]))))
            feat.setAttributes([
                s.get("name", ""), s.get("company", ""), s.get("state", ""),
                s.get("water", ""), str(s.get("started", "")),
            ])
            feats.append(feat)
        if feats:
            dp.addFeatures(feats)
        self._layer.updateExtents()
        self._layer.triggerRepaint()

    # --- styling / filter ------------------------------------------------
    def set_state_visible(self, state, visible):
        if visible:
            self._visible.add(state)
        else:
            self._visible.discard(state)
        if self._layer_valid():
            self._apply_visibility()
            self._layer.triggerRepaint()

    def _apply_visibility(self):
        renderer = self._layer.renderer()
        if not isinstance(renderer, QgsCategorizedSymbolRenderer):
            return
        for i, cat in enumerate(renderer.categories()):
            renderer.updateCategoryRenderState(i, cat.value() in self._visible)

    def _style(self):
        try:
            cats = [QgsRendererCategory(state, self._marker(color), state)
                    for state, color in STATE_COLORS]
            self._layer.setRenderer(
                QgsCategorizedSymbolRenderer("state", cats))
            self._apply_visibility()
        except Exception as exc:  # noqa: BLE001 - styling must never block data
            QgsMessageLog.logMessage(f"styling skipped: {exc}", "Outfall UK",
                                     Qgis.MessageLevel.Warning)

    def _marker(self, color):
        svg = QgsSvgMarkerSymbolLayer(_DROP_SVG)
        svg.setSize(4)
        svg.setFillColor(QColor(color))
        svg.setStrokeColor(QColor("#333333"))
        svg.setStrokeWidth(0.2)
        sym = QgsMarkerSymbol()
        sym.changeSymbolLayer(0, svg)
        return sym
