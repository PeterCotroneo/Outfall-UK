"""Per-nation data-source descriptions.

Single source of truth for the "ⓘ" information button shown next to each nation
in the panel. Keyed by the bathing-water source id (england / wales / scotland /
ni). Each entry lists the bathing-water regulator and the storm-overflow feeds
that nation contributes, with links.
"""

OGL = ('<p style="color:gray">All data under the '
       '<a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">'
       'Open Government Licence v3.0</a>.</p>')

NATION_SOURCES = {
    "england": {
        "title": "England",
        "html": (
            "<b>Bathing-water quality</b><br/>"
            "Environment Agency, via the DEFRA data-services platform "
            '(<a href="https://environment.data.gov.uk/">environment.data.gov.uk</a>) '
            "— annual classification and, in season, the daily short-term "
            "pollution-risk forecast."
            "<br/><br/>"
            "<b>Live storm overflows</b><br/>"
            "Near-real-time Event Duration Monitoring (EDM) feeds from the "
            "English water companies — Anglian, Northumbrian, Severn Trent, "
            "Southern, Thames, United Utilities, Wessex, Yorkshire and South "
            "West Water — published via the Water UK "
            '<a href="https://www.streamwaterdata.co.uk/pages/the-national-storm-overflow-hub">'
            "Stream / National Storm Overflow Hub</a>."
        ),
    },
    "wales": {
        "title": "Wales",
        "html": (
            "<b>Bathing-water quality</b><br/>"
            "Natural Resources Wales, via the DEFRA data-services platform "
            '(<a href="https://environment.data.gov.uk/wales/bathing-waters/">'
            "environment.data.gov.uk/wales</a>)."
            "<br/><br/>"
            "<b>Live storm overflows</b><br/>"
            "Near-real-time EDM feed from Welsh Water (Dŵr Cymru), published via "
            "the Water UK Stream programme."
        ),
    },
    "scotland": {
        "title": "Scotland",
        "html": (
            "<b>Bathing-water quality</b><br/>"
            "Scottish Environment Protection Agency (SEPA), via its open ArcGIS "
            'map server (<a href="https://map.sepa.org.uk/">map.sepa.org.uk</a>) '
            "— annual classification."
            "<br/><br/>"
            "<b>Live storm overflows</b><br/>"
            "Near-real-time feed from Scottish Water, published via the Water UK "
            "Stream programme."
        ),
    },
    "ni": {
        "title": "Northern Ireland",
        "html": (
            "<b>Bathing-water quality</b><br/>"
            "Department of Agriculture, Environment and Rural Affairs (DAERA), "
            "via its open ArcGIS feature service — annual classification."
            "<br/><br/>"
            "<b>Live storm overflows</b><br/>"
            "Not available — NI Water does not currently publish a comparable "
            "near-real-time storm-overflow feed, so Northern Ireland is not in "
            "the live spills layer."
        ),
    },
}


def nation_html(source_id):
    """Return (title, body-html) for a nation, or None if unknown."""
    entry = NATION_SOURCES.get(source_id)
    if entry is None:
        return None
    return entry["title"], entry["html"] + OGL
