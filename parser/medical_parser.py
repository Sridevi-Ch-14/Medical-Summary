"""
ClinIQ - Medical Report Parser (Phase 2) v3.0
==============================================
Noise-Resistant Extraction Pipeline that distinguishes
Clinical Data (facts) from Interpretive Text (explanations).

v3.0: Junk text filter, qualitative detection (Urine/Microscopy),
      header-based segmentation, </>  prefix handling.
"""

import re
import logging
from typing import List, Optional, Tuple

from schemas.medical_schemas import TestResult
from parser.normalizer import normalize_test_name

logger = logging.getLogger(__name__)

# ============================================================
# JUNK TEXT / NOISE FILTER (Logic 1)
# ============================================================
JUNK_PATTERNS = [
    r"Excellent\s+Control.*",
    r"Good\s+Control.*",
    r"Fair\s+Control.*",
    r"Poor\s+Control.*",
    r"Interpretation\s*[:\-].*",
    r"Notes?\s*[:\-].*",
    r"Normal\s*:\s*<.*",
    r"Ref\.?\s+Range\s*[:\-].*",
    r"Control\s*[:\-].*",
    r"Comment\s*[:\-].*",
    r"Remark\s*[:\-].*",
    r"Method\s*[:\-].*",
    r"Methodology\s*[:\-].*",
    r"Sample\s+(Type|collected|received).*",
    r"Report\s+(Date|Status|Generated).*",
    r"^\*+.*\*+$",
    r"^-{5,}$",
    r"^={5,}$",
    r"Page\s+\d+\s+of\s+\d+",
    r"^\s*(Dr\.?|Doctor)\s+[A-Z].*",
    r"Printed\s+(on|at|by)\s+.*",
    r"This\s+report\s+is\s+.*",
    r"^\s*End\s+of\s+Report\s*$",
    # Medicover-specific noise
    r"Near\s+Optimal.*",
    r"Optimal.*",
    r"Desirable.*",
    r"Borderline\s+High.*",
    r"Normal\s*:\s*.*",
    r"Diabetic\s*:\s*.*",
    r"Pre[-\s]?Diabetic\s*:\s*.*",
    r"Derived\s+from.*",
    r"^\s*Tolerance.*",
    r"^\s*High\s+Risk.*",
    r"^\s*Low\s+Risk.*",
    r"^\s*Adequate\s+for.*",
    r"^\s*Insufficient.*reference.*",
    r"^\s*Target\s*[:<].*",
    # Report footer/metadata noise
    r"^\s*Remarks?\s*[:.].*",
    r"^\s*Remarks?\s*$",
    r"^\s*Disclaimer.*",
    r"^\s*Authorized\s+(by|signatory).*",
    r"^\s*Checked\s+By.*",
    r"^\s*Collected\s+(on|at|by).*",
    r"^\s*Received\s+(on|at|by).*",
    r"^\s*Verified\s+(by|on).*",
    r"^\s*Report\s+(Footer|Generated|Printed).*",
    r"^\s*Sample\s+(ID|No|Type|Collected).*",
    r"^\s*Bill\s+(Date|No).*",
    r"^\s*Rec\.\s+Dt.*",
    r"^\s*Rept\.\s+Dt.*",
    r"^\s*Ref\s+By.*",
    r"^\s*UMR\s+No.*",
]
JUNK_COMPILED = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]

