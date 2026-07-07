import cv2
import numpy as np
import time
import threading

try:
    import RPi.GPIO as GPIO
    from RPLCD.i2c import CharLCD
    IS_RASPI = True
except ImportError:
    IS_RASPI = False
    print("[SIMULASI] RPi.GPIO / RPLCD tidak ditemukan — servo & LCD dinonaktifkan")

# ===================== CONFIG =====================
CAMERA_INDEX   = 0   # Logitech C270 ada di /dev/video0 (konfirmasi via v4l2-ctl)
ROI_SIZE       = 300
USE_CENTER_ROI = True

# GPIO pin servo (BCM numbering)
PIN_SERVO_RIGHT = 17    # servo kanan → RIPE (MERAH)
PIN_SERVO_LEFT  = 27    # servo kiri  → SEMI-RIPE (KUNING)

# Duty cycle MG90S pada 50 Hz
# MG90S: ~2.5% = 0°  |  ~7.5% = 90°  |  ~12.5% = 180°
DC_NEUTRAL = 7.5        # posisi netral (lurus, tidak memilah)
DC_DEFLECT = 12.0       # posisi memilah (coba 2.5 jika arah terbalik)

# I2C LCD 16x2
LCD_I2C_ADDR = 0x27     # cek dengan: sudo i2cdetect -y 1
LCD_I2C_PORT = 1        # /dev/i2c-1

# Logika deteksi
CONFIRM_FRAMES = 5      # jumlah frame konsisten sebelum servo dipicu
DEFLECT_SEC    = 0.8    # lama servo deflect sebelum kembali netral (detik)
COOLDOWN_SEC   = 1.5    # jeda minimum antar aksi (detik)

# ===================== HSV RANGES =====================
GREEN_LO  = np.array([25,  30,  40]);  GREEN_HI  = np.array([95,  255, 255])
YELLOW_LO = np.array([12,  60,  60]);  YELLOW_HI = np.array([35,  255, 255])
RED1_LO   = np.array([0,   70,  50]);  RED1_HI   = np.array([10,  255, 255])
RED2_LO   = np.array([170, 70,  50]);  RED2_HI   = np.array([180, 255, 255])

LABEL_COLOR = {
    "RIPE (MERAH)"              : (0,   0,   255),
    "SEMI-RIPE (KUNING/ORANYE)" : (0,   200, 255),
    "UNRIPE (HIJAU)"            : (0,   200,   0),
    "NONE"                      : (180, 180, 180),
}

# ===================== HARDWARE =====================
lcd   = None
pwm_r = None
pwm_l = None

def find_camera_index(max_index=5):
    """Cari index kamera yang valid (bisa buka dan baca frame)."""
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        # Webcam USB butuh warmup — buang beberapa frame awal
        time.sleep(0.5)
        for _ in range(5):
            cap.read()
        ret, _ = cap.read()
        cap.release()
        if ret:
            return idx
    return -1


