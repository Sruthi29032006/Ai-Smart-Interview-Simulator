"""AI question generation + answer evaluation."""
import json
from typing import Literal
from pydantic import BaseModel, Field
from .llm import generate_json

Diff = Literal["basic", "intermediate", "advanced"]


class GenQuestion(BaseModel):
    text: str = Field(min_length=10)
    category: str = "General"
    difficulty: Diff = "intermediate"
    expected_concepts: list[str] = []
    evaluation_criteria: list[str] = []
    hint: str | None = None
    sample_answer: str | None = None
    is_coding: bool = False
    is_followup: bool = False


class Coding(BaseModel):
    correctness: float = Field(ge=0, le=10)
    logic: float = Field(ge=0, le=10)
    edge_cases: float = Field(ge=0, le=10)
    complexity: float = Field(ge=0, le=10)
    code_quality: float = Field(ge=0, le=10)
    notes: str = ""


class Evaluation(BaseModel):
    technical: float = Field(ge=0, le=10)
    relevance: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    structure: float = Field(ge=0, le=10)
    communication: float = Field(ge=0, le=10)
    examples: float = Field(ge=0, le=10)
    correct_concepts: list[str] = []
    missing_concepts: list[str] = []
    incorrect_statements: list[str] = []
    suggestions: list[str] = []
    reference_answer: str = ""
    explanation: str = ""
    coding: Coding | None = None


class Summary(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    improvements: list[str]
    next_interview_recommendations: list[str]


Q_SYSTEM = ("You are a senior interviewer at a real company. You write original, realistic interview questions. "
            "Respond ONLY with JSON matching the requested schema.")
E_SYSTEM = ("You are a strict, fair interview evaluator. Judge only what the candidate actually said or wrote. "
            "Never credit concepts that are absent from the answer. Scores are 0-10 per dimension. "
            "Respond ONLY with JSON matching the requested schema.")

Q_SCHEMA = """{"text": "question shown to candidate (for coding: full problem statement with input/output examples and constraints)",
"category": "topic area e.g. 'Statistics', 'SQL joins', 'Behavioral - conflict'",
"difficulty": "basic|intermediate|advanced",
"expected_concepts": ["key concepts a good answer covers"],
"evaluation_criteria": ["what you will judge"],
"hint": "optional short hint that does not give the answer away",
"sample_answer": "model answer (hidden from candidate until they submit)",
"is_coding": false,
"is_followup": false}"""

E_SCHEMA = """{"technical":0-10,"relevance":0-10,"completeness":0-10,"clarity":0-10,"structure":0-10,"communication":0-10,"examples":0-10,
"correct_concepts":[],"missing_concepts":[],"incorrect_statements":[],"suggestions":[],
"reference_answer":"concise strong answer","explanation":"why this is the expected answer",
"coding": null or {"correctness":0-10,"logic":0-10,"edge_cases":0-10,"complexity":0-10,"code_quality":0-10,"notes":""}}"""


def target_difficulty(setting: str, avg_prev: float | None) -> str:
    if setting in ("basic", "intermediate", "advanced"):
        return setting
    if avg_prev is None:
        return "intermediate"
    return "advanced" if avg_prev >= 75 else "basic" if avg_prev < 45 else "intermediate"


def generate_question(iv, history: list[dict]) -> GenQuestion:
    cfg = iv.config
    scores = [h["score"] for h in history if h.get("score") is not None]
    avg = sum(scores) / len(scores) if scores else None
    diff = target_difficulty(iv.difficulty.lower(), avg)
    asked = [h["text"] for h in history]
    last = history[-1] if history else None
    prompt = f"""Generate interview question number {len(history) + 1}{'' if not iv.num_questions else f' of {iv.num_questions}'}.
Interview type: {iv.interview_type}
Candidate target role: {cfg.get('target_role') or 'not specified'} at {cfg.get('target_company') or 'not specified'}
Experience level: {cfg.get('experience_level')}
Skills: {cfg.get('skills')}; Programming languages: {cfg.get('languages')}
Extra preparation requirements: {cfg.get('extra') or 'none'}
Difficulty setting: {iv.difficulty} -> use '{diff}' for this question (candidate's average so far: {avg if avg is not None else 'n/a'}).
Questions already asked (do NOT repeat or paraphrase): {json.dumps(asked)}
"""
    if last:
        prompt += f"""Previous question: {last['text']}
Candidate's previous answer (transcript): {last['transcript'][:2500]}
Previous score: {last.get('score')}; missing concepts: {last.get('missing')}
If the previous answer was vague, incomplete, or made a claim worth probing, ask a short, specific FOLLOW-UP (is_followup=true) that builds on what the candidate actually said. Otherwise move to a new topic relevant to the role.
"""
    else:
        prompt += "This is the opening question: make it appropriate for starting the interview (a warm-up is fine for HR/behavioral).\n"
    prompt += "If the interview type is Coding, set is_coding=true and write a complete problem with examples and constraints. Do not include the answer in 'text'.\nSchema:\n" + Q_SCHEMA
    return generate_json(prompt, GenQuestion, Q_SYSTEM, 0.9)


def question_score(ev: Evaluation) -> float:
    tech = ev.technical
    if ev.coding:
        c = ev.coding
        tech = (c.correctness * 0.4 + c.logic * 0.2 + c.edge_cases * 0.15 + c.complexity * 0.1 + c.code_quality * 0.15)
    parts = [(tech, 0.30), (ev.relevance, 0.20), (ev.completeness, 0.15), (ev.clarity, 0.10),
             (ev.structure, 0.08), (ev.communication, 0.10), (ev.examples, 0.07)]
    return round(sum(v * w for v, w in parts) * 10, 1)


def evaluate_answer(q, transcript: str, mode: str) -> tuple[Evaluation, float]:
    prompt = f"""Evaluate this interview answer.
Question ({q.difficulty}, {q.category}, coding={q.is_coding}): {q.text}
Expected concepts: {json.dumps(q.expected_concepts)}
Criteria: {json.dumps(q.evaluation_criteria)}
Answer given by voice (speech-to-text, may contain minor transcription errors) or text; mode={mode}:
\"\"\"{transcript}\"\"\"
Rules: score only content present in the answer; list concepts the candidate actually covered in correct_concepts;
list expected concepts that are absent in missing_concepts; quote or describe wrong claims in incorrect_statements.
{'This is a coding question: fill the "coding" object judging the code/approach given.' if q.is_coding else 'Set "coding" to null.'}
Schema:
{E_SCHEMA}"""
    ev = generate_json(prompt, Evaluation, E_SYSTEM, 0.2)
    return ev, question_score(ev)


def summarize(interview_type: str, role: str, rows: list[dict], categories: dict) -> Summary:
    prompt = f"""Write the final interview performance summary for a candidate ({interview_type}, role: {role or 'n/a'}).
Category scores (0-100, null = not measured): {json.dumps(categories)}
Per-question data: {json.dumps(rows)[:12000]}
Visual and speech metrics are coaching signals only; never infer personality, honesty, intelligence or emotion from them.
Schema: {{"summary":"3-5 sentences","strengths":[],"weaknesses":[],"improvements":["specific actions"],"next_interview_recommendations":[]}}"""
    return generate_json(prompt, Summary, E_SYSTEM, 0.3)
