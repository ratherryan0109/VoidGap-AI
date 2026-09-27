"""
Mock market-intelligence layer.

In production this would be replaced by live calls to job-posting APIs
(LinkedIn, Naukri, Indeed) that mine thousands of postings for a role and
compute skill frequency/importance. For the hackathon demo we ship a
curated static taxonomy so the system works fully offline and the judges
can see deterministic, explainable output.

Each skill has:
  - weight: 0-1 importance of the skill for the role (mocked "% of job
    postings requiring it")
  - min_level: proficiency (1-5) generally expected for an entry-level hire
"""

ROLE_TAXONOMY = {
    "Frontend Developer": {
        "skills": {
            "HTML/CSS": {"weight": 0.95, "min_level": 4},
            "JavaScript": {"weight": 0.95, "min_level": 4},
            "React": {"weight": 0.85, "min_level": 3},
            "TypeScript": {"weight": 0.55, "min_level": 3},
            "Git": {"weight": 0.80, "min_level": 3},
            "REST APIs": {"weight": 0.70, "min_level": 3},
            "Testing (Jest/RTL)": {"weight": 0.45, "min_level": 2},
            "Accessibility (a11y)": {"weight": 0.35, "min_level": 2},
            "Web Performance": {"weight": 0.30, "min_level": 2},
        }
    },
    "Backend Developer": {
        "skills": {
            "Python or Java or Node.js": {"weight": 0.95, "min_level": 4},
            "SQL / Databases": {"weight": 0.90, "min_level": 4},
            "REST API Design": {"weight": 0.85, "min_level": 3},
            "Git": {"weight": 0.80, "min_level": 3},
            "System Design Basics": {"weight": 0.60, "min_level": 2},
            "Docker": {"weight": 0.55, "min_level": 2},
            "Cloud (AWS/GCP/Azure)": {"weight": 0.55, "min_level": 2},
            "Testing & CI/CD": {"weight": 0.45, "min_level": 2},
            "Message Queues": {"weight": 0.25, "min_level": 1},
        }
    },
    "Data Analyst": {
        "skills": {
            "SQL": {"weight": 0.95, "min_level": 4},
            "Excel/Sheets": {"weight": 0.80, "min_level": 3},
            "Python (pandas)": {"weight": 0.75, "min_level": 3},
            "Data Visualization": {"weight": 0.70, "min_level": 3},
            "Statistics Fundamentals": {"weight": 0.65, "min_level": 3},
            "BI Tools (Power BI/Tableau)": {"weight": 0.55, "min_level": 2},
            "A/B Testing": {"weight": 0.30, "min_level": 1},
        }
    },
    "ML / AI Engineer": {
        "skills": {
            "Python": {"weight": 0.95, "min_level": 4},
            "Machine Learning Fundamentals": {"weight": 0.90, "min_level": 3},
            "PyTorch/TensorFlow": {"weight": 0.75, "min_level": 3},
            "SQL": {"weight": 0.60, "min_level": 2},
            "Statistics & Probability": {"weight": 0.70, "min_level": 3},
            "Model Deployment (APIs/Docker)": {"weight": 0.50, "min_level": 2},
            "LLM/Prompt Engineering": {"weight": 0.45, "min_level": 2},
            "Data Engineering Basics": {"weight": 0.35, "min_level": 1},
        }
    },
    "Product Manager": {
        "skills": {
            "Product Discovery & Research": {"weight": 0.85, "min_level": 3},
            "Roadmapping & Prioritization": {"weight": 0.85, "min_level": 3},
            "Analytics/SQL Basics": {"weight": 0.60, "min_level": 2},
            "Wireframing (Figma)": {"weight": 0.50, "min_level": 2},
            "Stakeholder Communication": {"weight": 0.80, "min_level": 3},
            "A/B Testing & Metrics": {"weight": 0.55, "min_level": 2},
            "Technical Fluency": {"weight": 0.45, "min_level": 2},
        }
    },
}


def list_roles():
    return list(ROLE_TAXONOMY.keys())


def get_role_skills(role_title: str):
    """Case-insensitive lookup with a safe fallback for unknown/custom roles."""
    for name, data in ROLE_TAXONOMY.items():
        if name.lower() == role_title.strip().lower():
            return name, data["skills"]
    # Graceful fallback: unknown role -> generic, low-confidence baseline
    return role_title, {
        "Core Technical Skill": {"weight": 0.8, "min_level": 3},
        "Tooling & Version Control (Git)": {"weight": 0.6, "min_level": 3},
        "Communication": {"weight": 0.5, "min_level": 3},
        "Problem Solving": {"weight": 0.5, "min_level": 3},
    }
