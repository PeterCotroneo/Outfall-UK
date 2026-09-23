"""Live storm-overflow layer: merge outfalls from every water company and render
them by discharge state, like the SAS Live Sewage Map.

Keeps records keyed by source (company) and rebuilds a memory layer whenever a
company loads, refreshes, or is switched off. Individual states can be shown or
hidden (the panel's filter) without refetching.
"""

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProject, QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsMessageLog, Qgis,
)

LAYER_NAME = "Outfall UK — Storm Overflows"

# Discharge state -> colour, sampled from the Surfers Against Sewage Live Sewage
# Map legend so the symbols match it exactly. Rendered as filled circles, as SAS
# does.
STATE_COLORS = [
    ("Discharging", "#de5f5f"),          # coral red — spilling now
    ("Recently discharged", "#c9982e"),  # amber — stopped in last 48h
    ("Not discharging", "#5cb7a0"),      # teal — monitored, dry
    ("Offline", "#939aa2"),              # blue-grey — monitor offline
    ("No Data", "#3b3b3b"),              # charcoal — status unknown
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
        self._hidden = set()    # nation display names hidden by the nation filter

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

    def set_nation_visible(self, nation, visible):
        """Show or hide a whole nation's overflows (driven by the nation
        checkboxes), without refetching."""
        changed = (nation in self._hidden) == visible
        if visible:
            self._hidden.discard(nation)
        else:
            self._hidden.add(nation)
        if changed:
            self._rebuild()

    def _all(self):
        for spills in self._by_company.values():
            for s in spills:
                if s.get("nation") not in self._hidden:
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

    # --- styling ---------------------------------------------------------
    def _style(self):
        try:
            cats = [QgsRendererCategory(state, self._marker(color), state)
                    for state, color in STATE_COLORS]
            self._layer.setRenderer(
                QgsCategorizedSymbolRenderer("state", cats))
        except Exception as exc:  # noqa: BLE001 - styling must never block data
            QgsMessageLog.logMessage(f"styling skipped: {exc}", "Outfall UK",
                                     Qgis.MessageLevel.Warning)

    def _marker(self, color):
        # Filled circle, matching the SAS Live Sewage Map.
        circle = QgsSimpleMarkerSymbolLayer()   # default shape is a circle
        circle.setSize(1.5)
        circle.setColor(QColor(color))
        circle.setStrokeColor(QColor(0, 0, 0, 60))
        circle.setStrokeWidth(0.2)
        sym = QgsMarkerSymbol()
        sym.changeSymbolLayer(0, circle)
        return sym