# ============================================================
# LAB METHOD WORDS (Medicover/Indian Lab interference)
# ============================================================
METHOD_WORDS = [
    "Photometric", "Calculated", "Derived", "HPLC", "ECLIA",
    "Impedance", "Turbidimetric", "Colorimetric", "Enzymatic",
    "Ion Selective", "ISE", "Flow Cytometry", "Nephelometric",
    "Immunoturbidimetric", "Kinetic", "ELISA", "CLIA",
    "Chemiluminescence", "Direct", "Indirect", "Modified",
    "Fluorescence", "Latex", "Agglutination", "Reflectance",
    "Electrophoresis", "Capillary", "Spectrophotometric",
    "Automated", "Semi-Automated", "Manual",
    # Medicover-specific multi-word methods
    "Hexokinase", "DIAZO", "Jaffe", "Calculation",
    "Electrical Impedance", "DHSS/Microscopy", "DHSS",
    "Glucose oxidase", "Bromthymol blue",
    "Tetra-bromophenol blue", "Diazonium salt",
    "Sodium nitroprusside", "Sulfanilic acid",
    "UV without P5P", "Homogeneous enzymatic colorimetric",
    "Direct-Enzymatic colorimetric", "Enzymatic colorimetric",
    "Homogeneous enzymatic", "Leishman",
    "Peroxidase", "Rothera",
]
# For stripping method words from lines that ALSO have data
_METHOD_PATTERN = re.compile(
    r'\b(?:' + '|'.join(re.escape(w) for w in METHOD_WORDS) + r')\b',
    re.IGNORECASE
)
# Keywords that signal a standalone method line (no digits required)
_METHOD_LINE_KEYWORDS = [
    "photometric", "calculated", "derived", "hplc", "eclia", "impedance",
    "turbidimetric", "colorimetric", "enzymatic", "nephelometric",
    "kinetic", "elisa", "clia", "chemiluminescence", "fluorescence",
    "spectrophotometric", "hexokinase", "diazo", "jaffe", "calculation",
    "dhss", "microscopy", "bromthymol", "diazonium", "nitroprusside",
    "sulfanilic", "peroxidase", "rothera", "leishman", "agglutination",
    "homogeneous", "p5p",
]


def _strip_method_words(line: str) -> str:
    """Strip lab methodology words from a line."""
    cleaned = _METHOD_PATTERN.sub('', line)
    cleaned = re.sub(r'\s{2,}', '  ', cleaned).strip()
    return cleaned


def clean_medical_text(raw_text: str) -> str:
    """
    Two-pass noise filter:
    Pass 1: Remove interpretive text, junk lines, narrative blocks
    Pass 2: Strip lab method words from surviving lines
    """
    lines = raw_text.split('\n')
    cleaned = []
    skip_block = False  # Track if we're inside an interpretation block

    for line in lines:
        stripped = line.strip()
        if not stripped:
            skip_block = False  # Empty line ends a block
            cleaned.append(line)
            continue

        # Block-level skip: if we hit an INTERPRETATION header,
        # skip all lines until the next section header or empty line
        if re.match(r'^\s*INTERPRETATION\s*$', stripped, re.IGNORECASE):
            skip_block = True
            continue
        if skip_block:
            # Check if this line starts a new section (ends the block)
            if _detect_section_header(stripped):
                skip_block = False
                cleaned.append(line)
            continue

        # Rule 1: Lines with 4+ words but NO digits = narrative text
        words = stripped.split()
        has_digit = any(char.isdigit() for char in stripped)
        has_qualitative = any(kw in stripped.lower() for kw in
            ['present', 'absent', 'nil', 'positive', 'negative', 'trace', 'reactive'])
        if not has_digit and not has_qualitative and len(words) > 4:
            if _detect_section_header(stripped):
                cleaned.append(line)
            continue

        # Rule 2: Skip lines matching known junk patterns
        if any(p.search(stripped) for p in JUNK_COMPILED):
            logger.debug(f"Junk filtered: {stripped[:60]}")
            continue

        # Pass 2: Strip method words from data lines
        processed = _strip_method_words(stripped)
        if processed:
            cleaned.append(processed)

    result = "\n".join(cleaned)
    logger.info(f"Noise filter: {len(lines)} lines -> {len(cleaned)} lines ({len(lines) - len(cleaned)} removed)")
    return result


# ============================================================
# QUALITATIVE VALUE DETECTION (Logic 2)
# ============================================================
QUALITATIVE_PATTERNS = [
    # Pattern: "Glucose (Urine)  Present (+)"  or  "LEUCOCYTES  Positive (+++)"
    re.compile(
        r'^(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
        r'\s{2,}'
        r'(?P<qualval>Present\s*\(\+{1,4}\)|Positive\s*\(\+{1,4}\)|Present|Absent|Nil|Negative|Positive|Trace|'
        r'Plenty|Numerous|Few|Occasional|'
        r'Not\s+Detected|Detected|Non[- ]?Reactive|Reactive)',
        re.IGNORECASE
    ),
    # Pattern: "Glucose (Urine): Present (+)"
    re.compile(
        r'(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
        r'\s*:\s*'
        r'(?P<qualval>Present\s*\(\+{1,4}\)|Positive\s*\(\+{1,4}\)|Present|Absent|Nil|Negative|Positive|Trace|'
        r'Plenty|Numerous|Few|Occasional|'
        r'Not\s+Detected|Detected|Non[- ]?Reactive|Reactive)',
        re.IGNORECASE
    ),
]


