"""
ClinIQ - Abnormality Detector (Phase 3) v2.0
=============================================
DETERMINISTIC logic only - NO AI involved.
Compares observed values against reference ranges.

v2.0: Added clinical override thresholds for medically significant
      tests (ADA glucose cutoffs, vitamin deficiency tiers, etc.)
      and clinical_urgency classification.
"""

import logging
from typing import List, Tuple
from schemas.medical_schemas import TestResult, FlaggedResult

logger = logging.getLogger(__name__)

# ============================================================
# CLINICAL OVERRIDE THRESHOLDS
# ============================================================
# These override the generic range-based classification for tests
# where specific clinical cutpoints define disease states.
# Format: test_name -> list of (threshold, direction, status, severity, urgency)
# Evaluated in ORDER - first match wins, so put most severe first.
CLINICAL_OVERRIDES = {
    # --- ADA Diabetes Thresholds ---
    "Glucose": [
        (200, ">=", "CRITICAL_HIGH", 10, "CRITICAL"),   # Random glucose ≥200 = confirmed diabetes
        (126, ">=", "CRITICAL_HIGH", 8, "CRITICAL"),    # Fasting ≥126 = diabetic (ADA)
        (100, ">=", "HIGH", 5, "WARNING"),              # 100-125 = pre-diabetic
        (54,  "<",  "CRITICAL_LOW", 9, "CRITICAL"),     # Severe hypoglycemia
        (70,  "<",  "LOW", 4, "WARNING"),               # Hypoglycemia
    ],
    "HbA1c": [
        (9.0, ">=", "CRITICAL_HIGH", 10, "CRITICAL"),   # Very poorly controlled
        (6.5, ">=", "CRITICAL_HIGH", 8, "CRITICAL"),    # Diabetic (ADA)
        (5.7, ">=", "HIGH", 5, "WARNING"),              # Pre-diabetic
    ],
    # --- Vitamin D Tiers (Endocrine Society) ---
    "Vitamin D": [
        (10,  "<",  "CRITICAL_LOW", 9, "CRITICAL"),     # Severe deficiency
        (20,  "<",  "LOW", 6, "WARNING"),               # Deficiency
        (30,  "<",  "LOW", 3, "WARNING"),               # Insufficiency
    ],
    # --- Vitamin B12 ---
    "Vitamin B12": [
        (148, "<",  "CRITICAL_LOW", 9, "CRITICAL"),     # Severe - neuropathy risk
        (200, "<",  "CRITICAL_LOW", 7, "CRITICAL"),     # Deficiency
        (300, "<",  "LOW", 4, "WARNING"),               # Borderline
    ],
    # --- IgE (Allergy) ---
    "IgE": [
        (500, ">=", "CRITICAL_HIGH", 9, "CRITICAL"),    # Severe - parasitic/ABPA
        (200, ">=", "CRITICAL_HIGH", 7, "CRITICAL"),    # Significant elevation - allergy referral
        (100, ">=", "HIGH", 3, "WARNING"),              # Mild elevation
    ],
    # --- Hemoglobin (Anemia) ---
    "Hemoglobin": [
        (7.0, "<",  "CRITICAL_LOW", 10, "CRITICAL"),    # Transfusion threshold
        (8.0, "<",  "CRITICAL_LOW", 9, "CRITICAL"),     # Severe anemia
        (10.0, "<", "LOW", 6, "WARNING"),               # Moderate anemia
        (12.0, "<", "LOW", 3, "WARNING"),               # Mild anemia
        (18.0, ">=", "HIGH", 5, "WARNING"),             # Polycythemia
    ],
    # --- Kidney ---
    "Creatinine": [
        (4.0, ">=", "CRITICAL_HIGH", 10, "CRITICAL"),   # Kidney failure
        (2.0, ">=", "CRITICAL_HIGH", 8, "CRITICAL"),    # Severe impairment
        (1.3, ">=", "HIGH", 5, "WARNING"),              # Mild elevation
    ],
    # --- Thyroid ---
    "TSH": [
        (10.0, ">=", "CRITICAL_HIGH", 8, "CRITICAL"),   # Overt hypothyroidism
        (4.5, ">=", "HIGH", 5, "WARNING"),              # Subclinical
        (0.1, "<",  "CRITICAL_LOW", 8, "CRITICAL"),     # Overt hyperthyroidism
        (0.4, "<",  "LOW", 5, "WARNING"),               # Subclinical
    ],
    # --- eGFR (INVERTED — higher is better) ---
    # eGFR >= 90 = NORMAL. DO NOT flag as HIGH.
    # Only LOW eGFR is clinically concerning.
    "eGFR": [
        (15,  "<",  "CRITICAL_LOW", 10, "CRITICAL"),    # Stage 5 - kidney failure
        (30,  "<",  "CRITICAL_LOW", 8, "CRITICAL"),     # Stage 4 - severe
        (60,  "<",  "LOW", 6, "WARNING"),               # Stage 3 - moderate
        (90,  "<",  "LOW", 3, "WARNING"),               # Stage 2 - mild
        # >= 90 will fall through to NORMAL — which is correct
    ],
    # --- Homocysteine ---
    "Homocysteine": [
        (30, ">=", "CRITICAL_HIGH", 9, "CRITICAL"),     # Severe - thrombotic risk
        (15, ">=", "HIGH", 6, "WARNING"),               # Elevated CVD risk
    ],
}


