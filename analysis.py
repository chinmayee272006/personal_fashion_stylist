"""
Computer-vision helpers — OpenCV + MediaPipe.
Analyses an uploaded photo to estimate body type and skin tone.
Falls back gracefully when detection fails (never raises).
"""

import cv2
import numpy as np

try:
    import mediapipe as mp

    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False


BODY_TYPES = ["Hourglass", "Pear", "Apple", "Rectangle", "Inverted Triangle"]
SKIN_TONES = ["Fair", "Light", "Medium", "Olive", "Tan", "Deep"]


def analyze_photo(image_path: str) -> dict:
    """Analyse an uploaded photo for body type and skin tone.

    Returns
    -------
    dict with keys
        body_type  : str | None
        skin_tone  : str | None
        confidence : float  (0-1, rough landmark confidence)
        error      : str | None  (human-readable message when detection fails)
    """
    result = {
        "body_type": None,
        "skin_tone": None,
        "confidence": 0.0,
        "error": None,
    }

    # ── Read image ──────────────────────────────────────────────
    try:
        img = cv2.imread(image_path)
        if img is None:
            result["error"] = (
                "Could not read the image. Please upload a valid JPEG or PNG file."
            )
            return result
    except Exception as exc:
        result["error"] = f"Error reading image: {exc}"
        return result

    if not _MP_AVAILABLE:
        result["error"] = (
            "MediaPipe is not installed — automatic detection is unavailable. "
            "Please select your values manually below."
        )
        return result

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = img.shape

    # ── Body-type estimation (MediaPipe Pose) ──────────────────
    try:
        mp_pose = mp.solutions.pose
        with mp_pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.5,
        ) as pose:
            res = pose.process(img_rgb)
            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark
                ls = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
                rs = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                lh = lm[mp_pose.PoseLandmark.LEFT_HIP]
                rh = lm[mp_pose.PoseLandmark.RIGHT_HIP]

                sw = abs(ls.x - rs.x)  # shoulder width (normalised)
                hw = abs(lh.x - rh.x)  # hip width

                if sw > 0 and hw > 0:
                    ratio = sw / hw
                    result["confidence"] = round(
                        min(ls.visibility, rs.visibility, lh.visibility, rh.visibility),
                        2,
                    )

                    if ratio > 1.20:
                        result["body_type"] = "Inverted Triangle"
                    elif ratio < 0.85:
                        result["body_type"] = "Pear"
                    else:
                        # Estimate waist width from midpoint of shoulder/hip
                        ww = abs(
                            (ls.x + lh.x) / 2 - (rs.x + rh.x) / 2
                        )
                        wr = ww / max(sw, hw)
                        if wr < 0.78:
                            result["body_type"] = "Hourglass"
                        elif ratio > 1.05:
                            result["body_type"] = "Apple"
                        else:
                            result["body_type"] = "Rectangle"
    except Exception:
        pass  # body-type detection failed — continue to skin tone

    # ── Skin-tone estimation (face-region HSV sampling) ────────
    try:
        mp_face = mp.solutions.face_detection
        with mp_face.FaceDetection(min_detection_confidence=0.5) as fd:
            fres = fd.process(img_rgb)
            if fres.detections:
                bb = fres.detections[0].location_data.relative_bounding_box
                fx = max(0, int(bb.xmin * w))
                fy = max(0, int(bb.ymin * h))
                fw = min(int(bb.width * w), w - fx)
                fh = min(int(bb.height * h), h - fy)

                if fw > 10 and fh > 10:
                    # Sample forehead region (less likely to be shadowed)
                    sy = fy + int(fh * 0.12)
                    sh = max(1, int(fh * 0.22))
                    sx = fx + int(fw * 0.30)
                    sw2 = max(1, int(fw * 0.40))
                    sy, sx = min(sy, h - 1), min(sx, w - 1)
                    sh = min(sh, h - sy)
                    sw2 = min(sw2, w - sx)

                    if sh > 0 and sw2 > 0:
                        sample = img[sy : sy + sh, sx : sx + sw2]
                        hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
                        avg_v = float(np.mean(hsv[:, :, 2]))

                        for threshold, tone in [
                            (185, "Fair"),
                            (155, "Light"),
                            (125, "Medium"),
                            (95, "Olive"),
                            (65, "Tan"),
                        ]:
                            if avg_v > threshold:
                                result["skin_tone"] = tone
                                break
                        else:
                            result["skin_tone"] = "Deep"
    except Exception:
        pass  # skin-tone detection failed

    # ── Final fallback message ─────────────────────────────────
    if result["body_type"] is None and result["skin_tone"] is None:
        result["error"] = (
            "Could not detect body landmarks or face in this image. "
            "Please try a clearer full-body photo, or select your values manually below."
        )

    return result