def _parse_qualitative(raw_value: str) -> Optional[str]:
    """Convert raw qualitative text to a canonical form."""
    lower = raw_value.strip().lower()
    if "plenty" in lower or "numerous" in lower:
        return "POSITIVE"
    if "present" in lower or "positive" in lower or lower == "detected" or lower == "reactive":
        return "POSITIVE"
    if "nil" in lower or "absent" in lower or "negative" in lower or "not detected" in lower or "non-reactive" in lower or "nonreactive" in lower:
        return "NEGATIVE"
    if "trace" in lower or "few" in lower or "occasional" in lower:
        return "POSITIVE"  # Trace is still clinically positive
    return None


def _get_qualitative_intensity(raw_value: str) -> float:
    """Get intensity score from qualitative value for severity grading."""
    lower = raw_value.strip().lower()
    plus_count = lower.count('+')
    if "plenty" in lower or "numerous" in lower:
        return 4.0
    if plus_count >= 3:
        return 3.0
    if plus_count == 2:
        return 2.0
    if plus_count == 1:
        return 1.0
    if "trace" in lower or "few" in lower:
        return 0.5
    if "present" in lower or "positive" in lower:
        return 1.0
    return 0.0


def _extract_qualitative(line: str) -> Optional[TestResult]:
    """Try to extract a qualitative (non-numeric) result from a line."""
    for pattern in QUALITATIVE_PATTERNS:
        match = pattern.search(line)
        if match:
            raw_name = match.group("test").strip()
            raw_val = match.group("qualval").strip()

            test_name = normalize_test_name(raw_name)
            qual = _parse_qualitative(raw_val)
            if qual:
                intensity = _get_qualitative_intensity(raw_val)
                return TestResult(
                    test_name=test_name,
                    observed_value=intensity if qual == "POSITIVE" else 0.0,
                    unit="qualitative",
                    reference_low=None,
                    reference_high=None,
                    qualitative_value=qual if intensity < 0.5 else f"POSITIVE({'+'*int(intensity) if intensity >= 1 else 'Trace'})",
                )
    return None


# ============================================================
# REGEX PATTERNS for various medical report formats
# ============================================================

# Pattern 1: "Hemoglobin    12.5 g/dL    13.0 - 17.0"
# Also handles: "Vitamin B12  <148 pg/mL   187 - 833"
PATTERN_TABLE = re.compile(
    r'^(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s+'
    r'(?P<qualifier>[<>])?\s*(?P<value>\d+\.?\d*)'
    r'\s+'
    r'(?P<unit>[A-Za-z/%\^0-9\.\-]+(?:/[A-Za-z]+)?)'
    r'\s+'
    r'(?P<low>\d+\.?\d*)'
    r'\s*[\-to]+\s*'
    r'(?P<high>\d+\.?\d*)',
    re.IGNORECASE
)

# Pattern 2: "Hemoglobin: 12.5 g/dL (ref: 13.0-17.0)"
PATTERN_COLON = re.compile(
    r'(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s*:\s*'
    r'(?P<qualifier>[<>])?\s*(?P<value>\d+\.?\d*)'
    r'\s*'
    r'(?P<unit>[A-Za-z/%\^0-9\.\-]+(?:/[A-Za-z]+)?)?'
    r'\s*'
    r'(?:\(?\s*(?:ref(?:erence)?[:\s]*)?'
    r'(?P<low>\d+\.?\d*)'
    r'\s*[\-to]+\s*'
    r'(?P<high>\d+\.?\d*)'
    r'\s*\)?)',
    re.IGNORECASE
)

# Pattern 3: "Hemoglobin  12.5  (13.0 - 17.0)  g/dL"
PATTERN_RANGE_FIRST = re.compile(
    r'(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s+'
    r'(?P<value>\d+\.?\d*)'
    r'\s*'
    r'\(\s*(?P<low>\d+\.?\d*)'
    r'\s*[\-to]+\s*'
    r'(?P<high>\d+\.?\d*)'
    r'\s*\)'
    r'\s*'
    r'(?P<unit>[A-Za-z/%\^0-9\.\-]+(?:/[A-Za-z]+)?)?',
    re.IGNORECASE
)

