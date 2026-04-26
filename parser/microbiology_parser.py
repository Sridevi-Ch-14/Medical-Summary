"""
ClinIQ - Microbiology Culture & Sensitivity Parser (Phase 2M) v1.0
====================================================================
Dedicated parser for microbiology reports that extracts:
- Organism isolated (e.g., Escherichia coli)
- Colony count and significance (e.g., 10^5 CFU/ml)
- Antibiotic susceptibility table (Sensitive/Resistant/Intermediate)
- Specimen type (Urine, Blood, Sputum, etc.)
- Gram stain results

This parser runs BEFORE the standard numeric parser. If a microbiology
report is detected, it extracts culture-specific data that regex-based
numeric parsers would completely miss.

Designed against real Tenet Diagnostics Culture & Sensitivity reports.
"""

import re
import logging
from typing import Optional, List, Tuple

from schemas.medical_schemas import MicrobiologyResult, AntibioticResult

logger = logging.getLogger(__name__)

# ============================================================
# REPORT TYPE DETECTION
# ============================================================
MICRO_KEYWORDS = [
    r"culture\s+and\s+sensitivity",
    r"culture\s*&\s*sensitivity",
    r"antimicrobial\s+susceptibility",
    r"antibiotic\s+susceptibility",
    r"organism\s+isolated",
    r"department\s+of\s+microbiology",
    r"colony\s+count",
    r"CFU/ml",
    r"kirby[\s\-]?bauer",
    r"disc\s+diffusion",
    r"aerobic\s+culture",
]
MICRO_DETECTION_RE = [re.compile(p, re.IGNORECASE) for p in MICRO_KEYWORDS]


def is_microbiology_report(text: str) -> bool:
    """Detect if the text contains a microbiology culture & sensitivity report."""
    match_count = sum(1 for p in MICRO_DETECTION_RE if p.search(text))
    detected = match_count >= 2  # Need at least 2 keyword matches
    if detected:
        logger.info(f"Microbiology report detected ({match_count} keyword matches)")
    return detected


# ============================================================
# ORGANISM EXTRACTION
# ============================================================
ORGANISM_PATTERNS = [
    # "Organism  Isolated : Escherichia coli grown in culture."
    re.compile(
        r'Organism\s+Isolated\s*:\s*(?P<org>[A-Za-z][A-Za-z\s\.]+?)'
        r'\s*(?:grown|detected|isolated|identified)',
        re.IGNORECASE
    ),
    # "Organism  Isolated : Escherichia coli" (end of line)
    re.compile(
        r'Organism\s+Isolated\s*:\s*(?P<org>[A-Za-z][A-Za-z\s\.]+?)\s*$',
        re.IGNORECASE | re.MULTILINE
    ),
    # OCR format: ": Escherichia coli grown in culture." on its own line (after "Organism Isolated" header)
    re.compile(
        r':\s*(?P<org>[A-Z][a-z]+\s+[a-z]+)\s+grown\s+in\s+culture',
        re.IGNORECASE
    ),
    # Direct search for known organism names in text
    re.compile(
        r'(?P<org>(?:Escherichia\s+coli|Staphylococcus\s+aureus|Klebsiella\s+pneumoniae|'
        r'Proteus\s+mirabilis|Pseudomonas\s+aeruginosa|Enterococcus\s+faecalis|'
        r'Acinetobacter\s+baumannii|Citrobacter\s+freundii|Enterobacter\s+cloacae|'
        r'Serratia\s+marcescens|Morganella\s+morganii|Candida\s+albicans))',
        re.IGNORECASE
    ),
    # "Growth of Escherichia coli"
    re.compile(
        r'(?:Growth|Isolation)\s+of\s+(?P<org>[A-Z][a-z]+\s+[a-z]+)',
        re.IGNORECASE
    ),
    # "Isolated: Staphylococcus aureus"
    re.compile(
        r'Isolated\s*:\s*(?P<org>[A-Z][a-z]+\s+[a-z]+)',
        re.IGNORECASE
    ),
]

