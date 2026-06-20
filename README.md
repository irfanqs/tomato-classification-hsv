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

## Raspberry Pi — Koneksi Hardware

### Ringkasan Komponen

| Komponen | Jumlah |
|---|---|
| Servo MG90S | 2 buah |
| LCD I2C 16×2 (PCF8574) | 1 buah |
| Kamera USB / Pi Camera | 1 buah |

---

### Servo Motor (MG90S)

Servo menggunakan **BCM numbering** sesuai konstanta di `main_raspi.py`:

| Fungsi | GPIO (BCM) | Pin Fisik | Kabel Servo |
|---|---|---|---|
| Servo Kanan — RIPE (MERAH) | **GPIO 17** | Pin **11** | Sinyal (oranye/kuning) |
| Servo Kiri — SEMI-RIPE (KUNING) | **GPIO 27** | Pin **13** | Sinyal (oranye/kuning) |
| VCC kedua servo | — | Pin **2** atau **4** (5 V) | Merah |
| GND kedua servo | — | Pin **6** (GND) | Cokelat/hitam |

> **Catatan:** Jika menggerakkan 2 servo sekaligus, gunakan **catu daya 5 V eksternal** (min. 1 A) untuk VCC servo. GND eksternal tetap harus dihubungkan ke GND Raspberry Pi agar referensi tegangan sama.

```
Raspberry Pi          Servo MG90S
 Pin 11 (GPIO17) ───► Sinyal  (servo KANAN)
 Pin 13 (GPIO27) ───► Sinyal  (servo KIRI)
 Pin 2  (5V)     ───► VCC    (kedua servo)
 Pin 6  (GND)    ───► GND    (kedua servo)
```

---

### LCD I2C 16×2 (PCF8574)

LCD terhubung via bus I2C-1 Raspberry Pi:

| Pin LCD | GPIO (BCM) | Pin Fisik | Keterangan |
|---|---|---|---|
| SDA | **GPIO 2** | Pin **3** | Data I2C |
| SCL | **GPIO 3** | Pin **5** | Clock I2C |
| VCC | — | Pin **2** atau **4** (5 V) | Tegangan LCD |
| GND | — | Pin **6** (GND) | Ground |

```
Raspberry Pi          LCD I2C (PCF8574)
 Pin 3  (SDA/GPIO2) ── SDA
 Pin 5  (SCL/GPIO3) ── SCL
 Pin 2  (5V)        ── VCC
 Pin 6  (GND)       ── GND
```

Cek alamat I2C setelah memasang:
```bash
sudo i2cdetect -y 1
```
Alamat default PCF8574 adalah `0x27`. Jika berbeda, ubah konstanta `LCD_I2C_ADDR` di `main_raspi.py`.

---

### Kamera

| Jenis Kamera | Sambungan |
|---|---|
| **USB Camera** | Port USB mana saja, set `CAMERA_INDEX = 0` |
| **Pi Camera Module** | Port CSI (ribbon cable), aktifkan dengan `sudo raspi-config` → Interface → Camera |

---

### Diagram Pinout Lengkap (Raspberry Pi 40-pin)

```
         3V3 [ 1] [ 2] 5V  ◄── VCC LCD & Servo
 SDA/GPIO2  [ 3] [ 4] 5V
 SCL/GPIO3  [ 5] [ 6] GND ◄── GND LCD & Servo
            [ 7] [ 8]
        GND [ 9] [10]
 GPIO17     [11] [12]      ◄── Pin 11: Sinyal Servo Kanan (RIPE)
 GPIO27     [13] [14] GND
            [15] [16]
        3V3 [17] [18]
            [19] [20] GND
            [21] [22]
            [23] [24]
        GND [25] [26]
            ...
```

---

### Jalankan di Raspberry Pi

```bash
pip install -r requirements_raspi.txt
python main_raspi.py
```

---

## Dependensi

- `opencv-python-headless`
- `numpy`
- `matplotlib`
- `requests`