# Pattern 4: Simple value-only "Hemoglobin  12.5 g/dL" (no reference range)
PATTERN_SIMPLE = re.compile(
    r'^(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s+'
    r'(?P<qualifier>[<>])?\s*(?P<value>\d+\.?\d*)'
    r'\s+'
    r'(?P<unit>[A-Za-z/%\^0-9\.\-]+(?:/[A-Za-z]+)?)\s*$',
    re.IGNORECASE
)

# Pattern 6: MEDICOVER FORMAT — "TEST  VALUE  REF_LOW - REF_HIGH  UNIT [UNIT]"
# Value comes BEFORE reference range. This is the Indian lab format.
# Handles: "HEMOGLOBIN  10.8 12.0 - 15.0  gms/dL gms/dL"
# Also handles: "CREATININE  0.78 0.50 - 0.99 mg/dL"
PATTERN_MEDICOVER = re.compile(
    r'^(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s{2,}'
    r'(?P<qualifier>[<>])?\s*(?P<value>\d+\.?\d*)'
    r'\s+'
    r'(?P<low>\d+\.?\d*)'
    r'\s*[\-to]+\s*'
    r'(?P<high>\d+\.?\d*)'
    r'\s+'
    r'(?P<unit>[A-Za-z/%\^0-9\.\-]+(?:/[A-Za-z0-9]+)?)',
    re.IGNORECASE
)

# Pattern 7: Value + single upper ref only: "TEST  0.31 1.2 mg/dL"
PATTERN_SINGLE_REF = re.compile(
    r'^(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s{2,}'
    r'(?P<value>\d+\.?\d*)'
    r'\s+'
    r'(?P<high>\d+\.?\d*)'
    r'\s+'
    r'(?P<unit>[A-Za-z/%\^0-9\.\-]+(?:/[A-Za-z0-9]+)?)\s*$',
    re.IGNORECASE
)

# Pattern 8: BARE value — "HBA1C  6.1" (no unit, no ref range)
# Last resort: just test name + number
PATTERN_BARE = re.compile(
    r'^(?P<test>[A-Za-z][A-Za-z0-9\s\.\-\(\)/]+?)'
    r'\s{2,}'
    r'(?P<qualifier>[<>])?\s*(?P<value>\d+\.?\d*)\s*$',
    re.IGNORECASE
)

ALL_PATTERNS = [
    ("MEDICOVER", PATTERN_MEDICOVER),   # Most specific — value before ref
    ("TABLE", PATTERN_TABLE),
    ("COLON", PATTERN_COLON),
    ("RANGE_FIRST", PATTERN_RANGE_FIRST),
    ("SINGLE_REF", PATTERN_SINGLE_REF),
    ("SIMPLE", PATTERN_SIMPLE),
    ("BARE", PATTERN_BARE),             # Last resort — no unit
]