# Common clinically significant organisms for validation
KNOWN_ORGANISMS = [
    "escherichia coli", "e. coli", "e.coli",
    "staphylococcus aureus", "s. aureus",
    "klebsiella pneumoniae", "klebsiella",
    "proteus mirabilis", "proteus vulgaris",
    "pseudomonas aeruginosa", "pseudomonas",
    "enterococcus faecalis", "enterococcus",
    "streptococcus", "streptococcus pyogenes",
    "acinetobacter", "citrobacter",
    "candida", "candida albicans",
    "salmonella", "shigella",
    "enterobacter", "serratia",
    "morganella morganii",
]


def _extract_organism(text: str) -> str:
    """Extract the isolated organism from the report text."""
    for pattern in ORGANISM_PATTERNS:
        match = pattern.search(text)
        if match:
            org = match.group("org").strip().rstrip(".")
            # Clean up: remove trailing noise words
            org = re.sub(r'\s+(grown|detected|in|culture|from|specimen).*$', '', org, flags=re.IGNORECASE)
            org = org.strip()
            if len(org) >= 3:
                logger.info(f"Organism extracted: '{org}'")
                return org
    return ""


# ============================================================
# COLONY COUNT EXTRACTION
# ============================================================
COLONY_COUNT_PATTERNS = [
    # "Colony Count : 10^5 CFU/ml"
    re.compile(
        r'Colony\s+Count\s*:\s*(?P<qualifier>[><=]*)?\s*(?P<count>[\d]+[\^x][\d]+)\s*CFU/ml',
        re.IGNORECASE
    ),
    # "Colony Count : >10^5 CFU/ml"
    re.compile(
        r'Colony\s+Count\s*:\s*(?P<qualifier>[><=]*)\s*(?P<count>\d+\s*[\^x]\s*\d+)\s*CFU/ml',
        re.IGNORECASE
    ),
    # "10^5 CFU/ml" standalone in text
    re.compile(
        r'(?P<qualifier>[><=]*)?\s*(?P<count>\d+[\^x]\d+)\s*CFU/ml',
        re.IGNORECASE
    ),
    # ">100000 CFU/ml" numeric format
    re.compile(
        r'(?P<qualifier>[><=]*)\s*(?P<count>\d{3,})\s*CFU/ml',
        re.IGNORECASE
    ),
]


