# /polish

Reviews and improves an existing project to make it more demo-ready.

## Usage
```
/polish <project-folder-name>
/polish <project-folder-name> focus on <area>
```

Examples:
```
/polish neighbourhood_scout
/polish "Demo 2 - Nasa Data Analysis" focus on visual polish
/polish Movie-Night-Recommendation-main focus on performance
```

## What this does

**Step 1 — Review**
Spawns `project-reviewer` to run smoke tests and checks on the project. Produces a prioritised finding list (P1/P2/P3).

**Step 2 — Fix P1 issues**
If there are P1 (broken) findings, fix those in the main session before proceeding to polish.

**Step 3 — Improve**
Spawns `app-improver` on the project. If you specified a focus area, it prioritises that. Otherwise it does a holistic pass covering narrative, visual polish, performance, and interactivity.

---

Project to polish: $ARGUMENTS

Start by running the `project-reviewer` agent on this project. Once the review is complete, present the findings and confirm with the user before proceeding to the improvement phase.
