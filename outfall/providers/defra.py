"""England and Wales — the DEFRA bathing-water data-services platform.

Both nations publish the same linked-data structure at environment.data.gov.uk;
only the base path and the nation differ. Each site carries its annual compliance
classification and, in season, a short-term pollution-risk prediction.
"""

from .base import SiteSource

_PAGE = 500   # England ~464 and Wales ~110 both fit in a single page


def _name(obj):
    return ((obj or {}).get("name") or {}).get("_value") or ""


def _profile_url(item):
    prof = item.get("latestProfile")
    if isinstance(prof, dict):
        return prof.get("_about") or ""
    return prof or ""


class _DefraSource(SiteSource):
    base_url = ""

    def url(self):
        return f"{self.base_url}?_pageSize={_PAGE}"

    def parse(self, doc):
        items = (doc.get("result") or {}).get("items") or []
        out = []
        for it in items:
            sp = it.get("samplingPoint") or {}
            lat, lon = sp.get("lat"), sp.get("long")
            if lat is None or lon is None:
                continue
            rating = _name((it.get("latestComplianceAssessment") or {})
                           .get("complianceClassification")) or "Not classified"
            rp = it.get("latestRiskPrediction") or {}
            level = (_name(rp.get("riskLevel")) or "").lower()
            risk = {"normal": "Normal", "increased": "Increased risk"}.get(
                level, "No current forecast")
            sid = it.get("eubwidNotation") or it.get("_about") or _name(it)
            out.append({
                "id": f"{self.id}:{sid}",
                "lat": float(lat), "lon": float(lon),
                "name": _name(it) or "Bathing water",
                "nation": self.nation,
                "rating": rating,
                "risk": risk,
                "operator": _name(it.get("appointedSewerageUndertaker")),
                "kind": "",
                "url": _profile_url(it),
            })
        return out


class EnglandSource(_DefraSource):
    id = "england"
    label = "England — Environment Agency"
    nation = "England"
    base_url = "https://environment.data.gov.uk/doc/bathing-water.json"


class WalesSource(_DefraSource):
    id = "wales"
    label = "Wales — Natural Resources Wales"
    nation = "Wales"
    base_url = ("https://environment.data.gov.uk/wales/"
                "bathing-waters/doc/bathing-water.json")
