# /add-component

Adds a missing component to an existing project.

## Usage
```
/add-component <project-folder-name> <component-type>
```

Component types: `streamlit`, `dashapp`, `airflow`, `dbt`

Examples:
```
/add-component neighbourhood_scout streamlit
/add-component "Demo 2 - Nasa Data Analysis" dbt
/add-component Movie-Night-Recommendation-main airflow
```

## What this does

1. Reads the existing project to understand its data model, database schema, and what data is already available
2. Designs how the new component fits into the existing architecture
3. Scaffolds the new component following the conventions of the existing project
4. Updates the README with the new component's setup and startup instructions

---

Project and component: $ARGUMENTS

Read the existing project first, then design and scaffold the requested component. Follow the conventions already established in the project (connection names, data patterns, import style). Present the design briefly before creating files.
