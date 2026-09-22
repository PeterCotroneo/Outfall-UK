"""Scotland — the Scottish Environment Protection Agency (SEPA).

SEPA publishes bathing-water points with their annual classification through its
open ArcGIS map server. Geometry is requested in WGS84 (outSR=4326). SEPA also
runs daily in-season predictions, but those are not exposed on this layer, so
the short-term risk is reported as "no current forecast" here.
"""

from .base import SiteSource

_URL = ("https://map.sepa.org.uk/server/rest/services/Open/"
        "Environmental_Monitoring/MapServer/1/query"
        "?where=1%3D1&outFields=objectid,description,class_description,bw_url"
        "&outSR=4326&returnGeometry=true&f=json")


class ScotlandSource(SiteSource):
    id = "scotland"
    label = "Scotland — SEPA"
    nation = "Scotland"

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
                "id": f"{self.id}:{a.get('objectid')}",
                "lat": float(lat), "lon": float(lon),
                "name": a.get("description") or "Bathing water",
                "nation": self.nation,
                "rating": a.get("class_description") or "Not classified",
                "risk": "No current forecast",
                "operator": "",
                "kind": "",
                "url": a.get("bw_url") or "",
            })
        return out
