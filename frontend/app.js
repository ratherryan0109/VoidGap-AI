// Point this at your running backend (see backend/README instructions).
const API_BASE = "http://localhost:8000";

let state = {
  studentId: null,
  roleOptions: [],
};

// ---------- View switching ----------
function showView(id) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

// ---------- Dynamic rows: skills ----------
function addSkillRow(skill = "", level = 3) {
  const wrap = document.getElementById("skillRows");
  const row = document.createElement("div");
  row.className = "skill-row";
  row.innerHTML = `
    <input type="text" placeholder="e.g. Python" class="skill-name" value="${skill}" />
    <select class="skill-level">
      ${[1, 2, 3, 4, 5].map((l) => `<option value="${l}" ${l == level ? "selected" : ""}>Level ${l}</option>`).join("")}
    </select>
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>`;
  wrap.appendChild(row);
}

function addProjectRow(title = "", desc = "") {
  const wrap = document.getElementById("projectRows");
  const row = document.createElement("div");
  row.className = "project-row";
  row.innerHTML = `
    <input type="text" placeholder="Project title" class="project-title" value="${title}" />
    <input type="text" placeholder="One-line description" class="project-desc" value="${desc}" />
    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>`;
  wrap.appendChild(row);
}

document.getElementById("addSkillRow").onclick = () => addSkillRow();
document.getElementById("addProjectRow").onclick = () => addProjectRow();
// seed with a couple of empty rows so the form isn't intimidating
addSkillRow(); addSkillRow();
addProjectRow();

// ---------- Step 1 -> 2 ----------
document.getElementById("toRoleBtn").onclick = async () => {
  const name = document.getElementById("studentName").value.trim();
  if (!name) return alert("Please enter your name.");

  const skills = [...document.querySelectorAll(".skill-row")]
    .map((r) => ({
      skill: r.querySelector(".skill-name").value.trim(),
      level: parseInt(r.querySelector(".skill-level").value, 10),
    }))
    .filter((s) => s.skill);

  const projects = [...document.querySelectorAll(".project-row")]
    .map((r) => ({
      title: r.querySelector(".project-title").value.trim(),
      description: r.querySelector(".project-desc").value.trim(),
      skills: [],
    }))
    .filter((p) => p.title);

  const github = document.getElementById("githubUsername").value.trim() || null;

  try {
    const res = await fetch(`${API_BASE}/api/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_name: name,
        current_skills: skills,
        projects,
        github_username: github,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.studentId = data.student_id;
    await loadRoles();
    showView("view-role");
  } catch (err) {
    alert("Couldn't save your profile. Is the backend running? " + err.message);
  }
};

async function loadRoles() {
  const res = await fetch(`${API_BASE}/api/roles`);
  const data = await res.json();
  state.roleOptions = data.roles;
  const sel = document.getElementById("roleSelect");
  sel.innerHTML = data.roles.map((r) => `<option value="${r}">${r}</option>`).join("");
}

document.getElementById("backToProfile").onclick = () => showView("view-profile");

// ---------- Step 2 -> 3 ----------
document.getElementById("analyzeBtn").onclick = async () => {
  const custom = document.getElementById("customRole").value.trim();
  const roleTitle = custom || document.getElementById("roleSelect").value;
  const jd = document.getElementById("jobDescription").value.trim();

  try {
    const res = await fetch(`${API_BASE}/api/target-role`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: state.studentId,
        role_title: roleTitle,
        job_description: jd,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderDashboard(data.canonical_role, data.gaps, data.roadmap, data.explanations_from_llm);
    showView("view-dashboard");
  } catch (err) {
    alert("Couldn't run the analysis. Is the backend running? " + err.message);
  }
};

document.getElementById("backToRole").onclick = () => showView("view-role");

// ---------- Dashboard rendering ----------
function renderDashboard(role, gaps, roadmap, llmUsed) {
  document.getElementById("dashRoleTitle").textContent = `Roadmap → ${role}`;

  const badge = document.getElementById("llmBadge");
  badge.textContent = llmUsed ? "✦ AI-explained" : "Rule-based fallback (no API key set)";
  badge.className = "badge" + (llmUsed ? " llm" : "");

  const gapList = document.getElementById("gapList");
  gapList.innerHTML = gaps
    .map((g) => {
      const pct = Math.min(100, (g.current_level / 5) * 100);
      const met = g.status === "met";
      return `
      <div class="gap-card ${met ? "met" : ""}">
        <div class="gap-card-top">
          <span class="gap-skill">${g.skill}</span>
          <span class="tag ${met ? "met" : ""}">${met ? "On track" : `Gap: ${g.target_level - g.current_level} lvl`}</span>
        </div>
        <div class="gap-meter"><div class="gap-meter-fill" style="width:${pct}%"></div></div>
        <div class="gap-explain">${g.explanation}</div>
      </div>`;
    })
    .join("");

  renderRoadmap(roadmap);
}

function renderRoadmap(roadmap) {
  const list = document.getElementById("roadmapList");
  if (roadmap.length === 0) {
    list.innerHTML = `<p class="muted">No gaps left — you meet the bar on every tracked skill for this role. 🎉</p>`;
    updateProgress(roadmap);
    return;
  }
  list.innerHTML = roadmap
    .map(
      (item) => `
      <div class="roadmap-card">
        <div class="roadmap-rank">${item.priority_rank}</div>
        <div class="roadmap-body">
          <div class="roadmap-skill">${item.skill}</div>
          <div class="roadmap-reason">${item.reason || ""}</div>
          ${item.suggested_project ? `<div class="roadmap-project">💡 ${item.suggested_project}</div>` : ""}
          <select class="status-select" data-id="${item.id}" onchange="onStatusChange(this)">
            <option value="pending" ${item.status === "pending" ? "selected" : ""}>Not started</option>
            <option value="in_progress" ${item.status === "in_progress" ? "selected" : ""}>In progress</option>
            <option value="done" ${item.status === "done" ? "selected" : ""}>Done</option>
          </select>
        </div>
      </div>`
    )
    .join("");
  updateProgress(roadmap);
}

async function onStatusChange(selectEl) {
  const itemId = selectEl.dataset.id;
  const status = selectEl.value;
  await fetch(`${API_BASE}/api/progress`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: parseInt(itemId, 10), status }),
  });
  const state_ = await fetchState();
  updateProgress(state_.roadmap);
}

function updateProgress(roadmap) {
  const total = roadmap.length;
  const done = roadmap.filter((r) => r.status === "done").length;
  const pct = total ? Math.round((100 * done) / total) : 0;
  document.getElementById("progressFill").style.width = pct + "%";
  document.getElementById("progressLabel").textContent = `${pct}% complete (${done}/${total})`;
}

async function fetchState() {
  const res = await fetch(`${API_BASE}/api/state/${state.studentId}`);
  return res.json();
}

// ---------- Recompute (adaptive roadmap) ----------
document.getElementById("recomputeBtn").onclick = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/recompute/${state.studentId}`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderDashboard(data.canonical_role, data.gaps, data.roadmap, data.explanations_from_llm);
  } catch (err) {
    alert("Recompute failed: " + err.message);
  }
};
