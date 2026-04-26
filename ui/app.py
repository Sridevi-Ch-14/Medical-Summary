"""
ClinIQ - Streamlit Medical Dashboard v2.0
============================================
Premium medical-themed UI with:
- Severity % bars (pulsing red for extreme deviations)
- HIPAA Privacy Mode toggle
- NIH deep links in RAG sources
- Differentiated Patient vs Doctor views
"""

import os
import sys
import re
import time
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="ClinIQ - Medical Report Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }

    .cliniq-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0d4f8b 100%);
        padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
        box-shadow: 0 10px 40px rgba(15,23,42,0.3); position: relative; overflow: hidden;
    }
    .cliniq-header::before {
        content: ''; position: absolute; top: -50%; right: -20%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%);
        border-radius: 50%;
    }
    .cliniq-header h1 { color: #fff; font-size: 2.2rem; font-weight: 700; margin: 0; }
    .cliniq-header p { color: #94a3b8; font-size: 1rem; margin: 0.3rem 0 0 0; }
    .cliniq-badge {
        display: inline-block; background: rgba(59,130,246,0.2);
        border: 1px solid rgba(59,130,246,0.3); color: #60a5fa;
        padding: 0.2rem 0.8rem; border-radius: 20px; font-size: 0.75rem;
        font-weight: 600; margin-top: 0.5rem; letter-spacing: 0.5px;
    }

    .condition-card {
        background: linear-gradient(135deg, #fffbeb, #fef3c7);
        border: 1px solid #fcd34d; border-left: 4px solid #f59e0b;
        padding: 1rem 1.2rem; border-radius: 10px; margin-bottom: 0.8rem;
    }
    .condition-card.critical {
        background: linear-gradient(135deg, #fef2f2, #fee2e2);
        border-color: #f87171; border-left-color: #dc2626;
    }
    .condition-card h4 { margin: 0 0 0.3rem 0; color: #1e293b; font-size: 1rem; }
    .condition-card p { margin: 0.2rem 0; font-size: 0.85rem; color: #475569; }
    .condition-card a { color: #2563eb; text-decoration: none; font-weight: 500; }
    .condition-card a:hover { text-decoration: underline; }

    .metric-card {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 1px solid #e2e8f0; padding: 1.2rem; border-radius: 12px;
        text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .metric-card .metric-value { font-size: 2rem; font-weight: 700; color: #0f172a; }
    .metric-card .metric-label {
        font-size: 0.8rem; color: #64748b; text-transform: uppercase;
        letter-spacing: 0.5px; margin-top: 0.2rem;
    }

    .summary-box {
        background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.05); line-height: 1.7;
    }
    .summary-box h3 {
        color: #1e3a5f; border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.5rem; margin-bottom: 1rem;
    }

    /* Severity bar */
    .severity-bar-container {
        background: #f1f5f9; border-radius: 8px; height: 18px;
        overflow: hidden; margin: 2px 0;
    }
    .severity-bar {
        height: 100%; border-radius: 8px; transition: width 0.5s ease;
        display: flex; align-items: center; justify-content: flex-end;
        padding-right: 6px; font-size: 0.65rem; font-weight: 700; color: white;
    }
    .severity-bar.pulse {
        animation: pulse-red 1.5s ease-in-out infinite;
    }
    @keyframes pulse-red {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* HIPAA badge */
    .hipaa-badge {
        background: linear-gradient(135deg, #059669, #047857);
        color: white; padding: 0.3rem 0.8rem; border-radius: 8px;
        font-size: 0.75rem; font-weight: 600; text-align: center;
        margin-top: 0.5rem; letter-spacing: 0.5px;
    }

    /* Sidebar toggle button — appears when sidebar is collapsed */
    .sidebar-toggle-btn {
        position: fixed; top: 14px; left: 14px; z-index: 999999;
        width: 44px; height: 44px; border-radius: 12px;
        background: linear-gradient(135deg, #0f172a, #1e3a5f);
        border: 1px solid rgba(59,130,246,0.35);
        color: #60a5fa; font-size: 1.3rem; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 16px rgba(15,23,42,0.45);
        transition: all 0.25s ease;
    }
    .sidebar-toggle-btn:hover {
        background: linear-gradient(135deg, #1e3a5f, #2563eb);
        box-shadow: 0 6px 24px rgba(37,99,235,0.4);
        transform: scale(1.08);
    }
    /* Hide when sidebar is open (Streamlit adds data-testid="stSidebar" with aria-expanded) */
    [data-testid="stSidebar"][aria-expanded="true"] ~ section .sidebar-toggle-btn,
    [data-testid="stSidebar"][aria-expanded="true"] ~ .main .sidebar-toggle-btn {
        display: none !important;
    }

    /* Center upload area */
    .center-upload-area {
        max-width: 560px; margin: 2rem auto; padding: 3rem 2.5rem;
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 2px dashed #94a3b8; border-radius: 20px; text-align: center;
        transition: all 0.3s ease;
    }
    .center-upload-area:hover {
        border-color: #3b82f6;
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        box-shadow: 0 8px 32px rgba(59,130,246,0.12);
    }
    .center-upload-icon {
        font-size: 3.5rem; margin-bottom: 0.5rem;
        display: block; line-height: 1;
    }
    .center-upload-title {
        font-size: 1.25rem; font-weight: 700; color: #1e293b;
        margin: 0.5rem 0 0.3rem 0;
    }
    .center-upload-sub {
        font-size: 0.9rem; color: #64748b; margin: 0;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 20px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR TOGGLE BUTTON (visible when sidebar is collapsed)
# ============================================================
st.markdown("""
<script>
// Periodically check if sidebar is collapsed and show/hide the toggle button
function checkSidebar() {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    const btn = document.getElementById('sidebarToggleBtn');
    if (!sidebar || !btn) return;
    const expanded = sidebar.getAttribute('aria-expanded');
    btn.style.display = (expanded === 'false') ? 'flex' : 'none';
}
setInterval(checkSidebar, 300);

function openSidebar() {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (sidebar) {
        const btn = sidebar.querySelector('button[data-testid="stSidebarCollapseButton"], button[kind="header"], button');
        if (btn) btn.click();
        else sidebar.setAttribute('aria-expanded', 'true');
    }
}
</script>
<button id="sidebarToggleBtn" class="sidebar-toggle-btn" onclick="openSidebar()" title="Open sidebar">
    ☰
</button>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="cliniq-header">
    <h1>🏥 ClinIQ</h1>
    <p>Medical Report Intelligence Engine — Verified Clinical Pipeline</p>
    <span class="cliniq-badge">DETERMINISTIC + RAG + AI</span>
</div>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### 📁 Upload Medical Report")
    uploaded_file = st.file_uploader(
        "Drag & drop your file here",
        type=["pdf", "docx", "txt"],
        help="Supported: PDF, Word (.docx), Plain Text (.txt)"
    )

    st.markdown("---")
    st.markdown("### ⚙️ Pipeline Settings")
    enable_rag = st.toggle("Enable RAG (Knowledge Grounding)", value=True)
    enable_ai = st.toggle("Enable AI Summary (Groq)", value=True)
    enable_pii = st.toggle("Enable PII Scrubbing", value=True)

    st.markdown("---")
    st.markdown("### 🛡️ HIPAA Privacy Mode")
    hipaa_mode = st.toggle("Ghost Mode (Full PII Redaction)", value=False,
                          help="Replaces all patient identifiers with anonymized tags before display")
    if hipaa_mode:
        st.markdown('<div class="hipaa-badge">🔒 HIPAA GHOST MODE ACTIVE</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 Pipeline Phases")
    st.markdown("""
    1. 📄 **Extract** → Text
    2. 🧬 **Parse** → Structured JSON
    3. ⚡ **Detect** → Deterministic Flags
    4. 🏥 **Rules** → Clinical Conditions
    5. 📚 **RAG** → Knowledge Context
    6. 🤖 **Summarize** → AI Dual Summary
    """)
    st.markdown("---")
    st.markdown(
        "<p style='color: #94a3b8; font-size: 0.75rem; text-align: center;'>"
        "ClinIQ v2.0 | Not for clinical use<br>For educational purposes only</p>",
        unsafe_allow_html=True
    )


# ============================================================
# HIPAA GHOST MODE HELPER
# ============================================================
def apply_ghost_mode(text: str) -> str:
    """Replace PII with anonymized tags for HIPAA compliance display."""
    result = text
    # Names after Patient/Name labels
    result = re.sub(
        r'(?i)(patient\s*(?:name)?[\s:]+)([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\1PATIENT_ALFA', result)
    result = re.sub(
        r'(?i)(name[\s:]+)([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'\1PATIENT_ALFA', result)
    # DOB -> AGE tag
    result = re.sub(
        r'(?i)((?:date of birth|dob|d\.o\.b\.|birth\s*date)[\s:]+)\S+',
        r'\1[AGE_REDACTED]', result)
    # MRN
    result = re.sub(r'(?i)((?:mrn|medical record)[\s:#]+)\S+', r'\1[MRN_REDACTED]', result)
    # Phone
    result = re.sub(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE_REDACTED]', result)
    # Email
    result = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', result)
    # SSN
    result = re.sub(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', '[SSN_REDACTED]', result)
    return result


# ============================================================
# SEVERITY CALCULATION
# ============================================================
def calc_severity_pct(value, ref_low, ref_high, status):
    """Calculate severity as % deviation from reference range."""
    if ref_high is None or ref_low is None:
        return 0
    if "HIGH" in status and ref_high > 0:
        return min(500, round(((value - ref_high) / ref_high) * 100, 1))
    elif "LOW" in status and ref_low > 0:
        return min(500, round(((ref_low - value) / ref_low) * 100, 1))
    return 0


def severity_bar_html(pct, status):
    """Generate HTML for a severity progress bar."""
    if pct <= 0:
        return '<span style="color: #16a34a; font-weight: 600;">✓ Normal</span>'
    color = "#ef4444" if "HIGH" in status else "#3b82f6"
    width = min(100, max(8, pct / 5 * 100 if pct < 50 else min(pct, 100)))
    pulse = "pulse" if pct > 100 else ""
    direction = "above" if "HIGH" in status else "below"
    return f"""<div class="severity-bar-container">
        <div class="severity-bar {pulse}" style="width: {width}%; background: {color};">
            {pct:.0f}% {direction}
        </div>
    </div>"""


# ============================================================
# PIPELINE
# ============================================================
def run_pipeline(uploaded_file):
    from extractor.extract_router import extract_text, get_file_type
    from parser.medical_parser import parse_medical_text
    from parser.microbiology_parser import parse_microbiology
    from engine.abnormality_detector import detect_abnormalities, detect_microbiology_abnormalities
    from engine.clinical_rules import evaluate_conditions, evaluate_microbiology_conditions
    from privacy.pii_scrubber import scrub_pii
    from ai.clinical_summarizer import generate_clinical_summary

    progress = st.progress(0, text="Starting analysis pipeline...")
    start_time = time.time()

    temp_dir = os.path.join(ROOT, "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        progress.progress(10, text="Phase 1: Extracting text...")
        raw_text = extract_text(temp_path)
        file_type = get_file_type(temp_path)
        if not raw_text.strip():
            st.error("Could not extract any text from the uploaded file.")
            return None

        progress.progress(25, text="Scrubbing PII...")
        pii_text, masked = scrub_pii(raw_text) if enable_pii else (raw_text, [])

        # Phase 2M: Microbiology Culture & Sensitivity parsing
        progress.progress(35, text="Phase 2M: Detecting microbiology data...")
        micro_result = parse_microbiology(pii_text)

        progress.progress(40, text="Phase 2: Parsing structured data...")
        test_results = parse_medical_text(pii_text)

        progress.progress(55, text="Phase 3: Detecting abnormalities...")
        flagged = detect_abnormalities(test_results)

        # Merge microbiology flagged results
        if micro_result:
            micro_flagged = detect_microbiology_abnormalities(micro_result)
            flagged = micro_flagged + flagged  # Micro results first (highest priority)

        progress.progress(65, text="Phase 4: Evaluating clinical rules...")
        conditions = evaluate_conditions(flagged)

        # Merge microbiology conditions
        if micro_result:
            micro_conditions = evaluate_microbiology_conditions(micro_result)
            conditions = micro_conditions + conditions  # Micro conditions first

        rag_contexts = []
        if enable_rag:
            progress.progress(75, text="Phase 5: Retrieving medical knowledge...")
            try:
                from rag.knowledge_indexer import index_knowledge_base, is_indexed
                from rag.knowledge_retriever import retrieve_for_abnormals
                kb_path = os.path.join(ROOT, "data", "medical_knowledge.txt")
                if os.path.exists(kb_path) and not is_indexed():
                    index_knowledge_base(kb_path)
                rag_contexts = retrieve_for_abnormals(flagged)
            except Exception as e:
                st.warning(f"RAG unavailable: {e}")

        summary = None
        if enable_ai:
            progress.progress(88, text="Phase 6: Generating AI summary...")
            analysis_data = {
                "test_results": [r.model_dump() for r in flagged],
                "detected_conditions": [c.model_dump() for c in conditions],
                "rag_contexts": [ctx.model_dump() for ctx in rag_contexts],
            }
            # Include microbiology data for the AI prompt
            if micro_result:
                analysis_data["microbiology"] = micro_result.model_dump()
            summary = generate_clinical_summary(analysis_data)

        progress.progress(100, text="Analysis complete!")
        time.sleep(0.3)
        progress.empty()

        return {
            "raw_text": raw_text, "pii_text": pii_text, "masked": masked,
            "flagged": flagged, "conditions": conditions,
            "rag_contexts": rag_contexts, "summary": summary,
            "micro": micro_result,  # Microbiology data for UI
            "elapsed": round(time.time() - start_time, 2),
            "file_name": uploaded_file.name, "file_type": file_type,
        }
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# ============================================================
# MAIN CONTENT
# ============================================================
# Accept file from either sidebar uploader or center uploader
active_file = None
if "center_file" in st.session_state and st.session_state["center_file"] is not None:
    active_file = st.session_state.pop("center_file")
elif uploaded_file is not None:
    active_file = uploaded_file

# Run pipeline only when a NEW file is uploaded; cache results in session_state
if active_file is not None:
    # Check if this is a new file (different name or first upload)
    prev_name = st.session_state.get("_last_file_name")
    if prev_name != active_file.name or "pipeline_results" not in st.session_state:
        results = run_pipeline(active_file)
        if results:
            st.session_state["pipeline_results"] = results
            st.session_state["_last_file_name"] = active_file.name

# Use cached results for display (survives reruns from widget interactions)
has_results = False
if "pipeline_results" in st.session_state and st.session_state["pipeline_results"]:
    results = st.session_state["pipeline_results"]
    has_results = True

if has_results:
    flagged = results["flagged"]
    conditions = results["conditions"]
    abnormal = [f for f in flagged if f.status not in ("NORMAL", "UNKNOWN", "NEGATIVE")]
    critical = [f for f in flagged if "CRITICAL" in (f.clinical_urgency or "")]
    micro = results.get("micro")

    # === METRICS BAR ===
    st.markdown("---")
    cols = st.columns(6 if micro else 5)
    with cols[0]:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{len(flagged)}</div>
            <div class="metric-label">Tests Parsed</div>
        </div>""", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value" style="color: #dc2626;">{len(abnormal)}</div>
            <div class="metric-label">Abnormal</div>
        </div>""", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value" style="color: #ea580c;">{len(critical)}</div>
            <div class="metric-label">Critical</div>
        </div>""", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value" style="color: #f59e0b;">{len(conditions)}</div>
            <div class="metric-label">Conditions</div>
        </div>""", unsafe_allow_html=True)
    with cols[4]:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value" style="color: #0ea5e9;">{results['elapsed']}s</div>
            <div class="metric-label">Processing Time</div>
        </div>""", unsafe_allow_html=True)
    if micro and len(cols) > 5:
        with cols[5]:
            organism_short = micro.organism.split()[0] if micro.organism else "Detected"
            st.markdown(f"""<div class="metric-card" style="border: 2px solid #dc2626;">
                <div class="metric-value" style="color: #dc2626; font-size: 1.3rem;">🦠 {organism_short}</div>
                <div class="metric-label">Organism</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # === TABBED RESULTS ===
    if micro:
        tab1, tab_micro, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Parsed Results", "🦠 Microbiology", "⚠️ Conditions", "🤖 AI Summary",
            "📄 Extracted Text", "📚 RAG Sources"
        ])
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Parsed Results", "⚠️ Conditions", "🤖 AI Summary",
            "📄 Extracted Text", "📚 RAG Sources"
        ])
        tab_micro = None

    # --- TAB 1: Parsed Results with Severity Bars ---
    with tab1:
        st.markdown("### Lab Results — Abnormality Detection")
        if flagged:
            import pandas as pd
            table_data = []
            for f in flagged:
                ref = f"{f.reference_low} - {f.reference_high}" if f.reference_low else "N/A"
                sev_pct = calc_severity_pct(f.observed_value, f.reference_low, f.reference_high, f.status)
                table_data.append({
                    "Test": f.test_name,
                    "Value": f"{f.observed_value} {f.unit}",
                    "Reference": ref,
                    "Status": f.status,
                    "Deviation": sev_pct,
                    "Severity": f"{'🔴' * min(f.severity_score, 5)}{'⚪' * max(0, 5 - f.severity_score)}"
                })
            df = pd.DataFrame(table_data)

            def color_status(val):
                colors = {
                    "HIGH": "background-color: #fee2e2; color: #dc2626; font-weight: 600",
                    "CRITICAL_HIGH": "background-color: #fecaca; color: #b91c1c; font-weight: 700",
                    "LOW": "background-color: #dbeafe; color: #2563eb; font-weight: 600",
                    "CRITICAL_LOW": "background-color: #bfdbfe; color: #1d4ed8; font-weight: 700",
                    "NORMAL": "background-color: #dcfce7; color: #16a34a; font-weight: 500",
                }
                return colors.get(val, "")

            styled = df.style.map(color_status, subset=["Status"])
            st.dataframe(styled, width='stretch', hide_index=True, height=400)

            # Severity % Bars for abnormals
            if abnormal:
                st.markdown("#### Severity Index (% Deviation from Reference)")
                for f in abnormal:
                    pct = calc_severity_pct(f.observed_value, f.reference_low, f.reference_high, f.status)
                    col_name, col_bar = st.columns([1, 3])
                    with col_name:
                        st.markdown(f"**{f.test_name}**")
                    with col_bar:
                        st.markdown(severity_bar_html(pct, f.status), unsafe_allow_html=True)

            # Plotly chart
            if abnormal:
                st.markdown("#### Severity Distribution")
                names = [f.test_name for f in abnormal]
                scores = [f.severity_score for f in abnormal]
                colors_map = ["#ef4444" if "HIGH" in f.status else "#3b82f6" for f in abnormal]
                fig = go.Figure(go.Bar(
                    x=names, y=scores, marker_color=colors_map,
                    text=scores, textposition="outside"
                ))
                fig.update_layout(
                    yaxis_title="Severity (0-10)", height=350,
                    margin=dict(t=20, b=40),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, width='stretch')
        else:
            st.info("No test results were parsed from the document.")
    # --- TAB MICRO: Microbiology Culture & Sensitivity ---
    if tab_micro is not None:
        with tab_micro:
            st.markdown("### 🦠 Microbiology — Culture & Sensitivity Report")
            if micro and micro.organism:
                # Organism + Colony Count header
                sig_badge = (
                    '<span style="background: #dc2626; color: white; padding: 2px 10px; '
                    'border-radius: 12px; font-size: 0.75rem; font-weight: 700;">SIGNIFICANT INFECTION</span>'
                    if micro.is_significant else
                    '<span style="background: #f59e0b; color: white; padding: 2px 10px; '
                    'border-radius: 12px; font-size: 0.75rem; font-weight: 700;">EQUIVOCAL</span>'
                )
                st.markdown(f"""<div class="condition-card critical" style="border-left-width: 6px;">
                    <h4>🦠 Organism Isolated: <strong>{micro.organism}</strong></h4>
                    <p><strong>Specimen:</strong> {micro.specimen_type or 'Not specified'}</p>
                    <p><strong>Colony Count:</strong> {micro.colony_count or 'Not reported'} &nbsp; {sig_badge}</p>
                    {f'<p><strong>Method:</strong> {micro.method}</p>' if micro.method else ''}
                    {f'<p><strong>Gram Stain:</strong> {micro.gram_stain}</p>' if micro.gram_stain else ''}
                </div>""", unsafe_allow_html=True)

                # Antibiotic Susceptibility Table
                if micro.antibiotics:
                    st.markdown("#### 💊 Antibiotic Susceptibility Pattern")

                    resistant = [a for a in micro.antibiotics if a.status == "Resistant"]
                    sensitive = [a for a in micro.antibiotics if a.status == "Sensitive"]
                    intermediate = [a for a in micro.antibiotics if a.status == "Intermediate"]

                    # MDR Warning Banner
                    if len(resistant) >= 3:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #fef2f2, #fee2e2);
                            border: 2px solid #dc2626; border-radius: 12px; padding: 1rem 1.5rem;
                            margin-bottom: 1rem; text-align: center;">
                            <span style="font-size: 1.2rem; font-weight: 700; color: #dc2626;">
                            ⚠️ MULTI-DRUG RESISTANCE (MDR) — Resistant to {len(resistant)} antibiotics
                            </span>
                        </div>""", unsafe_allow_html=True)

                    # Build table
                    import pandas as pd
                    abx_data = []
                    for a in micro.antibiotics:
                        icon = {"Resistant": "🔴", "Sensitive": "🟢", "Intermediate": "🟡"}.get(a.status, "⚪")
                        abx_data.append({
                            "Antibiotic": a.name,
                            "Susceptibility": f"{icon} {a.status}",
                            "Clinical Action": (
                                "❌ DO NOT prescribe — treatment will fail" if a.status == "Resistant"
                                else "✅ Effective — recommended for therapy" if a.status == "Sensitive"
                                else "⚠️ May require adjusted dosage"
                            )
                        })

                    abx_df = pd.DataFrame(abx_data)

                    def color_susceptibility(val):
                        if "Resistant" in val:
                            return "background-color: #fee2e2; color: #dc2626; font-weight: 700"
                        elif "Sensitive" in val:
                            return "background-color: #dcfce7; color: #16a34a; font-weight: 700"
                        elif "Intermediate" in val:
                            return "background-color: #fef3c7; color: #d97706; font-weight: 600"
                        return ""

                    styled_abx = abx_df.style.map(color_susceptibility, subset=["Susceptibility"])
                    st.dataframe(styled_abx, width='stretch', hide_index=True, height=min(600, 40 + len(abx_data) * 35))

                    # Summary cards
                    col_r, col_s = st.columns(2)
                    with col_r:
                        r_names = ", ".join(a.name for a in resistant)
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #fef2f2, #fee2e2);
                            border: 1px solid #f87171; border-radius: 10px; padding: 1rem;">
                            <h4 style="color: #dc2626; margin: 0 0 0.5rem 0;">🔴 Resistant ({len(resistant)})</h4>
                            <p style="font-size: 0.85rem; color: #7f1d1d; margin: 0;">{r_names or 'None'}</p>
                        </div>""", unsafe_allow_html=True)
                    with col_s:
                        s_names = ", ".join(a.name for a in sensitive)
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #f0fdf4, #dcfce7);
                            border: 1px solid #4ade80; border-radius: 10px; padding: 1rem;">
                            <h4 style="color: #16a34a; margin: 0 0 0.5rem 0;">🟢 Sensitive ({len(sensitive)})</h4>
                            <p style="font-size: 0.85rem; color: #14532d; margin: 0;">{s_names or 'None'}</p>
                        </div>""", unsafe_allow_html=True)
            else:
                st.info("No microbiology data found in this report.")

    # --- TAB 2: Detected Conditions with NIH Links ---
    with tab2:
        st.markdown("### Detected Potential Conditions")
        if conditions:
            from engine.clinical_rules import get_nih_url
            for c in conditions:
                card_class = "critical" if c.severity in ("HIGH", "CRITICAL") else ""
                sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(c.severity, "⚪")
                nih = get_nih_url(c.condition)
                nih_link = f'<a href="{nih}" target="_blank">📖 NIH Clinical Reference</a>' if nih else ""
                st.markdown(f"""
                <div class="condition-card {card_class}">
                    <h4>{sev_icon} {c.condition}</h4>
                    <p><strong>Rule:</strong> {c.logic}</p>
                    <p><strong>Severity:</strong> {c.severity}</p>
                    <p><strong>Supporting Tests:</strong> {', '.join(c.supporting_tests)}</p>
                    <p><strong>Recommendation:</strong> {c.recommendation}</p>
                    {nih_link}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No concerning conditions detected based on clinical rules.")

    # --- TAB 3: AI Summary (Differentiated) ---
    with tab3:
        summary = results.get("summary")
        if summary:
            view = st.radio("Summary View", ["🧑 Patient View", "👨‍⚕️ Doctor View"], horizontal=True)
            if view == "🧑 Patient View":
                content = summary.patient_summary
                if hipaa_mode:
                    content = apply_ghost_mode(content)
                st.markdown(f"""<div class="summary-box">
                    <h3>🧑 Patient Summary</h3>
                    {content.replace(chr(10), '<br>')}
                </div>""", unsafe_allow_html=True)
            else:
                content = summary.doctor_summary
                if hipaa_mode:
                    content = apply_ghost_mode(content)
                st.markdown(f"""<div class="summary-box">
                    <h3>👨‍⚕️ Doctor Summary</h3>
                    {content.replace(chr(10), '<br>')}
                </div>""", unsafe_allow_html=True)

            if summary.citations:
                st.markdown("#### 📎 Source Citations")
                for cit in summary.citations:
                    st.markdown(f"- {cit}")
        else:
            st.info("AI Summary was not generated. Enable it in the sidebar settings.")

    # --- TAB 4: Extracted Text ---
    with tab4:
        col_orig, col_masked = st.columns(2)
        display_raw = apply_ghost_mode(results["raw_text"]) if hipaa_mode else results["raw_text"]
        display_pii = apply_ghost_mode(results["pii_text"]) if hipaa_mode else results["pii_text"]
        with col_orig:
            st.markdown("#### Original Text")
            st.text_area("Raw", display_raw, height=400, label_visibility="collapsed")
        with col_masked:
            st.markdown("#### PII-Masked Text")
            st.text_area("Masked", display_pii, height=400, label_visibility="collapsed")
        if results["masked"]:
            st.markdown("#### 🔒 Masked PII Entities")
            for m in results["masked"]:
                st.markdown(f"- `{m}`")

    # --- TAB 5: RAG Sources with NIH Links ---
    with tab5:
        st.markdown("### 📚 Retrieved Medical Knowledge")
        rag_contexts = results.get("rag_contexts", [])
        if rag_contexts:
            for i, ctx in enumerate(rag_contexts, 1):
                with st.expander(f"Source {i}: {ctx.source} (relevance: {ctx.relevance_score:.2%})"):
                    st.markdown(ctx.text)
                    # Extract NIH URL if present in the chunk
                    nih_match = re.search(r'\[NIH Source:\s*(https?://\S+)\]', ctx.text)
                    if nih_match:
                        st.markdown(f"🔗 **[View on NIH →]({nih_match.group(1)})**")
        else:
            st.info("No RAG context retrieved. Enable RAG in sidebar or ensure knowledge base is indexed.")

if not has_results:
    # === LANDING STATE ===
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""<div class="metric-card">
            <div class="metric-value">📄</div>
            <div class="metric-label">Upload a Report</div>
            <p style="color: #64748b; font-size: 0.85rem; margin-top: 0.5rem;">PDF, Word, or Text files</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="metric-card">
            <div class="metric-value">⚡</div>
            <div class="metric-label">6-Phase Pipeline</div>
            <p style="color: #64748b; font-size: 0.85rem; margin-top: 0.5rem;">Extract → Parse → Detect → Rules → RAG → AI</p>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="metric-card">
            <div class="metric-value">🛡️</div>
            <div class="metric-label">Privacy First</div>
            <p style="color: #64748b; font-size: 0.85rem; margin-top: 0.5rem;">PII scrubbed before AI processing</p>
        </div>""", unsafe_allow_html=True)

    # === CENTER UPLOAD AREA ===
    st.markdown("""<div class="center-upload-area">
        <span class="center-upload-icon">📂</span>
        <p class="center-upload-title">Upload Your Medical Report</p>
        <p class="center-upload-sub">Drag & drop or click below — PDF, Word (.docx), Plain Text (.txt)</p>
    </div>""", unsafe_allow_html=True)

    center_col1, center_col2, center_col3 = st.columns([1, 2, 1])
    with center_col2:
        center_uploaded = st.file_uploader(
            "Upload here",
            type=["pdf", "docx", "txt"],
            help="Supported: PDF, Word (.docx), Plain Text (.txt)",
            key="center_upload",
            label_visibility="collapsed"
        )
        if center_uploaded:
            st.session_state["center_file"] = center_uploaded
            st.rerun()

    st.markdown("""<div style="text-align: center; color: #94a3b8; padding: 1rem;">
        <p style="font-size: 0.9rem;">Or use the ☰ sidebar for advanced pipeline settings</p>
    </div>""", unsafe_allow_html=True)
