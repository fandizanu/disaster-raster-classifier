# -*- coding: utf-8 -*-
"""
Disaster Classifier Dialog — UI with 9 separate raster inputs
Input  : slope, elev, landuse, ndvi, rain, coast, buffer,
         contour_density, contour_spacing
Output : 1 risk classification raster (1=Low, 2=Medium, 3=High)
"""

import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QProgressBar, QFileDialog,
    QMessageBox, QGroupBox, QGridLayout, QFrame, QSizePolicy,
    QScrollArea, QWidget
)
from qgis.PyQt.QtCore  import Qt
from qgis.PyQt.QtGui   import QFont, QColor

from qgis.core import (
    QgsRasterLayer, QgsProject,
    QgsColorRampShader, QgsRasterShader,
    QgsSingleBandPseudoColorRenderer
)

from .classification_worker import ClassificationWorker


# ── Output class configuration ──────────────────────────────────────────────
CLASS_CONFIG = {
    1: {"label": "Low Risk",    "color": QColor(0, 200, 100)},   # Green
    2: {"label": "Medium Risk", "color": QColor(255, 180, 0)},   # Yellow
    3: {"label": "High Risk",   "color": QColor(220, 30,  30)},  # Red
}

# ── Input variables with display labels ─────────────────────────────────────
VARIABLES = [
    ("slope",            "Slope"),
    ("elev",             "Elevation"),
    ("landuse",          "Land Use"),
    ("ndvi",             "NDVI"),
    ("rain",             "Rainfall (IDW)"),
    ("coast",            "Distance to Coast"),
    ("buffer",           "River Buffer (3 classes)"),
    ("contour_density",  "Contour Density"),
    ("contour_spacing",  "Contour Spacing"),
]




