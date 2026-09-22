"""Data-source abstraction for Outfall UK.

Each source fetches every bathing water it covers in a single asynchronous
request (off the GUI thread, via QGIS's network manager) and emits a normalised
list. The store merges the sources, keyed by source id, so they refresh and
toggle independently.

QtNetwork is used through ``qgis.PyQt`` (no hard-coded PyQt binding), and enum
members are fully scoped for Qt6 compatibility.

Normalised site dict:
    id (str)         - unique key, prefixed by source ("england:03600")
    lat, lon (float) - WGS84
    name (str)
    nation (str)     - England | Wales | Scotland | Northern Ireland
    rating (str)     - Excellent | Good | Sufficient | Poor | ... (annual class)
    risk (str)       - Normal | Increased risk | No current forecast (forecast)
    operator (str)   - responsible water company / council ("" if unknown)
    kind (str)       - Coastal / Inland / "" (where the source states it)
    url (str)        - link to the site's official profile ("" if none)
"""

import json

from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.core import QgsNetworkAccessManager

from .._debug import dbg

_USER_AGENT = ("Outfall-UK QGIS plugin "
               "(+https://github.com/PeterCotroneo/Outfall-UK)")


class SiteSource(QObject):
    """Abstract national bathing-water source. Subclasses set id/label/nation
    and implement url() and parse()."""

    sites_update = pyqtSignal(str, list)   # (source id, list of site dicts)
    status_changed = pyqtSignal(str)
    error = pyqtSignal(str)

    id = "base"
    label = "Abstract source"
    nation = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reply = None

    # --- interface -------------------------------------------------------
    def url(self):
        raise NotImplementedError

    def parse(self, doc):
        """Return a list of normalised site dicts from the decoded response."""
        raise NotImplementedError

    def start(self):
        self.status_changed.emit(f"{self.nation}: loading…")
        self._get(self.url())

    def stop(self):
        if self._reply is not None:
            try:
                self._reply.abort()
            except RuntimeError:
                pass
            self._reply = None

    # --- async fetch -----------------------------------------------------
    def _get(self, url):
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, _USER_AGENT)
        self._reply = QgsNetworkAccessManager.instance().get(req)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.error.emit(f"{self.nation}: {reply.errorString()}")
                return
            raw = bytes(reply.readAll())
        finally:
            reply.deleteLater()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.error.emit(f"{self.nation}: could not read the response")
            return
        try:
            sites = self.parse(doc)
        except Exception as exc:  # noqa: BLE001 - one bad source must not break the rest
            self.error.emit(f"{self.nation}: {exc}")
            return
        dbg(f"{self.nation}: {len(sites)} bathing waters")
        self.status_changed.emit(f"{self.nation}: {len(sites)} sites")
        self.sites_update.emit(self.id, sites)
