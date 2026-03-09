# -*- coding: utf-8 -*-
"""
Disaster Raster Classifier - Plugin Utama
"""

import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon


class DisasterClassifierPlugin:
    """Plugin QGIS untuk klasifikasi raster bencana."""

    def __init__(self, iface):
        """
        :param iface: QgsInterface — jembatan ke aplikasi QGIS
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dlg = None

    def initGui(self):
        """Tambahkan menu dan toolbar icon ke QGIS."""
        icon_path = os.path.join(self.plugin_dir, 'icons', 'icon.png')

        # Gunakan icon default QGIS jika icon tidak tersedia
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon(':/plugins/disaster_classifier/icons/icon.png')

        self.action = QAction(
            icon,
            'Disaster Raster Classifier',
            self.iface.mainWindow()
        )
        self.action.setToolTip('Klasifikasi Raster Bencana (Banjir, Banjir Bandang, Longsor)')
        self.action.triggered.connect(self.run)

        # Tambah ke toolbar dan menu Raster
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToRasterMenu('&Disaster Classifier', self.action)

    def unload(self):
        """Hapus plugin dari menu dan toolbar QGIS."""
        self.iface.removePluginRasterMenu('&Disaster Classifier', self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Tampilkan dialog utama plugin."""
        from .disaster_classifier_dialog import DisasterClassifierDialog
        self.dlg = DisasterClassifierDialog(self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.exec_()