class DisasterClassifierDialog(QDialog):

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface        = iface
        self.model        = None
        self.worker       = None
        self.raster_paths = {k: "" for k, _ in VARIABLES}

        self.setWindowTitle("🌊 Disaster Risk Classifier  v1.0")
        self.setMinimumSize(560, 780)
        self._build_ui()
        self._load_builtin_model()

    # ────────────────────────────────────────────────────────────────────────
    # BUILD UI
    # ────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Header ──────────────────────────────────────────────────────────
        header = QLabel("Disaster Risk Classification — Flood · Flash Flood · Landslide")
        f = QFont(); f.setBold(True); f.setPointSize(10)
        header.setFont(f)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "background:#1565C0; color:white; padding:8px; border-radius:4px;"
        )
        root.addWidget(header)

        # ── Legend ───────────────────────────────────────────────────────────
        leg_box    = QGroupBox("Output Risk Classes")
        leg_layout = QHBoxLayout()
        for cfg in CLASS_CONFIG.values():
            c   = cfg["color"]
            lbl = QLabel(f"  {cfg['label']}  ")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"background:rgb({c.red()},{c.green()},{c.blue()});"
                f"color:white; border-radius:3px; padding:4px 8px; font-weight:bold;"
            )
            leg_layout.addWidget(lbl)
        leg_box.setLayout(leg_layout)
        root.addWidget(leg_box)

        # ── 9 Raster Inputs ──────────────────────────────────────────────────
        grp_vars = QGroupBox("1. Select Raster File for Each Variable (9 variables)")
        grid     = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        self._var_edits = {}

        for row_idx, (key, label) in enumerate(VARIABLES):
            lbl_num  = QLabel(f"{row_idx+1}.")
            lbl_num.setFixedWidth(20)
            lbl_name = QLabel(label)
            lbl_name.setFixedWidth(170)
            lbl_name.setStyleSheet("font-size:10px;")

            edit = QLineEdit()
            edit.setReadOnly(True)
            edit.setPlaceholderText(f"Select {label} .tif ...")
            edit.setStyleSheet("font-size:10px;")
            self._var_edits[key] = edit

            btn = QPushButton("📂")
            btn.setFixedWidth(32)
            btn.setToolTip(f"Browse {label} raster file")
            btn.clicked.connect(lambda checked, k=key, lb=label: self._browse_var(k, lb))

            grid.addWidget(lbl_num,  row_idx, 0)
            grid.addWidget(lbl_name, row_idx, 1)
            grid.addWidget(edit,     row_idx, 2)
            grid.addWidget(btn,      row_idx, 3)

        btn_auto = QPushButton("⚡ Auto-fill from Folder")
        btn_auto.setToolTip("Select a folder containing all .tif files — plugin will auto-match by filename")
        btn_auto.clicked.connect(self._auto_fill_folder)
        btn_auto.setStyleSheet("background:#E3F2FD; border:1px solid #90CAF9; padding:4px;")

        grp_vars.setLayout(grid)
        root.addWidget(grp_vars)
        root.addWidget(btn_auto)

        # ── Load Model ───────────────────────────────────────────────────────
        grp_model = QGroupBox("2. Load Scikit-learn Model (.pkl / .joblib)")
        row_m     = QHBoxLayout()
        self.txtModelPath = QLineEdit()
        self.txtModelPath.setReadOnly(True)
        self.txtModelPath.setPlaceholderText("No model selected...")
        btn_model = QPushButton("📂 Browse Model")
        btn_model.setFixedWidth(130)
        btn_model.clicked.connect(self._browse_model)
        row_m.addWidget(self.txtModelPath)
        row_m.addWidget(btn_model)
        self.lblModelInfo = QLabel("")
        self.lblModelInfo.setStyleSheet("color:#2e7d32; font-size:10px;")
        vbox_m = QVBoxLayout()
        vbox_m.addLayout(row_m)
        vbox_m.addWidget(self.lblModelInfo)
        grp_model.setLayout(vbox_m)
        root.addWidget(grp_model)

        # ── Output ───────────────────────────────────────────────────────────
        grp_out  = QGroupBox("3. Set Output File")
        row_out  = QHBoxLayout()
        self.txtOutputPath = QLineEdit()
        self.txtOutputPath.setPlaceholderText("Save classification result (.tif)...")
        btn_out  = QPushButton("💾 Save As...")
        btn_out.setFixedWidth(120)
        btn_out.clicked.connect(self._browse_output)
        row_out.addWidget(self.txtOutputPath)
        row_out.addWidget(btn_out)
        grp_out.setLayout(row_out)
        root.addWidget(grp_out)

        # ── Progress ─────────────────────────────────────────────────────────
        self.progressBar = QProgressBar()
        self.progressBar.setValue(0)
        root.addWidget(self.progressBar)

        # ── Log ──────────────────────────────────────────────────────────────
        grp_log = QGroupBox("Process Log")
        vl      = QVBoxLayout()
        self.txtLog = QTextEdit()
        self.txtLog.setReadOnly(True)
        self.txtLog.setMinimumHeight(120)
        self.txtLog.setStyleSheet("font-family:Consolas,monospace; font-size:10px;")
        btn_clr = QPushButton("🗑 Clear Log")
        btn_clr.setFixedWidth(100)
        btn_clr.clicked.connect(self.txtLog.clear)
        vl.addWidget(self.txtLog)
        vl.addWidget(btn_clr, alignment=Qt.AlignRight)
        grp_log.setLayout(vl)
        root.addWidget(grp_log)

        # ── Action Buttons ───────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        row_btn = QHBoxLayout()
        self.btnRun = QPushButton("▶  Run Classification")
        self.btnRun.setMinimumHeight(38)
        self.btnRun.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold;"
            "font-size:12px; border-radius:4px;"
        )
        self.btnRun.clicked.connect(self._run)

        self.btnCancel = QPushButton("⛔  Cancel")
        self.btnCancel.setMinimumHeight(38)
        self.btnCancel.setEnabled(False)
        self.btnCancel.setStyleSheet(
            "background:#D32F2F; color:white; font-size:12px; border-radius:4px;"
        )
        self.btnCancel.clicked.connect(self._cancel)

        btn_close = QPushButton("✖  Close")
        btn_close.setMinimumHeight(38)
        btn_close.setStyleSheet("font-size:12px; border-radius:4px;")
        btn_close.clicked.connect(self.close)

        row_btn.addWidget(self.btnRun)
        row_btn.addWidget(self.btnCancel)
        row_btn.addWidget(btn_close)
        root.addLayout(row_btn)

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Browse variable raster
    # ────────────────────────────────────────────────────────────────────────

    def _browse_var(self, key, label):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select Raster: {label}", "", "GeoTIFF (*.tif *.tiff);;All Files (*)"
        )
        if path:
            self.raster_paths[key] = path
            self._var_edits[key].setText(os.path.basename(path))
            self._var_edits[key].setToolTip(path)
            self._log(f"✅ {label}: {os.path.basename(path)}")

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Auto-fill from folder
    # ────────────────────────────────────────────────────────────────────────

    def _auto_fill_folder(self):
        """Search .tif files in selected folder and match by keyword."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Raster Files")
        if not folder:
            return

        keywords = {
            "slope":           ["slope", "lereng", "kelerengan"],
            "elev":            ["elev", "topograph", "dem", "dtm"],
            "landuse":         ["landuse", "land_use", "classification", "tutupan"],
            "ndvi":            ["ndvi"],
            "rain":            ["rain", "curah", "idw_ch", "ch"],
            "coast":           ["coast", "pantai", "distance"],
            "buffer":          ["buffer", "river", "sungai"],
            "contour_density": ["contour_density", "kerapatan"],
            "contour_spacing": ["contour_spacing", "jarak"],
        }

        tif_files = [f for f in os.listdir(folder)
                     if f.lower().endswith(('.tif', '.tiff'))]

        matched = 0
        for key, kwds in keywords.items():
            for fname in tif_files:
                if any(kw in fname.lower() for kw in kwds):
                    full_path = os.path.join(folder, fname)
                    self.raster_paths[key] = full_path
                    self._var_edits[key].setText(fname)
                    self._var_edits[key].setToolTip(full_path)
                    matched += 1
                    break

        self._log(f"⚡ Auto-fill: {matched}/{len(VARIABLES)} variables matched from folder.")
        if matched < len(VARIABLES):
            self._log("   ⚠️  Unmatched variables must be selected manually.")

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Browse model
    # ────────────────────────────────────────────────────────────────────────

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Scikit-learn Model", "",
            "Model Files (*.pkl *.joblib);;All Files (*)"
        )
        if not path:
            return
        try:
            self._log("🔄 Loading model...")
            import joblib
            self.model = joblib.load(path)

            self.txtModelPath.setText(path)

            parts = [f"✅ {type(self.model).__name__}"]
            if hasattr(self.model, 'n_features_in_'):
                parts.append(f"| Features: {self.model.n_features_in_}")
            if hasattr(self.model, 'classes_'):
                parts.append(f"| Classes: {list(self.model.classes_)}")
            self.lblModelInfo.setText("  ".join(parts))
            self._log(f"✅ Model loaded: {type(self.model).__name__} from {os.path.basename(path)}")
            if hasattr(self.model, 'n_features_in_'):
                self._log(f"   Features : {self.model.n_features_in_} (must be 9)")
            if hasattr(self.model, 'classes_'):
                self._log(f"   Classes  : {list(self.model.classes_)}")

        except Exception as e:
            QMessageBox.critical(self, "Failed to Load Model", str(e))

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Load built-in model (embedded in plugin folder)
    # ────────────────────────────────────────────────────────────────────────

    def _download_model(self, model_path):
        """Download model dari GitHub Releases menggunakan urllib yang aman."""
        import urllib.request
        import urllib.parse

        MODEL_URL = (
            "https://github.com/fandizanu/disaster-raster-classifier"
            "/releases/download/v1.0.0/disaster_model.pkl"
        )

        # Validasi URL hanya boleh https
        parsed = urllib.parse.urlparse(MODEL_URL)
        if parsed.scheme != "https":
            self._log("❌ Download rejected: only HTTPS URLs are allowed.")
            return False

        model_dir = os.path.dirname(model_path)
        os.makedirs(model_dir, exist_ok=True)

        self._log("⬇️  Model not found. Downloading from GitHub...")
        self._log(f"   URL: {MODEL_URL}")

        try:
            from qgis.PyQt.QtWidgets import QProgressDialog, QApplication
            from qgis.PyQt.QtCore import Qt

            progress = QProgressDialog(
                "Downloading disaster_model.pkl from GitHub...",
                "Cancel", 0, 0, self
            )
            progress.setWindowTitle("Downloading Model")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()

            # Download menggunakan https request yang sudah divalidasi
            req = urllib.request.Request(MODEL_URL, method='GET')
            with urllib.request.urlopen(req) as response:  # nosec B310
                data = response.read()
            with open(model_path, 'wb') as out_file:
                out_file.write(data)

            progress.close()
            self._log("✅ Model downloaded successfully!")
            return True

        except Exception as e:
            self._log(f"❌ Failed to download model: {e}")
            self._log("   Please download manually from GitHub Releases:")
            self._log(f"   {MODEL_URL}")
            self._log("   and place it in the 'model/' folder inside the plugin directory.")
            from qgis.PyQt.QtWidgets import QMessageBox
            msg = (
                "Could not download the model automatically.\n\n"
                "Please download it manually from:\n" + MODEL_URL + "\n\n"
                "And place it in:\n" + model_dir
            )
            QMessageBox.warning(self, "Model Download Failed", msg)
            return False

    def _load_builtin_model(self):
        """Auto-load .pkl model embedded in the plugin model/ folder.
        Jika tidak ada, otomatis download dari GitHub Releases."""
        import sys
        import importlib.util

        plugin_dir = os.path.dirname(__file__)
        model_path = os.path.join(plugin_dir, 'model', 'disaster_model.pkl')

        if not os.path.exists(model_path):
            self._log("ℹ️  No built-in model found. Trying to download from GitHub...")
            success = self._download_model(model_path)
            if not success:
                self._log("ℹ️  Please load a model manually via '📂 Browse Model'.")
                return

        try:
            # Register ensemble_model into sys.modules so joblib can resolve the class
            ensemble_file = os.path.join(plugin_dir, "ensemble_model.py")
            spec   = importlib.util.spec_from_file_location("ensemble_model", ensemble_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            sys.modules['ensemble_model']                     = module
            sys.modules['disaster_classifier.ensemble_model'] = module

            import joblib
            self.model = joblib.load(model_path)

            parts = [f"✅ {type(self.model).__name__} (built-in)"]
            if hasattr(self.model, 'n_features_in_'):
                parts.append(f"| Features: {self.model.n_features_in_}")
            if hasattr(self.model, 'classes_'):
                parts.append(f"| Classes: {list(self.model.classes_)}")
            self.lblModelInfo.setText("  ".join(parts))
            self.txtModelPath.setText("[Built-in Model]  disaster_model.pkl")
            self.txtModelPath.setStyleSheet("color:#2e7d32; font-style:italic;")
            self._log("✅ Built-in model loaded successfully!")
            if hasattr(self.model, 'n_features_in_'):
                self._log(f"   Features : {self.model.n_features_in_} (must be 9)")
            if hasattr(self.model, 'classes_'):
                self._log(f"   Classes  : {list(self.model.classes_)}")

        except Exception as e:
            import traceback
            self._log(f"❌ Failed to load built-in model: {e}")
            self._log(traceback.format_exc())

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Browse output
    # ────────────────────────────────────────────────────────────────────────

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Classification Output", "", "GeoTIFF (*.tif)"
        )
        if path:
            if not path.lower().endswith('.tif'):
                path += '.tif'
            self.txtOutputPath.setText(path)

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Run classification
    # ────────────────────────────────────────────────────────────────────────

    def _run(self):
        output_path = self.txtOutputPath.text().strip()

        empty = [label for key, label in VARIABLES if not self.raster_paths.get(key)]
        if empty:
            QMessageBox.warning(self, "Missing Input",
                                "No file selected for:\n• " + "\n• ".join(empty))
            return
        if self.model is None:
            QMessageBox.warning(self, "Missing Input", "Please load a model (.pkl) first.")
            return
        if not output_path:
            QMessageBox.warning(self, "Missing Input", "Please set an output file path.")
            return

        self._log("\n" + "─" * 52)
        self._log("🚀 Starting disaster risk classification...")
        self._log(f"   Output : {output_path}")

        self.btnRun.setEnabled(False)
        self.btnCancel.setEnabled(True)
        self.progressBar.setValue(0)

        self.worker = ClassificationWorker(
            raster_paths=self.raster_paths,
            output_path=output_path,
            model=self.model
        )
        self.worker.progress.connect(self.progressBar.setValue)
        self.worker.log.connect(self._log)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Cancel
    # ────────────────────────────────────────────────────────────────────────

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        self.btnRun.setEnabled(True)
        self.btnCancel.setEnabled(False)

    # ────────────────────────────────────────────────────────────────────────
    # SLOT — Finished
    # ────────────────────────────────────────────────────────────────────────

    def _on_finished(self, output_path):
        self._log("\n✅ Classification complete!")
        self._log(f"📁 Saved to: {output_path}")

        layer = QgsRasterLayer(output_path, "Disaster Risk")
        if layer.isValid():
            self._apply_style(layer)
            QgsProject.instance().addMapLayer(layer)
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()
            self._log("🗺️  Result layer added to QGIS map with automatic styling.")
        else:
            self._log("⚠️  Output layer is not valid. Please check the output file.")

        self.btnRun.setEnabled(True)
        self.btnCancel.setEnabled(False)
        QMessageBox.information(self, "Done",
                                f"Classification successful!\n\nOutput:\n{output_path}")

    def _on_error(self, msg):
        self._log(f"\n❌ ERROR:\n{msg}")
        self.btnRun.setEnabled(True)
        self.btnCancel.setEnabled(False)
        QMessageBox.critical(self, "Classification Error", msg)

    # ────────────────────────────────────────────────────────────────────────
    # HELPER — Apply classification style
    # ────────────────────────────────────────────────────────────────────────

    def _apply_style(self, layer):
        shader = QgsColorRampShader()
        shader.setColorRampType(QgsColorRampShader.Exact)
        items = [
            QgsColorRampShader.ColorRampItem(
                cls_id, cfg["color"], cfg["label"]
            )
            for cls_id, cfg in CLASS_CONFIG.items()
        ]
        shader.setColorRampItemList(items)
        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(shader)
        renderer = QgsSingleBandPseudoColorRenderer(
            layer.dataProvider(), 1, raster_shader
        )
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _log(self, text):
        self.txtLog.append(text)
        self.txtLog.verticalScrollBar().setValue(
            self.txtLog.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        super().closeEvent(event)
