"""
ClinIQ - Test Name Normalizer (Phase 2) v2.0
==============================================
Handles REAL-WORLD report formats including:
- Trailing H/L/HH/LL flags (e.g., "Fasting Blood Sugar H")
- Lab-specific naming (Sterling Accuris, SRL, Thyrocare, etc.)
- Parenthetical formats: "25(OH) Vitamin D"
- Comma-separated: "Homocysteine, Serum"
"""

import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# MASTER NORMALIZATION MAP
# ============================================================
NORMALIZATION_MAP = {
    # --- Complete Blood Count (CBC) ---
    "hb": "Hemoglobin", "hgb": "Hemoglobin", "hemoglobin": "Hemoglobin",
    "haemoglobin": "Hemoglobin",

    "wbc": "White Blood Cell Count", "white blood cells": "White Blood Cell Count",
    "white blood cell count": "White Blood Cell Count", "leukocytes": "White Blood Cell Count",
    "leukocyte count": "White Blood Cell Count", "total wbc": "White Blood Cell Count",
    "total wbc count": "White Blood Cell Count", "wbc count": "White Blood Cell Count",
    "total leucocyte count": "White Blood Cell Count", "tlc": "White Blood Cell Count",

    "rbc": "Red Blood Cell Count", "red blood cells": "Red Blood Cell Count",
    "red blood cell count": "Red Blood Cell Count", "erythrocytes": "Red Blood Cell Count",
    "erythrocyte count": "Red Blood Cell Count", "rbc count": "Red Blood Cell Count",
    "total rbc count": "Red Blood Cell Count",

    "plt": "Platelet Count", "platelets": "Platelet Count",
    "platelet count": "Platelet Count", "thrombocytes": "Platelet Count",
    "thrombocyte count": "Platelet Count",

    "hct": "Hematocrit", "hematocrit": "Hematocrit", "haematocrit": "Hematocrit",
    "packed cell volume": "Hematocrit", "pcv": "Hematocrit",
    "pcv/hct": "Hematocrit", "pcv / hct": "Hematocrit",

    "mcv": "MCV", "mean corpuscular volume": "MCV",
    "mch": "MCH", "mean corpuscular hemoglobin": "MCH",
    "mchc": "MCHC", "mean corpuscular hemoglobin concentration": "MCHC",
    "rdw": "RDW", "red cell distribution width": "RDW", "rdw-cv": "RDW",
    "rdw(cv)": "RDW", "rdw (cv)": "RDW",
    "mpv": "MPV", "mean platelet volume": "MPV",

    # Medicover CBC variants
    "r b c count": "Red Blood Cell Count",
    "tlc (total leucocyte count)": "White Blood Cell Count",
    "total leucocytes count": "White Blood Cell Count",

    # --- Metabolic Panel / Glucose ---
    "glu": "Glucose", "glucose": "Glucose", "fasting glucose": "Glucose",
    "blood sugar": "Glucose", "fasting blood sugar": "Glucose", "fbs": "Glucose",
    "blood glucose": "Glucose", "random glucose": "Glucose", "serum glucose": "Glucose",
    "plasma glucose": "Glucose", "fasting plasma glucose": "Glucose",
    "glucose, fasting": "Glucose", "glucose fasting": "Glucose",
    "glucose (fasting)": "Glucose", "blood sugar (fasting)": "Glucose",
    "fasting blood glucose": "Glucose", "fbg": "Glucose",
    # Medicover glucose variants
    "fbs (fasting blood glucose)": "Glucose",
    "fasting blood glucose (fbs)": "Glucose",
    "post lunch blood glucose": "Post-Prandial Glucose",
    "plbs (post lunch blood glucose)": "Post-Prandial Glucose",
    "plbs": "Post-Prandial Glucose",
    "post prandial blood sugar": "Post-Prandial Glucose",
    "ppbs": "Post-Prandial Glucose",

    # --- HbA1c ---
    "hba1c": "HbA1c", "a1c": "HbA1c", "glycated hemoglobin": "HbA1c",
    "glycosylated hemoglobin": "HbA1c", "hemoglobin a1c": "HbA1c",
    "hb a1c": "HbA1c", "glycated hb": "HbA1c", "glycohemoglobin": "HbA1c",
    "hba1c (glycated hemoglobin)": "HbA1c",
    # Medicover HbA1c variants
    "hba1c (glycosylated haemoglobin)": "HbA1c",
    "glycosylated haemoglobin": "HbA1c",

    # --- Kidney ---
    "bun": "BUN", "blood urea nitrogen": "BUN", "urea nitrogen": "BUN",
    "urea": "Urea", "blood urea": "Urea", "serum urea": "Urea",
    "creatinine": "Creatinine", "creat": "Creatinine", "serum creatinine": "Creatinine",
    "creatinine, serum": "Creatinine",
    "egfr": "eGFR", "estimated gfr": "eGFR", "glomerular filtration rate": "eGFR",
    "egfr (estimated creatine clearance)": "eGFR",
    "estimated creatine clearance": "eGFR",

    # --- Electrolytes ---
    "sodium": "Sodium", "na": "Sodium", "na+": "Sodium", "serum sodium": "Sodium",
    "potassium": "Potassium", "k": "Potassium", "k+": "Potassium", "serum potassium": "Potassium",
    "calcium": "Calcium", "ca": "Calcium", "ca2+": "Calcium",
    "serum calcium": "Calcium", "total calcium": "Calcium",
    "chloride": "Chloride", "cl": "Chloride", "cl-": "Chloride",
    "co2": "CO2", "carbon dioxide": "CO2", "bicarbonate": "CO2", "hco3": "CO2",
    "phosphorus": "Phosphorus", "phosphate": "Phosphorus", "serum phosphorus": "Phosphorus",
    "magnesium": "Magnesium", "mg": "Magnesium", "serum magnesium": "Magnesium",

    # --- Lipid Panel ---
    "chol": "Total Cholesterol", "cholesterol": "Total Cholesterol",
    "total cholesterol": "Total Cholesterol", "total chol": "Total Cholesterol",
    "serum cholesterol": "Total Cholesterol",
    "ldl": "LDL Cholesterol", "ldl cholesterol": "LDL Cholesterol",
    "ldl-c": "LDL Cholesterol", "low density lipoprotein": "LDL Cholesterol",
    "ldl cholesterol (direct)": "LDL Cholesterol", "ldl direct": "LDL Cholesterol",
    "hdl": "HDL Cholesterol", "hdl cholesterol": "HDL Cholesterol",
    "hdl-c": "HDL Cholesterol", "high density lipoprotein": "HDL Cholesterol",
    "triglycerides": "Triglycerides", "trig": "Triglycerides", "tg": "Triglycerides",
    "serum triglycerides": "Triglycerides", "tryglycerides": "Triglycerides",
    "serum tryglycerides": "Triglycerides",
    "vldl": "VLDL", "vldl cholesterol": "VLDL",
    "cho/hdl ratio": "Cholesterol/HDL Ratio", "chol/hdl ratio": "Cholesterol/HDL Ratio",
    "ldl/hdl": "LDL/HDL Ratio", "ldl/hdl ratio": "LDL/HDL Ratio",
    "ldl cholesterol direct": "LDL Cholesterol",

    # --- Thyroid ---
    "tsh": "TSH", "thyroid stimulating hormone": "TSH",
    "tsh (ultrasensitive)": "TSH", "tsh ultrasensitive": "TSH",
    "t3": "T3", "triiodothyronine": "T3", "total t3": "T3",
    "free t3": "Free T3", "ft3": "Free T3",
    "t4": "T4", "thyroxine": "T4", "total t4": "T4",
    "free t4": "Free T4", "ft4": "Free T4",

    # --- Vitamins & Minerals ---
    "vit d": "Vitamin D", "vitamin d": "Vitamin D", "vit. d": "Vitamin D",
    "25-oh vitamin d": "Vitamin D", "25-hydroxyvitamin d": "Vitamin D",
    "25 oh vit d": "Vitamin D", "calcidiol": "Vitamin D",
    "25(oh) vitamin d": "Vitamin D", "25 (oh) vitamin d": "Vitamin D",
    "vitamin d, 25-hydroxy": "Vitamin D", "vitamin d total": "Vitamin D",
    "25-oh-d": "Vitamin D", "vitamin d 25 hydroxy": "Vitamin D",
    "25 hydroxy vitamin d": "Vitamin D",

    "vit b12": "Vitamin B12", "vitamin b12": "Vitamin B12", "b12": "Vitamin B12",
    "cobalamin": "Vitamin B12", "cyanocobalamin": "Vitamin B12",
    "vitamin b-12": "Vitamin B12", "vit. b12": "Vitamin B12",
    "serum vitamin b12": "Vitamin B12",

    "folate": "Folate", "folic acid": "Folate", "serum folate": "Folate",
    "vitamin b9": "Folate",

    "iron": "Iron", "serum iron": "Iron", "fe": "Iron",
    "ferritin": "Ferritin", "serum ferritin": "Ferritin",
    "tibc": "TIBC", "total iron binding capacity": "TIBC",
    "transferrin saturation": "Transferrin Saturation",

    # --- Liver Panel ---
    "alt": "ALT", "alanine aminotransferase": "ALT", "sgpt": "ALT",
    "alt (sgpt)": "ALT", "sgpt (alt)": "ALT",
    "sgpt (alanine aminotransferase)": "ALT",
    "ast": "AST", "aspartate aminotransferase": "AST", "sgot": "AST",
    "ast (sgot)": "AST", "sgot (ast)": "AST",
    "alp": "ALP", "alkaline phosphatase": "ALP",
    "ggt": "GGT", "gamma gt": "GGT", "gamma glutamyl transferase": "GGT",
    "bilirubin": "Bilirubin", "total bilirubin": "Bilirubin", "tbil": "Bilirubin",
    "serum bilirubin total": "Bilirubin",
    "direct bilirubin": "Direct Bilirubin", "indirect bilirubin": "Indirect Bilirubin",
    "conjugated bilirubin": "Direct Bilirubin",
    "albumin": "Albumin", "serum albumin": "Albumin", "alb": "Albumin",
    "total protein": "Total Protein", "tp": "Total Protein",
    "a/g ratio": "A/G Ratio", "albumin/globulin ratio": "A/G Ratio",
    "globulin": "Globulin",

    # --- Inflammatory Markers ---
    "crp": "CRP", "c-reactive protein": "CRP", "c reactive protein": "CRP",
    "hs-crp": "hs-CRP", "hs crp": "hs-CRP", "high sensitivity crp": "hs-CRP",
    "esr": "ESR", "erythrocyte sedimentation rate": "ESR", "sed rate": "ESR",

    # --- Homocysteine (Cardiovascular) ---
    "homocysteine": "Homocysteine", "homocysteine, serum": "Homocysteine",
    "serum homocysteine": "Homocysteine", "hcy": "Homocysteine",
    "homocysteine serum": "Homocysteine", "plasma homocysteine": "Homocysteine",
    "total homocysteine": "Homocysteine",

    # --- Immunology ---
    "ige": "IgE", "total ige": "IgE", "serum ige": "IgE",
    "immunoglobulin e": "IgE", "ige total": "IgE",
    "iga": "IgA", "immunoglobulin a": "IgA",
    "igg": "IgG", "immunoglobulin g": "IgG",
    "igm": "IgM", "immunoglobulin m": "IgM",

    # --- Urinalysis ---
    "uric acid": "Uric Acid", "serum uric acid": "Uric Acid",

    # --- Urine Tests (Qualitative + Quantitative) ---
    "glucose (urine)": "Glucose (Urine)", "urine glucose": "Glucose (Urine)",
    "glucose urine": "Glucose (Urine)", "sugar (urine)": "Glucose (Urine)",
    "urine sugar": "Glucose (Urine)",

    "albumin (urine)": "Albumin (Urine)", "urine albumin": "Albumin (Urine)",
    "albumin urine": "Albumin (Urine)", "protein (urine)": "Protein (Urine)",
    "urine protein": "Protein (Urine)",

    "blood (urine)": "Blood (Urine)", "urine blood": "Blood (Urine)",
    "occult blood (urine)": "Blood (Urine)",

    "ketone (urine)": "Ketones (Urine)", "urine ketones": "Ketones (Urine)",
    "ketones (urine)": "Ketones (Urine)", "ketone bodies": "Ketones (Urine)",

    "bilirubin (urine)": "Bilirubin (Urine)", "urine bilirubin": "Bilirubin (Urine)",
    "urobilinogen": "Urobilinogen", "urine urobilinogen": "Urobilinogen",

    "nitrite (urine)": "Nitrite (Urine)", "urine nitrite": "Nitrite (Urine)",
    "nitrite": "Nitrite (Urine)",
    "leukocyte esterase": "Leukocyte Esterase",
    "leucocytes": "Leucocytes (Urine)", "leucocyte": "Leucocytes (Urine)",
    "leukocytes": "Leucocytes (Urine)",
    "leucocytes (urine)": "Leucocytes (Urine)",

    # --- Urine Microscopy ---
    "pus cells": "Pus Cells", "pus cells (urine)": "Pus Cells",
    "wbc (urine)": "Pus Cells", "pus cells /hpf": "Pus Cells",
    "rbc (urine)": "RBC (Urine)", "red blood cells (urine)": "RBC (Urine)",
    "rbc /hpf": "RBC (Urine)",
    "epithelial cells": "Epithelial Cells", "epithelial cells (urine)": "Epithelial Cells",
    "casts": "Casts (Urine)", "casts (urine)": "Casts (Urine)",
    "crystals": "Crystals (Urine)", "crystals (urine)": "Crystals (Urine)",
    "bacteria": "Bacteria (Urine)", "bacteria (urine)": "Bacteria (Urine)",
    "yeast": "Yeast (Urine)", "yeast (urine)": "Yeast (Urine)",
    "others": "Others (Urine)",

    # --- Urine Physical ---
    "urine colour": "Urine Color", "urine color": "Urine Color", "colour (urine)": "Urine Color",
    "colour": "Urine Color", "color": "Urine Color",
    "urine appearance": "Urine Appearance", "appearance (urine)": "Urine Appearance",
    "appearance": "Urine Appearance",
    "urine ph": "Urine pH", "ph (urine)": "Urine pH", "ph": "Urine pH",
    "specific gravity": "Specific Gravity", "specific gravity (urine)": "Specific Gravity",
    "sp. gravity": "Specific Gravity",
    "volume": "Urine Volume",
    # NOTE: "protein" alone is NOT mapped to urine — it could be Total Protein (liver).
    # Section-aware enrichment in the parser handles urine context.
    # Same for "ketone" — only "ketone (urine)" or "urine ketones" maps to urine.
    "glucose": "Glucose",
}

