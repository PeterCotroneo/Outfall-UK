"""Bathing-water layer: merge sites from the four national sources and render
them coloured by annual classification or by today's pollution-risk forecast.

Sites are static points (not a live stream), so the store keeps them keyed by
source and rebuilds the memory layer whenever a source loads, refreshes, or is
toggled off.
"""

import os

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProject, QgsMarkerSymbol, QgsSvgMarkerSymbolLayer,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsMessageLog, Qgis,
)

LAYER_NAME = "Outfall UK — Bathing Waters"
_DROP_SVG = os.path.join(os.path.dirname(__file__), "drop.svg")

# Annual bathing-water classification -> colour (green good … red poor)
RATING_COLORS = [
    ("Excellent", "#1a9850"),
    ("Good", "#66bd63"),
    ("Sufficient", "#fee08b"),
    ("Poor", "#d73027"),
]
# Short-term pollution-risk forecast -> colour
RISK_COLORS = [
    ("Normal", "#1a9850"),
    ("Increased risk", "#d73027"),
    ("No current forecast", "#bdbdbd"),
]
_OTHER_COLOR = "#9e9e9e"   # catch-all: New site, Not classified, unknown

MODE_RATING = "rating"
MODE_RISK = "risk"

_FIELDS = [
    ("name", QVariant.String),
    ("nation", QVariant.String),
    ("rating", QVariant.String),
    ("risk", QVariant.String),
    ("operator", QVariant.String),
    ("kind", QVariant.String),
    ("url", QVariant.String),
]
_ALIASES = {
    "name": "Bathing water", "nation": "Nation", "rating": "Annual rating",
    "risk": "Pollution risk (today)", "operator": "Operator",
    "kind": "Type", "url": "Profile",
}
_MAP_TIP = (
    '<b>🏊 [% "name" %]</b> · [% "nation" %]<br/>'
    'Annual rating: [% "rating" %]<br/>'
    'Pollution risk today: [% "risk" %]'
    '[% CASE WHEN "operator" != \'\' THEN \'<br/>Operator: \' || "operator" '
    'ELSE \'\' END %]'
)


class SiteStore:
    def __init__(self):
        self._layer = None
        self._by_source = {}   # source id -> list of site dicts
        self._mode = MODE_RATING

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
        self._by_source.clear()

    # --- data ------------------------------------------------------------
    def set_sites(self, source_id, sites):
        self._by_source[source_id] = list(sites)
        self._rebuild()

    def clear_source(self, source_id):
        if source_id in self._by_source:
            del self._by_source[source_id]
            self._rebuild()

    def set_mode(self, mode):
        self._mode = mode if mode in (MODE_RATING, MODE_RISK) else MODE_RATING
        if self._layer_valid():
            self._style()
            self._layer.triggerRepaint()

    def _all_sites(self):
        for sites in self._by_source.values():
            for site in sites:
                yield site

    def count(self):
        return sum(len(v) for v in self._by_source.values())

    def count_where(self, field, value):
        return sum(1 for s in self._all_sites() if s.get(field) == value)

    def _rebuild(self):
        if not self._layer_valid():
            return
        dp = self._layer.dataProvider()
        existing = [f.id() for f in self._layer.getFeatures()]
        if existing:
            dp.deleteFeatures(existing)
        feats = []
        for s in self._all_sites():
            feat = QgsFeature(self._layer.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(float(s["lon"]), float(s["lat"]))))
            feat.setAttributes([
                s.get("name", ""), s.get("nation", ""), s.get("rating", ""),
                s.get("risk", ""), s.get("operator", ""), s.get("kind", ""),
                s.get("url", ""),
            ])
            feats.append(feat)
        if feats:
            dp.addFeatures(feats)
        self._layer.updateExtents()
        self._layer.triggerRepaint()

    # --- styling ---------------------------------------------------------
    def _style(self):
        try:
            scheme = RATING_COLORS if self._mode == MODE_RATING else RISK_COLORS
            cats = [QgsRendererCategory(value, self._marker(color), value)
                    for value, color in scheme]
            # catch-all row (invalid value) for anything outside the scheme
            cats.append(QgsRendererCategory(
                QVariant(), self._marker(_OTHER_COLOR), "Other / not classified"))
            self._layer.setRenderer(QgsCategorizedSymbolRenderer(self._mode, cats))
        except Exception as exc:  # noqa: BLE001 - styling must never block data
            QgsMessageLog.logMessage(f"styling skipped: {exc}", "Outfall UK",
                                     Qgis.MessageLevel.Warning)

    def _marker(self, color):
        svg = QgsSvgMarkerSymbolLayer(_DROP_SVG)
        svg.setSize(5)
        svg.setFillColor(QColor(color))
        svg.setStrokeColor(QColor("#333333"))
        svg.setStrokeWidth(0.2)
        sym = QgsMarkerSymbol()
        sym.changeSymbolLayer(0, svg)
        return sym
