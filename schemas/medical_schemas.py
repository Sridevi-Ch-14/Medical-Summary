"""
ClinIQ - Medical Data Schemas
==============================
Pydantic models enforcing strict typing for all medical data
flowing through the 6-phase pipeline.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class TestResult(BaseModel):
    """A single parsed lab test result."""
    test_name: str = Field(..., description="Normalized test name (e.g., 'Hemoglobin')")
    observed_value: float = Field(default=0.0, description="The numeric result value (0.0 for qualitative)")
    unit: str = Field(default="", description="Measurement unit (e.g., 'g/dL')")
    reference_low: Optional[float] = Field(default=None, description="Low end of reference range")
    reference_high: Optional[float] = Field(default=None, description="High end of reference range")
    test_group: Optional[str] = Field(default=None, description="Lab section (e.g., 'Biochemistry', 'Immunoassay', 'Hematology')")
    qualitative_value: Optional[str] = Field(default=None, description="Non-numeric result: POSITIVE, NEGATIVE, TRACE, etc.")


class FlaggedResult(BaseModel):
    """A test result with abnormality classification attached."""
    test_name: str
    observed_value: float = 0.0
    unit: str = ""
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    status: Literal[
        "CRITICAL_LOW", "LOW", "NORMAL", "HIGH", "CRITICAL_HIGH", "UNKNOWN",
        "POSITIVE", "NEGATIVE"
    ] = Field(..., description="Deterministic classification based on reference range")
    severity_score: int = Field(
        default=0, ge=0, le=10,
        description="Severity from 0 (normal) to 10 (life-threatening)"
    )
    test_group: Optional[str] = Field(default=None, description="Lab section (e.g., 'Biochemistry', 'Immunoassay')")
    clinical_urgency: Optional[str] = Field(
        default="NORMAL",
        description="Clinical significance: CRITICAL (crosses disease threshold), WARNING (approaching threshold), NORMAL"
    )
    qualitative_value: Optional[str] = Field(default=None, description="Non-numeric result: POSITIVE, NEGATIVE, TRACE, etc.")


class DetectedCondition(BaseModel):
    """A clinical condition detected by the rule engine."""
    condition: str = Field(..., description="Name of detected condition")
    logic: str = Field(..., description="Human-readable rule that triggered detection")
    severity: str = Field(..., description="LOW / MODERATE / HIGH / CRITICAL")
    supporting_tests: List[str] = Field(
        default_factory=list,
        description="Test names that contributed to this detection"
    )
    recommendation: str = Field(
        default="", description="Clinical recommendation for this condition"
    )


class RetrievedContext(BaseModel):
    """A chunk of medical knowledge retrieved from the RAG layer."""
    text: str = Field(..., description="The retrieved knowledge text")
    source: str = Field(default="medical_knowledge.txt", description="Source document")
    relevance_score: float = Field(
        default=0.0, description="Cosine similarity score (0-1)"
    )


class ClinicalSummary(BaseModel):
    """AI-generated dual-persona clinical summary."""
    patient_summary: str = Field(
        ..., description="Patient-friendly summary in simple language"
    )
    doctor_summary: str = Field(
        ..., description="Technical summary for clinicians"
    )
    citations: List[str] = Field(
        default_factory=list,
        description="Source citations for every AI claim"
    )


class AntibioticResult(BaseModel):
    """A single antibiotic susceptibility result from culture & sensitivity testing."""
    name: str = Field(..., description="Antibiotic name (e.g., 'Ciprofloxacin')")
    status: str = Field(..., description="Susceptibility: 'Sensitive', 'Resistant', or 'Intermediate'")
    mic: Optional[str] = Field(default=None, description="Minimum Inhibitory Concentration if reported")


class MicrobiologyResult(BaseModel):
    """Parsed microbiology culture & sensitivity report data."""
    organism: str = Field(default="", description="Isolated organism (e.g., 'Escherichia coli')")
    specimen_type: str = Field(default="", description="Specimen type (e.g., 'Urine', 'Blood')")
    colony_count: Optional[str] = Field(default=None, description="Colony count (e.g., '10^5 CFU/ml')")
    colony_count_numeric: Optional[float] = Field(default=None, description="Numeric colony count (e.g., 100000.0)")
    antibiotics: List[AntibioticResult] = Field(default_factory=list, description="Antibiotic susceptibility results")
    gram_stain: Optional[str] = Field(default=None, description="Gram stain result if reported")
    method: Optional[str] = Field(default=None, description="Culture method (e.g., 'Kirby-Bauer disc diffusion')")
    is_significant: bool = Field(default=False, description="Whether colony count indicates significant infection")


class AnalysisReport(BaseModel):
    """The complete output of the 6-phase analysis pipeline."""
    # Metadata
    file_name: str = Field(default="", description="Original uploaded file name")
    file_type: str = Field(default="", description="File extension (.pdf, .docx, .txt)")
    processing_time_seconds: float = Field(default=0.0)

    # Phase 1: Extraction
    raw_text: str = Field(default="", description="Raw extracted text from document")

    # Privacy
    pii_masked_text: str = Field(default="", description="Text after PII scrubbing")
    masked_entities: List[str] = Field(
        default_factory=list, description="List of PII entities that were masked"
    )

    # Phase 2-3: Parsing + Abnormality Detection
    test_results: List[FlaggedResult] = Field(
        default_factory=list, description="Parsed and classified test results"
    )

    # Phase 2M: Microbiology
    microbiology_results: Optional[MicrobiologyResult] = Field(
        default=None, description="Parsed microbiology culture & sensitivity data"
    )

    # Phase 4: Clinical Rules
    detected_conditions: List[DetectedCondition] = Field(
        default_factory=list, description="Conditions flagged by the rule engine"
    )

    # Phase 5: RAG
    rag_contexts: List[RetrievedContext] = Field(
        default_factory=list, description="Retrieved medical knowledge passages"
    )

    # Phase 6: AI Summary
    clinical_summary: Optional[ClinicalSummary] = Field(
        default=None, description="AI-generated dual summary"
    )
