# -*- coding: utf-8 -*-
"""
Classification Worker — reads 9 separate rasters, stacks them, then predicts
"""

import numpy as np
from qgis.PyQt.QtCore import QThread, pyqtSignal




class WeightedEnsemble:
    """
    Ensemble LGBM + RF + XGB dengan bobot F1-score.
    Class ini WAJIB ada di plugin agar joblib bisa load model .pkl
    yang dibuat dari Jupyter Notebook.
    """

    def __init__(self, models: dict, weights: dict, metadata: dict):
        self.models          = models
        self.weights         = weights
        self.meta            = metadata
        self.n_features_in_  = metadata.get('n_features', 9)
        self.classes_        = np.array([1, 2, 3])
        self.feature_names_  = metadata.get('feature_names', [])

    def predict_proba(self, X):
        proba = np.zeros((X.shape[0], len(self.classes_)))
        for name, model in self.models.items():
            proba += self.weights[name] * model.predict_proba(X)
        return proba

    def predict(self, X):
        indices = np.argmax(self.predict_proba(X), axis=1)
        return self.classes_[indices]

    def __repr__(self):
        w = self.weights
        return (
            f"WeightedEnsemble(\n"
            f"  RF={w.get('rf', 0):.6f}, "
            f"LGBM={w.get('lgbm', 0):.6f}, "
            f"XGB={w.get('xgb', 0):.6f}\n"
            f"  features={self.n_features_in_}, "
            f"classes={list(self.classes_)}\n"
            f")"
        )