def detect_abnormalities(results: List[TestResult]) -> List[FlaggedResult]:
    """Classify each test result against its reference range using hard logic."""
    flagged = []
    for result in results:
        # Handle qualitative results (Urine, Microscopy)
        if result.qualitative_value:
            status, severity, urgency = _classify_qualitative(
                result.test_name, result.qualitative_value
            )
            flagged.append(FlaggedResult(
                test_name=result.test_name, observed_value=result.observed_value,
                unit=result.unit, reference_low=result.reference_low,
                reference_high=result.reference_high, status=status,
                severity_score=severity, test_group=result.test_group,
                clinical_urgency=urgency,
                qualitative_value=result.qualitative_value
            ))
            if status == "POSITIVE":
                logger.info(
                    f"FLAGGED (QUALITATIVE): {result.test_name} = "
                    f"{result.qualitative_value} -> severity: {severity}/10, urgency: {urgency}"
                )
            continue

        # Numeric classification: try clinical override first
        override = _check_clinical_override(result.test_name, result.observed_value)

        if override:
            status, severity, urgency = override
        else:
            status, severity = _classify_single(
                result.observed_value, result.reference_low,
                result.reference_high, result.test_name
            )
            urgency = _infer_urgency(status, severity)

        flagged.append(FlaggedResult(
            test_name=result.test_name, observed_value=result.observed_value,
            unit=result.unit, reference_low=result.reference_low,
            reference_high=result.reference_high, status=status,
            severity_score=severity, test_group=result.test_group,
            clinical_urgency=urgency
        ))
        if status != "NORMAL":
            logger.info(
                f"FLAGGED: {result.test_name} = {result.observed_value} -> "
                f"{status} (severity: {severity}/10, urgency: {urgency})"
            )

    abnormal_count = sum(1 for f in flagged if f.status not in ("NORMAL", "NEGATIVE"))
    logger.info(f"Detection: {len(flagged)} tests, {abnormal_count} abnormal")
    return flagged


# ============================================================
# QUALITATIVE CLASSIFICATION
# ============================================================
# Tests where POSITIVE is clinically significant
CRITICAL_POSITIVE_TESTS = {
    "Glucose (Urine)": ("CRITICAL", 8),     # Glucosuria = diabetes investigation
    "Blood (Urine)": ("CRITICAL", 7),       # Hematuria = kidney/bladder concern
    "Protein (Urine)": ("WARNING", 5),      # Proteinuria
    "Albumin (Urine)": ("WARNING", 5),      # Albuminuria
    "Nitrite (Urine)": ("WARNING", 6),      # UTI indicator
    "Bilirubin (Urine)": ("WARNING", 5),    # Liver concern
    "Ketones (Urine)": ("WARNING", 5),      # DKA or fasting
    "Leukocyte Esterase": ("WARNING", 6),   # UTI indicator
    "Bacteria (Urine)": ("WARNING", 5),     # Infection
}

def _classify_qualitative(test_name: str, qual_value: str):
    """Classify a qualitative test result. Returns (status, severity, urgency)."""
    if qual_value in ("POSITIVE", "TRACE"):
        if test_name in CRITICAL_POSITIVE_TESTS:
            urgency, severity = CRITICAL_POSITIVE_TESTS[test_name]
            return ("POSITIVE", severity, urgency)
        return ("POSITIVE", 3, "WARNING")
    elif qual_value == "NEGATIVE":
        return ("NEGATIVE", 0, "NORMAL")
    return ("UNKNOWN", 0, "NORMAL")


def _check_clinical_override(test_name: str, value: float):
    """
    Check if a test has clinical override thresholds.
    Returns (status, severity, urgency) or None.
    """
    if test_name not in CLINICAL_OVERRIDES:
        return None

    for threshold, direction, status, severity, urgency in CLINICAL_OVERRIDES[test_name]:
        if direction == ">=" and value >= threshold:
            return (status, severity, urgency)
        elif direction == "<" and value < threshold:
            return (status, severity, urgency)

    return None  # Value doesn't trigger any override -> use generic logic


def _infer_urgency(status: str, severity: int) -> str:
    """Infer clinical urgency from status and severity when no override exists."""
    if "CRITICAL" in status or severity >= 8:
        return "CRITICAL"
    elif status in ("HIGH", "LOW") and severity >= 4:
        return "WARNING"
    elif status in ("HIGH", "LOW"):
        return "WARNING"
    return "NORMAL"


