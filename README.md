# 🌊 Disaster Raster Classifier — Plugin QGIS

Plugin QGIS untuk **klasifikasi raster bencana** menggunakan model Machine Learning (Scikit-learn).

## Kelas yang Didukung

| ID | Kelas         | Warna       |
|----|---------------|-------------|
| 0  | Non-Bencana   | Hijau Muda  |
| 1  | Banjir        | Biru        |
| 2  | Banjir Bandang| Biru Tua    |
| 3  | Longsor       | Coklat      |

---

## 📦 Instalasi

### Langkah 1 — Salin folder plugin
Salin seluruh folder `disaster_classifier/` ke direktori plugin QGIS:

**Windows:**
```
C:\Users\[username]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
```

**Linux:**
```
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
```

**macOS:**
```
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
```

### Langkah 2 — Generate Icon (opsional)
Buka OSGeo4W Shell dan jalankan:
```bash
cd path/ke/disaster_classifier
python generate_icon.py
```

### Langkah 3 — Aktifkan Plugin di QGIS
1. Buka QGIS
2. Menu **Plugins → Manage and Install Plugins**
3. Tab **Installed** → cari **Disaster Raster Classifier**
4. Centang ✅ untuk mengaktifkan

---

## 🚀 Cara Penggunaan

1. **Buka plugin**: Menu **Raster → Disaster Classifier → Disaster Raster Classifier**
   (atau klik icon di toolbar)

2. **Pilih Layer Raster Input**: Pilih raster yang sudah dimuat di QGIS. Pastikan raster tiap input variabel memiliki resolusi dan Coordinate Reference System (CRS) yang sama. 

3. **Load Model**: Klik "Pilih Model" → pilih file `.pkl` atau `.joblib`
   - Plugin memiliki model built-in yang dapat didownload dari awal 
   - Plugin akan otomatis mendeteksi jumlah band dari raster
   - Pastikan jumlah band raster = jumlah fitur saat training model

4. **Tentukan Output**: Klik "Simpan Ke..." → pilih lokasi file `.tif`

5. **Jalankan**: Klik "▶ Jalankan Klasifikasi"
   - Progress bar menunjukkan kemajuan
   - Log menampilkan detail proses dan statistik hasil
   - Hasil otomatis ditambahkan ke peta QGIS dengan pewarnaan per kelas

---

## ⚙️ Persiapan Model

Model Scikit-learn kamu harus:
- Disimpan dengan `joblib.dump(model, 'model.pkl')` atau `pickle.dump(model, f)`
- Dilatih dengan fitur = nilai piksel per band (tiap baris = 1 piksel)
- Label kelas: **0** (Non-Bencana), **1** (Banjir), **2** (Banjir Bandang), **3** (Longsor)

Contoh training:
```python
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib

# X shape: (n_samples, n_bands) — tiap baris = 1 piksel
# y shape: (n_samples,) — label: 0, 1, 2, atau 3
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# Simpan model
joblib.dump(model, 'disaster_model.pkl')
```

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Plugin tidak muncul | Restart QGIS setelah install |
| `ModuleNotFoundError: joblib` | Buka OSGeo4W Shell → `pip install joblib scikit-learn` |
| Jumlah band tidak sesuai | Pastikan raster input memiliki band yang sama dengan saat training |
| Model gagal dimuat | Pastikan model disimpan dengan versi sklearn yang kompatibel |
| Error GDAL | Pastikan raster tidak corrupt dan memiliki proyeksi yang valid |

---

## 📁 Struktur File Plugin

```
disaster_classifier/
├── __init__.py                    ← Entry point
├── disaster_classifier.py         ← Logika plugin (menu/toolbar)
├── disaster_classifier_dialog.py  ← UI dialog utama
├── classification_worker.py       ← Thread klasifikasi (background)
├── generate_icon.py               ← Script pembuat icon
├── metadata.txt                   ← Info plugin QGIS
├── icons/
│   └── icon.png                   ← Icon plugin
└── README.md                      ← Dokumentasi ini
```

---

## 📝 Lisensi
Proyek ini menggunakan MIT License.
