"""
Core reasoning layer for the Skill-Gap & Personalized Learning Agent.

Design principles (mapped to hackathon judging criteria):
  - Explainability: every gap and every roadmap step carries a human-
    readable "reason" grounded in concrete numbers (weight, level delta),
    never a black-box score alone.
  - Human-in-the-loop: this module only *recommends*. Nothing here writes
    to a calendar, enrolls the student in a course, or takes any
    irreversible action -- the roadmap is proposed, the student accepts/
    edits it via the API, progress is marked by the student explicitly.
  - Graceful failure handling: every call to the LLM is wrapped. If the
    Groq API key is missing, the request fails, or the model returns
    malformed JSON, we fall back to a deterministic rule-based explanation
    so the product never breaks or shows an empty state.
"""

import os
import json
import re

try:
    from openai import OpenAI
    _client = (
        OpenAI(
            api_key=os.environ.get("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )
        if os.environ.get("GROQ_API_KEY")
        else None
    )
except Exception:
    _client = None

from skills_data import get_role_skills

# Served on GroqCloud via the OpenAI-compatible Responses API.
MODEL = "openai/gpt-oss-20b"


def compute_gap(current_skills, role_title):
    """
    Deterministic gap computation (always runs, LLM or not -- this is the
    trustworthy core; the LLM only adds natural-language explanation).

    current_skills: [{"skill": str, "level": int 1-5}]
    Returns: list of dicts, one per required skill, sorted by gap severity.
    """
    canonical_role, required = get_role_skills(role_title)
    have = {s["skill"].strip().lower(): s["level"] for s in current_skills}

    gaps = []
    for skill, meta in required.items():
        current_level = have.get(skill.strip().lower(), 0)
        delta = max(meta["min_level"] - current_level, 0)
        severity = round(delta * meta["weight"], 2)  # importance-weighted gap
        gaps.append(
            {
                "skill": skill,
                "current_level": current_level,
                "target_level": meta["min_level"],
                "market_weight": meta["weight"],
                "gap_severity": severity,
                "status": "met" if delta == 0 else "gap",
            }
        )

    gaps.sort(key=lambda g: g["gap_severity"], reverse=True)
    return canonical_role, gaps


def _fallback_explanation(gap):
    if gap["status"] == "met":
        return (
            f"You already meet the bar for {gap['skill']} "
            f"(level {gap['current_level']}/5 vs target {gap['target_level']}/5)."
        )
    return (
        f"{gap['skill']} appears in roughly {int(gap['market_weight']*100)}% of postings "
        f"for this role and typically expects level {gap['target_level']}/5. "
        f"You're currently at {gap['current_level']}/5, a gap of "
        f"{gap['target_level'] - gap['current_level']} level(s)."
    )


def _fallback_project(skill):
    return f"Build a small project that specifically exercises '{skill}' and document it publicly (GitHub + README)."


def _extract_json(text):
    """LLMs sometimes wrap JSON in prose or code fences; salvage it."""
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in model output")
    return json.loads(match.group(0))


def explain_gaps_with_llm(canonical_role, gaps, projects):
    """
    Ask the Groq-hosted model to write natural-language, personalized explanations and to
    ground project suggestions in the student's *existing* projects where
    possible. Falls back to deterministic text on any failure.
    """
    if _client is None:
        for g in gaps:
            g["explanation"] = _fallback_explanation(g)
            if g["status"] == "gap":
                g["suggested_project"] = _fallback_project(g["skill"])
        return gaps, False  # False = LLM not used

    try:
        prompt = f"""You are a career-skills advisor. A student is targeting the role
"{canonical_role}". Here is the computed skill gap analysis (already scored
deterministically -- do NOT change the numbers, only explain them):

{json.dumps(gaps, indent=2)}

The student's existing projects: {json.dumps(projects, indent=2)}

For each item with status "gap", write:
  - "explanation": one sentence, concrete, referencing the market_weight and level delta, plain language, no fluff.
  - "suggested_project": one concrete, specific project idea (not generic like "learn X"). If one of the student's
    existing projects could be *extended* to demonstrate this skill, say so explicitly instead of proposing a new one.

For items with status "met", write a one-sentence "explanation" acknowledging it's covered.

Respond with ONLY a JSON array, same order as input, each object having exactly:
"skill", "explanation", "suggested_project" (empty string if status is "met").
No prose, no markdown fences."""

        resp = _client.responses.create(
            model=MODEL,
            input=prompt,
        )
        text = resp.output_text
        enriched = _extract_json(text)

        by_skill = {e["skill"]: e for e in enriched}
        for g in gaps:
            e = by_skill.get(g["skill"])
            if e:
                g["explanation"] = e.get("explanation", _fallback_explanation(g))
                g["suggested_project"] = e.get("suggested_project", "") or (
                    _fallback_project(g["skill"]) if g["status"] == "gap" else ""
                )
            else:
                g["explanation"] = _fallback_explanation(g)
                g["suggested_project"] = _fallback_project(g["skill"]) if g["status"] == "gap" else ""
        return gaps, True

    except Exception:
        # Graceful degradation: any API/network/parsing failure -> deterministic path
        for g in gaps:
            g["explanation"] = _fallback_explanation(g)
            if g["status"] == "gap":
                g["suggested_project"] = _fallback_project(g["skill"])
        return gaps, False


def build_roadmap(gaps):
    """
    Turn the explained gap list into a prioritized roadmap.
    Priority = gap_severity, ties broken by market_weight.
    This step is pure and deterministic -- explainability of *ordering*
    doesn't depend on the LLM being available.
    """
    only_gaps = [g for g in gaps if g["status"] == "gap"]
    only_gaps.sort(key=lambda g: (g["gap_severity"], g["market_weight"]), reverse=True)

    roadmap = []
    for rank, g in enumerate(only_gaps, start=1):
        roadmap.append(
            {
                "skill": g["skill"],
                "priority_rank": rank,
                "reason": g["explanation"],
                "suggested_project": g["suggested_project"],
            }
        )
    return roadmap


def recompute(current_skills, role_title, projects):
    """Full pipeline: gap -> explain (LLM w/ fallback) -> roadmap."""
    canonical_role, gaps = compute_gap(current_skills, role_title)
    gaps, llm_used = explain_gaps_with_llm(canonical_role, gaps, projects)
    roadmap = build_roadmap(gaps)
    return {
        "canonical_role": canonical_role,
        "gaps": gaps,
        "roadmap": roadmap,
        "llm_used": llm_used,
    }
