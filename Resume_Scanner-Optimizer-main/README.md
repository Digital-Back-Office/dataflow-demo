# Resume ATS Scanner & Optimizer

A comprehensive tool to analyze, optimize, and generate ATS-friendly resumes tailored to specific job descriptions.

## Features

- **Resume Parsing**: Extract content from PDF and DOCX files
- **Job Description Analysis**: Parse and analyze job requirements
- **ATS Match Scoring**: Calculate explainable ATS compatibility scores
- **Keyword Gap Analysis**: Identify missing and weak keywords
- **AI-Powered Suggestions**: Get targeted bullet point improvements
- **ATS Formatting Detection**: Detect formatting issues that may hurt ATS parsing
- **LaTeX Resume Generation**: Generate clean, ATS-friendly optimized resumes
- **PDF Export**: Compile and download optimized resumes as PDFs

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Download spaCy model:
   ```bash
   python -m spacy download en_core_web_sm
   ```
4. Set up your API keys in the `.env` file

## Usage

Run the Streamlit app:
```bash
streamlit run app.py
```

## Tech Stack

- **Backend**: Python
- **Parsing**: pdfplumber, python-docx, spaCy
- **AI**: Groq/OpenRouter APIs
- **UI**: Streamlit
- **Resume Generation**: LaTeX, ReportLab
