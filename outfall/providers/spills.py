"""Live storm-overflow (sewage spill) sources.

Every English and Welsh water and sewerage company, plus Scottish Water, publishes
near-real-time storm-overflow activity through the Water UK "Stream" programme as
open ArcGIS feature services — the same data behind the National Storm Overflow
Hub. Companies aim to report a spill within an hour of it starting.

Most use one standard schema (an integer ``Status``: 1 discharging, 0 not, -1
offline). South West uses the same fields lower-cased; Welsh Water and Scottish
Water use their own schemas. This module normalises all of them to one spill
record and one three-state classification:

    Discharging          - spilling right now
    Recently discharged  - stopped recently (where the source reports it)
    Offline              - monitor offline / no signal

Position always comes from the feature geometry (requested in WGS84), so the
differing latitude/longitude field names never matter.
"""

import urllib.parse

from .base import SiteSource

# Only these states are kept on the live layer; "not discharging" is dropped so
# the map shows what is (or was just) spilling, not every monitored outfall.
KEEP_STATES = ("Discharging", "Recently discharged", "Offline")

# Per-company field map by schema kind. Position is taken from geometry, so only
# the status / name / watercourse / start fields are listed here.
_FIELDMAP = {
    "int": {"status": "Status", "start": "LatestEventStart",
            "water": "ReceivingWaterCourse", "name": "ReceivingWaterCourse",
            "id": "Id"},
    "int_lc": {"status": "status", "start": "latestEventStart",
               "water": "receivingWaterCourse", "name": "receivingWaterCourse",
               "id": "Id"},
    "welsh": {"status": "status", "start": "start_date_time_discharge",
              "water": "Receiving_Water", "name": "asset_name",
              "id": "permit_number"},
    "scot": {"status": "STATUS_DESCRIPTION", "start": "START_DATETIME",
             "water": "RECEIVING_WATER", "name": "ASSET_NAME",
             "id": "ASSET_ID"},
}


def _classify(kind, value):
    if kind in ("int", "int_lc"):
        return {1: "Discharging", -1: "Offline", 0: "Not discharging"}.get(
            value, "Unknown")
    text = str(value or "")
    if kind == "welsh":
        if "Operating" in text and "Not Operating" not in text:
            return "Discharging"
        if "last 24 hours" in text:
            return "Recently discharged"
        if "Offline" in text or "Out of Service" in text or "Unavailable" in text:
            return "Offline"
        return "Not discharging"
    if kind == "scot":
        if text.startswith("OF"):
            return "Discharging"
        if text.startswith("RO"):
            return "Recently discharged"
        return "Not discharging"
    return "Unknown"


class StreamSpillSource(SiteSource):
    """One water company's live storm-overflow feed."""

    def __init__(self, key, company, service_url, kind, where, layer=0,
                 parent=None):
        super().__init__(parent)
        self.id = f"spill:{key}"
        self.label = company
        self.nation = company          # used only in status messages
        self._company = company
        self._service = service_url.rstrip("/")
        self._kind = kind
        self._where = where
        self._layer = layer

    def url(self):
        params = urllib.parse.urlencode({
            "where": self._where,
            "outFields": "*",
            "outSR": "4326",
            "returnGeometry": "true",
            "resultRecordCount": "4000",
            "f": "json",
        })
        return f"{self._service}/{self._layer}/query?{params}"

    def parse(self, doc):
        fm = _FIELDMAP[self._kind]
        out = []
        for feat in doc.get("features") or []:
            a = feat.get("attributes") or {}
            g = feat.get("geometry") or {}
            lat, lon = g.get("y"), g.get("x")
            if lat is None or lon is None:
                continue
            state = _classify(self._kind, a.get(fm["status"]))
            if state not in KEEP_STATES:
                continue
            name = a.get(fm["name"]) or a.get(fm["water"]) or "Storm overflow"
            out.append({
                "id": f"{self.id}:{a.get(fm['id'])}",
                "lat": float(lat), "lon": float(lon),
                "company": self._company,
                "name": str(name),
                "state": state,
                "water": str(a.get(fm["water"]) or ""),
                "started": a.get(fm["start"]) or "",
            })
        return out


_STD = "Status=1 OR Status=-1"
_STD_LC = "status=1 OR status=-1"

# (key, company, service url, kind, where)
_COMPANIES = [
    ("anglian", "Anglian Water",
     "https://services3.arcgis.com/VCOY1atHWVcDlvlJ/arcgis/rest/services/"
     "stream_service_outfall_locations_view/FeatureServer", "int", _STD),
    ("northumbrian", "Northumbrian Water",
     "https://services-eu1.arcgis.com/MSNNjkZ51iVh8yBj/arcgis/rest/services/"
     "Northumbrian_Water_Storm_Overflow_Activity_2_view/FeatureServer", "int", _STD),
    ("severntrent", "Severn Trent Water",
     "https://services1.arcgis.com/NO7lTIlnxRMMG9Gw/arcgis/rest/services/"
     "Severn_Trent_Water_Storm_Overflow_Activity/FeatureServer", "int", _STD),
    ("southern", "Southern Water",
     "https://services-eu1.arcgis.com/6qJmARkS2dt2IjVA/arcgis/rest/services/"
     "SouthernWater_StormOverflowActivity_PROD_view/FeatureServer", "int", _STD),
    ("thames", "Thames Water",
     "https://services2.arcgis.com/g6o32ZDQ33GpCIu3/arcgis/rest/services/"
     "Thames_Water_Storm_Overflow_Activity_(Production)_view/FeatureServer", "int", _STD),
    ("unitedutilities", "United Utilities",
     "https://services5.arcgis.com/5eoLvR0f8HKb7HWP/arcgis/rest/services/"
     "United_Utilities_Storm_Overflow_Activity/FeatureServer", "int", _STD),
    ("wessex", "Wessex Water",
     "https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/"
     "Wessex_Water_Storm_Overflow_Activity/FeatureServer", "int", _STD),
    ("yorkshire", "Yorkshire Water",
     "https://services-eu1.arcgis.com/1WqkK5cDKUbF0CkH/arcgis/rest/services/"
     "Yorkshire_Water_Storm_Overflow_Activity/FeatureServer", "int", _STD),
    ("southwest", "South West Water",
     "https://services-eu1.arcgis.com/OMdMOtfhATJPcHe3/arcgis/rest/services/"
     "NEH_outlets_PROD/FeatureServer", "int_lc", _STD_LC),
    ("welsh", "Welsh Water (Dŵr Cymru)",
     "https://services3.arcgis.com/KLNF7YxtENPLYVey/arcgis/rest/services/"
     "Spill_Prod_Welsh/FeatureServer", "welsh", "status<>'Overflow Not Operating'"),
    ("scottish", "Scottish Water",
     "https://services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services/"
     "Scottish_Water_Storm_Overflow_Activity/FeatureServer", "scot",
     "STATUS_DESCRIPTION<>'NO - No Overflows'"),
]


def spill_sources():
    """Return a fresh StreamSpillSource for every company."""
    return [StreamSpillSource(key, company, url, kind, where)
            for key, company, url, kind, where in _COMPANIES]
