from collections import defaultdict
from statistics import mean
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import current_user
from ..models import Interview, User
from ..serializers import iv_out

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _m(v):
    v = [x for x in v if x is not None]
    return round(mean(v), 1) if v else None


@router.get("/summary")
def summary(u: User = Depends(current_user), db: Session = Depends(get_db)):
    ivs = db.query(Interview).filter_by(user_id=u.id).order_by(Interview.started_at).all()
    done = [i for i in ivs if i.status == "completed"]
    trend = [{"id": i.id, "date": i.started_at.strftime("%d %b"), "type": i.interview_type, "overall": i.overall_score,
              **{k: (i.report or {}).get("category_scores", {}).get(k) for k in ("technical", "relevance", "communication", "speaking", "visual", "coding")}}
             for i in done]
    by_diff, by_skill = defaultdict(list), defaultdict(list)
    for i in done:
        for q in i.questions:
            if q.answer and q.answer.score is not None:
                by_diff[q.difficulty].append(q.answer.score); by_skill[q.category].append(q.answer.score)
    return {
        "attempts": len(ivs), "completed": len(done), "average_score": _m([i.overall_score for i in done]),
        "trend": trend,
        "difficulty": [{"name": k, "score": _m(v), "count": len(v)} for k, v in by_diff.items()],
        "skills": sorted([{"name": k, "score": _m(v), "count": len(v)} for k, v in by_skill.items()], key=lambda x: -x["count"])[:12],
        "recent": [iv_out(i) for i in reversed(ivs[-5:])],
        "types": sorted({i.interview_type for i in done}),
    }
