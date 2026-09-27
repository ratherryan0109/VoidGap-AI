from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

import db
import agent
from skills_data import list_roles

app = FastAPI(title="AI Skill-Gap & Personalized Learning Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only -- restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()


# ---------- Schemas ----------

class SkillIn(BaseModel):
    skill: str
    level: int  # 1-5 self-assessed or quiz-derived proficiency


class ProjectIn(BaseModel):
    title: str
    description: str = ""
    skills: List[str] = []


class ProfileIn(BaseModel):
    student_name: str
    current_skills: List[SkillIn]
    projects: List[ProjectIn] = []
    github_username: Optional[str] = None


class TargetRoleIn(BaseModel):
    student_id: int
    role_title: str
    job_description: Optional[str] = ""


class ProgressIn(BaseModel):
    item_id: int
    status: str  # pending | in_progress | done


# ---------- Endpoints ----------

@app.get("/api/roles")
def roles():
    """Known roles in the mock market-intelligence taxonomy."""
    return {"roles": list_roles()}


@app.post("/api/profile")
def create_profile(payload: ProfileIn):
    student_id = db.create_or_get_student(payload.student_name)
    db.save_profile(
        student_id,
        [s.dict() for s in payload.current_skills],
        [p.dict() for p in payload.projects],
        payload.github_username,
    )
    return {"student_id": student_id}


@app.post("/api/target-role")
def set_target_role(payload: TargetRoleIn):
    profile = db.get_profile(payload.student_id)
    if not profile:
        raise HTTPException(404, "Profile not found -- create a profile first")
    db.save_target_role(payload.student_id, payload.role_title, payload.job_description)
    return _recompute_and_store(payload.student_id)


@app.get("/api/state/{student_id}")
def get_state(student_id: int):
    profile = db.get_profile(student_id)
    role = db.get_target_role(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")
    roadmap = db.get_roadmap(student_id)
    total = len(roadmap)
    done = len([r for r in roadmap if r["status"] == "done"])
    return {
        "profile": profile,
        "target_role": role,
        "roadmap": roadmap,
        "progress_pct": round(100 * done / total, 1) if total else 0,
    }


@app.post("/api/recompute/{student_id}")
def recompute(student_id: int):
    """Student updated their skills/projects -> re-run gap analysis, roadmap adapts."""
    return _recompute_and_store(student_id)


@app.post("/api/progress")
def mark_progress(payload: ProgressIn):
    if payload.status not in ("pending", "in_progress", "done"):
        raise HTTPException(400, "Invalid status")
    db.update_progress(payload.item_id, payload.status)
    return {"ok": True}


# ---------- Internal ----------

def _recompute_and_store(student_id: int):
    profile = db.get_profile(student_id)
    role = db.get_target_role(student_id)
    if not profile or not role:
        raise HTTPException(400, "Profile and target role are both required")

    result = agent.recompute(
        current_skills=profile["current_skills"],
        role_title=role["role_title"],
        projects=profile["projects"],
    )
    db.replace_roadmap(student_id, result["roadmap"])

    return {
        "canonical_role": result["canonical_role"],
        "gaps": result["gaps"],
        "roadmap": db.get_roadmap(student_id),
        "explanations_from_llm": result["llm_used"],
    }
