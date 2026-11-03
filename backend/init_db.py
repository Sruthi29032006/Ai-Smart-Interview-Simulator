"""Create tables, seed interview categories and download the face landmarker model."""
from app.main import init_db
from app import vision

init_db()
print("Database initialised.")
print("Face landmarker model:", "ready" if vision.ensure_model() else "NOT downloaded (check internet); basic face detection will be used")