# ============================================================
# DEFAULT REFERENCE RANGES
# ============================================================
DEFAULT_REFERENCE_RANGES = {
    "Hemoglobin": (12.0, 17.5, "g/dL"),
    "White Blood Cell Count": (4.5, 11.0, "x10^3/uL"),
    "Red Blood Cell Count": (4.0, 5.5, "x10^6/uL"),
    "Platelet Count": (150.0, 400.0, "x10^3/uL"),
    "Hematocrit": (36.0, 54.0, "%"),
    "MCV": (80.0, 100.0, "fL"),
    "MCH": (27.0, 33.0, "pg"),
    "MCHC": (32.0, 36.0, "g/dL"),
    "Glucose": (70.0, 100.0, "mg/dL"),
    "HbA1c": (4.0, 5.6, "%"),
    "BUN": (7.0, 20.0, "mg/dL"),
    "Creatinine": (0.6, 1.2, "mg/dL"),
    "eGFR": (90.0, 120.0, "mL/min/1.73m2"),
    "Sodium": (136.0, 145.0, "mEq/L"),
    "Potassium": (3.5, 5.0, "mEq/L"),
    "Calcium": (8.5, 10.5, "mg/dL"),
    "Chloride": (96.0, 106.0, "mEq/L"),
    "CO2": (23.0, 29.0, "mEq/L"),
    "Total Cholesterol": (0.0, 200.0, "mg/dL"),
    "LDL Cholesterol": (0.0, 100.0, "mg/dL"),
    "HDL Cholesterol": (40.0, 60.0, "mg/dL"),
    "Triglycerides": (0.0, 150.0, "mg/dL"),
    "TSH": (0.4, 4.0, "mIU/L"),
    "Free T4": (0.8, 1.8, "ng/dL"),
    "Free T3": (2.3, 4.2, "pg/mL"),
    "Vitamin D": (30.0, 100.0, "ng/mL"),
    "Vitamin B12": (200.0, 900.0, "pg/mL"),
    "Folate": (3.0, 20.0, "ng/mL"),
    "Iron": (60.0, 170.0, "ug/dL"),
    "Ferritin": (12.0, 300.0, "ng/mL"),
    "ALT": (7.0, 56.0, "U/L"),
    "AST": (10.0, 40.0, "U/L"),
    "ALP": (44.0, 147.0, "U/L"),
    "Bilirubin": (0.1, 1.2, "mg/dL"),
    "Albumin": (3.4, 5.4, "g/dL"),
    "Total Protein": (6.0, 8.3, "g/dL"),
    "CRP": (0.0, 3.0, "mg/L"),
    "ESR": (0.0, 20.0, "mm/hr"),
    "Uric Acid": (3.0, 7.0, "mg/dL"),
    "Homocysteine": (5.0, 15.0, "umol/L"),
    "IgE": (0.0, 100.0, "IU/mL"),
    "RDW": (11.5, 14.5, "%"),
    "MPV": (7.5, 11.5, "fL"),
    "GGT": (0.0, 51.0, "U/L"),
    "TIBC": (250.0, 450.0, "ug/dL"),
    "Transferrin Saturation": (20.0, 50.0, "%"),
    "Phosphorus": (2.5, 4.5, "mg/dL"),
    "Magnesium": (1.7, 2.2, "mg/dL"),
    "Globulin": (2.0, 3.5, "g/dL"),
    "VLDL": (2.0, 30.0, "mg/dL"),
    "A/G Ratio": (1.0, 2.5, "ratio"),
    "Direct Bilirubin": (0.0, 0.3, "mg/dL"),
    "hs-CRP": (0.0, 3.0, "mg/L"),
    "IgA": (70.0, 400.0, "mg/dL"),
    "IgG": (700.0, 1600.0, "mg/dL"),
    "IgM": (40.0, 230.0, "mg/dL"),
    "Urea": (15.0, 45.0, "mg/dL"),
    "Post-Prandial Glucose": (0.0, 140.0, "mg/dL"),
    "Indirect Bilirubin": (0.0, 1.0, "mg/dL"),
    "Cholesterol/HDL Ratio": (0.0, 3.5, "ratio"),
    "LDL/HDL Ratio": (0.0, 2.5, "ratio"),
    "Neutrophils": (40.0, 80.0, "%"),
    "Lymphocytes": (20.0, 40.0, "%"),
    "Monocytes": (2.0, 10.0, "%"),
    "Eosinophils": (0.0, 6.0, "%"),
    "Basophils": (0.0, 1.0, "%"),
    "Specific Gravity": (1.000, 1.030, ""),
}
# ============================================================
# IMAGING/RADIOLOGY SECTION KEYWORDS (block these entirely)
# ============================================================
IMAGING_KEYWORDS = [
    "x-ray", "xray", "ultrasound", "usg", "2d echo", "echocardiogram",
    "ct scan", "mri", "mammography", "doppler", "angiography",
    "electrocardiogram", "ecg", "ekg", "pet scan", "dexa",
    "chest pa view", "colour doppler",
]

# Reference-label patterns (Medicover puts these between tests)
REFERENCE_LABEL_RE = re.compile(
    r'^\s*(?:Desirable|Borderline\s+High|Near\s+Optimal|Optimal|Very\s+High|'
    r'Low\s*:|High\s*:|Normal\s+Range|Impaired|Diabetes\s+Mellitus|'
    r'Pre[\s-]?diabetic|Stage\s+\d|Note:)'
    , re.IGNORECASE
)

def _is_method_word_only(line: str) -> bool:
    """Check if a line is ONLY a lab method description (no data)."""
    cleaned = line.strip().rstrip('*').strip()
    if not cleaned or len(cleaned) < 3:
        return False
    # Must have NO digits to be a pure method line
    if any(c.isdigit() for c in cleaned):
        return False
    lower = cleaned.lower()
    # Check if line contains any method keyword
    return any(kw in lower for kw in _METHOD_LINE_KEYWORDS)

