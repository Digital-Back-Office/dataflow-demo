# ⚖️ Legal Document Summarizer

An intelligent **Legal Document Analysis** system powered by reasoning-based RAG. Upload legal documents (contracts, agreements, policies) and get:

- **Legal Document Summarization** — Executive and section-level summaries
- **Risk Detection** — Identify unfavorable clauses, liabilities, missing protections, ambiguous terms
- **Renewal & Expiry Tracking** — Detect renewal dates, expiry clauses, auto-renewal terms
- **Page-Level Intelligence** — Per-page importance scoring and topic analysis
- **Reasoning-Based Legal Q&A** — Ask legal questions with chain-of-thought reasoning
- **Document Viewer** — View uploaded PDFs directly in the browser
- **Local Embeddings** — SentenceTransformers (no API cost for embeddings)
- **ChromaDB** — Persistent vector storage with page-level metadata
- **Groq LLM** — Free tier with context optimization

## 🏗️ Architecture

```
Doc-summarize/
│
├── docs_ingestion/           # Document ingestion pipeline
│   ├── doc_loader.py         # Multi-format loader with page-level extraction
│   ├── clean_text.py         # Text preprocessing
│   ├── chunk_docs.py         # Page-aware document chunking
│   └── scrape_docs.py        # Web scraper (optional)
│
├── rag_pipeline/             # Reasoning-based RAG components
│   ├── embeddings.py         # Local SentenceTransformers embeddings
│   ├── vector_store.py       # ChromaDB with page metadata
│   ├── retriever.py          # Context-optimized retrieval
│   └── qa.py                 # Reasoning-based legal Q&A
│
├── summarization/            # Legal summary generation
│   ├── section_summary.py    # Per-document legal summaries
│   ├── executive_summary.py  # High-level legal overview
│   └── faq_generator.py      # Legal FAQ generation
│
├── legal_analysis/           # Legal-specific analysis modules
│   ├── risk_detector.py      # Risk detection (clauses, liabilities)
│   ├── renewal_detector.py   # Renewal & expiry detection
│   └── page_analyzer.py      # Page importance scoring
│
├── app.py                    # Streamlit web UI
├── main.py                   # CLI application
├── requirements.txt          # Dependencies
├── venv/                     # Python virtual environment
└── README.md
```

## 🚀 Quick Start

### 1. Set Up Virtual Environment

```bash
# Create venv (already created)
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up API Key

Create a `.env` file:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Launch Streamlit UI (Recommended)

```bash
streamlit run app.py
```

Or via CLI:

```bash
python main.py ui
```

Open **http://localhost:8501** in your browser.

### 5. Upload & Analyze via CLI

```bash
python main.py upload --files contract.pdf agreement.docx
python main.py summarize
python main.py ask "What are the termination conditions?"
```

## 🔧 Features

### 📤 Document Upload
- Supports PDF, DOCX, TXT, MD formats
- Up to 3 documents at a time
- Page-level text extraction for PDFs

### 📄 Document Viewer
- View uploaded PDFs directly in the browser
- Navigate pages and see page-level text

### 📑 Page-Level Intelligence
- Each page scored for importance (Critical/High/Medium/Low, 1-10)
- Per-page summaries and key legal topics extracted

### 📝 Legal Summaries
- Executive summary with legal focus (obligations, rights, risks)
- Section-by-section breakdowns

### ⚠️ Risk Detection
- Full document risk analysis
- Page-by-page risk scanning
- Categories: Unfavorable Clauses, Legal Liabilities, Missing Protections, Ambiguous Terms, Penalty Provisions, Unilateral Rights

### 🔄 Renewal & Expiry Detection
- Identifies contract start/end dates
- Detects auto-renewal and manual renewal terms
- Finds notice periods and termination conditions

### 💬 Reasoning-Based Legal Q&A
- Step-by-step reasoning through relevant clauses
- Cites specific pages and sections
- Highlights legal implications in answers

## 📖 CLI Commands

```bash
python main.py upload --files contract.pdf     # Upload documents
python main.py summarize                        # Generate summaries
python main.py ask "Your legal question"        # Ask questions
python main.py interactive                      # Interactive Q&A mode
python main.py status                           # Check knowledge base
python main.py export                           # Export to markdown
python main.py ui                               # Launch Streamlit UI
```

## 🛠️ Tech Stack

| Component | Tool |
|-----------|------|
| Web UI | Streamlit |
| Doc Loading | Custom (PDF, TXT, MD, DOCX) with page-level extraction |
| Text Processing | Custom Python |
| Chunking | Page-aware (500 words, 50 overlap) |
| Embeddings | SentenceTransformers (all-MiniLM-L6-v2) — local, no API cost |
| Vector DB | ChromaDB (persistent, cosine, page metadata) |
| LLM | Groq free tier (llama-3.1-8b-instant) |
| Legal Analysis | Risk detection, renewal detection, page importance scoring |