# ============================================================
# DEFAULT REFERENCE RANGES (extended)
# ============================================================
EXTENDED_DEFAULTS = {
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
}


def normalize_test_name(raw_name: str) -> str:
    """
    Normalize a raw test name to its canonical form.

    Strategy:
    1. Strip trailing H/L/HH/LL flags (lab abnormality markers)
    2. Lowercase + strip whitespace + remove trailing punctuation
    3. Look up in normalization map
    4. If not found, try without parenthetical content
    5. If still not found, return title-cased original
    """
    if not raw_name:
        return raw_name

    # Step 1: Strip trailing H/L flags (e.g., "Fasting Blood Sugar H" -> "Fasting Blood Sugar")
    cleaned = raw_name.strip()
    cleaned = re.sub(r'\s+[HL]{1,2}\s*$', '', cleaned, flags=re.IGNORECASE)

    # Step 2: Lowercase, remove trailing punctuation, normalize whitespace
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r'[:\-\.]+$', '', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Step 3: Direct lookup
    if cleaned in NORMALIZATION_MAP:
        normalized = NORMALIZATION_MAP[cleaned]
        logger.debug(f"Normalized: '{raw_name}' -> '{normalized}'")
        return normalized

    # Step 4: Try without parenthetical content — "25(OH) Vitamin D" -> "25 vitamin d"
    no_parens = re.sub(r'\([^)]*\)', '', cleaned).strip()
    no_parens = re.sub(r'\s+', ' ', no_parens)
    if no_parens in NORMALIZATION_MAP:
        normalized = NORMALIZATION_MAP[no_parens]
        logger.debug(f"Normalized (no-parens): '{raw_name}' -> '{normalized}'")
        return normalized

    # Step 5: Try with commas removed — "Homocysteine, Serum" -> "homocysteine serum"
    no_commas = cleaned.replace(",", "").strip()
    no_commas = re.sub(r'\s+', ' ', no_commas)
    if no_commas in NORMALIZATION_MAP:
        normalized = NORMALIZATION_MAP[no_commas]
        logger.debug(f"Normalized (no-commas): '{raw_name}' -> '{normalized}'")
        return normalized

    # Step 6: Try just the first word for abbreviated tests
    first_word = cleaned.split()[0] if cleaned.split() else ""
    if first_word and len(first_word) >= 2 and first_word in NORMALIZATION_MAP:
        normalized = NORMALIZATION_MAP[first_word]
        logger.debug(f"Normalized (first-word): '{raw_name}' -> '{normalized}'")
        return normalized

    # Not found — return title-cased original (without H/L flag)
    fallback = re.sub(r'\s+[HL]{1,2}\s*$', '', raw_name.strip(), flags=re.IGNORECASE)
    return fallback.strip().title()
