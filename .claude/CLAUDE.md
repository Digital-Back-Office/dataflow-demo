# dataflow-demo

---

## STRICT RULES — Read and follow these before doing anything else

### Git workflow — MUST run before starting any project work

1. **Stash uncommitted changes** — run `git status`. If there are any uncommitted changes (staged or unstaged), stash them with a descriptive name: `git stash push -u -m "<project>: <short description of what was in progress>"`. Never discard or overwrite uncommitted work.
2. **Checkout main and pull** — run `git checkout main && git pull origin main`.
3. **Stop on conflicts** — if the pull produces merge conflicts, stop immediately and ask the user to resolve them. Do not attempt to auto-resolve conflicts.
4. **Create a feature branch** — once main is clean and up to date, create a descriptive branch: `git checkout -b <project-name>/<short-description>` (e.g. `eu-electricity-pulse/add-dbt-models`). All project work goes on this branch.

### Project structure rules — non-negotiable

1. **dbt inside dags/ when run via Airflow.** If dbt is triggered from an Airflow DAG, the entire dbt project must live at `airflow/dags/dbt/`, not at the project root. There must be no top-level `dbt/` folder in projects that use Airflow + dbt together.

2. **All Airflow dependencies co-located in dags/.** Any data files, SQL scripts, config files, seed CSVs, or other files referenced by a DAG must live inside `airflow/dags/` at the same level as the DAG file (or in a subdirectory of it). Never reference files outside the `dags/` directory from a DAG.

3. **Relative paths only.** All file references within DAG code and dbt profiles must use paths relative to the DAG file (`os.path.dirname(__file__)` as the base). Never use absolute paths. Airflow in production runs on a different server where absolute paths will break.

---

## What this repo is

This is the official demo repository for [dataflow.zone](https://dataflow.zone) — a platform where users can host Airflow, Streamlit apps, Dash apps, and dbt projects with full infrastructure managed by Dataflow.

**Purpose:** Every project here is a marketing asset. The audience is a developer or data engineer evaluating whether to use Dataflow. Projects must be impressive enough to make them think "I want to build that, and I want to host it on Dataflow." Nothing generic. Nothing that could run equally well on any other platform.

## The Dataflow component stack

Each project uses one or more of these components:

| Component | Role | When to use |
|---|---|---|
| **Airflow** | Data pipeline / ETL | Any project that ingests, schedules, or processes data from external sources |
| **Streamlit** | Interactive data app | Exploratory UIs, chat interfaces, data exploration tools |
| **Dash** | Dashboard / visualisation app | Polished dashboards, map-heavy apps, multi-page analytics |
| **dbt** | Data transformation | When raw data needs multi-step SQL transformation before visualisation |
| **Custom Docker image** | Any web app (React, Next.js, FastAPI, etc.) | When a richer UI would meaningfully increase the wow-factor or usability of the demo — e.g. real-time interactions, polished animations, complex layouts that Streamlit/Dash would make clunky. The image must expose a single HTTP port. |

**Docker is a first-class option.** Choose Streamlit or Dash when they naturally fit the UI. Choose a custom Docker image (React, Next.js, etc.) when it would deliver a noticeably better demo experience. The question is always: what makes this app most impressive and usable for someone evaluating Dataflow?

## Dataflow-specific conventions

- **Connection names** are project-specific, lowercase, and use only letters, numbers, and underscores (e.g. `flight_db`, `nasa_db`, `scout_db`). Never use a generic name like `demo_db`. Never hardcode connection strings.
- **Secret/variable names** follow the same rule — lowercase, letters/numbers/underscores only (e.g. `nasa_api_key`, `gemini_api_key`). Accessed via `Variable.get('secret_name')` or `BaseHook.get_connection('conn_name')` in Airflow tasks.
- Every project README must include: Prerequisites (exact connection and secret names to create in Dataflow console), how to start each component, and a brief architecture overview

## Project folder structure

```
project-name/
├── airflow/
│   └── dags/
│       ├── my_dag.py
│       ├── dbt/               # dbt lives HERE when run via Airflow — co-located with DAG files
│       │   ├── dbt_project.yml
│       │   └── models/
│       └── data/              # any data files or static dependencies also go here
├── streamlit/          # or dashapp/
│   └── app.py
├── requirements.txt
└── README.md
```

## Existing projects

| Project | Components | Topic |
|---|---|---|
| Demo 1 - Flight Delay Analysis | Airflow + Streamlit | BTS flight data, delay analysis, airline performance |
| Demo 2 - Nasa Data Analysis | Airflow + Dash | NASA APIs, space data dashboard |
| neighbourhood_scout | Airflow + dbt + Dash + Streamlit | UK crime & hygiene data, GRIT safety scoring, map |
| Legislative-watchdog-main | Airflow + Streamlit | UK parliamentary bills tracker |
| Movie-Night-Recommendation-main | Dash | Collaborative movie recommendations, semantic search |
| Recipe_Generator-main | Streamlit | AI recipe generation |
| Resume_Scanner-Optimizer-main | Streamlit | ATS resume scoring and optimisation |
| BackgroundRemoval-main | Streamlit | ML background removal tool |
| prettymapp-main | Streamlit | OSM map art generator |

## What makes a project impressive for this repo

- Uses real, live public data (not static CSVs)
- The pipeline does something non-trivial (not just download and store)
- The UI tells a story — there's a "so what" the user gets immediately
- Showcases multiple Dataflow components working together
- Timely — connected to something people care about right now
- Not already done to death (no generic stock price dashboards, weather apps)

## Agent usage

- `/new-project` — research trending ideas and scaffold a new project
- `/polish <project-name>` — review and improve an existing project
- `/add-component <project> <component>` — add a missing component to an existing project