def _classify_single(value, ref_low, ref_high, test_name=""):
    """Classify a single value. Returns (status, severity_score)."""
    if ref_low is None or ref_high is None:
        return ("UNKNOWN", 0)
    range_span = ref_high - ref_low
    if range_span == 0:
        if value == ref_low: return ("NORMAL", 0)
        return ("LOW", 5) if value < ref_low else ("HIGH", 5)

    critical_low = ref_low - (range_span * 0.5)
    critical_high = ref_high + (range_span * 0.5)

    if value < critical_low:
        sev = min(10, int(8 + 2 * (critical_low - value) / range_span))
        return ("CRITICAL_LOW", min(sev, 10))
    elif value < ref_low:
        dev = (ref_low - value) / range_span
        return ("LOW", min(7, max(2, int(2 + dev * 10))))
    elif value > critical_high:
        sev = min(10, int(8 + 2 * (value - critical_high) / range_span))
        return ("CRITICAL_HIGH", min(sev, 10))
    elif value > ref_high:
        dev = (value - ref_high) / range_span
        return ("HIGH", min(7, max(2, int(2 + dev * 10))))
    else:
        return ("NORMAL", 0)


def get_abnormal_results(flagged):
    return [f for f in flagged if f.status not in ("NORMAL", "UNKNOWN")]

def get_critical_results(flagged):
    return [f for f in flagged if "CRITICAL" in f.status]


# ============================================================
# MICROBIOLOGY ABNORMALITY DETECTION
# ============================================================
def detect_microbiology_abnormalities(micro) -> List[FlaggedResult]:
    """
    Convert microbiology culture & sensitivity data into FlaggedResult objects.
    These merge into the main flagged results list for downstream processing.

    Args:
        micro: MicrobiologyResult from the microbiology parser
    Returns:
        List of FlaggedResult objects for organism, colony count, and each antibiotic
    """
    if micro is None:
        return []

    flagged = []

    # 1. Organism Isolated → CRITICAL finding
    if micro.organism:
        severity = 9 if micro.is_significant else 7
        urgency = "CRITICAL" if micro.is_significant else "WARNING"
        specimen_tag = f" ({micro.specimen_type})" if micro.specimen_type else ""
        flagged.append(FlaggedResult(
            test_name=f"Organism Isolated{specimen_tag}",
            observed_value=1.0,
            unit="culture",
            reference_low=None,
            reference_high=None,
            status="POSITIVE",
            severity_score=severity,
            test_group="Microbiology",
            clinical_urgency=urgency,
            qualitative_value=micro.organism,
        ))
        logger.info(
            f"FLAGGED (MICRO): Organism '{micro.organism}' -> "
            f"severity: {severity}/10, urgency: {urgency}"
        )

    # 2. Colony Count → CRITICAL if significant
    if micro.colony_count:
        severity = 9 if micro.is_significant else 4
        urgency = "CRITICAL" if micro.is_significant else "WARNING"
        numeric_val = micro.colony_count_numeric or 0.0
        flagged.append(FlaggedResult(
            test_name="Colony Count",
            observed_value=numeric_val,
            unit="CFU/ml",
            reference_low=None,
            reference_high=100000.0,  # Significance threshold
            status="CRITICAL_HIGH" if micro.is_significant else "HIGH",
            severity_score=severity,
            test_group="Microbiology",
            clinical_urgency=urgency,
            qualitative_value=micro.colony_count,
        ))

    # 3. Each Resistant Antibiotic → CRITICAL flag
    resistant_drugs = [a for a in micro.antibiotics if a.status == "Resistant"]
    sensitive_drugs = [a for a in micro.antibiotics if a.status == "Sensitive"]

    for drug in resistant_drugs:
        flagged.append(FlaggedResult(
            test_name=f"{drug.name} (Resistance)",
            observed_value=1.0,
            unit="susceptibility",
            reference_low=None,
            reference_high=None,
            status="POSITIVE",
            severity_score=8,
            test_group="Antimicrobial Resistance",
            clinical_urgency="CRITICAL",
            qualitative_value="RESISTANT",
        ))

    # 4. Multi-Drug Resistance summary flag (if ≥3 resistant)
    if len(resistant_drugs) >= 3:
        drug_names = ", ".join(d.name for d in resistant_drugs)
        flagged.append(FlaggedResult(
            test_name="Multi-Drug Resistance (MDR)",
            observed_value=float(len(resistant_drugs)),
            unit="drugs resistant",
            reference_low=None,
            reference_high=None,
            status="POSITIVE",
            severity_score=10,
            test_group="Antimicrobial Resistance",
            clinical_urgency="CRITICAL",
            qualitative_value=f"RESISTANT to {len(resistant_drugs)} antibiotics: {drug_names}",
        ))
        logger.warning(
            f"MDR ALERT: {len(resistant_drugs)} drugs resistant: {drug_names}"
        )

    # 5. Each Sensitive Antibiotic → for treatment options display
    for drug in sensitive_drugs:
        flagged.append(FlaggedResult(
            test_name=f"{drug.name} (Effective)",
            observed_value=0.0,
            unit="susceptibility",
            reference_low=None,
            reference_high=None,
            status="NEGATIVE",
            severity_score=0,
            test_group="Effective Antibiotics",
            clinical_urgency="NORMAL",
            qualitative_value="SENSITIVE",
        ))

    logger.info(
        f"Microbiology detection: {len(flagged)} results generated "
        f"({len(resistant_drugs)} resistant, {len(sensitive_drugs)} sensitive)"
    )

    return flagged