def _is_value_line(line: str) -> bool:
    """Check if a line starts with a number (possibly a data line)."""
    cleaned = line.strip()
    return bool(re.match(r'^[\d\.]+\s*\*?', cleaned))

def _is_imaging_section(line: str) -> bool:
    """Check if we're entering an imaging/radiology section."""
    lower = line.lower().strip()
    return any(kw in lower for kw in IMAGING_KEYWORDS)


def _reconstruct_test_lines(lines: List[str]) -> List[str]:
    """
    Reconstruct multi-line test entries into single parseable lines.
    
    Medicover OCR format:
      Line 1: TEST NAME (may span 2 lines)
      Line 2: METHOD WORD (Photometric, HPLC, etc.)
      Line 3: VALUE [*] [REF_LOW - REF_HIGH] [UNIT]
    
    This function joins them: 'HEMOGLOBIN  10.8 12.0 - 15.0 gms/dL'
    """
    result = []
    pending_name = ""
    
    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            if pending_name:
                result.append(pending_name)
                pending_name = ""
            result.append(line)
            continue
        
        # Strip * flags from values: "10.8 *" -> "10.8"
        stripped = re.sub(r'(\d)\s*\*', r'\1', stripped)
        
        # Skip standalone method word lines
        if _is_method_word_only(stripped):
            continue
        
        # Skip reference label lines (Desirable : < 200, etc.)
        if REFERENCE_LABEL_RE.match(stripped):
            continue
        
        # Check if this is a value-only line (starts with number)
        if _is_value_line(stripped) and pending_name:
            # Join pending test name with this value line
            combined = f"{pending_name}  {stripped}"
            result.append(combined)
            pending_name = ""
            continue
        
        # Check if this is a test-name-only line vs a data line
        # Key insight: "HBA1C" has digits but NO standalone number (like 10.8)
        # A data line has standalone decimal numbers: "10.8 12.0 - 15.0 gms/dL"
        has_standalone_number = bool(re.search(r'(?<![A-Za-z])\d+\.?\d*(?![A-Za-z0-9])', stripped))
        has_qual = any(kw in stripped.lower() for kw in
            ['present', 'absent', 'nil', 'positive', 'negative', 'trace', 'plenty', 'numerous'])
        # A "name-like" line: mostly letters, maybe with embedded digits in test names
        is_name_like = bool(re.match(r'^[A-Za-z]', stripped)) and not has_standalone_number and not has_qual
        
        if is_name_like:
            if pending_name:
                # Could be name continuation (e.g., "LEUCOCYTE COUNT)" after "TLC (TOTAL")
                if len(stripped.split()) <= 4 and not _detect_section_header(stripped):
                    pending_name = f"{pending_name} {stripped}"
                else:
                    result.append(pending_name)
                    pending_name = ""
                    # Check if this new line is also a test name
                    if len(stripped.split()) <= 6 and not _detect_section_header(stripped):
                        pending_name = stripped
                    else:
                        result.append(stripped)
            else:
                # Start accumulating a potential test name
                if len(stripped.split()) <= 6 and not _detect_section_header(stripped):
                    pending_name = stripped
                else:
                    result.append(stripped)
            continue
        
        # Line has data (numbers or qualitative values)
        if pending_name and (has_standalone_number or has_qual):
            # Join with pending name if it looks like orphan data
            combined = f"{pending_name}  {stripped}"
            result.append(combined)
            pending_name = ""
            continue
        
        if pending_name:
            result.append(pending_name)
            pending_name = ""
        result.append(stripped)
    
    if pending_name:
        result.append(pending_name)
    
    return result


