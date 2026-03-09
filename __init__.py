# -*- coding: utf-8 -*-
"""
Disaster Raster Classifier - QGIS Plugin
Klasifikasi bencana: Banjir, Banjir Bandang, Longsor
"""

def classFactory(iface):
    """
    Entry point plugin QGIS.
    :param iface: QgsInterface instance dari QGIS
    :return: Instance plugin DisasterClassifier
    """
    from .disaster_classifier import DisasterClassifierPlugin
    return DisasterClassifierPlugin(iface)
