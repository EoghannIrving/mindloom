*Connecting the threads of your day*

# 🧠 Personal Assistant Roadmap

An offline-first, GPT-augmented assistant that helps manage life areas, projects, recurring tasks, and energy, integrating with Obsidian, calendars, GitHub, and more.

---

## 🔰 PHASE 1: Foundation – Context Engine + Prompt Modes

### 🎯 Goal:
Build the assistant core: life-area context, Obsidian integration, a structured task system, and basic GPT-powered prompts.

### ✅ Tasks:

[x] **Define life area taxonomy**  
  Writing, coding, photography, home, health, etc.  
  Store as YAML or JSON (`life_areas.yaml`)

[x] **Parse Obsidian project notes**  
  Walk `/Projects/` folder  
  Extract frontmatter: `status`, `area`, `effort`, `due`  
  Extract task checkboxes and summarize content

[ ] **Design task schema**  
  Fields: `id`, `title`, `area`, `type`, `due`, `recurrence`, `effort`, `energy_cost`, `status`, `last_completed`, `executive_trigger?`  
  Store as `tasks.yaml` or SQLite  
  _Future: add `activation_difficulty` for high-friction starts._

[x] **Allow daily energy/mood input**  
  CLI/PWA toggle or slider  
  Save with timestamp

[x] **Build GPT prompt templates**  
  Morning planner: inputs = energy, time blocks, tasks  
  Task explainer: “Break this goal down”  
  Light/Medium/Heavy plan selector  
  Reflection prompt: “What went well? What to adjust?”

[x] **FastAPI endpoints**  
  `GET /projects`, `GET /tasks`  
  `POST /plan` (generate daily plan via GPT)  
  `POST /goal-breakdown` (expand goal into tasks)

[ ] **Document future flexible input modes**  
  Voice, image capture, or rapid log features  
  Placeholder only; implement post-UI phase

---

## 🛠️ PHASE 2: Enrichment – Recurrence + Time Awareness

### 🎯 Goal:
Make task tracking sensitive to time, energy, and recurring schedules.

### ✅ Tasks:

[ ] Implement recurring task logic  
  Track `recurrence` field (daily, weekly, etc.)  
  Use `last_completed` to calculate next due  
  Mark tasks as due/today appropriately

[ ] Integrate calendar (Google/Outlook/.ics)  
  Import today’s events  
  Cache for quick lookup  
  Respect time zones and breaks

[ ] Expose calendar to GPT planner  
  Supply time blocks and durations as prompt context

[ ] Add energy-aware planning  
  Each task has `energy_cost`  
  GPT uses current energy to filter/sequence tasks

[ ] Implement plan intensity presets  
  Light = 1 must-do + 1 easy win  
  Medium = 3 mixed tasks  
  Full = 4–5 tasks, assumes high energy

[ ] Weekly “No Plan” day  
  GPT omits task planning to allow recharge/creativity

[ ] Time blindness helpers  
  Dashboard “time left today” indicator  
  GPT feedback like: “You have 90 mins left—1 small task?”

[ ] Flexible recurrence nudges  
  Fuzzy habits: “If not done in a while”  
  GPT can ask: “Still want this on your plate?”

---

## 🔁 PHASE 3: Goal Expansion & Task Breakdown

### 🎯 Goal:
Let users write high-level goals and have the assistant break them into step-by-step tasks based on time, energy, and domain.

### ✅ Tasks:

- Input UI/API for goal  
  Example: “Redesign photo portfolio”  
  Optional tags: domain, energy, due, emotional weight

- Run GPT breakdown prompt  
  Output: subtasks with estimated effort/time  
  Format: YAML or JSON with `parent_id`

- Store and link subtasks to parent goal  
  Enables project view and navigation

- Enable recursive breakdown  
  Ask GPT to break down vague/stuck tasks  
  Include “what’s stopping me?” logic

- Display next step per goal in dashboard  
  “Here’s what’s next for this project…”

- Gracefully handle vague or emotional goals  
  GPT offers clarification or motivational framing

- Optional emotional tag for goals  
  Identify avoidance-prone or heavy goals

---

## 🔌 PHASE 4: Integrations

### 🎯 Goal:
Import tasks and context from key external sources: GitHub, Git repos, Docker, and Obsidian.

### ✅ Tasks:

- GitHub adapter  
  Fetch open issues + PRs  
  Parse urgency, labels, assignments

- Parse TODOs from Git repos  
  Use `git grep 'TODO'`  
  Store line + file as `source: code`

- Scan unmerged branches  
  List WIP branches  
  Suggest: complete, merge, or archive

- Docker/Dockge integration  
  Monitor container health and logs  
  Alert if service down or backup fails

- Enrich Obsidian parser  
  Detect backlinks  
  Parse and classify tags  
  Summarize daily notes

- Triage mode for bulk imports  
  GPT asks: Urgent? Emotional? Backlog?  
  Prioritize with neurodivergent framing

---

## 🖥️ PHASE 5: UI – Dashboard and Interaction

### 🎯 Goal:
Create a friendly interface for daily planning, tracking, and reflection.

### ✅ Tasks:

- Build local web app (PWA-ready)  
  Use Tailwind + React or Svelte  
  Support dark mode and offline use

- Dashboard view  
  Energy slider  
  Top 3 task suggestions  
  Calendar + time-left panel  
  Plan intensity toggle  
  “You’re here” project cue

- Task Interaction  
  Mark tasks done / snoozed / forgotten  
  Add new task or goal

- GPT Interaction Modes  
  Ask about blocked tasks  
  Request gentle/creative plans  
  Explore project options

- Alternate dashboard modes  
  Focus Mode: hide all but 1–2 tasks  
  Dopamine Mode: affirmations, badge streaks

- Give-me-options selector  
  GPT offers: Easy Win / Push Forward / Feel-Good

- “No shame” UX  
  Use gentle labels: paused, awaiting  
  Avoid red overdue alerts

---

## 🌱 PHASE 6: Smart Behaviors and Nudging

### 🎯 Goal:
Make the assistant helpful even when you don’t ask, and kinder when things slip.

### ✅ Tasks:

- Weekly review mode  
  GPT summarizes wins, lapsed goals  
  Suggests balance/rescoping

- Soft-deadline expiration  
  Auto-archive stale tasks  
  GPT: “Forget, revise, or return?”

- Mood-aware guidance  
  On low energy: offer reflection or journaling  
  Avoid hard tasks

- Suggestion mode without pressure  
  Offer non-goal activities: “sort photos?”, “go for a walk?”

- Hyperfocus helper  
  GPT asks: “Want to log what you just spent time on?”

- Stall recovery prompts  
  “Want to reset?”, “Review your wins?”

---

## 📁 Optional Add-Ons (Future)

- Sync wearable data (steps, sleep, HRV)
- Import media stats from Last.fm, Jellyfin
- Voice mode (Whisper + TTS)
- Memory trimming/logging for GPT
- Flexible input capture (voice, OCR, quick log)
- Safe to Forget mode: guilt-free archival
- Spark Tracker: track what energized you