# ============================================================
# MAIN PARSER
# ============================================================
def parse_medical_text(text: str) -> List[TestResult]:
    """
    Parse cleaned medical report text into structured TestResult objects.
    
    Strategy:
    1. Apply junk text filter to remove interpretive noise
    2. Reconstruct multi-line entries (Medicover format)
    3. Block imaging/radiology sections
    4. Try qualitative patterns first (urine, microscopy)
    5. Then try numeric regex patterns in priority order
    6. Apply default reference ranges if not found
    """
    if not text or not text.strip():
        logger.warning("Empty text received for parsing")
        return []

    # Phase 0: Clean the text — remove interpretive noise
    cleaned_text = clean_medical_text(text)

    # Phase 0.5: Reconstruct multi-line entries
    raw_lines = cleaned_text.split("\n")
    reconstructed = _reconstruct_test_lines(raw_lines)
    
    logger.info(f"Line reconstruction: {len(raw_lines)} -> {len(reconstructed)} lines")

    results = []
    seen_tests = set()
    current_group = None
    in_imaging = False  # Block imaging sections

    for line_num, line in enumerate(reconstructed, 1):
        line = line.strip()
        if not line or len(line) < 3:
            continue

        # Check for imaging section — block entirely
        if _is_imaging_section(line):
            in_imaging = True
            logger.debug(f"Entering imaging section, blocking: {line[:40]}")
            continue
        
        # Resume parsing if we see a new LABORATORY REPORT header
        if "laboratory report" in line.lower():
            in_imaging = False
            continue
        
        if in_imaging:
            continue

        # Skip header-like lines
        if _is_header_line(line):
            continue

        # Detect section headers
        detected_group = _detect_section_header(line)
        if detected_group:
            current_group = detected_group
            logger.debug(f"Line {line_num}: Section header: '{current_group}'")
            continue

        # Try qualitative extraction first (Urine, Microscopy)
        result = _extract_qualitative(line)

        # If no qualitative, try numeric extraction
        if not result:
            result = _extract_from_line(line)

        if result:
            # Attach current section group
            if current_group and not result.test_group:
                result = TestResult(
                    test_name=result.test_name,
                    observed_value=result.observed_value,
                    unit=result.unit,
                    reference_low=result.reference_low,
                    reference_high=result.reference_high,
                    test_group=current_group,
                    qualitative_value=result.qualitative_value,
                )
            
            # Section-aware name enrichment: when generic names are in urine section
            urine_sections = ["urine", "clinical pathology", "cue", "urinalysis"]
            is_urine_section = current_group and any(
                kw in current_group.lower() for kw in urine_sections
            )
            # Map generic names to urine-specific ONLY when in urine section
            urine_generic_names = {
                "Glucose": "Glucose (Urine)",
                "Bilirubin": "Bilirubin (Urine)",
                "Protein": "Protein (Urine)",      # standalone "Protein" in urine section
                "Ketone": "Ketones (Urine)",        # standalone "Ketone" in urine section
            }
            # NEVER convert these to urine — they are blood/liver tests
            urine_exclusions = {"Total Protein", "A/G Ratio", "Albumin", "Globulin"}
            
            if is_urine_section and result.test_name in urine_generic_names and result.test_name not in urine_exclusions:
                new_name = urine_generic_names[result.test_name]
                if new_name != result.test_name:
                    result = TestResult(
                        test_name=new_name,
                        observed_value=result.observed_value,
                        unit=result.unit,
                        reference_low=result.reference_low,
                        reference_high=result.reference_high,
                        test_group=result.test_group,
                        qualitative_value=result.qualitative_value,
                    )
            # Avoid duplicate tests (keep first occurrence)
            if result.test_name not in seen_tests:
                seen_tests.add(result.test_name)
                results.append(result)
                qual_tag = f" [QUAL={result.qualitative_value}]" if result.qualitative_value else ""
                logger.debug(
                    f"Line {line_num}: Parsed '{result.test_name}' = "
                    f"{result.observed_value} {result.unit} "
                    f"[{result.reference_low}-{result.reference_high}]"
                    f" group={result.test_group}{qual_tag}"
                )

    logger.info(f"Parsed {len(results)} test results from {len(reconstructed)} lines")
    return results


def _extract_from_line(line: str) -> Optional[TestResult]:
    """
    Two-pass line extraction:
    1. Try regex on the original line
    2. If no match, strip method words and retry
    This handles 'HEMOGLOBIN Photometric 10.8 g/dL 12.0 - 17.0'
    """
    # Pass 1: Try the line as-is
    result = _try_all_patterns(line)
    if result:
        return result

    # Pass 2: Strip method words and retry
    stripped_line = _strip_method_words(line)
    if stripped_line != line:
        result = _try_all_patterns(stripped_line)
        if result:
            logger.debug(f"Matched after stripping method words: '{line[:50]}' -> '{stripped_line[:50]}'")
            return result

    return None


