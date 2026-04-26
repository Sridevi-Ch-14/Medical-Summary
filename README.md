# 🏥 ClinIQ — Medical Report Intelligence Engine

> A production-grade 6-phase pipeline that converts raw medical documents into structured, verified clinical insights.

## Architecture

```
Top Layer:    Hard Logic (Regex/Rules)    → Reliable
Middle Layer: Medical Knowledge (RAG)     → Contextual
Bottom Layer: LLM (Groq Llama-3)          → Fluent
```

**This is NOT a chatbot.** It's a Verified Clinical Pipeline where every claim is traceable to either the source report or a medical knowledge base.

## Features

- **Multi-format support**: PDF (digital & scanned), Word (.docx), Plain Text (.txt)
- **140+ test name normalizations** (Hb → Hemoglobin, WBC → White Blood Cell Count)
- **Deterministic abnormality detection** — NO AI, pure logic
- **13 clinical rules** for conditions like Diabetes, Anemia, Thyroid disorders
- **RAG-grounded summaries** with source citations
- **Dual-persona AI output**: Patient-friendly + Doctor-technical summaries
- **PII scrubbing** before any data reaches the LLM
- **Sub-second AI responses** via Groq inference engine

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Groq API key
# Edit .env file: GROQ_API_KEY=gsk_your_key_here

# 3. Generate mock data
python setup_data.py

# 4a. Run Streamlit dashboard
streamlit run ui/app.py

# 4b. Or run FastAPI backend
uvicorn api.main:app --reload --port 8000
```

## Tech Stack

| Category | Tool |
|---|---|
| PDF Extraction | pdfplumber + pytesseract |
| Word Extraction | python-docx |
| LLM Inference | Groq (Llama 3.1 70B) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | ChromaDB (local) |
| Backend API | FastAPI |
| Frontend | Streamlit + Plotly |
| PII Masking | Presidio + regex fallback |

## Pipeline Phases

1. **Extract** — PDF/DOCX/TXT → Clean text
2. **Parse** — Text → Structured JSON (TestResult objects)
3. **Detect** — Deterministic LOW/NORMAL/HIGH/CRITICAL classification
4. **Rules** — Constraint-based condition detection
5. **RAG** — ChromaDB knowledge retrieval for clinical context
6. **Summarize** — Groq-powered dual AI summary with citations

## API Usage

```bash
# Upload a file for analysis
curl -X POST http://localhost:8000/analyze \
  -F "file=@data/sample_report.pdf"

# Health check
curl http://localhost:8000/health
```
