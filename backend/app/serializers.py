def q_out(q, reveal=False):
    d = {"id": q.id, "number": q.number, "text": q.text, "category": q.category, "difficulty": q.difficulty,
         "hint": q.hint, "is_coding": q.is_coding, "is_followup": q.is_followup}
    if reveal:
        d.update(expected_concepts=q.expected_concepts, evaluation_criteria=q.evaluation_criteria, sample_answer=q.sample_answer)
    return d


def a_out(a):
    if not a:
        return None
    return {"id": a.id, "mode": a.mode, "transcript": a.transcript, "raw_transcript": a.raw_transcript,
            "has_media": bool(a.media_path), "duration_sec": a.duration_sec, "audio_analysis": a.audio_analysis,
            "visual_analysis": a.visual_analysis, "evaluation": a.evaluation, "score": a.score, "status": a.status}


def question_full(q):
    done = bool(q.answer and q.answer.status == "evaluated")
    return {**q_out(q, reveal=done), "answer": a_out(q.answer)}


def iv_out(iv, detail=False):
    d = {"id": iv.id, "type": iv.interview_type, "difficulty": iv.difficulty, "num_questions": iv.num_questions,
         "status": iv.status, "started_at": iv.started_at.isoformat(), "ended_at": iv.ended_at.isoformat() if iv.ended_at else None,
         "duration_sec": iv.duration_sec, "overall_score": iv.overall_score, "consent_recording": iv.consent_recording,
         "target_role": iv.config.get("target_role"), "answered": sum(1 for q in iv.questions if q.answer and q.answer.status == "evaluated"),
         "question_count": len(iv.questions)}
    if detail:
        d["config"] = iv.config
        d["report"] = iv.report
        d["questions"] = [question_full(q) for q in iv.questions]
    return d
