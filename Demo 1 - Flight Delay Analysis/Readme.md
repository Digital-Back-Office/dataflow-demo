# Demo 1 - Flight Delay Analysis

## Overview

This application consists of an Airflow ETL pipeline that extracts Bureau of Transportation Statistics (BTS) flight data, processes it, and stores it in a database. The data is then visualized through a Streamlit application that provides interactive analysis of:

* Flight delays
* Airport statistics
* Airline performance

---

## Prerequisites

Before running this application, ensure the following setup is complete:

* **Database Connection**:
  Create a connection in the Dataflow console named `demo_db` that points to your target database.

* **Gemini API Key**:
  Create a secret in the Dataflow console named `gemini_api_key` containing your Google Gemini API key, used by the chatbot component.

---

## Architecture

This project follows a standard ETL (Extract, Transform, Load) pipeline with a visualization layer:

* **Extract**: Flight data is pulled from external sources using Airflow tasks.
* **Transform**: Data is cleansed, formatted, and enriched.
* **Load**: Transformed data is written into a relational database.
* **Visualize**: A Streamlit app queries the database and displays interactive charts and tables.

---

## Airflow DAG

Steps to run the data pipeline:

1. Start Airflow in the Dataflow environment.
2. Open the Airflow UI and trigger the `bts_pipeline_dag`.
3. The pipeline will:

   * Extract BTS flight data
   * Transform it using helper functions
   * Load it into the configured database
4. Monitor DAG progress in the Airflow UI.

---

## Streamlit Application

Once the data pipeline is complete, start the Streamlit application. The app includes multiple pages for data exploration:

* **Statistics**: Overview of flight data metrics
* **Delays**: In-depth analysis of delay reasons and patterns
* **Airport Maps**: Geographic mapping of airport statistics
* **Airline Performance**: Compare performance of different airlines
* **Chatbot**: AI-powered assistant for querying flight data in natural language

---