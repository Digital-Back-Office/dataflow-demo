# dataflow-demo

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
├── streamlit/          # or dashapp/
│   └── app.py
├── dbt/               # if transforms are needed
│   ├── dbt_project.yml
│   └── models/
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
