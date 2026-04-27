# Tomato Classification HSV

Klasifikasi kematangan tomat secara **realtime** menggunakan kamera dan analisis warna HSV dengan OpenCV.

## Cara Kerja

Program membaca frame dari kamera, memotong area ROI (Region of Interest) di tengah frame, lalu menganalisis distribusi warna HSV untuk menentukan tingkat kematangan tomat:

| Label | Kondisi |
|---|---|
| **UNRIPE (HIJAU)** | Rasio hijau ≥ 28% dari piksel valid |
| **SEMI-RIPE (KUNING/ORANYE)** | Rasio kuning ≥ 14% (dan hijau tidak dominan) |
| **RIPE (MERAH)** | Selain kondisi di atas |

## Instalasi

```bash
pip install -r requirements.txt
```

## Penggunaan

```bash
python main.py
```

- Kotak ROI akan muncul di tengah jendela kamera
- Label kematangan, rasio R/G/Y ditampilkan langsung di layar
- Tekan **`q`** untuk keluar

## Konfigurasi

Edit bagian `CONFIG` di `main.py`:

```python
CAMERA_INDEX   = 0     # ganti ke 1, 2, dst. untuk kamera eksternal
ROI_SIZE       = 300   # ukuran kotak ROI dalam pixel
USE_CENTER_ROI = True  # False = gunakan koordinat ROI_X0, ROI_Y0 manual
```

## Rentang HSV

| Warna | H | S | V |
|---|---|---|---|
| Hijau | 25–95 | 30–255 | 40–255 |
| Kuning/Oranye | 12–35 | 60–255 | 60–255 |
| Merah | 0–10 & 170–180 | 70–255 | 50–255 |

## Dependensi

- `opencv-python-headless`
- `numpy`
- `matplotlib`
- `requests`
