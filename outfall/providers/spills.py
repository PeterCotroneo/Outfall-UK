"""Live storm-overflow (sewage spill) sources.

Every English and Welsh water and sewerage company, plus Scottish Water, publishes
near-real-time storm-overflow activity through the Water UK "Stream" programme as
open ArcGIS feature services — the same data behind the National Storm Overflow
Hub. Companies aim to report a spill within an hour of it starting.

This loads *every* monitored outfall (like the SAS Live Sewage Map) and colours
each by one of five states:

    Discharging          - spilling right now
    Recently discharged  - stopped in the last 48 hours
    Not discharging      - monitored, not currently spilling
    Offline              - monitor offline / no signal
    No Data              - status unknown

Most companies use one standard schema (an integer ``Status``: 1 discharging,
0 not, -1 offline, with recency derived from the latest event end). South West
uses the same fields lower-cased; Welsh Water and Scottish Water use their own
schemas. Position always comes from the feature geometry (requested in WGS84), so
the differing latitude/longitude field names never matter.
"""

import time
import urllib.parse

from .base import SiteSource

# All five states, in legend order.
STATES = ("Discharging", "Recently discharged", "Not discharging",
          "Offline", "No Data")

_RECENT_MS = 48 * 3600 * 1000   # "recently discharged" window for the int schema

# Per-company field map by schema kind. Position is taken from geometry.
_FIELDMAP = {
    "int": {"status": "Status", "start": "LatestEventStart",
            "end": "LatestEventEnd", "water": "ReceivingWaterCourse",
            "name": "ReceivingWaterCourse", "id": "Id"},
    "int_lc": {"status": "status", "start": "latestEventStart",
               "end": "latestEventEnd", "water": "receivingWaterCourse",
               "name": "receivingWaterCourse", "id": "Id"},
    "welsh": {"status": "status", "start": "start_date_time_discharge",
              "end": "stop_date_time_discharge", "water": "Receiving_Water",
              "name": "asset_name", "id": "permit_number"},
    "scot": {"status": "STATUS_DESCRIPTION", "start": "START_DATETIME",
             "end": "END_DATETIME", "water": "RECEIVING_WATER",
             "name": "ASSET_NAME", "id": "ASSET_ID"},
    # Northern Ireland publishes outfall *locations* only — no live status —
    # so every NI overflow is classified "No Data".
    "ni": {"status": None, "start": None, "end": None, "water": "Water_Body",
           "name": "Name", "id": "fid"},
}


def _classify(kind, attrs, fm, now_ms):
    if kind == "ni":
        return "No Data"
    value = attrs.get(fm["status"])
    if kind in ("int", "int_lc"):
        if value == 1:
            return "Discharging"
        if value == -1:
            return "Offline"
        if value == 0:
            end = attrs.get(fm["end"])
            if isinstance(end, (int, float)) and now_ms - end <= _RECENT_MS:
                return "Recently discharged"
            return "Not discharging"
        return "No Data"
    text = str(value or "")
    if kind == "welsh":
        if not text:
            return "No Data"
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
        if text.startswith("NO"):
            return "Not discharging"
        return "No Data"
    return "No Data"


class StreamSpillSource(SiteSource):
    """One water company's live storm-overflow feed (all outfalls)."""

    paginate = True

    def __init__(self, key, company, service_url, kind, region, where="1=1",
                 layer=0, parent=None):
        super().__init__(parent)
        self.id = f"spill:{key}"
        self.label = company
        self.nation = company          # used only in status messages
        self._company = company
        self._region = region          # England / Wales / Scotland / Northern Ireland
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
            "resultOffset": self._offset,
            "resultRecordCount": self.page_size,
            "f": "json",
        })
        return f"{self._service}/{self._layer}/query?{params}"

    def parse(self, doc):
        fm = _FIELDMAP[self._kind]
        now_ms = time.time() * 1000
        out = []
        for feat in doc.get("features") or []:
            a = feat.get("attributes") or {}
            g = feat.get("geometry") or {}
            lat, lon = g.get("y"), g.get("x")
            if lat is None or lon is None:
                continue
            state = _classify(self._kind, a, fm, now_ms)
            name = a.get(fm["name"]) or a.get(fm["water"]) or "Storm overflow"
            out.append({
                "id": f"{self.id}:{a.get(fm['id'])}",
                "lat": float(lat), "lon": float(lon),
                "company": self._company,
                "nation": self._region,
                "name": str(name),
                "state": state,
                "water": str(a.get(fm["water"]) or ""),
                "started": a.get(fm["start"]) or "",
            })
        return out


