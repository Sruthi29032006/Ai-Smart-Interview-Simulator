"""Combine per-answer results into category scores + overall report. Missing data is excluded, never zero-filled."""
from statistics import mean

WEIGHTS = {"technical": 0.35, "relevance": 0.20, "communication": 0.15, "speaking": 0.10, "visual": 0.05, "coding": 0.15}
LABELS = {"technical": "Technical knowledge", "relevance": "Answer relevance", "communication": "Communication",
          "speaking": "Speaking delivery", "visual": "Visual interview behavior", "coding": "Coding performance"}


def _avg(v):
    v = [x for x in v if x is not None]
    return round(mean(v), 1) if v else None


def category_scores(answers) -> dict:
    tech, rel, comm, speak, vis, code = [], [], [], [], [], []
    for a in answers:
        ev = a.evaluation
        if not ev:
            continue
        if ev.get("coding"):
            c = ev["coding"]
            code.append((c["correctness"] * .4 + c["logic"] * .2 + c["edge_cases"] * .15 + c["complexity"] * .1 + c["code_quality"] * .15) * 10)
        else:
            tech.append(ev["technical"] * 10)
        rel.append(ev["relevance"] * 10)
        comm.append((ev["clarity"] + ev["structure"] + ev["communication"]) / 3 * 10)
        if a.audio_analysis and a.audio_analysis.get("available"):
            speak.append(a.audio_analysis["delivery_score"])
        if a.visual_analysis and a.visual_analysis.get("available"):
            vis.append(a.visual_analysis["visual_score"])
    return {"technical": _avg(tech), "relevance": _avg(rel), "communication": _avg(comm),
            "speaking": _avg(speak), "visual": _avg(vis), "coding": _avg(code)}


def overall(cats: dict):
    avail = {k: v for k, v in cats.items() if v is not None}
    if not avail:
        return None, {}
    tot = sum(WEIGHTS[k] for k in avail)
    used = {k: round(WEIGHTS[k] / tot, 3) for k in avail}
    return round(sum(avail[k] * used[k] for k in avail), 1), used
