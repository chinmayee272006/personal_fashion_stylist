import os
import cv2
import numpy as np
import mediapipe as mp
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(
    BASE_DIR,
    "models"
)
POSE_MODEL = os.path.join(
    MODELS_DIR,
    "pose_landmarker_full.task"
)
FACE_MODEL = os.path.join(
    MODELS_DIR,
    "blaze_face_full_range.tflite"
)
BODY_TYPES = [
    "Hourglass",
    "Pear",
    "Apple",
    "Rectangle",
    "Inverted Triangle"
]
SKIN_TONES = [
    "Fair",
    "Light",
    "Medium",
    "Olive",
    "Tan",
    "Deep"
]
def check_models():
    """
    Check whether the required MediaPipe model files exist.
    """

    missing = []

    if not os.path.isfile(POSE_MODEL):
        missing.append("pose_landmarker_full.task")

    if not os.path.isfile(FACE_MODEL):
        missing.append("blaze_face_full_range.tflite")

    return missing
def detect_body_type(img_rgb):
    """
    Detect body landmarks using MediaPipe Pose Landmarker
    and estimate body type from shoulder and hip widths.
    """

    try:
        if not os.path.isfile(POSE_MODEL):
            return (
                None,
                0.0,
                "Pose model file is missing."
            )
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=img_rgb
        )
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=POSE_MODEL
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # -------------------------------------------------
        # Run pose detection
        # -------------------------------------------------

        with mp.tasks.vision.PoseLandmarker.create_from_options(
            options
        ) as detector:

            result = detector.detect(mp_image)

        # -------------------------------------------------
        # Check detection
        # -------------------------------------------------

        if not result.pose_landmarks:

            return (
                None,
                0.0,
                "No body landmarks detected."
            )

        landmarks = result.pose_landmarks[0]

        # -------------------------------------------------
        # MediaPipe landmark indexes
        #
        # 11 = left shoulder
        # 12 = right shoulder
        # 23 = left hip
        # 24 = right hip
        # -------------------------------------------------

        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_HIP = 23
        RIGHT_HIP = 24

        left_shoulder = landmarks[LEFT_SHOULDER]
        right_shoulder = landmarks[RIGHT_SHOULDER]

        left_hip = landmarks[LEFT_HIP]
        right_hip = landmarks[RIGHT_HIP]

        # -------------------------------------------------
        # Calculate shoulder width
        # -------------------------------------------------

        shoulder_width = abs(
            left_shoulder.x -
            right_shoulder.x
        )

        # -------------------------------------------------
        # Calculate hip width
        # -------------------------------------------------

        hip_width = abs(
            left_hip.x -
            right_hip.x
        )

        if shoulder_width <= 0 or hip_width <= 0:

            return (
                None,
                0.0,
                "Could not calculate body measurements."
            )

        # -------------------------------------------------
        # Shoulder / hip ratio
        # -------------------------------------------------

        shoulder_hip_ratio = (
            shoulder_width /
            hip_width
        )

        # -------------------------------------------------
        # Calculate confidence
        # -------------------------------------------------

        visibility_values = []

        for landmark in [
            left_shoulder,
            right_shoulder,
            left_hip,
            right_hip
        ]:

            visibility = getattr(
                landmark,
                "visibility",
                None
            )

            if visibility is not None:

                visibility_values.append(
                    float(visibility)
                )

        if visibility_values:

            confidence = min(
                visibility_values
            )

        else:

            confidence = 0.5

        confidence = round(
            max(
                0.0,
                min(1.0, confidence)
            ),
            2
        )

        # =================================================
        # BODY TYPE CLASSIFICATION
        # =================================================

        # Wider shoulders than hips
        if shoulder_hip_ratio > 1.20:

            body_type = "Inverted Triangle"

        # Wider hips than shoulders
        elif shoulder_hip_ratio < 0.85:

            body_type = "Pear"

        else:

            # -------------------------------------------------
            # Estimate waist width
            # -------------------------------------------------

            left_midpoint = (
                left_shoulder.x +
                left_hip.x
            ) / 2

            right_midpoint = (
                right_shoulder.x +
                right_hip.x
            ) / 2

            waist_width = abs(
                left_midpoint -
                right_midpoint
            )

            waist_ratio = (
                waist_width /
                max(
                    shoulder_width,
                    hip_width
                )
            )

            # Narrow waist compared with shoulders/hips
            if waist_ratio < 0.78:

                body_type = "Hourglass"

            # Slightly wider shoulders
            elif shoulder_hip_ratio > 1.05:

                body_type = "Apple"

            else:

                body_type = "Rectangle"

        return (
            body_type,
            confidence,
            None
        )

    except Exception as exc:

        return (
            None,
            0.0,
            f"Body detection error: {exc}"
        )


# =========================================================
# FACE + SKIN TONE DETECTION
# =========================================================

