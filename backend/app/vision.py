"""Webcam video analysis with OpenCV + MediaPipe Face Landmarker (Haar fallback = face visibility only)."""
import logging, math, urllib.request
from pathlib import Path
import numpy as np
import cv2
from .config import settings

log = logging.getLogger("vision")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_PATH = settings.model_dir / "face_landmarker.task"
SAMPLE_MS = 250  # ~4 analysed frames/second


def ensure_model() -> bool:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return True
    try:
        log.info("Downloading face landmarker model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        return True
    except Exception as e:
        log.warning("Could not download face landmarker model: %s", e)
        return False


def _landmarker():
    import mediapipe as mp
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision
    opts = vision.FaceLandmarkerOptions(
        base_options=mpp.BaseOptions(model_asset_path=str(MODEL_PATH)), running_mode=vision.RunningMode.IMAGE,
        num_faces=1, output_face_blendshapes=True, output_facial_transformation_matrixes=True,
        min_face_detection_confidence=0.5, min_face_presence_confidence=0.5)
    return mp, vision.FaceLandmarker.create_from_options(opts)


def _euler(m):
    R = np.array(m)[:3, :3]
    sy = math.hypot(R[0, 0], R[1, 0])
    pitch = math.degrees(math.atan2(R[2, 1], R[2, 2]))
    yaw = math.degrees(math.atan2(-R[2, 0], sy))
    roll = math.degrees(math.atan2(R[1, 0], R[0, 0]))
    if abs(pitch) > 90:
        pitch -= math.copysign(180, pitch)
    return yaw, pitch, roll


def _iris_ratio(lm):
    # horizontal iris position within each eye (0.5 = centred). Right eye: outer 33 / inner 133; left: inner 362 / outer 263
    def r(iris, a, b):
        xa, xb = lm[a].x, lm[b].x
        return (lm[iris].x - xa) / (xb - xa) if abs(xb - xa) > 1e-6 else 0.5
    return (r(468, 33, 133) + r(473, 362, 263)) / 2


def _frames(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return
    last, idx = -1e9, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        if ms <= 0:
            ms = idx * 33.3
        idx += 1
        if ms - last >= SAMPLE_MS:
            last = ms
            h, w = fr.shape[:2]
            if w > 640:
                fr = cv2.resize(fr, (640, int(h * 640 / w)))
            yield ms, fr
    cap.release()


def analyze_video(path) -> dict:
    use_lm = ensure_model()
    try:
        mp, lmk = _landmarker() if use_lm else (None, None)
    except Exception as e:
        log.warning("Landmarker init failed (%s); using Haar fallback", e)
        mp, lmk, use_lm = None, None, False
    haar = None if use_lm else cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    total = vis = 0
    yaws, pitches, ratios, smiles, areas, bright, facing, expr = [], [], [], [], [], [], 0, []
    try:
        for ms, fr in _frames(path):
            total += 1
            gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            bright.append(float(gray.mean()))
            if use_lm:
                res = lmk.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)))
                if not res.face_landmarks:
                    continue
                vis += 1
                lm = res.face_landmarks[0]
                ys = [p.y for p in lm]; xs = [p.x for p in lm]
                areas.append(max(ys) - min(ys))
                yaw, pitch, _ = _euler(res.facial_transformation_matrixes[0]) if res.facial_transformation_matrixes else (0, 0, 0)
                ratio = _iris_ratio(lm) if len(lm) > 473 else 0.5
                yaws.append(yaw); pitches.append(pitch); ratios.append(ratio)
                if abs(yaw) < 20 and abs(pitch) < 20 and 0.33 <= ratio <= 0.67:
                    facing += 1
                if res.face_blendshapes:
                    b = {c.category_name: c.score for c in res.face_blendshapes[0]}
                    smiles.append((b.get("mouthSmileLeft", 0) + b.get("mouthSmileRight", 0)) / 2)
                    expr.append(sum(b.get(k, 0) for k in ("browDownLeft", "browDownRight", "browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight")))
            else:
                faces = haar.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
                if len(faces):
                    vis += 1
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    areas.append(h / fr.shape[0])
    finally:
        if lmk is not None:
            lmk.close()

    if total < 5:
        return {"available": False, "reason": "Video could not be decoded or was too short to analyze.", "frames_analyzed": total}

    vis_pct = vis / total * 100
    mean_b = float(np.mean(bright))
    area = float(np.mean(areas)) if areas else 0
    out = {"available": True, "mode": "mediapipe_face_landmarker" if use_lm else "opencv_haar_fallback",
           "frames_analyzed": total, "sample_rate_fps": round(1000 / SAMPLE_MS, 1),
           "face_visible_pct": round(vis_pct, 1), "brightness": round(mean_b, 1), "face_height_ratio": round(area, 2)}
    out["lighting"] = "too_dark" if mean_b < 70 else "too_bright" if mean_b > 200 else "ok"
    out["distance"] = "too_far" if 0 < area < 0.3 else "too_close" if area > 0.85 else "ok"
    fb = []
    if vis_pct < 80: fb.append(f"Your face was visible in only {vis_pct:.0f}% of sampled frames. Keep your face centred in the frame.")
    else: fb.append(f"Your face stayed visible for {vis_pct:.0f}% of the answer.")
    if out["lighting"] == "too_dark": fb.append("Lighting is low. Face a window or lamp so your face is clearly lit.")
    if out["lighting"] == "too_bright": fb.append("The image is very bright or backlit. Reduce light behind you.")
    if out["distance"] == "too_far" and vis: fb.append("You appear far from the camera. Move closer.")
    if out["distance"] == "too_close": fb.append("You appear very close to the camera. Sit back slightly.")

    score_parts = [(vis_pct, 0.45)]
    if use_lm and vis >= 5:
        yaw_arr, pit_arr = np.array(yaws), np.array(pitches)
        move = float(np.std(yaw_arr) + np.std(pit_arr))
        facing_pct = facing / vis * 100
        out.update({"looking_at_camera_pct": round(facing_pct, 1), "avg_yaw_deg": round(float(yaw_arr.mean()), 1),
                    "avg_pitch_deg": round(float(pit_arr.mean()), 1), "head_movement_deg": round(move, 1),
                    "gaze_note": "Gaze is estimated from iris position and head pose, so it is approximate. Reading notes or looking at the question on screen also counts as looking away.",
                    "expression": {"smile_mean": round(float(np.mean(smiles)), 2) if smiles else None,
                                   "facial_movement_variation": round(float(np.std(expr)), 3) if expr else None,
                                   "note": "Visible facial movement only. These are uncertain estimates and do NOT indicate confidence, honesty or emotion, and are not scored."}})
        stability = max(0.0, 100 - move * 4)
        score_parts += [(facing_pct, 0.30), (stability, 0.15)]
        if facing_pct < 50: fb.append("You often looked away from the camera. Glancing at the screen is natural, but try to return to the lens regularly.")
        else: fb.append(f"You faced the camera about {facing_pct:.0f}% of the time.")
        if move > 15: fb.append("There was a lot of head movement; a steadier posture can look more composed on video.")
    framing = (50 if out["lighting"] == "ok" else 0) + (50 if out["distance"] == "ok" else 0)
    score_parts.append((framing, 0.10))
    wsum = sum(w for _, w in score_parts)
    out["visual_score"] = round(sum(v * w for v, w in score_parts) / wsum, 1)
    out["feedback"] = fb
    out["limitations"] = ("Coaching feedback only. Upper-body posture is not analysed. The score reflects camera framing, face visibility, "
                          "facing the camera and head steadiness, not suitability, emotion or personality.")
    return out
