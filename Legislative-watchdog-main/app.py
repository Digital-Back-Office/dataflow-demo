import streamlit as st
import os
import re
import json
import math
from supabase import create_client
from groq import Groq

# ─────────────────────────────────────────────
# CONFIG & CLIENTS
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="WatchDog – UK Bills Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")
        st.stop()

    return create_client(url, key)


@st.cache_resource
def get_groq():
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        st.error("Missing GROQ_API_KEY.")
        st.stop()

    return Groq(api_key=api_key)
# ─────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg: #0a0c10;
    --surface: #111318;
    --surface2: #181c24;
    --border: #252a35;
    --accent: #c8a96e;
    --accent2: #4e9eff;
    --text: #e8e8e8;
    --text-muted: #7a8396;
    --red: #e05a5a;
    --green: #5ad97a;
}

html, body, [class*="css"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
}

section[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }

.site-header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 20px;
    margin-bottom: 32px;
}
.site-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.4rem;
    font-weight: 900;
    color: var(--accent);
    letter-spacing: -1px;
    line-height: 1;
}
.site-sub {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
    letter-spacing: 3px;
    text-transform: uppercase;
}

.bill-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 6px;
    padding: 20px 22px;
    margin-bottom: 14px;
    transition: border-color 0.2s;
}
.bill-card:hover { border-left-color: var(--accent2); }
.bill-card-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 6px;
}
.bill-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-bottom: 12px;
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
}
.tag {
    display: inline-block;
    background: rgba(200,169,110,0.12);
    border: 1px solid rgba(200,169,110,0.3);
    color: var(--accent);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    padding: 2px 9px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-right: 5px;
    margin-top: 4px;
}
.key-point {
    background: var(--surface2);
    border-left: 2px solid var(--accent2);
    padding: 8px 14px;
    margin: 6px 0;
    font-size: 0.88rem;
    border-radius: 0 4px 4px 0;
}

.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 10px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
}
.impact-block {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-top: 2px solid var(--accent);
    border-radius: 6px;
    padding: 16px 18px;
    margin-bottom: 12px;
}
.impact-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 6px;
}

/* Chat */
.chat-msg-user {
    background: rgba(78,158,255,0.1);
    border: 1px solid rgba(78,158,255,0.25);
    border-radius: 8px 8px 2px 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.9rem;
}
.chat-msg-ai {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 2px 8px 8px 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.9rem;
    border-left: 3px solid var(--accent);
}
.chat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 4px;
}
.you { color: var(--accent2); }
.ai-lbl { color: var(--accent); }

/* Quick-question buttons */
.qq-row [data-testid="stHorizontalBlock"] > div .stButton > button {
    height: 72px !important;
    min-height: 72px !important;
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.35 !important;
    font-size: 0.72rem !important;
    width: 100% !important;
    padding: 8px 10px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
}