def check_pinouts():
    """Melakukan pengecekan koneksi pinout dan komponen sebelum program utama berjalan."""
    print("\n" + "="*50)
    print("        DIAGNOSTIC & PINOUT SYSTEM CHECK")
    print("="*50)
    
    all_ok = True
    errors = []
    
    # 1. Platform Check
    if IS_RASPI:
        print("[+] OS / Raspberry Pi Platform  : OK (Raspberry Pi)")
    else:
        print("[!] OS / Raspberry Pi Platform  : SIMULATION MODE (Bukan Raspberry Pi)")
    
    # 2. Camera Check
    global CAMERA_INDEX
    if CAMERA_INDEX == -1:
        print("    Mencari kamera (auto-detect)...")
        CAMERA_INDEX = find_camera_index()

    if CAMERA_INDEX >= 0:
        print(f"[+] Kamera (Index {CAMERA_INDEX})            : OK (Terdeteksi)")
    else:
        print(f"[X] Kamera                       : ERROR (TIDAK TERDETEKSI!)")
        errors.append("Kamera tidak terdeteksi di index manapun (0-4). Hubungkan Kamera USB/Pi Camera.")
        all_ok = False
        
    # 3. I2C LCD Check
    lcd_ok = False
    if IS_RASPI:
        try:
            import smbus2
            # Coba write_quick ke alamat LCD untuk melihat respon ACK/NACK
            with smbus2.SMBus(LCD_I2C_PORT) as bus:
                bus.write_quick(LCD_I2C_ADDR)
            print(f"[+] I2C LCD (Alamat 0x{LCD_I2C_ADDR:02X})       : OK (Terdeteksi)")
            lcd_ok = True
        except ImportError:
            # Fallback jika smbus2 tidak terpasang, coba inisialisasi RPLCD langsung
            try:
                test_lcd = CharLCD(i2c_expander="PCF8574", address=LCD_I2C_ADDR,
                                   port=LCD_I2C_PORT, cols=16, rows=2, dotsize=8)
                test_lcd.close()
                print(f"[+] I2C LCD (Alamat 0x{LCD_I2C_ADDR:02X})       : OK (Terdeteksi via RPLCD)")
                lcd_ok = True
            except Exception as e:
                print(f"[X] I2C LCD (Alamat 0x{LCD_I2C_ADDR:02X})       : ERROR (Gagal init: {e})")
                errors.append(f"LCD I2C pada alamat 0x{LCD_I2C_ADDR:02X} gagal diinisialisasi.")
                all_ok = False
        except Exception as e:
            print(f"[X] I2C LCD (Alamat 0x{LCD_I2C_ADDR:02X})       : ERROR (TIDAK TERESPON: {e})")
            errors.append(f"LCD I2C pada alamat 0x{LCD_I2C_ADDR:02X} tidak terdeteksi.")
            all_ok = False
    else:
        print(f"[+] I2C LCD (Alamat 0x{LCD_I2C_ADDR:02X})       : SIMULASI (Terdeteksi)")
        lcd_ok = True

    # 4. GPIO Servo Setup Check
    servo_setup_ok = False
    if IS_RASPI:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(PIN_SERVO_RIGHT, GPIO.OUT)
            GPIO.setup(PIN_SERVO_LEFT,  GPIO.OUT)
            print(f"[+] GPIO / Pin Servo Kanan ({PIN_SERVO_RIGHT}): OK (Setup Berhasil)")
            print(f"[+] GPIO / Pin Servo Kiri ({PIN_SERVO_LEFT}) : OK (Setup Berhasil)")
            servo_setup_ok = True
        except Exception as e:
            print(f"[X] GPIO / Pin Servo Setup     : ERROR ({e})")
            errors.append("Gagal inisialisasi GPIO. Coba jalankan dengan hak akses root/sudo.")
            all_ok = False
    else:
        print(f"[+] GPIO / Pin Servo Kanan ({PIN_SERVO_RIGHT}): SIMULASI (Setup Berhasil)")
        print(f"[+] GPIO / Pin Servo Kiri ({PIN_SERVO_LEFT}) : SIMULASI (Setup Berhasil)")
        servo_setup_ok = True

    print("="*50)
    
    # Uji Gerak Servo jika setup berhasil
    if all_ok:
        if IS_RASPI and servo_setup_ok:
            print("Melakukan uji gerak servo (Servo Sweep Test)...")
            try:
                pwm_r_test = GPIO.PWM(PIN_SERVO_RIGHT, 50)
                pwm_l_test = GPIO.PWM(PIN_SERVO_LEFT,  50)
                
                pwm_r_test.start(DC_NEUTRAL)
                pwm_l_test.start(DC_NEUTRAL)
                time.sleep(0.3)
                
                print("-> Menguji Servo Kanan (RIPE/MERAH)...")
                pwm_r_test.ChangeDutyCycle(DC_DEFLECT)
                time.sleep(0.6)
                pwm_r_test.ChangeDutyCycle(DC_NEUTRAL)
                time.sleep(1.0)
                pwm_r_test.ChangeDutyCycle(0)

                print("-> Menguji Servo Kiri (SEMI-RIPE/KUNING)...")
                pwm_l_test.ChangeDutyCycle(DC_DEFLECT)
                time.sleep(0.6)
                pwm_l_test.ChangeDutyCycle(DC_NEUTRAL)
                time.sleep(1.0)
                pwm_l_test.ChangeDutyCycle(0)
                
                pwm_r_test.stop()
                pwm_l_test.stop()
                GPIO.cleanup() # Bersihkan agar init_hardware memulai dari awal
                print("Sweep test selesai.")
            except Exception as e:
                print(f"[X] Gagal melakukan uji servo: {e}")
                errors.append(f"Gagal uji servo: {e}")
                all_ok = False
        else:
            print("[SIMULASI] Uji gerak servo selesai.")
            
    # Tampilkan error jika ada
    if not all_ok:
        print("\n" + "!"*50)
        print("          PENGECEKAN PINOUT / HARDWARE GAGAL!")
        print("!"*50)
        for i, err in enumerate(errors, 1):
            print(f"{i}. {err}")
        print("-"*50)
        print("Saran perbaikan:")
        print("- Cek kembali kabel jumper SDA, SCL, VCC, GND pada LCD I2C.")
        print("- Cek kembali pin sinyal, 5V, dan GND untuk kedua servo.")
        print("- Pastikan kamera sudah dicolokkan ke port USB / CSI.")
        print("-"*50)
        print("[!] Program dihentikan karena komponen tidak lengkap.")
        print("="*50 + "\n")
        import sys
        sys.exit(1)
                
    # Sukses, tampilkan di LCD jika tercolok
    if all_ok and IS_RASPI and lcd_ok:
        try:
            # Tulis status ke LCD asli
            test_lcd = CharLCD(i2c_expander="PCF8574", address=LCD_I2C_ADDR,
                               port=LCD_I2C_PORT, cols=16, rows=2, dotsize=8)
            test_lcd.clear()
            test_lcd.write_string("Pinout: OK")
            test_lcd.cursor_pos = (1, 0)
            test_lcd.write_string("System Ready!")
            time.sleep(1.5)
            test_lcd.close()
        except Exception:
            pass

    print("\n" + "="*50)
    print("SEMUA KOMPONEN OK! Menjalankan program utama...")
    print("="*50 + "\n")
    return True


