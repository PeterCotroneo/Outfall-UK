def classFactory(iface):
    """Entry point required by QGIS to load the plugin."""
    from .outfall_plugin import OutfallPlugin
    return OutfallPlugin(iface)
