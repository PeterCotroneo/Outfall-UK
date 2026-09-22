"""Source registry.

Each UK nation is a bathing-water source that contributes points to one shared
map layer. Adding a source: implement SiteSource in a new module and add it here.
The plugin builds its nation checkboxes from SOURCES.
"""

from .base import SiteSource
from .defra import EnglandSource, WalesSource
from .sepa import ScotlandSource
from .daera import NorthernIrelandSource

# order shown in the panel (England, Wales, Scotland, Northern Ireland)
SOURCES = [EnglandSource, WalesSource, ScotlandSource, NorthernIrelandSource]

__all__ = ["SiteSource", "EnglandSource", "WalesSource", "ScotlandSource",
           "NorthernIrelandSource", "SOURCES"]