def init_hardware():
    global lcd, pwm_r, pwm_l
    if not IS_RASPI:
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_SERVO_RIGHT, GPIO.OUT)
    GPIO.setup(PIN_SERVO_LEFT,  GPIO.OUT)

    pwm_r = GPIO.PWM(PIN_SERVO_RIGHT, 50)
    pwm_l = GPIO.PWM(PIN_SERVO_LEFT,  50)
    pwm_r.start(DC_NEUTRAL)
    pwm_l.start(DC_NEUTRAL)
    time.sleep(0.5)
    # Stop sinyal setelah servo ke posisi netral — cegah jitter software PWM
    pwm_r.ChangeDutyCycle(0)
    pwm_l.ChangeDutyCycle(0)

    try:
        lcd = CharLCD(i2c_expander="PCF8574", address=LCD_I2C_ADDR,
                      port=LCD_I2C_PORT, cols=16, rows=2, dotsize=8)
        _lcd_write("Tomato Sorter", "Siap...")
    except Exception as e:
        print(f"[LCD] Gagal init: {e}")
        lcd = None


def cleanup_hardware():
    if not IS_RASPI:
        return
    if pwm_r:
        pwm_r.stop()
    if pwm_l:
        pwm_l.stop()
    GPIO.cleanup()


def _lcd_write(line1, line2=""):
    """Tulis dua baris ke LCD. Aman dipanggil dari thread manapun."""
    if lcd is None:
        print(f"[LCD] {line1:<16} | {line2:<16}")
        return
    try:
        lcd.clear()
        lcd.write_string(line1[:16])
        lcd.cursor_pos = (1, 0)
        lcd.write_string(line2[:16])
    except Exception as e:
        print(f"[LCD] Error tulis: {e}")


def _servo_deflect(pwm, label_text):
    """Putar servo ke posisi deflect, tahan, lalu kembali netral."""
    if pwm is None:
        print(f"[SERVO] deflect {DEFLECT_SEC}s untuk '{label_text}' (simulasi)")
        time.sleep(DEFLECT_SEC)
        return
    pwm.ChangeDutyCycle(DC_DEFLECT)
    time.sleep(DEFLECT_SEC)
    pwm.ChangeDutyCycle(DC_NEUTRAL)
    time.sleep(1.0)  # beri waktu servo bergerak balik ke netral sebelum sinyal dimatikan
    pwm.ChangeDutyCycle(0)

# ===================== KLASIFIKASI =====================

