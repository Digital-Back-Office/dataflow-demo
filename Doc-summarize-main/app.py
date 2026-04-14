"""
Legal Document Summarizer — Streamlit UI
Professional interface for legal document analysis with page-level intelligence,
reasoning-based RAG, risk detection, and renewal tracking.
"""

import os
import sys
import time
import traceback
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docs_ingestion.doc_loader import DocumentLoader
from docs_ingestion.clean_text import TextCleaner
from docs_ingestion.chunk_docs import DocChunker
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.vector_store import VectorStore
from rag_pipeline.retriever import Retriever
from rag_pipeline.qa import QAEngine
from summarization.section_summary import SectionSummarizer
from summarization.executive_summary import ExecutiveSummarizer
from legal_analysis.risk_detector import RiskDetector
from legal_analysis.renewal_detector import RenewalDetector
from legal_analysis.page_analyzer import PageAnalyzer
from cache.analysis_cache import AnalysisCache


RECOMMENDED_MAX_PAGES = int(os.getenv("RECOMMENDED_MAX_PAGES", "40"))
HARD_MAX_PAGES = int(os.getenv("HARD_MAX_PAGES", "120"))
RECOMMENDED_MAX_UPLOAD_MB = int(os.getenv("RECOMMENDED_MAX_UPLOAD_MB", "15"))
HARD_MAX_UPLOAD_MB = int(os.getenv("HARD_MAX_UPLOAD_MB", "30"))