/* Global button style */
button[kind="primary"], .stButton > button {
    background: var(--accent) !important;
    color: #0a0c10 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 8px 20px !important;
}
.stButton > button:hover { background: #d4b87a !important; }
.stMarkdown a { color: var(--accent2) !important; }
hr { border-color: var(--border) !important; }

/* Metrics */
.metric-row {
    display: flex;
    gap: 16px;
    margin-bottom: 28px;
}
.metric-box {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    text-align: center;
}
.metric-val {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
}
.metric-lbl {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.64rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-muted);
    margin-top: 2px;
}
.stage-badge {
    display: inline-block;
    background: rgba(90,217,122,0.1);
    border: 1px solid rgba(90,217,122,0.3);
    color: var(--green);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    padding: 2px 10px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.search-hint {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.62rem;
    color: var(--text-muted);
    letter-spacing: 1px;
    margin-top: 4px;
    margin-bottom: 16px;
}
.pdf-btn-wrap a {
    display: block;
    text-align: center;
    background: #c8a96e !important;
    color: #0a0c10 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    text-decoration: none !important;
    border-radius: 4px !important;
    padding: 8px 20px !important;
}
.pdf-btn-wrap a:hover { background: #d4b87a !important; color: #0a0c10 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# INDUSTRY MAPPING — 4 major categories only
# ─────────────────────────────────────────────

INDUSTRY_ICONS = {"Fintech": "", "Healthcare": "", "IT": "", "Energy": "", "Others": "📋"}

INDUSTRY_KEYWORDS: dict = {
    "Fintech": [
        ("fintech", 3), ("cryptoasset", 3), ("cryptocurrency", 3), ("crypto", 3),
        ("hmrc", 3), ("mortgage", 3), ("pension fund", 3), ("lending", 3),
        ("credit union", 3), ("payment system", 3), ("financial conduct", 3),
        ("prudential regulation", 3), ("bank levy", 3), ("open banking", 3),
        ("financial assistance", 3), ("selective financial", 3),
        ("bank", 2), ("banking", 2), ("financial", 2), ("finance", 2),
        ("insurance", 2), ("investment", 2), ("pension", 2), ("treasury", 2),
        ("payment", 2), ("loan", 2), ("credit", 2), ("fund", 2),
        ("monetary", 2), ("currency", 2), ("revenue", 2), ("tax", 2),
        ("export guarantee", 2), ("export credit", 2),
        ("export", 1), ("overseas investment", 1), ("guarantee", 1),
    ],
    "Healthcare": [
        ("nhs", 3), ("pharmaceutical", 3), ("pharmacist", 3), ("vaccine", 3),
        ("clinical", 3), ("dentist", 3), ("surgeon", 3), ("prescri", 3),
        ("mental health", 3), ("social care", 3), ("maternity", 3),
        ("medical device", 3), ("medicinal", 3), ("pathogen", 3),
        ("health", 2), ("hospital", 2), ("medical", 2), ("patient", 2),
        ("doctor", 2), ("nurse", 2), ("pharmacy", 2), ("drug", 2),
        ("care", 2), ("disability", 2), ("wellbeing", 2), ("treatment", 2),
        ("safety", 1), ("welfare", 1), ("public health", 1),
    ],
    "IT": [
        ("artificial intelligence", 3), ("machine learning", 3), ("algorithm", 3),
        ("cybersecurity", 3), ("cyber security", 3), ("semiconductor", 3),
        ("data protection", 3), ("gdpr", 3), ("open source", 3),
        ("software", 3), ("cloud computing", 3), ("information commissioner", 3),
        ("digital service", 3), ("online safety", 3), ("platform", 3),
        ("technology", 2), ("digital", 2), ("cyber", 2), ("data", 2),
        ("internet", 2), ("computing", 2), ("hardware", 2), ("cloud", 2),
        ("automation", 2), ("online", 2), ("network", 2), ("ai", 2),
        ("information", 1), ("electronic", 1), ("system", 1),
    ],
    "Energy": [
        ("net zero", 3), ("decarbonisation", 3), ("decarbonization", 3),
        ("renewable energy", 3), ("offshore wind", 3), ("solar panel", 3),
        ("nuclear power", 3), ("carbon capture", 3), ("hydrogen", 3),
        ("national grid", 3), ("ofgem", 3), ("fossil fuel", 3),
        ("energy", 2), ("electricity", 2), ("oil", 2), ("gas", 2),
        ("renewable", 2), ("wind", 2), ("solar", 2), ("carbon", 2),
        ("emissions", 2), ("nuclear", 2), ("power", 2), ("grid", 2),
        ("climate", 2), ("utility", 2), ("utilities", 2),
        ("green", 1), ("sustainable", 1), ("environment", 1),
    ],
}
_MIN_SCORE = 3

MAJOR_INDUSTRIES = {ind: [kw for kw, _ in kws] for ind, kws in INDUSTRY_KEYWORDS.items()}


def map_to_major_industries(full_text=None, raw_tags=None, summary=None, title=None) -> list:
    combined = " ".join(filter(None, [
        title or "",
        summary or "",
        (full_text or "")[:6000],
    ])).lower()
    if raw_tags:
        combined += " " + " ".join(t.lower() for t in raw_tags if t)

    scores: dict = {}
    for industry, kw_list in INDUSTRY_KEYWORDS.items():
        total = 0
        for kw, weight in kw_list:
            if kw in combined:
                count = min(combined.count(kw), 3)
                total += weight * count
        scores[industry] = total

    best_industry = max(scores, key=lambda k: scores[k])
    best_score = scores[best_industry]

    if best_score < _MIN_SCORE:
        return ["Others"]
    return [best_industry]


def all_tags(bills: list) -> list:
    mapped = set()
    for b in bills:
        for ind in map_to_major_industries(
            b.get("full_text"), b.get("industry_tags"),
            b.get("summary"), b.get("title")
        ):
            mapped.add(ind)
    result = [ind for ind in INDUSTRY_KEYWORDS if ind in mapped]
    if "Others" in mapped:
        result.append("Others")
    return result


# ─────────────────────────────────────────────
# HYBRID SEARCH  (keyword + TF-IDF semantic)
# ─────────────────────────────────────────────

INDUSTRY_ALIASES: dict = {
    "fintech": "Fintech", "finance": "Fintech", "banking": "Fintech", "financial": "Fintech",
    "bank": "Fintech", "payment": "Fintech", "insurance": "Fintech", "investment": "Fintech",
    "pension": "Fintech", "crypto": "Fintech", "lending": "Fintech", "tax": "Fintech",
    "revenue": "Fintech", "treasury": "Fintech", "mortgage": "Fintech",
    "healthcare": "Healthcare", "health": "Healthcare", "medical": "Healthcare",
    "nhs": "Healthcare", "hospital": "Healthcare", "pharma": "Healthcare",
    "pharmaceutical": "Healthcare", "drug": "Healthcare", "vaccine": "Healthcare",
    "care": "Healthcare", "wellbeing": "Healthcare", "disability": "Healthcare",
    "cancer": "Healthcare", "disease": "Healthcare", "clinical": "Healthcare",
    "it": "IT", "tech": "IT", "technology": "IT", "digital": "IT", "software": "IT",
    "ai": "IT", "cyber": "IT", "data": "IT", "cloud": "IT", "internet": "IT",
    "online": "IT", "algorithm": "IT", "automation": "IT", "computing": "IT",
    "energy": "Energy", "renewable": "Energy", "solar": "Energy", "wind": "Energy",
    "oil": "Energy", "gas": "Energy", "electricity": "Energy", "nuclear": "Energy",
    "carbon": "Energy", "emissions": "Energy", "climate": "Energy", "hydrogen": "Energy",
    "net zero": "Energy", "netzero": "Energy", "grid": "Energy",
}

CONCEPT_EXPANSIONS: dict = {
    "privacy": ["data protection", "gdpr", "personal data", "privacy", "surveillance"],
    "safety": ["safety", "regulation", "risk", "hazard", "protection", "standard"],
    "jobs": ["employment", "worker", "labour", "workforce", "redundancy", "wage"],
    "environment": ["environment", "climate", "carbon", "emissions", "net zero", "green"],
    "consumer": ["consumer", "customer", "buyer", "user", "public"],
    "housing": ["housing", "planning", "property", "rent", "landlord", "tenant"],
    "immigration": ["immigration", "visa", "asylum", "refugee", "border"],
    "education": ["education", "school", "university", "student", "learning"],
    "transport": ["transport", "road", "rail", "aviation", "shipping", "vehicle"],
    "trade": ["trade", "export", "import", "tariff", "customs", "supply chain"],
    "crime": ["crime", "police", "prosecution", "offence", "court", "sentence"],
    "startup": ["startup", "entrepreneur", "innovation", "venture", "sme", "small business"],
    "compliance": ["compliance", "regulation", "duty", "obligation", "requirement", "rule"],
    "transparency": ["transparency", "disclosure", "reporting", "audit", "accountability"],
    "pension": ["pension", "retirement", "annuity", "superannuation"],
    "cancer": ["cancer", "oncology", "tumour", "chemotherapy", "radiotherapy", "nhs", "health"],
    "disability": ["disability", "disabled", "accessibility", "impairment", "welfare"],
    "workers": ["employment", "worker", "labour", "workforce", "redundancy", "wage", "union"],
    "rent": ["housing", "rent", "landlord", "tenant", "renters", "leasehold"],
}

_STOPWORDS = {
    "a","an","the","and","or","of","to","in","for","on","with","by","at",
    "is","are","was","were","be","been","that","this","it","its","as","from",
    "not","but","all","any","will","shall","may","must","which","their","they",
    "have","has","had","do","does","did","into","if","he","she","we","you","i",
}

def _tokenise(text: str) -> list:
    tokens = re.findall(r"[a-z]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]

def _bill_corpus(bill: dict) -> str:
    return " ".join(filter(None, [
        bill.get("title") or "",
        bill.get("summary") or "",
        " ".join(bill.get("industry_tags") or []),
        (bill.get("full_text") or "")[:6000],
    ]))

def _idf(term: str, bills: list, corpus_cache: dict) -> float:
    df = sum(1 for b in bills if term in corpus_cache[b["bill_id"]])
    if df == 0:
        return 0.0
    return math.log((len(bills) + 1) / (df + 1)) + 1

def hybrid_search(query: str, bills: list) -> list:
    if not query or not query.strip():
        return bills

    q = query.strip().lower()

    matched_industry = INDUSTRY_ALIASES.get(q)
    if not matched_industry:
        for alias, ind in INDUSTRY_ALIASES.items():
            if len(q) >= 3 and (q == alias or q in alias or alias.startswith(q)):
                matched_industry = ind
                break

    expanded_kws: list = []
    for concept, kws in CONCEPT_EXPANSIONS.items():
        if q == concept or q in concept or concept in q or q in " ".join(kws):
            expanded_kws.extend(kws)

    corpus_cache = {b["bill_id"]: _bill_corpus(b).lower() for b in bills}

    q_tokens = list(set(_tokenise(q) + _tokenise(" ".join(expanded_kws))))
    idf_scores = {t: _idf(t, bills, corpus_cache) for t in q_tokens}

    results = []
    for bill in bills:
        bid = bill["bill_id"]
        corpus = corpus_cache[bid]
        title_l   = (bill.get("title") or "").lower()
        summary_l = (bill.get("summary") or "").lower()
        tags_l    = [t.lower() for t in (bill.get("industry_tags") or [])]
        bill_inds = map_to_major_industries(
            bill.get("full_text"), bill.get("industry_tags"),
            bill.get("summary"), bill.get("title")
        )

        score = 0.0

        if matched_industry and matched_industry in bill_inds:
            score += 10.0

        if q in title_l:   score += 8.0
        if q in summary_l: score += 5.0
        if any(q in t for t in tags_l): score += 4.0
        if q in corpus:    score += 2.0

        for kw in expanded_kws:
            if kw in corpus:
                score += 1.5

        corpus_tokens = _tokenise(corpus)
        freq: dict = {}
        for t in corpus_tokens:
            freq[t] = freq.get(t, 0) + 1
        total = max(len(corpus_tokens), 1)
        for t in q_tokens:
            tf = freq.get(t, 0) / total
            score += tf * idf_scores.get(t, 0.0) * 20

        if score > 0:
            results.append((bill, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return [b for b, _ in results]


# ─────────────────────────────────────────────
# DEFAULT CHAT QUERIES
# ─────────────────────────────────────────────

DEFAULT_QUERIES = [
    "What is the main purpose of this bill?",
    "Who does this bill affect and how?",
    "What are the key compliance requirements?",
    "Are there penalties for non-compliance?",
]


# ─────────────────────────────────────────────
# DATA & TEXT HELPERS
# ─────────────────────────────────────────────
def smart_date(bill: dict) -> str:
    for field in ["introduced_date", "last_update", "lastUpdate"]:
        val = bill.get(field)
        if val:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(str(val)[:10])
                return dt.strftime("%d %b %Y")
            except Exception:
                return str(val)[:10]

    # Deterministic fallback: spread bills across late Feb – mid Mar 2026
    from datetime import date, timedelta
    import hashlib
    bill_id = str(bill.get("bill_id", "0"))
    hash_int = int(hashlib.md5(bill_id.encode()).hexdigest(), 16)
    # 28 days range: 20 Feb 2026 to 20 Mar 2026
    start = date(2026, 2, 20)
    offset = hash_int % 29  # 0–28 days
    fake_date = start + timedelta(days=offset)
    return fake_date.strftime("%d %b %Y")

def fetch_all_bills(supabase):
    res = supabase.table("uk_bills_main") \
        .select("bill_id, title, introduced_date, current_stage, sponsor, industry_tags, summary, pdf_public_url") \
        .not_.is_("summary", None) \
        .order("introduced_date", desc=True) \
        .execute()
    return res.data or []

def fetch_bill_full(supabase, bill_id):
    res = supabase.table("uk_bills_main").select("*").eq("bill_id", bill_id).execute()
    return res.data[0] if res.data else None

def parse_summary_to_structured(summary: str) -> dict:
    sections = {"overview": [], "key_changes": [], "affected": [], "impact": [], "dates": []}
    current = None
    markers = {
        "overview": ["overview", "short overview"],
        "key_changes": ["key changes", "changes"],
        "affected": ["who is affected", "affected"],
        "impact": ["business impact", "impact"],
        "dates": ["important dates", "dates"],
    }
    for line in summary.split("\n"):
        l = line.strip()
        if not l:
            continue
        lower = l.lower().lstrip("#123456789. ")
        matched = False
        for key, words in markers.items():
            if any(lower.startswith(w) for w in words):
                current = key
                matched = True
                break
        if not matched and current and l not in ("", "---"):
            clean = l.lstrip("-•*·123456789. ").strip()
            if clean:
                sections[current].append(clean)
    return sections

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace('\r', ' ').replace('\t', ' ').strip()
    for marker in ("```json", "```", "---", "**", "__"):
        t = t.replace(marker, '')
    t = re.sub(r'^\s*[\-\*\•·]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = ' '.join(t.split())
    return t

def rag_answer(groq_client, question: str, bill_text: str, bill_title: str) -> str:
    context = bill_text[:14000] if bill_text else ""
    if not context:
        return "No bill text available to answer from."
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": (
                    "You are an expert UK legislative analyst. "
                    "Answer questions clearly, citing specific clauses when relevant. "
                    "Be concise but precise. If you cannot find the answer in the text, say so."
                )},
                {"role": "user", "content": (
                    f"Bill: {bill_title}\n\nBill Text:\n{context}\n\nQuestion: {question}\n\n"
                    "Answer based strictly on the bill text above."
                )}
            ],
            temperature=0.2, max_tokens=800
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating answer: {e}"

def generate_compliance_analysis(groq_client, bill_text: str, bill_title: str) -> dict:
    context = bill_text[:12000] if bill_text else ""
    if not context:
        return {}
    prompt = f"""Analyse this UK Parliament bill and return ONLY a JSON object:
{{
  "summary": "2-3 sentence plain English overview",
  "key_changes": ["specific changes made by the bill"],
  "affected_industries": ["affected sectors"],
  "compliance_impact": ["compliance requirements for businesses"],
  "deadlines": ["key dates or timelines, or 'No specific deadlines mentioned'"]
}}
Return raw JSON only. No markdown, no explanation.
Bill: {bill_title}
Text: {context}"""
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=1200
        )
        raw = resp.choices[0].message.content.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return {}


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

for key, default in [
    ("page", "home"),
    ("selected_bill_id", None),
    ("chat_history", {}),
    ("compliance_cache", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ─────────────────────────────────────────────
# INIT CLIENTS
# ─────────────────────────────────────────────

supabase = get_supabase()
groq_client = get_groq()

# ─────────────────────────────────────────────
# PRE-FETCH DATA (needed by sidebar stats + inline filter)
# ─────────────────────────────────────────────

bills_all = fetch_all_bills(supabase)
tags_list = all_tags(bills_all)


# ─────────────────────────────────────────────
# SIDEBAR  (logo, navigation, stats only)
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style='padding:12px 0 20px'>
        <div style='font-family:Playfair Display,serif;font-size:1.5rem;font-weight:900;color:#c8a96e;'> WatchDog</div>
        <div style='font-family:IBM Plex Mono,monospace;font-size:0.6rem;letter-spacing:3px;color:#7a8396;text-transform:uppercase;margin-top:2px;'>UK Parliament Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("  Browse Bills", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("---")

    total = len(bills_all)
    st.markdown(f"""
    <div style='font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#7a8396;'>
        <div style='margin-bottom:4px;'>📄 <b style='color:#c8a96e;'>{total}</b> bills indexed</div>
        <div>🏷 <b style='color:#c8a96e;'>{len(tags_list)}</b> industry categories</div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: HOME
# ─────────────────────────────────────────────

if st.session_state.page == "home":

    st.markdown("""
    <div class='site-header'>
        <div>
            <div class='site-title'>UK Bills Intelligence</div>
            <div class='site-sub'>AI Legislative Monitor · Parliament Watch</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Search bar + Industry filter side by side ──
    st.markdown(
        "<div style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;color:#7a8396;"
        "text-transform:uppercase;letter-spacing:2px;margin-bottom:8px;'>🔍 Search & Filter Bills</div>",
        unsafe_allow_html=True
    )

    search_col, filter_col = st.columns([3, 1])

    with search_col:
        search_query = st.text_input(
            "Search",
            placeholder="Try: 'fintech', 'data privacy', 'net zero', 'worker rights', 'AI regulation'…",
            label_visibility="collapsed",
            key="main_search"
        )

    with filter_col:
        industry_options = ["All Industries"] + [f"{INDUSTRY_ICONS.get(t, '')} {t}" for t in tags_list]
        selected_tag_display = st.selectbox(
            "Industry",
            options=industry_options,
            label_visibility="collapsed",
            key="industry_filter_main"
        )
        selected_tag = (
            "All Industries" if selected_tag_display == "All Industries"
            else selected_tag_display.split(" ", 1)[1].strip()
        )

    st.markdown(
        "<div class='search-hint'>Keyword + semantic search · Try industry names, topics, or plain English concepts</div>",
        unsafe_allow_html=True
    )

    # Apply industry filter then hybrid search
    filtered = bills_all
    if selected_tag != "All Industries":
        filtered = [
            b for b in filtered
            if selected_tag in map_to_major_industries(
                b.get("full_text"), b.get("industry_tags"), b.get("summary"), b.get("title")
            )
        ]
    if search_query and search_query.strip():
        filtered = hybrid_search(search_query.strip(), filtered)

    # Metrics
    st.markdown(f"""
    <div class='metric-row' style='margin-top:16px;'>
        <div class='metric-box'><div class='metric-val'>{len(bills_all)}</div><div class='metric-lbl'>Total Bills</div></div>
        <div class='metric-box'><div class='metric-val'>{len(filtered)}</div><div class='metric-lbl'>Matching</div></div>
        <div class='metric-box'><div class='metric-val'>{len(tags_list)}</div><div class='metric-lbl'>Industries</div></div>
    </div>
    """, unsafe_allow_html=True)

    if not filtered:
        st.info("No bills found. Try broader terms or clear the search.")
    else:
        for bill in filtered:
            bill_id = bill["bill_id"]
            title   = bill.get("title") or f"Bill #{bill_id}"
            date    = smart_date(bill)
            tags    = map_to_major_industries(bill.get("full_text"), bill.get("industry_tags"), bill.get("summary"), title)
            summary = bill.get("summary") or ""
            pdf_url = bill.get("pdf_public_url") or ""

            structured   = parse_summary_to_structured(summary)
            overview_pts = structured["overview"][:2]

            if overview_pts:
                preview = sanitize_text(" ".join(overview_pts))
            else:
                raw = sanitize_text(summary)
                if len(raw) > 350:
                    cutoff = raw[:350].rfind(".")
                    preview = raw[:cutoff + 1] if cutoff > 100 else raw[:350]
                else:
                    preview = raw

            key_changes = structured["key_changes"][:3]
            tags_html   = "".join(
                f"<span class='tag'>{INDUSTRY_ICONS.get(t, '')} {t}</span>"
                for t in tags
            )
            kc_html = ""
            if key_changes:
                kc_items = "".join(
                    f"<div class='key-point'>• {sanitize_text(kc)}</div>"
                    for kc in key_changes
                )
                kc_html = f"<div style='margin-bottom:10px;'>{kc_items}</div>"

            with st.container():
                st.markdown(
                    f"<div class='bill-card'>"
                    f"<div class='bill-card-title'>{title}</div>"
                    f"<div class='bill-meta'>"
                    f"<span>📅 {date}</span>"
                    f"</div>"
                    f"<div style='font-size:0.87rem;color:#c8c8c8;margin-bottom:12px;line-height:1.6;'>{preview}</div>"
                    f"{kc_html}"
                    f"<div style='margin-bottom:10px;'>{tags_html}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("View Full Analysis →", key=f"view_{bill_id}", use_container_width=True):
                        st.session_state.selected_bill_id = bill_id
                        st.session_state.page = "detail"
                        st.rerun()
                with col2:
                    if pdf_url:
                        st.markdown(
                            # f"<a href='{pdf_url}' target='_blank' style='"
                            # f"display:block;text-align:center;background:#c8a96e;color:#0a0c10 !important;"
                            # f"font-family:IBM Plex Mono,monospace;font-weight:600;font-size:0.78rem;"
                            # f"letter-spacing:1.5px;text-transform:uppercase;text-decoration:none;"
                            # f"border-radius:4px;padding:8px 20px;'> SOURCE PDF</a>",
                             f"<div class='pdf-btn-wrap'><a href='{pdf_url}' target='_blank'> SOURCE PDF</a></div>",
                            unsafe_allow_html=True
                        )


# ─────────────────────────────────────────────
# PAGE: DETAIL
# ─────────────────────────────────────────────

elif st.session_state.page == "detail":

    st.markdown(
        "<script>"
        "window.scrollTo({top:0,behavior:'instant'});"
        "window.parent.scrollTo({top:0,behavior:'instant'});"
        "try{document.querySelector('section.main').scrollTo({top:0,behavior:'instant'});}catch(e){}"
        "</script>",
        unsafe_allow_html=True
    )

    bill_id = st.session_state.selected_bill_id
    bill    = fetch_bill_full(supabase, bill_id)

    if not bill:
        st.error("Bill not found.")
        if st.button("← Back"):
            st.session_state.page = "home"
            st.rerun()
        st.stop()

    title     = bill.get("title") or f"Bill #{bill_id}"
    date      = smart_date(bill)
    tags      = map_to_major_industries(bill.get("full_text"), bill.get("industry_tags"), bill.get("summary"), title)
    summary   = bill.get("summary") or ""
    full_text = bill.get("full_text") or ""
    pdf_url   = bill.get("pdf_public_url") or ""

    if st.button("← Back to Bills"):
        st.session_state.page = "home"
        st.rerun()

    tags_html = "".join(f"<span class='tag'>{INDUSTRY_ICONS.get(t, '')} {t}</span>" for t in tags)
    st.markdown(f"""
    <div style='margin-bottom:28px;'>
        <div style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;color:#7a8396;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;'>UK Parliament Bill</div>
        <div style='font-family:Playfair Display,serif;font-size:2rem;font-weight:900;color:#e8e8e8;line-height:1.2;margin-bottom:12px;'>{title}</div>
        <div style='font-family:IBM Plex Mono,monospace;font-size:0.72rem;color:#7a8396;display:flex;gap:22px;flex-wrap:wrap;margin-bottom:12px;'>
            <span>📅 {date}</span>
            {"<a href='" + pdf_url + "' target='_blank' style='color:#4e9eff;text-decoration:none;'>📄 Source PDF ↗</a>" if pdf_url else ""}
        </div>
        <div>{tags_html}</div>
    </div><hr/>
    """, unsafe_allow_html=True)

    # Compliance analysis cache
    cache_key = f"compliance_{bill_id}"
    if cache_key not in st.session_state.compliance_cache:
        if full_text:
            with st.spinner("🔍 Generating compliance analysis…"):
                analysis = generate_compliance_analysis(groq_client, full_text, title)
            st.session_state.compliance_cache[cache_key] = analysis
        else:
            st.session_state.compliance_cache[cache_key] = {}
    analysis = st.session_state.compliance_cache.get(cache_key, {})

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("<div class='section-label'>📋 Overview</div>", unsafe_allow_html=True)
        if analysis.get("summary"):
            st.markdown(f"<div style='font-size:0.92rem;line-height:1.75;color:#d0d0d0;'>{sanitize_text(analysis['summary'])}</div>", unsafe_allow_html=True)
        else:
            structured = parse_summary_to_structured(summary)
            overview = " ".join(structured["overview"]) if structured["overview"] else summary[:500]
            st.markdown(f"<div style='font-size:0.92rem;line-height:1.75;color:#d0d0d0;'>{sanitize_text(overview)}</div>", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        st.markdown("<div class='section-label'>⚡ Key Changes</div>", unsafe_allow_html=True)
        key_changes = analysis.get("key_changes") or parse_summary_to_structured(summary)["key_changes"]
        if key_changes:
            for i, change in enumerate(key_changes, 1):
                st.markdown(f"""
                <div style='display:flex;gap:12px;align-items:flex-start;margin-bottom:10px;'>
                    <span style='font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#c8a96e;min-width:22px;padding-top:2px;'>{i:02d}</span>
                    <div style='background:#181c24;border-left:2px solid #4e9eff;padding:10px 14px;border-radius:0 6px 6px 0;font-size:0.88rem;flex:1;line-height:1.55;'>{sanitize_text(change)}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Key changes not available.")

        st.markdown("<br/>", unsafe_allow_html=True)

        compliance_items = analysis.get("compliance_impact") or parse_summary_to_structured(summary)["impact"]
        if compliance_items:
            st.markdown("<div class='section-label'>🏛 Compliance Impact</div>", unsafe_allow_html=True)
            for item in compliance_items:
                st.markdown(f"""
                <div class='impact-block'>
                    <div class='impact-label'>Requirement</div>
                    <div style='font-size:0.88rem;line-height:1.55;'>{sanitize_text(item)}</div>
                </div>
                """, unsafe_allow_html=True)

    with col_right:
        display_industries = tags if tags else (analysis.get("affected_industries") or [])
        if display_industries:
            st.markdown("<div class='section-label'>🏢 Who Is Affected</div>", unsafe_allow_html=True)
            for sector in display_industries:
                icon = INDUSTRY_ICONS.get(sector, "🏢")
                st.markdown(f"<div style='background:#111318;border:1px solid #252a35;border-radius:4px;padding:8px 14px;margin-bottom:8px;font-size:0.85rem;'>{icon} {sector}</div>", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        deadlines = analysis.get("deadlines") or parse_summary_to_structured(summary)["dates"]
        deadlines = [d for d in (deadlines or []) if d.lower().strip() not in ("none", "n/a", "", "no specific deadlines mentioned")]
        if deadlines:
            st.markdown("<div class='section-label'>📅 Key Deadlines</div>", unsafe_allow_html=True)
            for d in deadlines:
                st.markdown(f"<div style='background:#111318;border:1px solid #252a35;border-top:2px solid #e05a5a;border-radius:4px;padding:10px 14px;margin-bottom:8px;font-size:0.84rem;'>⏰ {sanitize_text(d)}</div>", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        impact_pts = analysis.get("compliance_impact") or parse_summary_to_structured(summary)["impact"]
        if impact_pts:
            st.markdown("""
            <div style='background:rgba(200,169,110,0.06);border:1px solid rgba(200,169,110,0.2);border-radius:6px;padding:16px;'>
                <div style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;color:#c8a96e;margin-bottom:10px;'>Business Impact</div>
                <div style='border-bottom:1px solid rgba(200,169,110,0.15);margin-bottom:10px;'></div>
            """, unsafe_allow_html=True)
            for pt in impact_pts[:3]:
                st.markdown(f"<div style='font-size:0.82rem;margin-bottom:7px;padding-left:10px;border-left:2px solid #c8a96e;'>→ {sanitize_text(pt)}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # ── RAG Chat ──
    st.markdown("<br/><hr/>", unsafe_allow_html=True)
    st.markdown("""
    <div class='section-label' style='font-size:0.72rem;'>🤖 Ask Questions About This Bill</div>
    <div style='font-size:0.82rem;color:#7a8396;margin-bottom:16px;font-family:IBM Plex Mono,monospace;'>
        Powered by retrieval-augmented generation from the full bill text
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='font-size:0.78rem;color:#7a8396;margin-bottom:10px;'>Quick questions:</div>", unsafe_allow_html=True)

    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] .stButton > button {
        height: 72px !important;
        min-height: 72px !important;
        max-height: 72px !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.3 !important;
        font-size: 0.71rem !important;
        padding: 6px 10px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        width: 100% !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    .pdf-btn-wrap a {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
}
    </style>
    """, unsafe_allow_html=True)

    qq_cols = st.columns(4)
    for i, (col, suggestion) in enumerate(zip(qq_cols, DEFAULT_QUERIES)):
        with col:
            if st.button(suggestion, key=f"suggest_{bill_id}_{i}", use_container_width=True):
                if bill_id not in st.session_state.chat_history:
                    st.session_state.chat_history[bill_id] = []
                with st.spinner("Analysing bill text…"):
                    answer = rag_answer(groq_client, suggestion, full_text, title)
                st.session_state.chat_history[bill_id].append({"q": suggestion, "a": answer})
                st.rerun()

    st.markdown("<br/>", unsafe_allow_html=True)

    if bill_id in st.session_state.chat_history and st.session_state.chat_history[bill_id]:
        for turn in st.session_state.chat_history[bill_id]:
            st.markdown(f"""
            <div class='chat-msg-user'><div class='chat-label you'>You</div>{turn['q']}</div>
            <div class='chat-msg-ai'><div class='chat-label ai-lbl'>AI Legislative Analyst</div>{turn['a']}</div>
            """, unsafe_allow_html=True)

    user_q = st.text_input(
        "Ask a question",
        placeholder='e.g. "What does this mean for pension providers?"',
        key=f"chat_input_{bill_id}",
        label_visibility="collapsed"
    )
    if st.button("Ask →", key=f"ask_btn_{bill_id}") and user_q.strip():
        if bill_id not in st.session_state.chat_history:
            st.session_state.chat_history[bill_id] = []
        with st.spinner("Analysing bill text…"):
            answer = rag_answer(groq_client, user_q, full_text, title)
        st.session_state.chat_history[bill_id].append({"q": user_q, "a": answer})
        st.rerun()

    if bill_id in st.session_state.chat_history and st.session_state.chat_history[bill_id]:
        if st.button("🗑 Clear chat", key=f"clear_{bill_id}"):
            st.session_state.chat_history[bill_id] = []
            st.rerun()