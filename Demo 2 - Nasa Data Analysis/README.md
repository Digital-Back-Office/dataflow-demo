# Demo 2 - NASA Data Analysis

## Overview
This application consists of an Airflow ETL pipeline that extracts data from NASA APIs, processes it, and stores it in a database. The data is then visualized through a Dash application that reads from the database and presents the information in an interactive dashboard.

## Prerequisites
Before running this application, you need to set up the following:

1. **NASA API Key**: Create a secret in the Dataflow console named `nasa_api_key` with your NASA API key.
   
2. **Database Connection**: Create a connection in the Dataflow console named `demo_db` that points to your database.

## Architecture
The application follows a simple ETL (Extract, Transform, Load) pattern:
1. **Extract**: Data is pulled from NASA APIs using Airflow tasks
2. **Transform**: The data is processed and formatted as needed
3. **Load**: Processed data is stored in the database
4. **Visualize**: A Dash application reads from the database and presents the information

## Airflow DAG
1. Start the Airflow.
2. Navigate to the Airflow UI and trigger the NASA data ETL DAG.
3. Once the data is loaded into the database, start the Dash application

## Dashapp Application
1. Start the Dashapp.
2. The Dash application provides an interactive way to explore the NASA data. 
    It includes various visualizations and filters to help analyze the information.

## Preview

<p align="center">
<img src="https://github.com/user-attachments/assets/14e150d0-b596-4368-83b2-9d730b004115" alt="Nasa Dashapp Preview">
</p>