def _choose_chunk_settings(total_pages: int) -> tuple[int, int]:
    """
    Adaptive chunk settings to speed indexing on large docs without changing pipeline behavior.
    Returns (chunk_size, chunk_overlap).
    """
    # Default quality-focused settings
    if total_pages <= 40:
        return 500, 50
    # Faster indexing profile for larger documents (fewer chunks to embed/index)
    return 800, 80

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Legal Document Summarizer",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        text-align: center; padding: 1rem 0;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: white; border-radius: 10px; margin-bottom: 1rem;
    }
    .main-header h1 { color: #e2e8f0; font-size: 2rem; margin: 0; }
    .main-header p { color: #94a3b8; font-size: 0.95rem; margin: 0.3rem 0 0; }
    .risk-high { background-color: #fee2e2; border-left: 4px solid #ef4444; padding: 0.75rem; border-radius: 5px; margin: 0.5rem 0; }
    .risk-medium { background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 0.75rem; border-radius: 5px; margin: 0.5rem 0; }
    .risk-low { background-color: #d1fae5; border-left: 4px solid #10b981; padding: 0.75rem; border-radius: 5px; margin: 0.5rem 0; }
    .page-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; padding: 1rem; text-align: center; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 20px; border-radius: 8px 8px 0 0; }
</style>
""", unsafe_allow_html=True)


# ── Initialize session state ──────────────────────────────────────────────────
def init_components():
    """Initialize pipeline components (cached in session state)."""
    if "initialized" not in st.session_state:
        DATA_DIR = "data"
        st.session_state.loader = DocumentLoader()
        st.session_state.cleaner = TextCleaner()
        st.session_state.chunker = DocChunker(output_dir=DATA_DIR)
        st.session_state.embed = EmbeddingModel(data_dir=DATA_DIR)
        st.session_state.store = VectorStore(data_dir=DATA_DIR)
        st.session_state.retriever = Retriever(
            embedding_model=st.session_state.embed,
            vector_store=st.session_state.store,
            data_dir=DATA_DIR,
        )
        st.session_state.qa = QAEngine(retriever=st.session_state.retriever, data_dir=DATA_DIR)
        st.session_state.section_sum = SectionSummarizer(data_dir=DATA_DIR)
        st.session_state.exec_sum = ExecutiveSummarizer(data_dir=DATA_DIR)
        st.session_state.risk_detector = RiskDetector(data_dir=DATA_DIR)
        st.session_state.renewal_detector = RenewalDetector(data_dir=DATA_DIR)
        st.session_state.page_analyzer = PageAnalyzer(data_dir=DATA_DIR)
        st.session_state.uploaded_docs = {}  # name -> doc dict with pages, file_path
        st.session_state.cache = AnalysisCache()
        st.session_state.doc_text_cache = {}
        st.session_state.last_processing_metrics = []
        st.session_state.initialized = True

        # Restore uploaded_docs from persisted files + ChromaDB on reload
        _restore_uploaded_docs()


def _restore_uploaded_docs():
    """Re-populate uploaded_docs from files saved in uploads/ that are still in ChromaDB."""
    store = st.session_state.store
    if not store.is_initialized():
        return
    indexed_docs = store.get_all_documents()
    if not indexed_docs:
        return
    loader = st.session_state.loader
    uploads_dir = "uploads"
    if not os.path.isdir(uploads_dir):
        return
    for fname in os.listdir(uploads_dir):
        fpath = os.path.join(uploads_dir, fname)
        if not os.path.isfile(fpath):
            continue
        stem = os.path.splitext(fname)[0]
        # Match against names indexed in ChromaDB
        doc_name = None
        for idx_name in indexed_docs:
            if idx_name == stem or idx_name == loader._generate_title(stem) or idx_name.replace(" ", "_").lower() == stem.lower():
                doc_name = idx_name
                break
        if doc_name is None:
            # Try using the stem directly if it's indexed
            if stem in indexed_docs:
                doc_name = stem
            else:
                continue
        if doc_name in st.session_state.uploaded_docs:
            continue
        doc = loader.load_file(fpath)
        if doc is None:
            continue
        with open(fpath, "rb") as fb:
            file_bytes = fb.read()
        st.session_state.uploaded_docs[doc["name"]] = {
            "pages": doc.get("pages", []),
            "total_pages": doc.get("total_pages", 1),
            "file_path": fpath,
            "file_type": doc.get("file_type", ""),
            "title": doc.get("title", fname),
            "file_bytes": file_bytes,
            "file_name": fname,
        }


init_components()


# ── Helper functions ──────────────────────────────────────────────────────────

def get_status():
    store = st.session_state.store
    if not store.is_initialized():
        return 0, 0, []
    stats = store.get_stats()
    return stats["num_documents"], stats["total_chunks"], stats["documents"]


def get_loaded_docs():
    """Reconstruct document texts from ChromaDB."""
    store = st.session_state.store
    if not store.is_initialized():
        return []
    doc_names = store.get_all_documents()
    collection = store._get_or_create_collection()
    docs = []
    for doc_name in doc_names:
        try:
            results = collection.get(where={"doc_name": doc_name}, include=["documents", "metadatas"])
            if results and results["documents"]:
                combined = "\n\n".join(results["documents"])
                title = results["metadatas"][0].get("title", doc_name) if results["metadatas"] else doc_name
                docs.append({"name": doc_name, "title": title, "content": combined, "url": ""})
        except Exception:
            traceback.print_exc()
    return docs


def _get_doc_text_from_store(doc_name: str) -> str:
    """Get reconstructed full text for one doc from ChromaDB, with session cache."""
    text_cache = st.session_state.doc_text_cache
    if doc_name in text_cache:
        return text_cache[doc_name]

    store = st.session_state.store
    if not store.is_initialized():
        return ""

    collection = store._get_or_create_collection()
    results = collection.get(where={"doc_name": doc_name}, include=["documents"])
    if not results or not results.get("documents"):
        return ""

    combined = "\n\n".join(results["documents"])
    text_cache[doc_name] = combined
    return combined


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>⚖️ Legal Document Summarizer</h1>
    <p>Upload legal documents · Analyze risks · Detect renewals · Ask legal questions</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Dashboard")
    num_docs, num_chunks, doc_list = get_status()
    st.metric("Documents", num_docs)
    if doc_list:
        st.markdown("**Loaded:**")
        for d in doc_list:
            st.markdown(f"- `{d}`")
    st.divider()

    with st.expander("⚡ Performance Guide", expanded=False):
        st.caption(
            f"Recommended: ≤ {RECOMMENDED_MAX_PAGES} pages / ≤ {RECOMMENDED_MAX_UPLOAD_MB} MB per file for responsive UX."
        )
        st.caption(
            f"Hard limit: {HARD_MAX_PAGES} pages / {HARD_MAX_UPLOAD_MB} MB per file."
        )
        st.caption("Deep analysis now runs on demand to reduce first-view waiting time.")

    if st.session_state.last_processing_metrics:
        with st.expander("⏱️ Last processing timings", expanded=False):
            for m in st.session_state.last_processing_metrics:
                st.markdown(
                    f"- **{m['file']}**: {m['pages']} pages, {m['size_mb']:.2f} MB, "
                    f"{m['chunks']} chunks, total **{m['total_s']:.1f}s** "
                    f"(load {m['load_s']:.1f}s · clean {m['clean_s']:.1f}s · chunk {m['chunk_s']:.1f}s · "
                    f"embed {m['embed_s']:.1f}s · index {m['index_s']:.1f}s)"
                )

    # ── Global Document Selector ──────────────────────────────────────────
    st.markdown("### 📂 Active Document")
    all_doc_names = list(st.session_state.uploaded_docs.keys()) if st.session_state.uploaded_docs else []
    if all_doc_names:
        selected_global = st.selectbox(
            "Select document",
            ["All Documents"] + all_doc_names,
            key="global_doc_selector",
            help="This selection applies to all tabs",
        )
        st.session_state.selected_doc = selected_global
    else:
        st.caption("No documents uploaded yet.")
        st.session_state.selected_doc = None

    st.divider()

    # ── Upload (always accessible in sidebar) ────────────────────────────
    with st.expander("📤 Upload Documents", expanded=not bool(all_doc_names)):
        st.caption("PDF, TXT, MD, DOCX · max 3 files")
        sidebar_files = st.file_uploader(
            "Choose files",
            type=["pdf", "txt", "md", "docx"],
            accept_multiple_files=True,
            key="sidebar_uploader",
            label_visibility="collapsed",
        )
        if st.button("🚀 Process & Index", type="primary",
                     disabled=not sidebar_files, key="sidebar_process_btn"):
            if sidebar_files and len(sidebar_files) <= 3:
                _progress = st.progress(0, text="Starting...")
                _log = st.empty()
                _logs: list = []
                _all_chunks: list = []
                _metrics: list = []
                _total = len(sidebar_files)
                _embed_s = 0.0
                _index_s = 0.0
                for _idx, _uf in enumerate(sidebar_files):
                    _start_total = time.perf_counter()
                    _fname = _uf.name
                    _size_mb = (_uf.size or 0) / (1024 * 1024)
                    if _size_mb > HARD_MAX_UPLOAD_MB:
                        _logs.append(f"📄 {_fname}")
                        _logs.append(f"  ❌ File too large ({_size_mb:.1f} MB). Hard limit is {HARD_MAX_UPLOAD_MB} MB")
                        _log.markdown("  \n".join(_logs))
                        continue
                    if _size_mb > RECOMMENDED_MAX_UPLOAD_MB:
                        _logs.append(f"📄 {_fname}")
                        _logs.append(f"  ⚠️ {_size_mb:.1f} MB may be slow; recommended max is {RECOMMENDED_MAX_UPLOAD_MB} MB")
                    _logs.append(f"📄 {_fname}")
                    _log.markdown("  \n".join(_logs))
                    _tmp = os.path.join("uploads", _fname)
                    os.makedirs("uploads", exist_ok=True)
                    with open(_tmp, "wb") as _f:
                        _f.write(_uf.getbuffer())
                    _t0 = time.perf_counter()
                    _doc = st.session_state.loader.load_file(_tmp)
                    _load_s = time.perf_counter() - _t0
                    if _doc is None:
                        _logs.append(f"  ❌ Could not extract text")
                        continue
                    _pages = _doc.get("total_pages", 1)
                    if _pages > HARD_MAX_PAGES:
                        _logs.append(f"  ❌ {_pages} pages exceeds hard limit ({HARD_MAX_PAGES}).")
                        _log.markdown("  \n".join(_logs))
                        continue
                    if _pages > RECOMMENDED_MAX_PAGES:
                        _logs.append(f"  ⚠️ {_pages} pages may be slow; recommended max is {RECOMMENDED_MAX_PAGES}.")

                    _t1 = time.perf_counter()
                    _cleaned = st.session_state.cleaner.clean_document(_doc)
                    _clean_s = time.perf_counter() - _t1
                    _cleaned["pages"] = _doc.get("pages", [])
                    _cleaned["total_pages"] = _doc.get("total_pages", 1)
                    _cleaned["file_path"] = _tmp
                    _chunk_size, _chunk_overlap = _choose_chunk_settings(_cleaned.get("total_pages", 1))
                    _fast_chunker = DocChunker(
                        chunk_size=_chunk_size,
                        chunk_overlap=_chunk_overlap,
                        output_dir="data",
                    )
                    _t2 = time.perf_counter()
                    _chunks = _fast_chunker.chunk_document(_cleaned)
                    _chunk_s = time.perf_counter() - _t2
                    _logs.append(f"  ✔️ {len(_chunks)} chunks from {_cleaned.get('total_pages', 1)} pages")
                    st.session_state.store.delete_document(_cleaned["name"])
                    st.session_state.cache.delete_doc(_cleaned["name"])
                    st.session_state.doc_text_cache.pop(_cleaned["name"], None)
                    _all_chunks.extend(_chunks)
                    with open(_tmp, "rb") as _fb:
                        _fbytes = _fb.read()
                    st.session_state.uploaded_docs[_cleaned["name"]] = {
                        "pages": _doc.get("pages", []),
                        "total_pages": _doc.get("total_pages", 1),
                        "file_path": _tmp,
                        "file_type": _doc.get("file_type", ""),
                        "title": _doc.get("title", _fname),
                        "file_bytes": _fbytes,
                        "file_name": _fname,
                    }
                    _metrics.append({
                        "file": _fname,
                        "pages": _cleaned.get("total_pages", 1),
                        "size_mb": _size_mb,
                        "chunks": len(_chunks),
                        "load_s": _load_s,
                        "clean_s": _clean_s,
                        "chunk_s": _chunk_s,
                        "embed_s": 0.0,
                        "index_s": 0.0,
                        "total_s": time.perf_counter() - _start_total,
                    })
                    _progress.progress((_idx + 1) / _total, text=f"{_idx+1}/{_total}")
                    _log.markdown("  \n".join(_logs))
                if _all_chunks:
                    _te = time.perf_counter()
                    _embeddings = st.session_state.embed.embed_chunks(_all_chunks)
                    _embed_s = time.perf_counter() - _te
                    _ti = time.perf_counter()
                    st.session_state.store.add_document_chunks(_embeddings, _all_chunks)
                    _index_s = time.perf_counter() - _ti
                    for _m in _metrics:
                        _m["embed_s"] = _embed_s / max(len(_metrics), 1)
                        _m["index_s"] = _index_s / max(len(_metrics), 1)
                        _m["total_s"] = _m["load_s"] + _m["clean_s"] + _m["chunk_s"] + _m["embed_s"] + _m["index_s"]
                    st.session_state.last_processing_metrics = _metrics
                    _logs.append("✅ Indexed!")
                    _logs.append(f"⏱️ Embedding: {_embed_s:.1f}s · Indexing: {_index_s:.1f}s")
                    _log.markdown("  \n".join(_logs))
                    _progress.progress(1.0, text="Done!")
                    st.rerun()
                else:
                    st.warning("No content extracted.")
            elif sidebar_files and len(sidebar_files) > 3:
                st.error("Max 3 files.")

    st.divider()
    if st.button("🗑️ Clear All Data", type="secondary"):
        try:
            st.session_state.store.client.delete_collection(st.session_state.store.collection_name)
            st.session_state.store.collection = None
            st.session_state.uploaded_docs = {}
            st.session_state.cache.clear()
        except Exception:
            pass
        st.rerun()


# ── Precompute / Cache Logic ──────────────────────────────────────────────────

def _content_hash(doc_name: str) -> str:
    """Build a hash from document text to detect changes."""
    doc_info = st.session_state.uploaded_docs.get(doc_name, {})
    pages = doc_info.get("pages", [])
    text = "\n".join(p.get("text", "") for p in pages)
    return AnalysisCache._hash_content(text)


def precompute_for_doc(doc_name: str):
    """Run all analysis features for a document and cache the results."""
    return precompute_for_doc_mode(doc_name, include_deep=True)


def precompute_for_doc_mode(doc_name: str, include_deep: bool = False):
    """Run summary/renewal first; optionally include deep page/risk analysis."""
    cache = st.session_state.cache
    ch = _content_hash(doc_name)
    full_text = _get_doc_text_from_store(doc_name)
    title = st.session_state.uploaded_docs.get(doc_name, {}).get("title", doc_name)

    if not full_text:
        return

    # --- Summary ---
    if cache.get(doc_name, "summary", ch) is None:
        section_sums = st.session_state.section_sum.summarize_all_docs(
            documents=[{"name": doc_name, "title": title, "content": full_text, "url": ""}]
        )
        exec_result = st.session_state.exec_sum.generate_executive_summary(section_sums)
        cache.put(doc_name, "summary", {
            "executive": exec_result.get("summary", "N/A"),
            "sections": section_sums,
        }, ch)

    # --- Renewal Detection ---
    if cache.get(doc_name, "renewal", ch) is None:
        result = st.session_state.renewal_detector.detect_renewals(full_text, doc_name)
        cache.put(doc_name, "renewal", result, ch)

    if not include_deep:
        return

    # --- Page Analysis ---
    if cache.get(doc_name, "page_analysis", ch) is None:
        doc_info = st.session_state.uploaded_docs.get(doc_name, {})
        pages = doc_info.get("pages", [])
        if pages:
            results = st.session_state.page_analyzer.analyze_pages(pages, doc_name)
            cache.put(doc_name, "page_analysis", results, ch)

    # --- Risk Detection ---
    if cache.get(doc_name, "risk", ch) is None:
        result = st.session_state.risk_detector.detect_risks(full_text, doc_name)
        cache.put(doc_name, "risk", result, ch)

    # --- Page-by-Page Risk ---
    if cache.get(doc_name, "risk_pages", ch) is None:
        doc_info = st.session_state.uploaded_docs.get(doc_name, {})
        pages = doc_info.get("pages", [])
        if pages:
            results = st.session_state.risk_detector.detect_page_risks(pages, doc_name)
            cache.put(doc_name, "risk_pages", results, ch)


# Auto-trigger precompute when a specific document is selected
sel_doc = st.session_state.get("selected_doc")
if sel_doc and sel_doc != "All Documents" and sel_doc in st.session_state.uploaded_docs:
    ch = _content_hash(sel_doc)
    needs_compute = (
        st.session_state.cache.get(sel_doc, "summary", ch) is None
        or st.session_state.cache.get(sel_doc, "renewal", ch) is None
    )
    if needs_compute:
        with st.spinner(f"⚙️ Preparing overview for **{sel_doc}** (summary + renewals)..."):
            precompute_for_doc_mode(sel_doc, include_deep=False)
        st.rerun()  # refresh so tabs render cached data

# ── Main area ─────────────────────────────────────────────────────────────────
if not st.session_state.uploaded_docs:
    st.markdown("""
    <div style="text-align:center; padding: 4rem 2rem;">
        <h2>📂 No documents loaded</h2>
        <p style="color:#94a3b8; font-size:1.1rem;">
            Use the <strong>📤 Upload Documents</strong> panel in the sidebar to get started.
        </p>
    </div>
    """, unsafe_allow_html=True)
else:
    tab_overview, tab_deep, tab_ask = st.tabs([
        "👁️ Master Overview", "🔍 Deep Analysis (Risks & Pages)", "💬 Legal Q&A"
    ])

    # ── Master Overview ────────────────────────────────────────────────────────
    with tab_overview:
        sel = st.session_state.get("selected_doc")
        if sel is None or sel == "All Documents":
            st.info("Select a specific document from the sidebar for the Master Overview.")
        elif sel not in st.session_state.uploaded_docs:
            st.warning(f"Document '{sel}' not found.")
        else:
            ch = _content_hash(sel)
            sum_cached = st.session_state.cache.get(sel, "summary", ch)
            ren_cached = st.session_state.cache.get(sel, "renewal", ch)
            
            if sum_cached is None or ren_cached is None:
                st.info("Master Overview is being prepared — please wait...")
            else:
                col1, col2 = st.columns([6, 4])
                with col1:
                    st.subheader("📊 Executive Summary")
                    st.markdown(sum_cached.get("executive", "N/A"))
                    st.divider()
                    st.subheader("📝 Key Sections")
                    for s in sum_cached.get("sections", []):
                        with st.expander(f"📄 {s['title']}"):
                            st.markdown(s["summary"])
                with col2:
                    st.subheader("🔄 Renewal & Expiry")
                    st.markdown(ren_cached.get("raw_analysis", "No analysis available."))
                    renewals = ren_cached.get("renewals", [])
                    if renewals:
                        for item in renewals:
                            st.divider()
                            for key, val in item.items():
                                st.markdown(f"**{key.replace('_', ' ').title()}:** {val}")

    # ── Deep Analysis ──────────────────────────────────────────────────────────
    with tab_deep:
        sel = st.session_state.get("selected_doc")
        if sel is None or sel == "All Documents":
            st.info("Select a specific document from the sidebar for deep analysis.")
        elif sel not in st.session_state.uploaded_docs:
            st.warning(f"Document '{sel}' not found.")
        else:
            ch = _content_hash(sel)
            risk_cached = st.session_state.cache.get(sel, "risk", ch)
            page_cached = st.session_state.cache.get(sel, "page_analysis", ch)
            
            if risk_cached is None or page_cached is None:
                st.info("Deep analysis isn't precomputed by default to keep the app responsive.")
                if st.button("⚡ Run Deep Analysis Now", key="run_deep_analysis_btn", type="primary"):
                    with st.spinner(f"Running deep analysis for {sel}..."):
                        precompute_for_doc_mode(sel, include_deep=True)
                    st.rerun()
            else:
                st.subheader("⚠️ High-Level Legal Risks")
                risks = risk_cached.get("risks", [])
                if risks:
                    for risk in risks:
                        sev = risk.get("severity", "Medium").lower()
                        css_class = "risk-high" if "high" in sev else ("risk-medium" if "medium" in sev else "risk-low")
                        st.markdown(
                            f'<div class="{css_class}">'
                            f'<strong>{risk.get("category", "Risk")}</strong> ({risk.get("severity", "N/A")})<br>'
                            f'{risk.get("description", "")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.success("No high-level risks detected.")

                st.divider()
                st.subheader("📑 Page-Level Intelligence & Risks")
                doc_info = st.session_state.uploaded_docs.get(sel, {})
                pages = doc_info.get("pages", [])
                
                # Merge page analysis and risk pages
                risk_pages_cached = st.session_state.cache.get(sel, "risk_pages", ch) or []
                risk_page_map = {r["page_num"]: r for r in risk_pages_cached}

                for r in page_cached:
                    p_num = r.get("page_num", 0)
                    rc = risk_page_map.get(p_num, {})
                    
                    importance = r.get("importance", "Medium")
                    score = r.get("score", 5)
                    has_risk = rc.get("has_risks", False)
                    
                    if has_risk or importance.lower() in ["critical", "high"] or score >= 7:
                        badge_color = "🔴"
                    elif importance.lower() == "medium" or score >= 4:
                        badge_color = "🟡"
                    else:
                        badge_color = "🟢"
                        
                    with st.expander(f"{badge_color} Page {p_num} — {importance} (Score: {score}/10) | {'⚠️ Risks Detected' if has_risk else '✅ Clear'}"):
                        p_col1, p_col2 = st.columns([1, 1])
                        with p_col1:
                            st.markdown(f"**Topics:** {', '.join(r.get('key_topics', []))}")
                            st.markdown(f"**Summary:** {r.get('summary', 'N/A')}")
                            if has_risk:
                                st.markdown(f"**Risks:** {rc.get('risk_summary', 'N/A')}")
                        with p_col2:
                            page_text = "Text not available."
                            for p in pages:
                                if p.get("page_num") == p_num:
                                    page_text = p.get("text", "")
                                    break
                            st.markdown("**Original Text Snippet:**")
                            st.info(f"_{page_text[:800]}..._" if len(page_text) > 800 else f"_{page_text}_")

    # ── Legal Q&A ──────────────────────────────────────────────────────────────
    with tab_ask:
        st.subheader("💬 Reasoning-Based Legal Q&A")
        sel = st.session_state.get("selected_doc")

        if not st.session_state.store.is_initialized():
            st.info("Upload documents first to ask legal questions.")
        elif sel is None:
            st.info("Select a document from the sidebar to ask questions.")
        else:
            sel_qa_doc = sel
            st.caption(f"🔎 Searching in: **{sel_qa_doc}**")

            question = st.text_area(
                "Your legal question",
                placeholder="e.g. What are the termination conditions in this contract?",
                height=80,
                key="qa_question",
            )

            if st.button("🔍 Ask", type="primary", key="ask_btn"):
                if question and question.strip():
                    with st.spinner("Analyzing with reasoning-based RAG..."):
                        filt = sel_qa_doc if sel_qa_doc and sel_qa_doc != "All Documents" else None
                        result = st.session_state.qa.answer(question.strip(), top_k=4, doc_filter=filt)

                        st.markdown("### 💡 Answer")
                        st.markdown(result["answer"])

                        pages_ref = result.get("pages_referenced", [])
                        if pages_ref:
                            st.caption(f"📄 Pages referenced: {', '.join(str(p) for p in pages_ref)}")

                        if result.get("sources"):
                            st.divider()
                            st.markdown("**📚 Sources:**")
                            for s in result["sources"]:
                                st.markdown(f"- {s.get('title', '')} ({s.get('doc_name', '')})")

                        st.caption(f"Chunks used: {result.get('num_chunks_used', 0)}")
                else:
                    st.warning("Please enter a question.")
