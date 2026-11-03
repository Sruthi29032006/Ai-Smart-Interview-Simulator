"""Local speech-to-text (faster-whisper) and audio/speech analysis from word timestamps."""
import re, logging
from functools import lru_cache
from .config import settings

log = logging.getLogger("speech")
FILLERS = ["um", "uh", "umm", "uhh", "er", "erm", "hmm", "like", "you know", "basically", "actually", "sort of", "kind of", "i mean"]


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    log.info("Loading Whisper model %s (first run downloads it)", settings.whisper_model)
    return WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")


def transcribe(path: str) -> dict:
    """Returns {text, words:[{w,start,end,p}], duration, error}. Never invents text."""
    try:
        segs, info = _model().transcribe(path, language=settings.whisper_language or None, word_timestamps=True,
                                         vad_filter=True, beam_size=5, initial_prompt="Hello. This is a job interview answer, with punctuation.")
        words, text = [], []
        for s in segs:
            text.append(s.text.strip())
            for w in (s.words or []):
                words.append({"w": w.word.strip(), "start": w.start, "end": w.end, "p": getattr(w, "probability", None)})
        return {"text": " ".join(text).strip(), "words": words, "duration": info.duration, "error": None}
    except Exception as e:  # missing model / undecodable audio / no audio track
        log.exception("transcription failed")
        return {"text": "", "words": [], "duration": None, "error": f"Transcription failed: {e}"}


def analyze_audio(tr: dict) -> dict:
    words, dur = tr["words"], tr.get("duration")
    if len(words) < 5:
        return {"available": False, "reason": "Too little speech detected to analyze delivery.", "duration_sec": dur, "word_count": len(words)}
    text = tr["text"].lower()
    n = len(words)
    first, last = words[0]["start"], words[-1]["end"]
    speaking_span = max(last - first, 1e-3)
    pauses = [words[i + 1]["start"] - words[i]["end"] for i in range(n - 1)]
    long_pauses = [round(p, 1) for p in pauses if p >= 2.0]
    mid_pauses = [p for p in pauses if 0.7 <= p < 2.0]
    voiced = sum(max(w["end"] - w["start"], 0) for w in words)
    wpm = n / speaking_span * 60
    filler_counts = {}
    for f in FILLERS:
        c = len(re.findall(rf"\b{re.escape(f)}\b", text))
        if c:
            filler_counts[f] = c
    # 'like'/'actually' etc. are ambiguous, so count only unambiguous disfluencies in the score
    hard = sum(filler_counts.get(f, 0) for f in ("um", "uh", "umm", "uhh", "er", "erm", "hmm"))
    soft = sum(filler_counts.values()) - hard
    toks = [re.sub(r"[^a-z']", "", w["w"].lower()) for w in words]
    repeats = [toks[i] for i in range(1, n) if toks[i] and toks[i] == toks[i - 1] and toks[i] not in ("that", "had")]
    probs = [w["p"] for w in words if w["p"] is not None]
    sentences = [s for s in re.split(r"[.!?]+", tr["text"]) if len(s.split()) >= 2]
    lead = first
    silence_ratio = 1 - voiced / dur if dur else None

    # delivery score (0-100): pace, fluency, pauses
    if 110 <= wpm <= 170:
        pace = 100
    elif wpm < 110:
        pace = max(30, 100 - (110 - wpm) * 1.5)
    else:
        pace = max(30, 100 - (wpm - 170) * 1.5)
    fl = max(0, 100 - (hard / n * 100) * 12 - (soft / n * 100) * 3 - len(repeats) / n * 100 * 4)
    pz = max(0, 100 - len(long_pauses) * 15 - len(mid_pauses) * 3)
    score = round(pace * 0.35 + fl * 0.4 + pz * 0.25, 1)

    fb = []
    fb.append(f"Speaking pace was about {wpm:.0f} words/min (comfortable range is roughly 110-170).")
    if wpm > 170: fb.append("You spoke quickly; slow down slightly so key points land.")
    if wpm < 110: fb.append("Your pace was slow; practise delivering ideas more steadily.")
    if hard: fb.append(f"Detected {hard} hesitation sound(s) (um/uh); brief pauses are better than fillers.")
    if soft: fb.append(f"Words like 'like/basically/you know' appeared {soft} time(s); they may be filler or normal usage.")
    if long_pauses: fb.append(f"{len(long_pauses)} long pause(s) of 2s or more (e.g. {long_pauses[:3]} s). Structure your thoughts before speaking.")
    if repeats: fb.append(f"Repeated consecutive words {len(repeats)} time(s), which can reduce fluency.")
    if lead > 5: fb.append(f"It took about {lead:.1f}s to begin speaking after recording started.")
    return {
        "available": True, "duration_sec": round(dur, 1) if dur else None, "speaking_time_sec": round(voiced, 1),
        "word_count": n, "words_per_minute": round(wpm, 1), "silence_ratio": round(silence_ratio, 2) if silence_ratio is not None else None,
        "long_pauses": long_pauses, "pause_count_0_7s": len(mid_pauses) + len(long_pauses), "filler_counts": filler_counts,
        "hesitation_fillers": hard, "repeated_words": len(repeats), "sentence_count": len(sentences),
        "avg_sentence_words": round(n / max(len(sentences), 1), 1), "start_delay_sec": round(lead, 1),
        "transcription_confidence": round(sum(probs) / len(probs), 2) if probs else None,
        "delivery_score": score,
        "feedback": fb,
        "notes": "Measures timing and fluency from the recording. It does NOT measure vocal confidence or emotion. "
                 "transcription_confidence is the speech recognizer's certainty and is only a rough proxy for audio clarity.",
    }