def classify_roi(hsv_roi, s_min=35, v_min=40):
    s = hsv_roi[:, :, 1]
    v = hsv_roi[:, :, 2]
    valid = (s >= s_min) & (v >= v_min)
    valid_area = int(np.count_nonzero(valid))
    if valid_area < 500:
        return "NONE", 0.0, 0.0, 0.0

    red    = (cv2.inRange(hsv_roi, RED1_LO, RED1_HI) | cv2.inRange(hsv_roi, RED2_LO, RED2_HI)).astype(bool)
    green  = cv2.inRange(hsv_roi, GREEN_LO,  GREEN_HI).astype(bool)
    yellow = cv2.inRange(hsv_roi, YELLOW_LO, YELLOW_HI).astype(bool)

    r_ratio = np.count_nonzero(red    & valid) / valid_area
    g_ratio = np.count_nonzero(green  & valid) / valid_area
    y_ratio = np.count_nonzero(yellow & valid) / valid_area

    if g_ratio >= 0.28:
        label = "UNRIPE (HIJAU)"
    elif y_ratio >= 0.14:
        label = "SEMI-RIPE (KUNING/ORANYE)"
    else:
        label = "RIPE (MERAH)"

    return label, r_ratio, g_ratio, y_ratio

# ===================== UI =====================

def draw_ui(frame, x0, y0, roi_size, label, r, g, y, status):
    color = LABEL_COLOR.get(label, (255, 255, 255))

    cv2.rectangle(frame, (x0, y0), (x0+roi_size, y0+roi_size), color, 3)

    (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.rectangle(frame, (x0, y0-th-bl-8), (x0+tw+8, y0), color, -1)
    cv2.putText(frame, label, (x0+4, y0-bl-4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)

    cv2.putText(frame, f"R:{r:.2f}  G:{g:.2f}  Y:{y:.2f}",
                (x0, y0+roi_size+24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    cv2.putText(frame, status, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)

    cv2.putText(frame, "Tekan 'q' untuk keluar",
                (10, frame.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

# ===================== MAIN =====================

def main():
    check_pinouts()
    init_hardware()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        cleanup_hardware()
        raise RuntimeError(f"Kamera index={CAMERA_INDEX} tidak bisa dibuka")

    # Warmup webcam USB — buang frame awal yang kosong/corrupt
    time.sleep(0.5)
    for _ in range(10):
        cap.read()

    print("Kamera aktif. Tekan 'q' untuk keluar.")

    label_history   = []
    last_action_t   = 0.0
    status_text     = "Menunggu tomat..."
    servo_busy      = False

    def on_servo_done():
        nonlocal servo_busy
        servo_busy = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Gagal membaca frame.")
            break

        H, W = frame.shape[:2]
        roi_size = min(ROI_SIZE, H, W)

        if USE_CENTER_ROI:
            x0 = (W - roi_size) // 2
            y0 = (H - roi_size) // 2
        else:
            x0 = max(0, min(W - roi_size, 162))
            y0 = max(0, min(H - roi_size, 418))

        roi     = frame[y0:y0+roi_size, x0:x0+roi_size]
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        label, r, g, y = classify_roi(hsv_roi)

        # Akumulasi history untuk konfirmasi
        label_history.append(label)
        if len(label_history) > CONFIRM_FRAMES:
            label_history.pop(0)

        confirmed = (
            len(label_history) == CONFIRM_FRAMES
            and all(lbl == label for lbl in label_history)
            and label != "NONE"
        )

        now = time.time()
        if confirmed and not servo_busy and (now - last_action_t) > COOLDOWN_SEC:
            last_action_t = now
            servo_busy    = True
            label_history.clear()

            if label == "RIPE (MERAH)":
                status_text = ">> MERAH  ->  Kanan"
                _lcd_write("RIPE  (MERAH)", "Pilah -> KANAN")
                def _task_r():
                    _servo_deflect(pwm_r, label)
                    on_servo_done()
                threading.Thread(target=_task_r, daemon=True).start()

            elif label == "SEMI-RIPE (KUNING/ORANYE)":
                status_text = "<< KUNING  ->  Kiri"
                _lcd_write("SEMI-RIPE", "Pilah <- KIRI")
                def _task_l():
                    _servo_deflect(pwm_l, label)
                    on_servo_done()
                threading.Thread(target=_task_l, daemon=True).start()

            else:  # UNRIPE (HIJAU) — lewat lurus
                status_text = "-- HIJAU  ->  Lurus"
                _lcd_write("UNRIPE (HIJAU)", "Lurus / Lewat")
                servo_busy = False   # tidak ada aksi servo

        draw_ui(frame, x0, y0, roi_size, label, r, g, y, status_text)
        cv2.imshow("Tomato Sorter", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    cleanup_hardware()


if __name__ == "__main__":
    main()