def detect_skin_tone(img_bgr):
    """
    Detect a face using MediaPipe Face Detector
    and estimate skin tone from a central face region.
    """

    try:

        # -------------------------------------------------
        # Check face model
        # -------------------------------------------------

        if not os.path.isfile(FACE_MODEL):

            return (
                None,
                "Face model file is missing."
            )

        # -------------------------------------------------
        # Convert BGR -> RGB
        # -------------------------------------------------

        img_rgb = cv2.cvtColor(
            img_bgr,
            cv2.COLOR_BGR2RGB
        )

        # -------------------------------------------------
        # Create MediaPipe image
        # -------------------------------------------------

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=img_rgb
        )

        # -------------------------------------------------
        # Face detector options
        # -------------------------------------------------

        options = mp.tasks.vision.FaceDetectorOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=FACE_MODEL
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            min_detection_confidence=0.3
        )

        # -------------------------------------------------
        # Run face detection
        # -------------------------------------------------

        with mp.tasks.vision.FaceDetector.create_from_options(
            options
        ) as detector:

            result = detector.detect(mp_image)

        # -------------------------------------------------
        # Check if face was found
        # -------------------------------------------------

        if not result.detections:

            return (
                None,
                "No face detected. Please upload a clear photo where your face is visible."
            )

        # -------------------------------------------------
        # Get first detected face
        # -------------------------------------------------

        detection = result.detections[0]

        bbox = detection.bounding_box

        # -------------------------------------------------
        # Bounding box
        # -------------------------------------------------

        x = max(
            0,
            int(bbox.origin_x)
        )

        y = max(
            0,
            int(bbox.origin_y)
        )

        width = int(
            bbox.width
        )

        height = int(
            bbox.height
        )

        image_height, image_width = img_bgr.shape[:2]

        width = min(
            width,
            image_width - x
        )

        height = min(
            height,
            image_height - y
        )

        if width <= 10 or height <= 10:

            return (
                None,
                "Detected face is too small."
            )

        # =================================================
        # SELECT FACE SKIN REGION
        # =================================================

        # Upper-middle face region.
        #
        # We avoid the extreme edges of the face because
        # they may contain background or hair.

        sample_x = x + int(
            width * 0.30
        )

        sample_y = y + int(
            height * 0.15
        )

        sample_width = max(
            1,
            int(width * 0.40)
        )

        sample_height = max(
            1,
            int(height * 0.25)
        )

        # Keep coordinates inside image

        sample_x = min(
            sample_x,
            image_width - 1
        )

        sample_y = min(
            sample_y,
            image_height - 1
        )

        sample_width = min(
            sample_width,
            image_width - sample_x
        )

        sample_height = min(
            sample_height,
            image_height - sample_y
        )

        if (
            sample_width <= 0
            or
            sample_height <= 0
        ):

            return (
                None,
                "Could not create face skin sample."
            )

        # -------------------------------------------------
        # Extract sample
        # -------------------------------------------------

        sample = img_bgr[
            sample_y:
            sample_y + sample_height,

            sample_x:
            sample_x + sample_width
        ]

        if sample.size == 0:

            return (
                None,
                "Skin sample is empty."
            )

        # =================================================
        # HSV ANALYSIS
        # =================================================

        hsv = cv2.cvtColor(
            sample,
            cv2.COLOR_BGR2HSV
        )

        average_brightness = float(
            np.mean(
                hsv[:, :, 2]
            )
        )

        # =================================================
        # SKIN TONE CLASSIFICATION
        # =================================================

        if average_brightness > 185:

            skin_tone = "Fair"

        elif average_brightness > 155:

            skin_tone = "Light"

        elif average_brightness > 125:

            skin_tone = "Medium"

        elif average_brightness > 95:

            skin_tone = "Olive"

        elif average_brightness > 65:

            skin_tone = "Tan"

        else:

            skin_tone = "Deep"

        return (
            skin_tone,
            None
        )

    except Exception as exc:

        return (
            None,
            f"Face/skin detection error: {exc}"
        )


# =========================================================
# MAIN FUNCTION
# =========================================================

def analyze_photo(image_path: str) -> dict:
    """
    Analyze an uploaded photograph.

    Returns:

    {
        "body_type": ...,
        "skin_tone": ...,
        "confidence": ...,
        "error": ...
    }
    """

    result = {
        "body_type": None,
        "skin_tone": None,
        "confidence": 0.0,
        "error": None
    }

    # =====================================================
    # CHECK MODEL FILES
    # =====================================================

    missing_models = check_models()

    if missing_models:

        result["error"] = (
            "Missing MediaPipe model files: "
            + ", ".join(missing_models)
        )

        return result

    # =====================================================
    # READ IMAGE
    # =====================================================

    try:

        img = cv2.imread(
            image_path
        )

        if img is None:

            result["error"] = (
                "Could not read the image. "
                "Please upload a valid JPG or PNG image."
            )

            return result

    except Exception as exc:

        result["error"] = (
            f"Error reading image: {exc}"
        )

        return result

    # =====================================================
    # CONVERT TO RGB
    # =====================================================

    img_rgb = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2RGB
    )

    # =====================================================
    # BODY TYPE
    # =====================================================

    body_type, confidence, body_error = (
        detect_body_type(img_rgb)
    )

    result["body_type"] = body_type

    result["confidence"] = confidence

    # =====================================================
    # SKIN TONE
    # =====================================================

    skin_tone, skin_error = (
        detect_skin_tone(img)
    )

    result["skin_tone"] = skin_tone

    # =====================================================
    # COLLECT ERRORS
    # =====================================================

    errors = []

    if body_error:

        errors.append(
            body_error
        )

    if skin_error:

        errors.append(
            skin_error
        )

    if errors:

        result["error"] = " | ".join(
            errors
        )

    # =====================================================
    # NOTHING DETECTED
    # =====================================================

    if (
        result["body_type"] is None
        and
        result["skin_tone"] is None
    ):

        if not result["error"]:

            result["error"] = (
                "Could not detect the person. "
                "Please upload a clear front-facing "
                "full-body photograph."
            )

    return result