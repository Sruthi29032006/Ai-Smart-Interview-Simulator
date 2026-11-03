from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from xml.sax.saxutils import escape as esc
from .scoring import LABELS


def build_pdf(iv, user, qs) -> bytes:
    st = getSampleStyleSheet()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Interview Report #{iv.id}")
    P = lambda t, s="BodyText": Paragraph(esc(str(t)), st[s])
    r = iv.report or {}
    el = [P("AI Smart Interview Simulator - Performance Report", "Title"),
          P(f"Candidate: {user.full_name}   |   {iv.interview_type}   |   Difficulty: {iv.difficulty}"),
          P(f"Date: {iv.started_at:%d %b %Y %H:%M} UTC   |   Duration: {round((iv.duration_sec or 0) / 60, 1)} min   |   Role: {iv.config.get('target_role') or 'n/a'}"),
          Spacer(1, 6), P(f"Overall score: {iv.overall_score if iv.overall_score is not None else 'n/a'} / 100", "Heading2")]
    w = r.get("weights_used", {})
    if w:
        el.append(P("Weighting (unavailable categories are excluded and the rest re-normalised): " + ", ".join(f"{LABELS[k]} {v * 100:.0f}%" for k, v in w.items())))
    rows = [["Category", "Score"]] + [[LABELS[k], "not measured" if v is None else f"{v}"] for k, v in r.get("category_scores", {}).items()]
    t = Table(rows, colWidths=[110 * mm, 40 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), .4, colors.grey)]))
    el += [Spacer(1, 6), t, Spacer(1, 8), P("Summary", "Heading2"), P(r.get("summary", ""))]
    for title, key in (("Strengths", "strengths"), ("Weaknesses", "weaknesses"), ("Areas for improvement", "improvements"),
                       ("Recommendations for next interview", "next_interview_recommendations")):
        el.append(P(title, "Heading3"))
        el += [P("- " + x) for x in r.get(key, [])]
    el.append(P("Visual and speech metrics are coaching signals only and do not measure emotion, honesty or personality.", "Italic"))
    el.append(PageBreak())
    el.append(P("Question-by-question", "Heading2"))
    for q in qs:
        a = q.answer
        el += [P(f"Q{q.number} [{q.category} / {q.difficulty}]{' (follow-up)' if q.is_followup else ''}", "Heading3"), P(q.text)]
        if not a or a.status != "evaluated":
            el.append(P("Not answered."))
            continue
        ev = a.evaluation
        el += [P(f"Score: {a.score}/100"), P("Answer: " + a.transcript)]
        for lab, k in (("Correct concepts", "correct_concepts"), ("Missing concepts", "missing_concepts"),
                       ("Incorrect statements", "incorrect_statements"), ("Suggestions", "suggestions")):
            if ev.get(k):
                el.append(P(f"{lab}: " + "; ".join(ev[k])))
        el.append(P("Reference answer: " + ev.get("reference_answer", "")))
        au, vi = a.audio_analysis or {}, a.visual_analysis or {}
        if au.get("available"):
            el.append(P(f"Speech: {au['words_per_minute']} wpm, {au['hesitation_fillers']} hesitation fillers, {len(au['long_pauses'])} long pauses, delivery {au['delivery_score']}/100"))
        if vi.get("available"):
            el.append(P(f"Visual: face visible {vi['face_visible_pct']}%, " + (f"facing camera {vi.get('looking_at_camera_pct')}%, " if 'looking_at_camera_pct' in vi else "") + f"visual score {vi['visual_score']}/100"))
        el.append(Spacer(1, 6))
    doc.build(el)
    return buf.getvalue()