class ClassificationWorker(QThread):
    """
    Background thread for classification.
    Input  : dict {nama: path_tif} — 9 variabel raster terpisah
    Output : GeoTIFF 1 band dengan kelas 1=Low, 2=Medium, 3=High
    """

    progress = pyqtSignal(int)
    log      = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    # Order MUST MATCH the order used during model training
    VARIABLE_ORDER = [
        "slope", "elev", "landuse", "ndvi", "rain",
        "coast", "buffer", "contour_density", "contour_spacing"
    ]

    def __init__(self, raster_paths: dict, output_path: str, model, nodata_fill=0.0):
        super().__init__()
        self.raster_paths  = raster_paths
        self.output_path   = output_path
        self.model         = model
        self.nodata_fill   = nodata_fill
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            from osgeo import gdal
            gdal.UseExceptions()

            n_vars = len(self.VARIABLE_ORDER)

            # ── 1. Validasi semua path tersedia ────────────────────────────
            self.log.emit("🔍 Checking raster input files...")
            missing = [k for k in self.VARIABLE_ORDER
                       if k not in self.raster_paths or not self.raster_paths[k]]
            if missing:
                self.error.emit(f"No file selected for variable: {', '.join(missing)}")
                return
            self.progress.emit(5)

            # ── 2. Buka referensi dari raster pertama ──────────────────────
            ref_ds        = gdal.Open(self.raster_paths[self.VARIABLE_ORDER[0]])
            cols          = ref_ds.RasterXSize
            rows          = ref_ds.RasterYSize
            geo_transform = ref_ds.GetGeoTransform()
            projection    = ref_ds.GetProjection()
            ref_ds        = None

            self.log.emit(f"   • Reference dimension : {cols} x {rows} piksel")
            self.log.emit(f"   • Number of variables   : {n_vars}")
            self.progress.emit(10)

            # ── 3. Baca & stack semua variabel ─────────────────────────────
            self.log.emit("\n📚 Reading raster variables:")
            bands = []
            for i, key in enumerate(self.VARIABLE_ORDER):
                if self._is_cancelled:
                    self.log.emit("⛔ Process cancelled.")
                    return

                path = self.raster_paths[key]
                ds   = gdal.Open(path)
                if ds is None:
                    self.error.emit(f"Failed to open: {path}")
                    return

                # Resample otomatis jika ukuran piksel berbeda
                if ds.RasterXSize != cols or ds.RasterYSize != rows:
                    self.log.emit(f"   ⚠️  {key}: different size, resampling...")
                    mem_drv = gdal.GetDriverByName('MEM')
                    mem_ds  = mem_drv.Create('', cols, rows, 1, gdal.GDT_Float32)
                    mem_ds.SetGeoTransform(geo_transform)
                    mem_ds.SetProjection(projection)
                    gdal.ReprojectImage(ds, mem_ds)
                    arr = mem_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                    mem_ds = None
                else:
                    arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

                nodata = ds.GetRasterBand(1).GetNoDataValue()
                if nodata is not None:
                    arr[arr == nodata] = self.nodata_fill
                arr = np.nan_to_num(arr, nan=self.nodata_fill,
                                    posinf=self.nodata_fill, neginf=self.nodata_fill)
                bands.append(arr)
                ds = None

                self.progress.emit(10 + int(30 * (i + 1) / n_vars))
                self.log.emit(
                    f"   ✅ [{i+1}/{n_vars}] {key:<20} "
                    f"min={arr.min():.3f}  max={arr.max():.3f}"
                )

            # ── 4. Stack & reshape ─────────────────────────────────────────
            self.log.emit("\n🔧 Building feature matrix (rows x cols x 9)...")
            img       = np.stack(bands, axis=-1)   # (rows, cols, 9)
            X         = img.reshape(-1, n_vars)     # (rows*cols, 9)
            total_px  = X.shape[0]
            self.log.emit(f"   • Total pixels : {total_px:,}")
            self.progress.emit(45)

            # ── 5. Checking model compatibility ────────────────────────────────
            if hasattr(self.model, 'n_features_in_'):
                expected = self.model.n_features_in_
                if n_vars != expected:
                    self.error.emit(
                        f"Number of variables ({n_vars}) ≠ model feature count ({expected}).\n"
                        f"Ensure variable order and count match training."
                    )
                    return

            # ── 6. Prediksi per batch (hemat RAM) ──────────────────────────
            self.log.emit("\n🤖 Running model prediction...")
            BATCH       = 500_000
            result_flat = np.zeros(total_px, dtype=np.uint8)
            n_batches   = int(np.ceil(total_px / BATCH))

            for b in range(n_batches):
                if self._is_cancelled:
                    self.log.emit("⛔ Process cancelled.")
                    return
                s = b * BATCH
                e = min(s + BATCH, total_px)
                result_flat[s:e] = self.model.predict(X[s:e]).astype(np.uint8)
                self.progress.emit(45 + int(37 * (b + 1) / n_batches))

            result = result_flat.reshape(rows, cols)
            self.progress.emit(84)

            # ── 7. Simpan GeoTIFF ──────────────────────────────────────────
            self.log.emit("\n💾 Saving output GeoTIFF...")
            driver = gdal.GetDriverByName('GTiff')
            out_ds = driver.Create(
                self.output_path, cols, rows, 1, gdal.GDT_Byte,
                options=['COMPRESS=LZW', 'TILED=YES']
            )
            out_ds.SetGeoTransform(geo_transform)
            out_ds.SetProjection(projection)
            out_band = out_ds.GetRasterBand(1)
            out_band.WriteArray(result)
            out_band.SetNoDataValue(0)
            out_ds.FlushCache()
            out_ds = None
            self.progress.emit(93)

            # ── 8. Statistik ───────────────────────────────────────────────
            CLASS_LABELS = {1: 'Low Risk', 2: 'Medium Risk', 3: 'High Risk'}
            valid = result[result != 0]
            self.log.emit("\n📊 Classification Result Statistics:")
            if valid.size > 0:
                for cls_id, label in CLASS_LABELS.items():
                    cnt = int(np.sum(valid == cls_id))
                    pct = cnt / valid.size * 100
                    bar = '█' * int(pct / 4)
                    self.log.emit(f"   {label:<14}: {cnt:>10,} px  ({pct:5.1f}%)  {bar}")
            else:
                self.log.emit("   ⚠️  No valid pixels in output.")

            self.progress.emit(100)
            self.finished.emit(self.output_path)

        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n\nDetail:\n{traceback.format_exc()}")
