"""Northern Ireland — the Department of Agriculture, Environment and Rural
Affairs (DAERA).

DAERA publishes bathing-water monitoring points with their water-quality
classification through an ArcGIS feature service. Geometry is requested in WGS84
(outSR=4326). There is no separate short-term forecast on this layer, so risk is
reported as "no current forecast".
"""

from .base import SiteSource

_URL = ("https://services-eu1.arcgis.com/kswen6BYexuc1SUk/arcgis/rest/services/"
        "Bathing_Water_Monitoring_Points_Public_View_PRD/FeatureServer/0/query"
        "?where=1%3D1&outFields=Site_name,water_quality_indicator,Type,"
        "Bathing_Water_Operator,Profile__URL&outSR=4326&returnGeometry=true"
        "&f=json")


class NorthernIrelandSource(SiteSource):
    id = "ni"
    label = "Northern Ireland — DAERA"
    nation = "Northern Ireland"

    def url(self):
        return _URL

    def parse(self, doc):
        out = []
        for feat in doc.get("features") or []:
            a = feat.get("attributes") or {}
            g = feat.get("geometry") or {}
            lat, lon = g.get("y"), g.get("x")
            if lat is None or lon is None:
                continue
            out.append({
                "id": f"{self.id}:{a.get('Site_name')}",
                "lat": float(lat), "lon": float(lon),
                "name": a.get("Site_name") or "Bathing water",
                "nation": self.nation,
                "rating": a.get("water_quality_indicator") or "Not classified",
                "risk": "No current forecast",
                "operator": a.get("Bathing_Water_Operator") or "",
                "kind": a.get("Type") or "",
                "url": a.get("Profile__URL") or "",
            })
        return out
