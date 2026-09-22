# Outfall UK

**Is it safe to swim?** Outfall UK loads every designated bathing water in
**England, Wales, Scotland and Northern Ireland** onto your QGIS map, coloured by
its official water-quality rating — so you can see the state of the whole coast
(and inland bathing waters) at a glance, and click any site for detail.

It is built on the same engine as a family of live-tracking QGIS plugins — a
pluggable data-source layer, a merged map layer, categorised rendering and
identify — but where those stream moving things, Outfall UK monitors places:

- [Wake](https://github.com/PeterCotroneo/Wake) — marine vessels (AIS)
- [Contrail](https://github.com/PeterCotroneo/Contrail) — aircraft (ADS-B)
- [Zenith](https://github.com/PeterCotroneo/Zenith) — satellites (SGP4)
- [SeaState US](https://github.com/PeterCotroneo/SeaState-US) — NOAA tides & buoys

![Outfall UK: every UK bathing water, coloured by its annual quality rating](docs/img/01-uk-overview.png)

## Features

- **Whole-UK coverage** — ~700 designated bathing waters across all four nations, from one panel.
- **Free and keyless** — official open data, no account or API key.
- **Colour by rating or risk** — switch between the **annual classification** (Excellent, Good, Sufficient, Poor) and, where published, **today's short-term pollution-risk forecast** (normal vs increased risk).
- **Toggle nations** — show or hide England, Wales, Scotland and Northern Ireland independently.
- **Click for detail** — Identify any site for its rating, latest risk, responsible operator and a link to its official profile page.
- **Refreshes** — reloads on demand and every half hour, so in-season risk forecasts stay current.

## Data sources

All data comes straight from the four national regulators, under the
[Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/):

| Nation | Regulator | Source |
|---|---|---|
| England | Environment Agency | DEFRA data-services platform (`environment.data.gov.uk`) |
| Wales | Natural Resources Wales | DEFRA data-services platform (`environment.data.gov.uk/wales`) |
| Scotland | Scottish Environment Protection Agency (SEPA) | SEPA open ArcGIS map server (`map.sepa.org.uk`) |
| Northern Ireland | Dept. of Agriculture, Environment & Rural Affairs (DAERA) | DAERA open ArcGIS feature service |

Short-term daily **pollution-risk forecasts** are published for England and Wales
during the bathing season; Scotland and Northern Ireland sites show their annual
classification only. Ratings are the official classifications calculated from up
to four years of monitoring; they are not a live measurement of the water in
front of you. Always check on-site signage before bathing.

## Install

1. Clone this repository (or use **Code → Download ZIP** on GitHub).
2. Zip the inner **`outfall/`** folder, so the archive contains `outfall/` at its top level — or copy `outfall/` straight into your QGIS plugins directory.
3. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**, and select that zip.
4. Enable **Outfall UK**. An **Outfall UK** panel appears on the right, and the bathing waters load automatically.

## Usage

1. Open the **Outfall UK** panel — every UK bathing water loads onto the map.
2. Use **Colour by** to switch between the annual rating and today's pollution risk.
3. Tick or untick a **nation** to show or hide it.
4. **Click** a site to see its rating, risk, operator and a link to its official profile.

## Credits

Contains public sector information from the Environment Agency, Natural Resources
Wales, the Scottish Environment Protection Agency and the Department of
Agriculture, Environment and Rural Affairs, licensed under the Open Government
Licence v3.0.

## License

GPL-2.0-or-later.
