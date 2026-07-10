# /new-project

Researches trending ideas and scaffolds a new dataflow-demo project.

## Usage
```
/new-project
/new-project <topic hint>
```

## What this does

**Step 1 — Research**
Spawns the `trend-scout` agent to find 3-5 project ideas. If you provided a topic hint, it focuses research there. Otherwise it does broad discovery.

**Step 2 — You select**
Review the ideas trend-scout returns. Reply with the number or title of the idea you want to build.

**Step 3 — Spec & scaffold**
Spawns the `scaffolder` agent with your chosen idea. Scaffolder produces the full implementation spec and creates the folder skeleton with stub files.

**Step 4 — Review the spec**
Read through the spec. If anything looks wrong — wrong components, wrong data source, different UI vision — say so now before implementation starts. It's easy to change the spec, hard to change after code is written.

**Step 5 — Implement**
Once you approve the spec, implementation happens in the main session. Work through the spec section by section: database schema first, then Airflow DAG, then dbt models if any, then the app UI.

---

Run the flow now:

$ARGUMENTS

Use the `trend-scout` agent to research project ideas based on the above topic (or broadly if no topic given). Present the results clearly and ask the user to select one before proceeding.
