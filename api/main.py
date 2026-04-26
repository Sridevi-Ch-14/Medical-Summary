"""
ClinIQ - FastAPI Backend
===========================
REST API for the Medical Report Intelligence Engine.
Orchestrates the full 6-phase pipeline.

Endpoints:
  POST /analyze     - Upload file, run full pipeline, return JSON
  POST /analyze/text - Submit raw text, run pipeline
  GET  /health      - Health check
"""

import os
import sys
import time
import shutil
import logging
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("cliniq.api")

from schemas.medical_schemas import AnalysisReport
from extractor.extract_router import extract_text, is_supported, get_file_type
from parser.medical_parser import parse_medical_text
from engine.abnormality_detector import detect_abnormalities
from engine.clinical_rules import evaluate_conditions
from privacy.pii_scrubber import scrub_pii
from ai.clinical_summarizer import generate_clinical_summary

# RAG imports (may fail if chromadb not installed yet)
try:
    from rag.knowledge_indexer import index_knowledge_base, is_indexed
    from rag.knowledge_retriever import retrieve_for_abnormals
    RAG_AVAILABLE = True
except Exception as e:
    logger.warning(f"RAG module not available: {e}")
    RAG_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Index knowledge base on startup if not already done."""
    if RAG_AVAILABLE:
        kb_path = Path(__file__).parent.parent / "data" / "medical_knowledge.txt"
        if kb_path.exists() and not is_indexed():
            logger.info("Indexing medical knowledge base on startup...")
            count = index_knowledge_base(str(kb_path))
            logger.info(f"Indexed {count} knowledge chunks")
        elif is_indexed():
            logger.info("Knowledge base already indexed")
        else:
            logger.warning(f"Knowledge base file not found: {kb_path}")
    yield


app = FastAPI(
    title="ClinIQ - Medical Report Intelligence Engine",
    description="6-phase pipeline: Extract -> Parse -> Detect -> Rules -> RAG -> Summarize",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent.parent / "temp_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ClinIQ Medical Report Intelligence Engine",
        "rag_available": RAG_AVAILABLE,
        "rag_indexed": is_indexed() if RAG_AVAILABLE else False,
    }


@app.post("/analyze", response_model=AnalysisReport)
async def analyze_report(file: UploadFile = File(...)):
    """
    Upload a medical document (PDF, DOCX, TXT) and run the full
    6-phase analysis pipeline.
    """
    start_time = time.time()

    # Validate file type
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in (".pdf", ".docx", ".txt"):
        raise HTTPException(400, f"Unsupported file type: '{ext}'. Use .pdf, .docx, or .txt")

    # Save uploaded file temporarily
    temp_path = UPLOAD_DIR / f"upload_{int(time.time())}_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        report = _run_pipeline(str(temp_path), file.filename or "unknown", ext)
        report.processing_time_seconds = round(time.time() - start_time, 3)
        return report

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(500, f"Analysis failed: {str(e)}")
    finally:
        if temp_path.exists():
            temp_path.unlink()


@app.post("/analyze/text", response_model=AnalysisReport)
async def analyze_text(text: str):
    """Analyze raw medical text directly (for testing without file upload)."""
    start_time = time.time()
    try:
        report = _run_pipeline_from_text(text, "direct_input", ".txt")
        report.processing_time_seconds = round(time.time() - start_time, 3)
        return report
    except Exception as e:
        logger.error(f"Text analysis failed: {e}", exc_info=True)
        raise HTTPException(500, f"Analysis failed: {str(e)}")


def _run_pipeline(file_path: str, file_name: str, file_type: str) -> AnalysisReport:
    """Run the full 6-phase pipeline on a file."""
    # Phase 1: Extract
    logger.info(f"Phase 1: Extracting text from {file_name}")
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        raise ValueError("Could not extract any text from the uploaded file")

    return _run_pipeline_from_text(raw_text, file_name, file_type)


def _run_pipeline_from_text(raw_text: str, file_name: str, file_type: str) -> AnalysisReport:
    """Run phases 2-6 on extracted text."""

    # PII Scrubbing
    logger.info("PII Scrubbing...")
    pii_masked_text, masked_entities = scrub_pii(raw_text)

    # Phase 2: Parse
    logger.info("Phase 2: Parsing structured data...")
    test_results = parse_medical_text(pii_masked_text)

    # Phase 3: Detect abnormalities
    logger.info("Phase 3: Detecting abnormalities...")
    flagged_results = detect_abnormalities(test_results)

    # Phase 4: Clinical rules
    logger.info("Phase 4: Evaluating clinical rules...")
    detected_conditions = evaluate_conditions(flagged_results)

    # Phase 5: RAG retrieval
    rag_contexts = []
    if RAG_AVAILABLE:
        logger.info("Phase 5: Retrieving RAG context...")
        try:
            rag_contexts = retrieve_for_abnormals(flagged_results)
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

    # Phase 6: AI Summary
    logger.info("Phase 6: Generating AI summary...")
    analysis_data = {
        "test_results": [r.model_dump() for r in flagged_results],
        "detected_conditions": [c.model_dump() for c in detected_conditions],
        "rag_contexts": [ctx.model_dump() for ctx in rag_contexts],
    }
    clinical_summary = generate_clinical_summary(analysis_data)

    return AnalysisReport(
        file_name=file_name,
        file_type=file_type,
        raw_text=raw_text,
        pii_masked_text=pii_masked_text,
        masked_entities=masked_entities,
        test_results=flagged_results,
        detected_conditions=detected_conditions,
        rag_contexts=rag_contexts,
        clinical_summary=clinical_summary,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
