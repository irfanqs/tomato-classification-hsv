import cv2
import numpy as np
import requests
import matplotlib.pyplot as plt

# ==== CONFIG ====
IMAGE_PATH = None       # e.g. "tomato.jpg"
IMAGE_URL  = None       # e.g. "https://example.com/tomato.jpg"

# ==== ROI ====
ROI_SIZE = 700
USE_CENTER_ROI = False
ROI_X0, ROI_Y0 = 162, 418

# ==== HSV ranges ====
GREEN_LO  = np.array([25,  30,  40]);  GREEN_HI  = np.array([95,  255, 255])
YELLOW_LO = np.array([12,  60,  60]);  YELLOW_HI = np.array([35,  255, 255])
RED1_LO   = np.array([0,   70,  50]);  RED1_HI   = np.array([10,  255, 255])
RED2_LO   = np.array([170, 70,  50]);  RED2_HI   = np.array([180, 255, 255])


def load_bgr(path=None, url=None):
    if (path is None) == (url is None):
        raise ValueError("Set salah satu: IMAGE_PATH atau IMAGE_URL")
    if path:
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Gagal baca: {path}")
        return img
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = np.frombuffer(r.content, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Gagal decode URL image")
    return img


def bgr2rgb(x):
    return cv2.cvtColor(x, cv2.COLOR_BGR2RGB)


def classify_roi(hsv_roi, s_min=35, v_min=40):
    s = hsv_roi[:, :, 1]
    v = hsv_roi[:, :, 2]
    valid = (s >= s_min) & (v >= v_min)
    valid_area = int(np.count_nonzero(valid))
    if valid_area < 500:
        return "NONE", 0.0, 0.0, 0.0, valid.astype(np.uint8) * 255

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

    return label, r_ratio, g_ratio, y_ratio, (valid.astype(np.uint8) * 255)


def main():
    bgr = load_bgr(IMAGE_PATH, IMAGE_URL)
    H, W = bgr.shape[:2]
    roi_size = min(ROI_SIZE, H, W)

    if USE_CENTER_ROI:
        x0 = (W - roi_size) // 2
        y0 = (H - roi_size) // 2
    else:
        x0, y0 = ROI_X0, ROI_Y0
        x0 = max(0, min(W - roi_size, x0))
        y0 = max(0, min(H - roi_size, y0))

    roi     = bgr[y0:y0+roi_size, x0:x0+roi_size].copy()
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    label, r, g, y, valid_mask = classify_roi(hsv_roi)

    print(f"Image size: {W} x {H}")
    print(f"ROI: x0={x0}, y0={y0}, size={roi_size}")
    print(f"Result: {label} | R={r:.3f} G={g:.3f} Y={y:.3f}")

    overlay = bgr.copy()
    cv2.rectangle(overlay, (x0, y0), (x0+roi_size, y0+roi_size), (0, 255, 0), 4)

    red_mask    = cv2.inRange(hsv_roi, RED1_LO, RED1_HI) | cv2.inRange(hsv_roi, RED2_LO, RED2_HI)
    green_mask  = cv2.inRange(hsv_roi, GREEN_LO,  GREEN_HI)
    yellow_mask = cv2.inRange(hsv_roi, YELLOW_LO, YELLOW_HI)

    plt.figure(figsize=(14, 8))
    plt.subplot(2, 3, 1); plt.title("Full + ROI");  plt.imshow(bgr2rgb(overlay)); plt.axis("off")
    plt.subplot(2, 3, 2); plt.title("ROI");         plt.imshow(bgr2rgb(roi));     plt.axis("off")
    plt.subplot(2, 3, 3); plt.title("Valid Mask");  plt.imshow(valid_mask,  cmap="gray"); plt.axis("off")
    plt.subplot(2, 3, 4); plt.title("Red Mask");    plt.imshow(red_mask,    cmap="gray"); plt.axis("off")
    plt.subplot(2, 3, 5); plt.title("Yellow Mask"); plt.imshow(yellow_mask, cmap="gray"); plt.axis("off")
    plt.subplot(2, 3, 6); plt.title("Green Mask");  plt.imshow(green_mask,  cmap="gray"); plt.axis("off")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