def _extract_colony_count(text: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Extract colony count string and numeric value.
    Returns (display_string, numeric_value).
    """
    for pattern in COLONY_COUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            qualifier = match.group("qualifier") or ""
            count_str = match.group("count").strip()
            display = f"{qualifier}{count_str} CFU/ml".strip()

            # Parse numeric value
            numeric = _parse_colony_numeric(count_str)
            logger.info(f"Colony count: '{display}' (numeric: {numeric})")
            return display, numeric

    return None, None


def _parse_colony_numeric(count_str: str) -> Optional[float]:
    """Convert colony count string to numeric value."""
    # "10^5" or "10x5" format
    match = re.match(r'(\d+)\s*[\^x]\s*(\d+)', count_str)
    if match:
        base = int(match.group(1))
        exp = int(match.group(2))
        return float(base ** exp)

    # Pure numeric: "100000"
    try:
        return float(count_str)
    except ValueError:
        return None


# ============================================================
# ANTIBIOTIC SUSCEPTIBILITY TABLE PARSER
# ============================================================
SUSCEPTIBILITY_VALUES = {"sensitive", "resistant", "intermediate"}

# Pattern: "Ciprofloxacin    Resistant"  (multi-whitespace separated)
ANTIBIOTIC_TABLE_RE = re.compile(
    r'^(?P<antibiotic>[A-Za-z][A-Za-z/\-\s\.]+?)'
    r'\s{2,}'
    r'(?P<status>Sensitive|Resistant|Intermediate)\s*$',
    re.IGNORECASE | re.MULTILINE
)

# Pattern: "Ciprofloxacin : Resistant"
ANTIBIOTIC_COLON_RE = re.compile(
    r'^(?P<antibiotic>[A-Za-z][A-Za-z/\-\s\.]+?)'
    r'\s*:\s*'
    r'(?P<status>Sensitive|Resistant|Intermediate)\s*$',
    re.IGNORECASE | re.MULTILINE
)

# Known antibiotic names for validation
KNOWN_ANTIBIOTICS = {
    "amikacin", "gentamycin", "gentamicin", "tobramycin",
    "cefoperazone", "cefoperazone/sulbactum", "cefoperazone/sulbactam",
    "amoxicillin", "amox/clavulinic acid", "amoxicillin/clavulanate",
    "amoxyclav", "augmentin",
    "piperacillin", "piperacillin/tazobactum", "piperacillin/tazobactam",
    "imipenem", "meropenem", "ertapenem", "doripenem",
    "cefazolin", "cephalexin", "cefadroxil",
    "cefepime", "ceftriaxone", "cefuroxime", "cefixime", "cefotaxime",
    "cefoxitin", "ceftazidime",
    "ciprofloxacin", "ofloxacin", "levofloxacin", "norfloxacin", "moxifloxacin",
    "nitrofurantoin", "fosfomycin",
    "ampicillin", "ampicillin/sulbactam",
    "co-trimoxazole", "trimethoprim", "trimethoprim/sulfamethoxazole",
    "tetracycline", "doxycycline", "minocycline",
    "azithromycin", "erythromycin", "clarithromycin",
    "vancomycin", "teicoplanin", "linezolid", "daptomycin",
    "colistin", "polymyxin b", "tigecycline",
    "chloramphenicol", "clindamycin", "metronidazole", "rifampicin",
    "nalidixic acid", "penicillin",
}


def _extract_antibiotics(text: str) -> List[AntibioticResult]:
    """Extract antibiotic susceptibility table from the report."""
    results = []
    seen = set()

    # Strategy 1: Multi-whitespace separated table
    for match in ANTIBIOTIC_TABLE_RE.finditer(text):
        name = match.group("antibiotic").strip()
        status = match.group("status").strip().title()

        # Skip noise lines that aren't antibiotics
        if _is_valid_antibiotic(name):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                results.append(AntibioticResult(name=name, status=status))

    # Strategy 2: Colon-separated (fallback if Strategy 1 yields nothing)
    if not results:
        for match in ANTIBIOTIC_COLON_RE.finditer(text):
            name = match.group("antibiotic").strip()
            status = match.group("status").strip().title()
            if _is_valid_antibiotic(name):
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    results.append(AntibioticResult(name=name, status=status))

    if results:
        resistant = [a.name for a in results if a.status == "Resistant"]
        sensitive = [a.name for a in results if a.status == "Sensitive"]
        logger.info(
            f"Antibiotic table: {len(results)} drugs parsed. "
            f"Resistant: {len(resistant)}, Sensitive: {len(sensitive)}"
        )

    return results


def _is_valid_antibiotic(name: str) -> bool:
    """Validate that a name is likely an antibiotic (not a noise line)."""
    lower = name.lower().strip()

    # Too short or too long
    if len(lower) < 3 or len(lower) > 50:
        return False

    # Filter out common noise
    noise_words = [
        "antibiotics", "susceptibility", "investigation", "result",
        "method", "interpretation", "note", "reference", "organism",
        "colony", "department", "page", "name", "test", "dr ",
        "consultant", "registered", "collected", "reported",
    ]
    if any(lower.startswith(nw) for nw in noise_words):
        return False

    # Check against known antibiotics (fuzzy match first word)
    first_word = lower.split("/")[0].split()[0] if lower else ""
    if any(first_word in known for known in KNOWN_ANTIBIOTICS):
        return True

    # Accept if it looks like a drug name (single or compound)
    if re.match(r'^[a-z][a-z\-]+(?:/[a-z\-\s]+)?$', lower):
        return True

    return False


# ============================================================
# SPECIMEN TYPE DETECTION
# ============================================================
SPECIMEN_PATTERNS = [
    re.compile(r'Culture\s+And\s+Sensitivity\s*,?\s*(?P<spec>Urine|Blood|Sputum|Wound|Stool|CSF|Pus)', re.IGNORECASE),
    re.compile(r'Specimen\s*(?:Type)?\s*:\s*(?P<spec>[A-Za-z\s]+)', re.IGNORECASE),
    re.compile(r'Sample\s*(?:Type)?\s*:\s*(?P<spec>Urine|Blood|Sputum|Wound|Stool|CSF|Pus)', re.IGNORECASE),
]

SPECIMEN_KEYWORDS = {
    "urine": "Urine",
    "blood": "Blood",
    "sputum": "Sputum",
    "wound": "Wound",
    "stool": "Stool",
    "csf": "CSF",
    "pus": "Pus",
    "tissue": "Tissue",
    "swab": "Swab",
}


def _extract_specimen_type(text: str) -> str:
    """Extract specimen type from the report."""
    for pattern in SPECIMEN_PATTERNS:
        match = pattern.search(text)
        if match:
            spec = match.group("spec").strip()
            # Normalize
            for key, canonical in SPECIMEN_KEYWORDS.items():
                if key in spec.lower():
                    return canonical
            return spec.title()
    return ""


# ============================================================
# GRAM STAIN EXTRACTION
# ============================================================
GRAM_STAIN_RE = re.compile(
    r'(?:Gram\s+Stain|Gram\s+Reaction)\s*:\s*(?P<result>[^\n]+)',
    re.IGNORECASE
)


def _extract_gram_stain(text: str) -> Optional[str]:
    """Extract gram stain result if present."""
    match = GRAM_STAIN_RE.search(text)
    if match:
        return match.group("result").strip()
    return None


# ============================================================
# METHOD EXTRACTION
# ============================================================
METHOD_RE = re.compile(
    r'Method\s*:\s*(?P<method>.*?(?:disc\s+diffusion|dilution|automated|vitek)[^\n]*)',
    re.IGNORECASE
)


def _extract_method(text: str) -> Optional[str]:
    """Extract culture method if present."""
    match = METHOD_RE.search(text)
    if match:
        return match.group("method").strip().rstrip(".")
    return None


# ============================================================
# SIGNIFICANCE ASSESSMENT
# ============================================================
def _assess_significance(colony_count_numeric: Optional[float], specimen_type: str) -> bool:
    """
    Determine if the colony count indicates significant infection.

    Urine:
      ≥10^5 CFU/ml = Significant (confirmed UTI)
      10^4 - 10^5 = Possibly significant (correlate clinically)
      <10^3 = Likely contamination

    Blood: Any growth is significant
    Other: ≥10^4 generally significant
    """
    if colony_count_numeric is None:
        return False

    specimen_lower = specimen_type.lower()

    if "urine" in specimen_lower:
        return colony_count_numeric >= 1e5
    elif "blood" in specimen_lower:
        return colony_count_numeric > 0
    else:
        return colony_count_numeric >= 1e4


# ============================================================
# MAIN PARSER ENTRY POINT
# ============================================================
def parse_microbiology(text: str) -> Optional[MicrobiologyResult]:
    """
    Parse a microbiology culture & sensitivity report.

    Returns MicrobiologyResult if microbiology data is found, None otherwise.
    This should be called BEFORE the standard numeric parser in the pipeline.
    """
    if not text or not text.strip():
        return None

    if not is_microbiology_report(text):
        return None

    logger.info("=" * 60)
    logger.info("MICROBIOLOGY PARSER: Processing culture & sensitivity report")
    logger.info("=" * 60)

    # Extract all components
    organism = _extract_organism(text)
    colony_count, colony_numeric = _extract_colony_count(text)
    antibiotics = _extract_antibiotics(text)
    specimen_type = _extract_specimen_type(text)
    gram_stain = _extract_gram_stain(text)
    method = _extract_method(text)

    # Must have at least organism OR antibiotics to be a valid micro result
    if not organism and not antibiotics:
        logger.warning("Microbiology keywords detected but no organism or antibiotics extracted")
        return None

    is_significant = _assess_significance(colony_numeric, specimen_type)

    result = MicrobiologyResult(
        organism=organism,
        specimen_type=specimen_type,
        colony_count=colony_count,
        colony_count_numeric=colony_numeric,
        antibiotics=antibiotics,
        gram_stain=gram_stain,
        method=method,
        is_significant=is_significant,
    )

    # Log summary
    resistant_count = sum(1 for a in antibiotics if a.status == "Resistant")
    sensitive_count = sum(1 for a in antibiotics if a.status == "Sensitive")
    logger.info(
        f"MICROBIOLOGY RESULT: Organism='{organism}', Specimen='{specimen_type}', "
        f"Colony='{colony_count}', Significant={is_significant}, "
        f"Antibiotics={len(antibiotics)} (R={resistant_count}, S={sensitive_count})"
    )

    return result