# (key, company, service url, kind, where)
_ALL = "1=1"
_COMPANIES = [
    ("anglian", "Anglian Water",
     "https://services3.arcgis.com/VCOY1atHWVcDlvlJ/arcgis/rest/services/"
     "stream_service_outfall_locations_view/FeatureServer", "int", _ALL),
    ("northumbrian", "Northumbrian Water",
     "https://services-eu1.arcgis.com/MSNNjkZ51iVh8yBj/arcgis/rest/services/"
     "Northumbrian_Water_Storm_Overflow_Activity_2_view/FeatureServer", "int", _ALL),
    ("severntrent", "Severn Trent Water",
     "https://services1.arcgis.com/NO7lTIlnxRMMG9Gw/arcgis/rest/services/"
     "Severn_Trent_Water_Storm_Overflow_Activity/FeatureServer", "int", _ALL),
    ("southern", "Southern Water",
     "https://services-eu1.arcgis.com/6qJmARkS2dt2IjVA/arcgis/rest/services/"
     "SouthernWater_StormOverflowActivity_PROD_view/FeatureServer", "int", _ALL),
    ("thames", "Thames Water",
     "https://services2.arcgis.com/g6o32ZDQ33GpCIu3/arcgis/rest/services/"
     "Thames_Water_Storm_Overflow_Activity_(Production)_view/FeatureServer", "int", _ALL),
    ("unitedutilities", "United Utilities",
     "https://services5.arcgis.com/5eoLvR0f8HKb7HWP/arcgis/rest/services/"
     "United_Utilities_Storm_Overflow_Activity/FeatureServer", "int", _ALL),
    ("wessex", "Wessex Water",
     "https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/"
     "Wessex_Water_Storm_Overflow_Activity/FeatureServer", "int", _ALL),
    ("yorkshire", "Yorkshire Water",
     "https://services-eu1.arcgis.com/1WqkK5cDKUbF0CkH/arcgis/rest/services/"
     "Yorkshire_Water_Storm_Overflow_Activity/FeatureServer", "int", _ALL),
    ("southwest", "South West Water",
     "https://services-eu1.arcgis.com/OMdMOtfhATJPcHe3/arcgis/rest/services/"
     "NEH_outlets_PROD/FeatureServer", "int_lc", _ALL),
    ("welsh", "Welsh Water (Dŵr Cymru)",
     "https://services3.arcgis.com/KLNF7YxtENPLYVey/arcgis/rest/services/"
     "Spill_Prod_Welsh/FeatureServer", "welsh", _ALL),
    ("scottish", "Scottish Water",
     "https://services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services/"
     "Scottish_Water_Storm_Overflow_Activity/FeatureServer", "scot", _ALL),
    # Northern Ireland: locations only (no live status), so all show as "No Data".
    ("ni", "NI Water (locations only)",
     "https://services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services/"
     "NI_discharges/FeatureServer", "ni", "Overflow_T='Storm Overflow'"),
]


# company key -> the nation whose checkbox shows/hides it
_NATION = {
    "anglian": "England", "northumbrian": "England", "severntrent": "England",
    "southern": "England", "thames": "England", "unitedutilities": "England",
    "wessex": "England", "yorkshire": "England", "southwest": "England",
    "welsh": "Wales", "scottish": "Scotland", "ni": "Northern Ireland",
}


def spill_sources():
    """Return a fresh StreamSpillSource for every company."""
    return [StreamSpillSource(key, company, url, kind, _NATION[key], where)
            for key, company, url, kind, where in _COMPANIES]
