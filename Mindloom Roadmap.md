*Connecting the threads of your day*

# 🧠 Personal Assistant Roadmap

An offline-first, GPT-augmented assistant that helps manage life areas, projects, recurring tasks, and energy, integrating with Obsidian, calendars, GitHub, and more.

---

## 🔰 PHASE 1: Foundation – Context Engine + Prompt Modes

### 🎯 Goal:
Build the assistant core: life-area context, Obsidian integration, a structured task system, and basic GPT-powered prompts.

### ✅ Tasks:

- [x] **Define life area taxonomy**
  - Writing, coding, photography, home, health, etc.
  - Store as YAML or JSON (`life_areas.yaml`)

- [x] **Parse Obsidian project notes**
  - Walk `/Projects/` folder
  - Extract frontmatter: `status`, `area`, `effort`, `due`
  - Extract task checkboxes and summarize content

- [x] **Design task schema**
  - Fields: `id`, `title`, `area`, `type`, `due`, `recurrence`, `effort`, `energy_cost`, `status`, `last_completed`
  - Store as `tasks.yaml` or SQLite

- [X] **Allow daily energy/mood input**
  - CLI/PWA toggle or slider
  - Save with timestamp

- [ ] **Build GPT prompt templates**
  - Morning planner: inputs = energy, time blocks, tasks
  - Task explainer: “Break this goal down”
  - Light/Medium/Heavy plan selector
  - Reflection prompt: “What went well? What to adjust?”

- [ ] **FastAPI endpoints**
  - `GET /projects`
  - `GET /tasks`
  - `POST /plan` (generates daily plan via GPT)
  - `POST /goal-breakdown` (expands goal into tasks)

---

## 🛠️ PHASE 2: Enrichment – Recurrence + Time Awareness

### 🎯 Goal:
Make task tracking sensitive to time, energy, and recurring schedules.

### ✅ Tasks:

- [ ] **Implement recurring task logic**
  - Track `recurrence` (daily, weekly, monthly)
  - Calculate due date from `last_completed`
  - Flag tasks due today

- [ ] **Integrate calendar (Google/Outlook or .ics)**
  - Pull today’s events (via API or file)
  - Calculate free time blocks
  - Cache events to reduce API hits

- [ ] **Expose calendar to GPT planner**
  - Provide list of free blocks + their lengths
  - Inject as context into planning prompt

- [ ] **Add energy-aware planning**
  - Each task has an `energy_cost`
  - GPT plans within a max daily energy budget
  - Avoids stacking too much work

- [ ] **Implement plan intensity presets**
  - Light = 1 must-do + 1 easy task
  - Medium = 3 tasks, balanced load
  - Full = 4–5 tasks, productivity mode

- [ ] **Weekly “No Plan” day**
  - Allow scheduling recovery or creativity day
  - GPT avoids assigning tasks on that day

---

## 🔁 PHASE 3: Goal Expansion & Task Breakdown

### 🎯 Goal:
Let users write high-level goals and have the assistant break them into step-by-step tasks based on time, energy, and domain.

### ✅ Tasks:

- [ ] **Input UI/API for goal**
  - Text input: “Redesign photo portfolio”
  - Optional fields: domain, due, energy level, preferred task size

- [ ] **Run GPT breakdown prompt**
  - Outputs subtasks with sequence, effort, and estimated time
  - Output format: YAML/JSON tasks

- [ ] **Store and link subtasks to parent goal**
  - Use `parent_id` field
  - Allow navigation from goal → subtasks → status

- [ ] **Enable recursive breakdown**
  - Ask GPT to split any one task into smaller steps
  - Used when task is stuck or too vague

- [ ] **Display next step per goal in dashboard**
  - “You’re here in this project. Next step is…”

---

## 🔌 PHASE 4: Integrations

### 🎯 Goal:
Import tasks and context from key external sources: GitHub, Git repos, Docker, and Obsidian.

### ✅ Tasks:

- [ ] **GitHub adapter**
  - Pull open issues from selected repos
  - Pull open PRs
  - Parse labels, priorities, assignments
  - Format as tasks with `source: github`

- [ ] **Parse local TODOs in Git repo**
  - Run `git grep 'TODO'`
  - Extract line + file
  - Store as `source: code` with link to line

- [ ] **Scan unmerged branches**
  - List WIP branches not merged into `main`
  - Suggest action: complete or archive

- [ ] **Docker/Dockge integration**
  - Poll API for container health
  - Parse logs for recent failures
  - Alert when service is down or backup failed

- [ ] **Enrich Obsidian parser**
  - Detect backlinks
  - Parse tags (`#project`, `#blocked`)
  - Support daily notes summary

---

## 🖥️ PHASE 5: UI – Dashboard and Interaction

### 🎯 Goal:
Create a friendly interface for daily planning, tracking, and reflection.

### ✅ Tasks:

- [ ] **Build local web app (PWA-ready)**
  - Tailwind UI with React or Svelte
  - Dark mode and mobile-friendly

- [ ] **Dashboard view**
  - Energy tracker (slider)
  - Suggested plan (top 3 tasks)
  - Calendar events + free time
  - “Next step” per project
  - Plan intensity toggle (light/med/full)

- [ ] **Task Interaction**
  - Mark done / snooze / forget
  - Add new task or goal manually

- [ ] **GPT Interaction Modes**
  - Ask about project state
  - Ask for recovery or creativity suggestions
  - Explore stalled tasks

---

## 🌱 PHASE 6: Smart Behaviors and Nudging

### 🎯 Goal:
Make the assistant helpful even when you don’t ask, and kinder when things slip.

### ✅ Tasks:

- [ ] **Weekly review mode**
  - GPT summarizes what you did
  - Highlights skipped or stale tasks
  - Suggests project rebalancing

- [ ] **Soft-deadline expiration**
  - Low-priority tasks expire if untouched after X days
  - GPT asks if you want to “forget” or “reschedule”

- [ ] **Mood-aware guidance**
  - On low energy days, GPT offers:
    - Encouragement
    - Easy wins
    - Non-task suggestions (reflect, journal, sort photos)

- [ ] **Suggestion mode without planning**
  - Offer “do less today” paths: journaling, review, light creative task
  - Replaces aggressive productivity with well-being

---

## 📁 Optional Add-Ons (Future)

- [ ] Sync wearable data (e.g. steps or sleep from Android Health Connect)
- [ ] Import from Last.fm or Jellyfin for creative mood triggers
- [ ] Voice assistant mode (Whisper input + TTS output)
- [ ] GPT memory trimming + logging
