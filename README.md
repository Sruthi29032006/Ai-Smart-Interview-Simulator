# AI Smart Interview Simulator and Performance Analytics

Webcam + microphone based AI interview platform: AI-generated adaptive questions, local speech-to-text,
audio-delivery analysis, face/head-pose analysis (OpenCV + MediaPipe), AI answer evaluation, analytics dashboard and PDF reports.

**Stack:** React + Vite + Recharts · FastAPI + SQLAlchemy + SQLite · faster-whisper (local STT) · OpenCV + MediaPipe · Gemini (or any OpenAI-compatible LLM) · ReportLab.

## Quick start (Windows, VS Code)
Prerequisites: **Python 3.11**, **Node.js 18+**, Chrome or Edge, a webcam and microphone, a free Gemini API key (https://aistudio.google.com/apikey).

1. Extract the ZIP and open the folder in VS Code.
2. Open a terminal and run `setup.bat` (creates the venv, installs everything, creates `backend\.env`, initialises the DB, downloads the face-landmarker model).
3. Edit `backend\.env`: set `GEMINI_API_KEY` and a long random `JWT_SECRET`. Optionally set `ADMIN_EMAIL` to the email you will register with to get the admin dashboard.
4. Terminal 1: `start-backend.bat` (API docs: http://127.0.0.1:8000/docs)
5. Terminal 2: `start-frontend.bat`
6. Open **http://localhost:5173**, register, complete your profile, start an interview, allow camera/mic.

First transcription downloads the Whisper model (~150 MB for `base.en`) once, so internet is required for that first run.

## How the core pipeline works
| Step | Where | Implementation |
|---|---|---|
| Capture | Browser | `getUserMedia` + `MediaRecorder` (webm, video+audio), device selection, mic level meter, pause/resume, playback |
| Upload | `POST /api/interviews/{id}/questions/{qid}/media` | extension + magic-byte + size validation, consent check, stored under `backend/storage/<user>/<interview>/` |
| Transcription | `speech.py` | faster-whisper (local, word timestamps). Transcript is editable before submit; nothing is invented, empty speech returns a warning |
| Audio analysis | `speech.py` | words/min, pauses, long pauses, um/uh and soft fillers, repeated words, sentence stats, ASR confidence. Does **not** claim to measure confidence/emotion |
| Visual analysis | `vision.py` | frames sampled at ~4 fps; MediaPipe Face Landmarker → face visibility, head pose (yaw/pitch from transformation matrix), approximate gaze (iris landmarks), head movement, lighting, distance, blendshape-based facial-movement stats (unscored, labelled uncertain). Falls back to OpenCV Haar face detection (visibility only) if the model is missing |
| Evaluation | `engine.py` | LLM returns schema-validated JSON (dimension scores, correct/missing/incorrect concepts, reference answer, coding scores). Question score computed server-side from the dimensions. On AI failure the API returns 502 and you can retry; no fake score is stored |
| Adaptivity | `engine.py` | next question uses previous answer, its score and missing concepts; follow-ups when warranted; difficulty rises/falls in Mixed mode |
| Report | `scoring.py`, `pdf.py` | six category scores; overall = weighted mean of **measured** categories only (weights re-normalised, missing ≠ 0); AI summary; PDF download |

Score weights: technical 35%, relevance 20%, communication 15%, speaking 10%, visual 5%, coding 15% (coding replaces nothing; it is included only if coding questions were answered).

## Privacy
Explicit consent checkbox before any recording; REC indicator; recordings stored only on your own server, visible only to their owner (admins see aggregates only);
per-recording delete, "delete all recordings" and "delete everything" in Settings; automatic deletion after `RECORDING_RETENTION_DAYS`.
Speech-to-text and vision run locally. **Only transcript text and interview context go to the external LLM provider**; video/audio never do.
Visual metrics are coaching feedback, not judgments of emotion, honesty, personality or suitability.

## Tests
`run-tests.bat` runs `backend/tests/test_api.py` (auth, isolation between users, full interview flow, PDF, upload validation, consent, admin protection, AI-failure behaviour). The LLM HTTP call is mocked **only inside the tests**.

## Troubleshooting
- **Camera blocked:** use `http://localhost:5173` (not an IP address), click the lock icon → allow camera and microphone. Close Teams/Zoom if the device is "in use".
- **502 "AI service error":** check `GEMINI_API_KEY`, model name and internet; press Retry.
- **Transcript empty:** check mic selection and the green level bar; speak for at least a few seconds; or type your answer.
- **Visual analysis says "basic face detection only":** the face-landmarker model did not download. Run `backend\.venv\Scripts\python backend\init_db.py` with internet.
- **`pip install` fails for mediapipe/faster-whisper:** use Python 3.11 (64-bit), not 3.13.
- **Forgot password:** the reset link is printed in the backend terminal (no email server).
- **Slow first answer:** Whisper model is loading; later answers are faster. Use `WHISPER_MODEL=tiny.en` on slow PCs.

## Known limitations (honest list)
- Upper-body posture analysis is **not** implemented (face-based framing/head pose only).
- Coding answers are judged by the LLM; code is **not executed** in a sandbox.
- Gaze is an approximation from iris position + head pose; reading the question on screen counts as looking away.
- Interview rounds/transcripts/recording metadata/analyses are stored on the `answers` row (one answer per question) rather than separate tables.
- Live (while-speaking) transcription is not provided; transcription runs right after you stop recording.
- Only English is configured (`WHISPER_LANGUAGE`, use a multilingual model e.g. `base` to add others).