def _try_all_patterns(line: str) -> Optional[TestResult]:
    """Try all regex patterns against a line."""
    for pattern_name, pattern in ALL_PATTERNS:
        match = pattern.match(line) if pattern_name != "COLON" else pattern.search(line)
        if match:
            try:
                return _build_test_result(match, pattern_name)
            except (ValueError, KeyError) as e:
                logger.debug(f"Pattern {pattern_name} matched but failed: {e}")
                continue
    return None


def _build_test_result(match: re.Match, pattern_name: str) -> Optional[TestResult]:
    """Build a TestResult from a regex match, applying normalization and defaults."""
    groups = match.groupdict()

    raw_name = groups.get("test", "").strip()
    if not raw_name or len(raw_name) < 2:
        return None

    test_name = normalize_test_name(raw_name)

    try:
        value = float(groups["value"])
    except (ValueError, KeyError):
        return None

    unit = groups.get("unit", "").strip() if groups.get("unit") else ""

    ref_low = _safe_float(groups.get("low"))
    ref_high = _safe_float(groups.get("high"))

    # Apply default reference ranges if not found in report
    if ref_low is None or ref_high is None:
        if test_name in DEFAULT_REFERENCE_RANGES:
            default_low, default_high, default_unit = DEFAULT_REFERENCE_RANGES[test_name]
            ref_low = ref_low or default_low
            ref_high = ref_high or default_high
            if not unit:
                unit = default_unit

    # Sanity check: ref_low should be less than ref_high
    if ref_low is not None and ref_high is not None:
        if ref_low > ref_high:
            ref_low, ref_high = ref_high, ref_low

    return TestResult(
        test_name=test_name,
        observed_value=value,
        unit=unit,
        reference_low=ref_low,
        reference_high=ref_high,
    )


def _is_header_line(line: str) -> bool:
    """Check if a line is a table header rather than data."""
    header_keywords = [
        "test name", "result", "reference", "units", "flag",
        "parameter", "normal range", "specimen", "collected",
        "reported", "ordered by", "lab report", "patient",
    ]
    lower = line.lower().strip()
    match_count = sum(1 for kw in header_keywords if kw in lower)
    return match_count >= 2


# ============================================================
# SECTION HEADER DETECTION
# ============================================================
SECTION_KEYWORDS = [
    "biochemistry", "hematology", "haematology", "immunoassay", "immunology",
    "lipid profile", "liver function", "kidney function", "renal function",
    "thyroid profile", "thyroid function", "complete blood count", "cbc",
    "serology", "urine analysis", "urinalysis", "urine examination",
    "urine microscopy", "urine routine", "coagulation",
    "diabetes panel", "metabolic panel", "electrolytes",
    "vitamin assay", "hormone assay", "cardiac markers",
    "iron studies", "inflammatory markers", "microscopy",
]

def _detect_section_header(line: str) -> Optional[str]:
    """Detect if a line is a section header."""
    lower = line.lower().strip()
    cleaned = re.sub(r'^[-=*#>]+\s*', '', lower)
    cleaned = re.sub(r'\s*[-=*#>]+$', '', cleaned)
    cleaned = cleaned.strip()

    if not cleaned or len(cleaned) < 3:
        return None

    for keyword in SECTION_KEYWORDS:
        if keyword in cleaned:
            return cleaned.title()

    # ALL-CAPS section headers with no numbers — BUT exclude known test names
    if line.isupper() and not re.search(r'\d', line) and len(line.split()) <= 4:
        # Don't treat known test names as section headers
        test_name_keywords = [
            "hemoglobin", "haemoglobin", "glucose", "cholesterol", "bilirubin",
            "creatinine", "platelet", "neutrophils", "lymphocytes", "monocytes",
            "eosinophils", "basophils", "albumin", "protein", "ketone",
            "urobilinogen", "nitrite", "volume", "colour", "color",
            "appearance", "specific gravity", "mchc", "mcv", "mch",
            "rdw", "mpv", "tsh", "vldl", "ldl", "hdl", "sgpt", "sgot",
            "alt", "ast", "alp", "ggt", "esr", "crp", "ferritin",
            "iron", "calcium", "sodium", "potassium", "chloride",
            "triglycerides", "tryglycerides", "urea",
        ]
        lower = line.lower().strip()
        if any(kw in lower for kw in test_name_keywords):
            return None
        # Must have at least 2 words to be a section header, to avoid
        # single test names like "SERUM" being treated as sections
        if len(line.split()) >= 2:
            return line.strip().title()

    return None


def _safe_float(value) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
