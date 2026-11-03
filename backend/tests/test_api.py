"""Backend tests. The LLM HTTP call is mocked ONLY here, so tests run offline; the app itself never mocks."""
import json, os, tempfile
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["RECORDING_RETENTION_DAYS"] = "0"

import pytest
from fastapi.testclient import TestClient
from app import llm
from app.main import app

Q = {"text": "Explain the bias-variance tradeoff and how you would diagnose it.", "category": "ML fundamentals", "difficulty": "intermediate",
     "expected_concepts": ["bias", "variance", "learning curves"], "evaluation_criteria": ["accuracy"], "hint": "Think underfitting vs overfitting",
     "sample_answer": "SECRET-SAMPLE", "is_coding": False, "is_followup": False}


def fake_call(prompt, system, temperature=0.7):
    if "Evaluate this interview answer" in prompt:
        n = min(len(prompt.split("\"\"\"")[1].split()), 10)  # score depends on the answer given
        return json.dumps({"technical": n, "relevance": n, "completeness": n - 1, "clarity": 7, "structure": 7, "communication": 7, "examples": 5,
                           "correct_concepts": ["bias"], "missing_concepts": ["learning curves"], "incorrect_statements": [],
                           "suggestions": ["Add an example"], "reference_answer": "ref", "explanation": "why", "coding": None})
    if "final interview performance summary" in prompt:
        return json.dumps({"summary": "Good.", "strengths": ["a"], "weaknesses": ["b"], "improvements": ["c"], "next_interview_recommendations": ["d"]})
    return json.dumps(Q)


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    monkeypatch.setattr(llm, "_call", fake_call)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def register(c, email):
    r = c.post("/api/auth/register", json={"email": email, "full_name": "Test User", "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_auth_flow(client):
    register(client, "a@x.com")
    assert client.post("/api/auth/register", json={"email": "a@x.com", "full_name": "T U", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "a@x.com", "password": "wrong-pass"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + r.json()["token"]}).json()["email"] == "a@x.com"


def test_full_interview_and_isolation(client):
    h, h2 = register(client, "b@x.com"), register(client, "c@x.com")
    assert client.get("/api/analytics/summary", headers=h).json()["attempts"] == 0
    r = client.post("/api/interviews", headers=h, json={"interview_type": "Data Science Interview", "difficulty": "Mixed",
                                                         "num_questions": 2, "consent_recording": True})
    assert r.status_code == 201, r.text
    iv = r.json(); q = iv["questions"][0]
    assert "sample_answer" not in q  # hidden before submission
    iid, qid = iv["id"], q["id"]
    assert client.get(f"/api/interviews/{iid}", headers=h2).status_code == 404  # other user cannot read it
    assert client.post(f"/api/interviews/{iid}/next", headers=h).status_code == 409  # must answer first
    assert client.post(f"/api/interviews/{iid}/questions/{qid}/submit", headers=h, json={"transcript": "hi", "mode": "text"}).status_code == 400
    r = client.post(f"/api/interviews/{iid}/questions/{qid}/submit", headers=h,
                    json={"transcript": "Bias is error from simplistic assumptions while variance is sensitivity to training data.", "mode": "text"})
    assert r.status_code == 200, r.text
    assert r.json()["question"]["sample_answer"] == "SECRET-SAMPLE" and r.json()["question"]["answer"]["score"] > 0
    n = client.post(f"/api/interviews/{iid}/next", headers=h).json()
    assert n["done"] is False
    client.post(f"/api/interviews/{iid}/questions/{n['question']['id']}/submit", headers=h,
                json={"transcript": "Variance means the model changes a lot with different data samples overall.", "mode": "text"})
    assert client.post(f"/api/interviews/{iid}/next", headers=h).json()["done"] is True
    rep = client.post(f"/api/interviews/{iid}/finish", headers=h).json()
    assert rep["status"] == "completed" and rep["overall_score"] is not None
    cats = rep["report"]["category_scores"]
    assert cats["visual"] is None and cats["speaking"] is None and "visual" not in rep["report"]["weights_used"]  # not zero-filled
    pdf = client.get(f"/api/interviews/{iid}/report.pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.get(f"/api/interviews/{iid}/report.pdf", headers=h2).status_code == 404
    s = client.get("/api/analytics/summary", headers=h).json()
    assert s["completed"] == 1 and s["average_score"] == rep["overall_score"]
    assert client.get("/api/analytics/summary", headers=h2).json()["completed"] == 0
    assert client.delete(f"/api/interviews/{iid}", headers=h).status_code == 200
    assert client.get(f"/api/interviews/{iid}", headers=h).status_code == 404


def test_llm_failure_is_an_error_not_fake_data(client, monkeypatch):
    h = register(client, "d@x.com")
    def boom(*a, **k): raise llm.LLMError("down")
    monkeypatch.setattr(llm, "_call", boom)
    r = client.post("/api/interviews", headers=h, json={"interview_type": "HR Interview", "consent_recording": False})
    assert r.status_code == 502
    assert client.get("/api/interviews", headers=h).json() == []


def test_upload_validation_and_consent(client):
    h = register(client, "e@x.com")
    base = {"interview_type": "HR Interview", "num_questions": 1}
    nc = client.post("/api/interviews", headers=h, json={**base, "consent_recording": False}).json()
    url = lambda iv: f"/api/interviews/{iv['id']}/questions/{iv['questions'][0]['id']}/media"
    assert client.post(url(nc), headers=h, files={"file": ("a.webm", b"x" * 5000)}).status_code == 403
    iv = client.post("/api/interviews", headers=h, json={**base, "consent_recording": True}).json()
    assert client.post(url(iv), headers=h, files={"file": ("a.exe", b"x" * 5000)}).status_code == 415
    assert client.post(url(iv), headers=h, files={"file": ("a.webm", b"not a video" * 500)}).status_code == 400


def test_admin_requires_role(client):
    h = register(client, "f@x.com")
    assert client.get("/api/admin/stats", headers=h).status_code == 403
    assert client.get("/api/admin/stats").status_code == 401
