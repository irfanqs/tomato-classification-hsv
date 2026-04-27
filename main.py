import cv2
import numpy as np

# ==== CONFIG ====
CAMERA_INDEX   = 0      # ganti ke 1, 2, dst. jika kamera eksternal
ROI_SIZE       = 300    # ukuran kotak ROI (pixel)
USE_CENTER_ROI = True   # True = ROI di tengah frame

# ==== HSV ranges ====
GREEN_LO  = np.array([25,  30,  40]);  GREEN_HI  = np.array([95,  255, 255])
YELLOW_LO = np.array([12,  60,  60]);  YELLOW_HI = np.array([35,  255, 255])
RED1_LO   = np.array([0,   70,  50]);  RED1_HI   = np.array([10,  255, 255])
RED2_LO   = np.array([170, 70,  50]);  RED2_HI   = np.array([180, 255, 255])

# warna kotak & teks per label
LABEL_COLOR = {
    "RIPE (MERAH)"           : (0,   0,   255),
    "SEMI-RIPE (KUNING/ORANYE)": (0, 200, 255),
    "UNRIPE (HIJAU)"         : (0,   200,  0),
    "NONE"                   : (180, 180, 180),
}


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


def draw_ui(frame, x0, y0, roi_size, label, r, g, y):
    color = LABEL_COLOR.get(label, (255, 255, 255))

    # kotak ROI
    cv2.rectangle(frame, (x0, y0), (x0 + roi_size, y0 + roi_size), color, 3)

    # label di atas kotak
    text = f"{label}"
    (tw, th), bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
    cv2.rectangle(frame, (x0, y0 - th - bl - 8), (x0 + tw + 8, y0), color, -1)
    cv2.putText(frame, text, (x0 + 4, y0 - bl - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)

    # rasio di bawah kotak
    stats = f"R:{r:.2f}  G:{g:.2f}  Y:{y:.2f}"
    cv2.putText(frame, stats, (x0, y0 + roi_size + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)

    # panduan
    cv2.putText(frame, "Tekan 'q' untuk keluar",
                (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Tidak dapat membuka kamera index={CAMERA_INDEX}")

    print("Kamera aktif. Tekan 'q' untuk keluar.")

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

        result = classify_roi(hsv_roi)
        label, r, g, y = result if len(result) == 4 else ("NONE", 0.0, 0.0, 0.0)

        draw_ui(frame, x0, y0, roi_size, label, r, g, y)

        cv2.imshow("Tomato Classifier - Realtime", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
