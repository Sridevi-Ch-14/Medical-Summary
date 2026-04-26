"""
ClinIQ - Clinical Rule Engine (Phase 4) v2.0
===============================================
Constraint-based medical logic for condition detection.
Handles real-world reports: Sterling Accuris, SRL, Thyrocare, etc.

v2.0: Added Homocysteine, IgE, severity tiers for Vitamin D,
      expanded diabetes detection, fixed default value logic.
"""

import logging
from typing import List, Dict
from schemas.medical_schemas import FlaggedResult, DetectedCondition

logger = logging.getLogger(__name__)

# ============================================================
# HELPER: Safe value getter with explicit "not present" handling
# ============================================================
def _has(vals, key):
    """Check if a test was actually measured (present in the report)."""
    return key in vals

def _val(vals, key, default=None):
    """Get value only if present."""
    return vals.get(key, default)

# ============================================================
# CLINICAL RULES v2.0
# ============================================================

CLINICAL_RULES = [
    # --- DIABETES ---
    {
        "condition": "Type 2 Diabetes Mellitus (Suspected)",
        "logic": "(HbA1c > 6.5%) OR (Fasting Glucose > 126 mg/dL)",
        "tests": ["HbA1c", "Glucose"],
        "evaluate": lambda v: (_has(v, "HbA1c") and v["HbA1c"] > 6.5) or
                              (_has(v, "Glucose") and v["Glucose"] > 126),
        "severity": "HIGH",
        "recommendation": "Endocrinology consult recommended. Repeat fasting glucose and HbA1c in 2 weeks. Begin monitoring for diabetic complications (retinopathy, nephropathy, neuropathy).",
        "icd10": "E11.9",
        "nih_url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/type-2-diabetes",
    },
    {
        "condition": "Pre-Diabetes",
        "logic": "(5.7% <= HbA1c <= 6.5%) OR (100 <= Glucose <= 126 mg/dL)",
        "tests": ["HbA1c", "Glucose"],
        "evaluate": lambda v: (
            (_has(v, "HbA1c") and 5.7 <= v["HbA1c"] <= 6.5) or
            (_has(v, "Glucose") and 100 <= v["Glucose"] <= 126)
        ) and not (
            (_has(v, "HbA1c") and v["HbA1c"] > 6.5) or
            (_has(v, "Glucose") and v["Glucose"] > 126)
        ),
        "severity": "MODERATE",
        "recommendation": "Lifestyle modifications: 150 min/week exercise, reduce refined carbs. Recheck in 3 months.",
        "icd10": "R73.03",
        "nih_url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/prediabetes-insulin-resistance",
    },

    # --- VITAMIN D (TIERED) ---
    {
        "condition": "Severe Vitamin D Deficiency",
        "logic": "Vitamin D < 10 ng/mL",
        "tests": ["Vitamin D"],
        "evaluate": lambda v: _has(v, "Vitamin D") and v["Vitamin D"] < 10,
        "severity": "HIGH",
        "recommendation": "URGENT: Vitamin D3 50,000 IU/week for 8 weeks, then 2000-4000 IU/day maintenance. Check calcium and PTH. High risk for osteomalacia and fractures.",
        "icd10": "E55.9",
        "nih_url": "https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/",
    },
    {
        "condition": "Vitamin D Deficiency",
        "logic": "10 <= Vitamin D < 20 ng/mL",
        "tests": ["Vitamin D"],
        "evaluate": lambda v: _has(v, "Vitamin D") and 10 <= v["Vitamin D"] < 20,
        "severity": "MODERATE",
        "recommendation": "Supplement Vitamin D3 2000-4000 IU daily. Increase sun exposure 15-20 min/day. Recheck in 8-12 weeks.",
        "icd10": "E55.9",
        "nih_url": "https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/",
    },
    {
        "condition": "Vitamin D Insufficiency",
        "logic": "20 <= Vitamin D < 30 ng/mL",
        "tests": ["Vitamin D"],
        "evaluate": lambda v: _has(v, "Vitamin D") and 20 <= v["Vitamin D"] < 30,
        "severity": "LOW",
        "recommendation": "Consider Vitamin D3 1000-2000 IU daily supplementation. Recheck in 3 months.",
        "icd10": "E55.9",
        "nih_url": "https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/",
    },

    # --- VITAMIN B12 ---
    {
        "condition": "Vitamin B12 Deficiency (Megaloblastic Anemia Risk)",
        "logic": "Vitamin B12 < 200 pg/mL",
        "tests": ["Vitamin B12"],
        "evaluate": lambda v: _has(v, "Vitamin B12") and v["Vitamin B12"] < 200,
        "severity": "HIGH",
        "recommendation": "B12 supplementation: IM injection 1000mcg weekly x4 weeks, then monthly. Risk of irreversible neuropathy if untreated. Evaluate for pernicious anemia (anti-intrinsic factor Ab).",
        "icd10": "E53.8",
        "nih_url": "https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/",
    },

    # --- HOMOCYSTEINE (NEW) ---
    {
        "condition": "Hyperhomocysteinemia (Elevated Cardiovascular Risk)",
        "logic": "Homocysteine > 15 umol/L",
        "tests": ["Homocysteine"],
        "evaluate": lambda v: _has(v, "Homocysteine") and v["Homocysteine"] > 15,
        "severity": "HIGH",
        "recommendation": "Elevated homocysteine is an independent cardiovascular risk factor. Check B12, folate, and B6 levels. Supplement with folate 1mg + B12 1000mcg + B6 25mg daily. Repeat in 8 weeks.",
        "icd10": "E72.11",
        "nih_url": "https://medlineplus.gov/lab-tests/homocysteine-test/",
    },
    {
        "condition": "Severe Hyperhomocysteinemia",
        "logic": "Homocysteine > 30 umol/L",
        "tests": ["Homocysteine"],
        "evaluate": lambda v: _has(v, "Homocysteine") and v["Homocysteine"] > 30,
        "severity": "CRITICAL",
        "recommendation": "URGENT: Very high cardiovascular and thrombotic risk. Immediate cardiology referral. Screen for MTHFR polymorphism. Aggressive B-vitamin supplementation.",
        "icd10": "E72.11",
        "nih_url": "https://medlineplus.gov/lab-tests/homocysteine-test/",
    },

    # --- IgE / ALLERGY (NEW) ---
    {
        "condition": "Allergic Sensitization / Atopy",
        "logic": "Total IgE > 100 IU/mL",
        "tests": ["IgE"],
        "evaluate": lambda v: _has(v, "IgE") and v["IgE"] > 100,
        "severity": "MODERATE",
        "recommendation": "Elevated IgE suggests allergic sensitization. Consider specific allergen panel testing (food, inhalant). Allergy/immunology referral if symptomatic.",
        "icd10": "T78.40",
        "nih_url": "https://medlineplus.gov/lab-tests/immunoglobulin-e-ige-test/",
    },
    {
        "condition": "Severe Allergic Response / Parasitic Infection",
        "logic": "Total IgE > 500 IU/mL",
        "tests": ["IgE"],
        "evaluate": lambda v: _has(v, "IgE") and v["IgE"] > 500,
        "severity": "HIGH",
        "recommendation": "Markedly elevated IgE. Rule out parasitic infection (stool O&P), allergic bronchopulmonary aspergillosis (if respiratory symptoms), and hyper-IgE syndrome. Immunology referral.",
        "icd10": "D80.6",
        "nih_url": "https://medlineplus.gov/lab-tests/immunoglobulin-e-ige-test/",
    },

    # --- ANEMIA ---
    {
        "condition": "Anemia",
        "logic": "Hemoglobin < 12.0 g/dL",
        "tests": ["Hemoglobin"],
        "evaluate": lambda v: _has(v, "Hemoglobin") and v["Hemoglobin"] < 12.0,
        "severity": "MODERATE",
        "recommendation": "Investigate: iron studies (ferritin, TIBC), B12, folate. Check MCV for classification (microcytic vs macrocytic). Dietary assessment.",
        "icd10": "D64.9",
        "nih_url": "https://www.nhlbi.nih.gov/health/anemia",
    },
    {
        "condition": "Severe Anemia (Critical)",
        "logic": "Hemoglobin < 8.0 g/dL",
        "tests": ["Hemoglobin"],
        "evaluate": lambda v: _has(v, "Hemoglobin") and v["Hemoglobin"] < 8.0,
        "severity": "CRITICAL",
        "recommendation": "URGENT: Transfusion evaluation. Immediate hematology referral. Identify and treat underlying cause.",
        "icd10": "D64.9",
        "nih_url": "https://www.nhlbi.nih.gov/health/anemia",
    },

    # --- THYROID ---
    {
        "condition": "Hypothyroidism (Suspected)",
        "logic": "TSH > 4.5 mIU/L",
        "tests": ["TSH"],
        "evaluate": lambda v: _has(v, "TSH") and v["TSH"] > 4.5,
        "severity": "MODERATE",
        "recommendation": "Order Free T4. Consider levothyroxine if confirmed. Recheck in 6-8 weeks.",
        "icd10": "E03.9",
        "nih_url": "https://www.niddk.nih.gov/health-information/endocrine-diseases/hypothyroidism",
    },
    {
        "condition": "Hyperthyroidism (Suspected)",
        "logic": "TSH < 0.4 mIU/L",
        "tests": ["TSH"],
        "evaluate": lambda v: _has(v, "TSH") and 0 < v["TSH"] < 0.4,
        "severity": "HIGH",
        "recommendation": "Order thyroid panel (Free T4, Free T3). Endocrinology referral.",
        "icd10": "E05.90",
        "nih_url": "https://www.niddk.nih.gov/health-information/endocrine-diseases/hyperthyroidism",
    },

    # --- LIPIDS ---
    {
        "condition": "Dyslipidemia",
        "logic": "(Total Cholesterol > 240) OR (LDL > 160 mg/dL)",
        "tests": ["Total Cholesterol", "LDL Cholesterol"],
        "evaluate": lambda v: (_has(v, "Total Cholesterol") and v["Total Cholesterol"] > 240) or
                              (_has(v, "LDL Cholesterol") and v["LDL Cholesterol"] > 160),
        "severity": "MODERATE",
        "recommendation": "Lifestyle modifications. Consider statin therapy per ACC/AHA guidelines. 10-year ASCVD risk calculation recommended.",
        "icd10": "E78.5",
        "nih_url": "https://www.nhlbi.nih.gov/health/high-blood-cholesterol",
    },

    # --- KIDNEY ---
    {
        "condition": "Kidney Function Concern",
        "logic": "(Creatinine > 1.3 mg/dL) OR (BUN > 25 mg/dL) OR (Urea > 45 mg/dL)",
        "tests": ["Creatinine", "BUN", "Urea"],
        "evaluate": lambda v: (_has(v, "Creatinine") and v["Creatinine"] > 1.3) or
                              (_has(v, "BUN") and v["BUN"] > 25) or
                              (_has(v, "Urea") and v["Urea"] > 45),
        "severity": "HIGH",
        "recommendation": "Order eGFR, urinalysis. Nephrology consult if persistent elevation.",
        "icd10": "N28.9",
        "nih_url": "https://www.niddk.nih.gov/health-information/kidney-disease",
    },

    # --- LIVER ---
    {
        "condition": "Liver Function Concern",
        "logic": "(ALT > 56 U/L) OR (AST > 40 U/L)",
        "tests": ["ALT", "AST"],
        "evaluate": lambda v: (_has(v, "ALT") and v["ALT"] > 56) or
                              (_has(v, "AST") and v["AST"] > 40),
        "severity": "MODERATE",
        "recommendation": "Repeat LFTs. Consider hepatitis panel, alcohol history, medication review.",
        "icd10": "R94.5",
        "nih_url": "https://www.niddk.nih.gov/health-information/liver-disease",
    },

    # --- IRON ---
    {
        "condition": "Iron Deficiency",
        "logic": "(Ferritin < 12 ng/mL) OR (Iron < 60 ug/dL)",
        "tests": ["Iron", "Ferritin"],
        "evaluate": lambda v: (_has(v, "Ferritin") and v["Ferritin"] < 12) or
                              (_has(v, "Iron") and v["Iron"] < 60),
        "severity": "MODERATE",
        "recommendation": "Iron supplementation (ferrous sulfate 325mg daily with Vitamin C). Evaluate for GI blood loss.",
        "icd10": "E61.1",
        "nih_url": "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/",
    },

    # --- INFLAMMATION ---
    {
        "condition": "Systemic Inflammation",
        "logic": "(CRP > 10 mg/L) OR (ESR > 30 mm/hr)",
        "tests": ["CRP", "ESR"],
        "evaluate": lambda v: (_has(v, "CRP") and v["CRP"] > 10) or
                              (_has(v, "ESR") and v["ESR"] > 30),
        "severity": "MODERATE",
        "recommendation": "Investigate source: infection, autoimmune workup (ANA, RF), malignancy screening.",
        "icd10": "R65.10",
        "nih_url": "https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/",
    },

    # ================================================================
    # MULTI-PARAMETER CORRELATIONS (v3.0 — Clinical Reasoning Logic)
    # ================================================================

    # --- ANEMIA SUBTYPING (cross-referencing Hb + MCV + Ferritin) ---
    {
        "condition": "Microcytic Anemia (Suggestive of Iron Deficiency)",
        "logic": "(Hemoglobin < 12.0 g/dL) AND (MCV < 80 fL)",
        "tests": ["Hemoglobin", "MCV"],
        "evaluate": lambda v: (_has(v, "Hemoglobin") and v["Hemoglobin"] < 12.0) and
                              (_has(v, "MCV") and v["MCV"] < 80),
        "severity": "HIGH",
        "recommendation": "The combination of low hemoglobin with low MCV strongly suggests iron deficiency anemia. Order iron studies (serum iron, ferritin, TIBC, transferrin saturation). Evaluate for GI blood loss in adults. Consider dietary assessment.",
        "icd10": "D50.9",
        "nih_url": "https://www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia",
    },
    {
        "condition": "Macrocytic Anemia (Possible B12/Folate Deficiency)",
        "logic": "(Hemoglobin < 12.0 g/dL) AND (MCV > 100 fL)",
        "tests": ["Hemoglobin", "MCV"],
        "evaluate": lambda v: (_has(v, "Hemoglobin") and v["Hemoglobin"] < 12.0) and
                              (_has(v, "MCV") and v["MCV"] > 100),
        "severity": "HIGH",
        "recommendation": "Elevated MCV with low hemoglobin suggests megaloblastic anemia. Check Vitamin B12, folate, reticulocyte count, and peripheral smear. Rule out hypothyroidism and liver disease as contributing factors.",
        "icd10": "D53.1",
        "nih_url": "https://www.nhlbi.nih.gov/health/anemia",
    },
    {
        "condition": "Iron Deficiency Anemia (Confirmed Pattern)",
        "logic": "(Hemoglobin < 12.0) AND (MCV < 80) AND (Ferritin < 30)",
        "tests": ["Hemoglobin", "MCV", "Ferritin"],
        "evaluate": lambda v: (_has(v, "Hemoglobin") and v["Hemoglobin"] < 12.0) and
                              (_has(v, "MCV") and v["MCV"] < 80) and
                              (_has(v, "Ferritin") and v["Ferritin"] < 30),
        "severity": "HIGH",
        "recommendation": "Classic iron deficiency triad confirmed (low Hb + low MCV + low ferritin). Begin iron supplementation (ferrous sulfate 325mg TID with Vitamin C). Investigate cause: menorrhagia, GI blood loss (occult blood test), celiac disease.",
        "icd10": "D50.9",
        "nih_url": "https://www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia",
    },

    # --- THYROID SUBTYPING ---
    {
        "condition": "Subclinical Hypothyroidism",
        "logic": "(TSH > 4.2 AND TSH <= 10) AND (Free T4 in normal range 0.8-1.8)",
        "tests": ["TSH", "Free T4"],
        "evaluate": lambda v: (_has(v, "TSH") and 4.2 < v["TSH"] <= 10) and
                              (_has(v, "Free T4") and 0.8 <= v["Free T4"] <= 1.8),
        "severity": "MODERATE",
        "recommendation": "Subclinical hypothyroidism: elevated TSH with normal Free T4. Monitor every 6-12 months. Consider levothyroxine if TSH > 10 or if symptomatic (fatigue, weight gain, cold intolerance). Check anti-TPO antibodies.",
        "icd10": "E02",
        "nih_url": "https://www.niddk.nih.gov/health-information/endocrine-diseases/hypothyroidism",
    },

    # --- GLUCOSURIA (Qualitative) ---
    {
        "condition": "Glucosuria (Requires Diabetes Investigation)",
        "logic": "Glucose (Urine) = POSITIVE",
        "tests": ["Glucose (Urine)"],
        "evaluate": lambda v: _has(v, "Glucose (Urine)") and v["Glucose (Urine)"] > 0,
        "severity": "HIGH",
        "recommendation": "CRITICAL: Glucose detected in urine indicates blood sugar spillage above renal threshold (~180 mg/dL). Order fasting blood glucose, HbA1c, and 2-hour OGTT immediately. If diabetes confirmed, begin management protocol.",
        "icd10": "R81",
        "nih_url": "https://medlineplus.gov/lab-tests/glucose-in-urine-test/",
    },

    # --- URINARY TRACT INFECTION INDICATORS ---
    {
        "condition": "Possible Urinary Tract Infection",
        "logic": "Nitrite (Urine) = POSITIVE OR Leukocyte Esterase = POSITIVE",
        "tests": ["Nitrite (Urine)", "Leukocyte Esterase"],
        "evaluate": lambda v: (_has(v, "Nitrite (Urine)") and v["Nitrite (Urine)"] > 0) or
                              (_has(v, "Leukocyte Esterase") and v["Leukocyte Esterase"] > 0),
        "severity": "MODERATE",
        "recommendation": "Positive nitrite and/or leukocyte esterase suggests urinary tract infection. Order urine culture and sensitivity. Begin empiric antibiotics if symptomatic (dysuria, frequency, urgency).",
        "icd10": "N39.0",
        "nih_url": "https://medlineplus.gov/urinarytractinfections.html",
    },

    # --- HEMATURIA ---
    {
        "condition": "Hematuria (Blood in Urine)",
        "logic": "Blood (Urine) = POSITIVE",
        "tests": ["Blood (Urine)"],
        "evaluate": lambda v: _has(v, "Blood (Urine)") and v["Blood (Urine)"] > 0,
        "severity": "HIGH",
        "recommendation": "Blood detected in urine. Rule out UTI, kidney stones, glomerulonephritis. In adults >40, consider urological evaluation to exclude bladder/kidney malignancy. Order urine microscopy, renal ultrasound.",
        "icd10": "R31.9",
        "nih_url": "https://medlineplus.gov/blood-in-urine.html",
    },

    # --- METABOLIC SYNDROME (Multi-parameter) ---
    {
        "condition": "Metabolic Syndrome Indicators",
        "logic": "(Glucose > 100 OR HbA1c > 5.7) AND (Triglycerides > 150) AND (HDL < 40)",
        "tests": ["Glucose", "HbA1c", "Triglycerides", "HDL Cholesterol"],
        "evaluate": lambda v: (
            (_has(v, "Glucose") and v["Glucose"] > 100) or
            (_has(v, "HbA1c") and v["HbA1c"] > 5.7)
        ) and (
            _has(v, "Triglycerides") and v["Triglycerides"] > 150
        ) and (
            _has(v, "HDL Cholesterol") and v["HDL Cholesterol"] < 40
        ),
        "severity": "HIGH",
        "recommendation": "Multiple metabolic syndrome indicators present. High cardiovascular risk. Aggressive lifestyle intervention: weight loss, Mediterranean diet, 150+ min/week exercise. Consider statin and metformin. Screen for NAFLD (liver ultrasound).",
        "icd10": "E88.81",
        "nih_url": "https://www.nhlbi.nih.gov/health/metabolic-syndrome",
    },

    # --- PRE-DIABETES (Impaired Glucose Tolerance — refined) ---
    {
        "condition": "Pre-Diabetes (Impaired Glucose Tolerance)",
        "logic": "(HbA1c 5.7-6.4%) with supporting metabolic markers",
        "tests": ["HbA1c"],
        "evaluate": lambda v: _has(v, "HbA1c") and 5.7 <= v["HbA1c"] <= 6.4 and not (
            _has(v, "HbA1c") and v["HbA1c"] > 6.5
        ),
        "severity": "MODERATE",
        "recommendation": "HbA1c in pre-diabetic range. Strong evidence that lifestyle modification can prevent progression to T2DM (58% risk reduction per DPP trial). Target: 7% weight loss, 150 min/week moderate activity. Recheck HbA1c in 3 months.",
        "icd10": "R73.03",
        "nih_url": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/prediabetes-insulin-resistance",
    },

    # --- UTI (Leucocytes + Pus Cells) ---
    {
        "condition": "Urinary Tract Infection (UTI) — Likely",
        "logic": "(Leucocytes POSITIVE) OR (Pus Cells > 5) OR (Leucocytes+Pus Cells both abnormal)",
        "tests": ["Leucocytes (Urine)", "Pus Cells", "Nitrite (Urine)"],
        "evaluate": lambda v: (
            (_has(v, "Leucocytes (Urine)") and v["Leucocytes (Urine)"] > 0) or
            (_has(v, "Pus Cells") and v["Pus Cells"] > 5)
        ),
        "severity": "CRITICAL",
        "recommendation": "URGENT: Strong indicators of urinary tract infection. Positive leucocytes and/or elevated pus cells confirm active infection. Order urine culture and sensitivity (C&S) immediately. Start empirical antibiotic therapy pending culture results. If nitrite also positive, bacterial UTI is highly likely.",
        "icd10": "N39.0",
        "nih_url": "https://medlineplus.gov/urinarytractinfections.html",
    },

    # --- DIABETIC KETOACIDOSIS RISK (Glucose + Ketones in urine) ---
    {
        "condition": "Diabetic Ketoacidosis Risk (Glucosuria + Ketonuria)",
        "logic": "(Urine Glucose POSITIVE) AND (Urine Ketones POSITIVE)",
        "tests": ["Glucose (Urine)", "Ketones (Urine)"],
        "evaluate": lambda v: (
            _has(v, "Glucose (Urine)") and v["Glucose (Urine)"] > 0 and
            _has(v, "Ketones (Urine)") and v["Ketones (Urine)"] > 0
        ),
        "severity": "CRITICAL",
        "recommendation": "EMERGENCY: Both glucose and ketones detected in urine. This combination suggests diabetic ketoacidosis (DKA) risk. Immediately check blood glucose, serum ketones, arterial blood gas, and electrolytes. If blood glucose > 250 mg/dL with ketonuria, treat as DKA emergency.",
        "icd10": "E13.10",
        "nih_url": "https://medlineplus.gov/diabeticketoacidosis.html",
    },

    # --- PROTEINURIA ---
    {
        "condition": "Proteinuria (Protein in Urine)",
        "logic": "Protein (Urine) POSITIVE",
        "tests": ["Protein (Urine)"],
        "evaluate": lambda v: _has(v, "Protein (Urine)") and v["Protein (Urine)"] > 0,
        "severity": "MODERATE",
        "recommendation": "Protein detected in urine. May indicate kidney damage, hypertension-related nephropathy, or diabetic nephropathy. Order 24-hour urine protein, serum albumin, and renal function tests. If persistent, consider nephrology referral.",
        "icd10": "R80.9",
        "nih_url": "https://medlineplus.gov/lab-tests/albumin-urine-test/",
    },

    # --- ACTIVE SYSTEMIC INFECTION (CRP + WBC) ---
    {
        "condition": "Active Systemic Infection/Inflammation",
        "logic": "(CRP > 5) AND (WBC > 11000)",
        "tests": ["CRP", "hs-CRP", "White Blood Cell Count"],
        "evaluate": lambda v: (
            ((_has(v, "CRP") and v["CRP"] > 5) or (_has(v, "hs-CRP") and v["hs-CRP"] > 5)) and
            (_has(v, "White Blood Cell Count") and v["White Blood Cell Count"] > 11)
        ),
        "severity": "HIGH",
        "recommendation": "Elevated inflammatory markers with leukocytosis suggest active infection or inflammatory process. Order blood cultures, procalcitonin, and imaging as indicated by clinical presentation. Consider empirical antibiotics if sepsis is suspected.",
        "icd10": "R65.10",
        "nih_url": "https://medlineplus.gov/sepsis.html",
    },

    # --- ELEVATED CRP (Standalone — no WBC required) ---
    {
        "condition": "Systemic Inflammation (Elevated CRP)",
        "logic": "(CRP > 5) OR (hs-CRP > 5)",
        "tests": ["CRP", "hs-CRP"],
        "evaluate": lambda v: (
            (_has(v, "CRP") and v["CRP"] > 5) or
            (_has(v, "hs-CRP") and v["hs-CRP"] > 5)
        ),
        "severity": "HIGH",
        "recommendation": "C-Reactive Protein is elevated, indicating systemic inflammation. Common causes: infection, autoimmune disease, tissue injury. Correlate with clinical symptoms. If persistent, investigate with ESR, CBC with differential, and consider rheumatologic or infectious workup.",
        "icd10": "R79.89",
        "nih_url": "https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/",
    },

    # --- REACTIVE THROMBOCYTOSIS (High Platelets + Inflammation) ---
    {
        "condition": "Reactive Thrombocytosis (Inflammation-Related)",
        "logic": "(Platelets > 400) AND (CRP > 5 OR ESR > 20)",
        "tests": ["Platelet Count", "CRP", "hs-CRP", "ESR"],
        "evaluate": lambda v: (
            _has(v, "Platelet Count") and v["Platelet Count"] > 400 and
            ((_has(v, "CRP") and v["CRP"] > 5) or (_has(v, "hs-CRP") and v["hs-CRP"] > 5) or
             (_has(v, "ESR") and v["ESR"] > 20))
        ),
        "severity": "MODERATE",
        "recommendation": "Elevated platelet count with inflammatory markers suggests reactive (secondary) thrombocytosis. Most common cause is acute/chronic infection or inflammation. Not usually dangerous but warrants investigation of underlying cause. If platelets > 1000K, rule out myeloproliferative disorder.",
        "icd10": "D75.839",
        "nih_url": "https://medlineplus.gov/plateletdisorders.html",
    },
]


def evaluate_conditions(flagged_results: List[FlaggedResult]) -> List[DetectedCondition]:
    """
    Run all clinical rules against the flagged results.
    Returns list of detected conditions with recommendations.
    """
    # Build lookup: test_name -> observed_value
    value_map: Dict[str, float] = {}
    for r in flagged_results:
        value_map[r.test_name] = r.observed_value

    logger.info(f"Rule engine input: {list(value_map.keys())}")

    detected = []
    seen_conditions = set()  # Prevent duplicate conditions (e.g., Anemia + Severe Anemia)

    for rule in CLINICAL_RULES:
        # Check if we have at least one relevant test
        relevant_tests = [t for t in rule["tests"] if t in value_map]
        if not relevant_tests:
            continue

        try:
            if rule["evaluate"](value_map):
                # Skip if a more severe version of same condition already detected
                base_condition = rule["condition"].split("(")[0].strip()
                if base_condition in seen_conditions and rule["severity"] in ("LOW", "MODERATE"):
                    continue

                condition = DetectedCondition(
                    condition=rule["condition"],
                    logic=rule["logic"],
                    severity=rule["severity"],
                    supporting_tests=relevant_tests,
                    recommendation=rule["recommendation"],
                )
                detected.append(condition)
                seen_conditions.add(base_condition)
                logger.warning(
                    f"CONDITION DETECTED: {rule['condition']} [{rule['severity']}] "
                    f"(ICD-10: {rule.get('icd10', 'N/A')})"
                )
        except Exception as e:
            logger.error(f"Rule evaluation error for '{rule['condition']}': {e}")

    logger.info(f"Clinical rules: {len(detected)} conditions detected from {len(CLINICAL_RULES)} rules")
    return detected


def get_nih_url(condition_name: str) -> str:
    """Get the NIH URL for a detected condition (for deep linking in UI)."""
    for rule in CLINICAL_RULES:
        if rule["condition"] == condition_name:
            return rule.get("nih_url", "")
    # Also check microbiology rules
    for rule in MICROBIOLOGY_RULES:
        if rule["condition"] == condition_name:
            return rule.get("nih_url", "")
    return ""


# ============================================================
# MICROBIOLOGY CLINICAL RULES (AMR Intelligence Layer)
# ============================================================
MICROBIOLOGY_RULES = [
    {
        "condition": "Confirmed Urinary Tract Infection (Culture-Proven)",
        "logic": "Organism isolated in urine at ≥10^5 CFU/ml (significant bacteriuria)",
        "severity": "CRITICAL",
        "recommendation": "URGENT: Culture-confirmed UTI. Initiate targeted antibiotic therapy based on sensitivity pattern. Avoid resistant antibiotics. Follow-up urine culture after completing treatment course to confirm clearance. If recurrent, consider urological evaluation.",
        "icd10": "N39.0",
        "nih_url": "https://medlineplus.gov/urinarytractinfections.html",
    },
    {
        "condition": "Bacterial Infection (Non-Urinary)",
        "logic": "Organism isolated in culture from non-urinary specimen",
        "severity": "HIGH",
        "recommendation": "Culture-confirmed bacterial infection. Initiate targeted antibiotic therapy based on susceptibility testing. Monitor clinical response. Consider infectious disease consult for complex cases.",
        "icd10": "A49.9",
        "nih_url": "https://medlineplus.gov/bacterialinfections.html",
    },
    {
        "condition": "Multi-Drug Resistant Organism (MDRO)",
        "logic": "Organism resistant to ≥3 antibiotic classes",
        "severity": "CRITICAL",
        "recommendation": "CRITICAL: Multi-drug resistant organism detected. Use ONLY antibiotics shown as Sensitive on susceptibility testing. DO NOT use empiric broad-spectrum antibiotics. Infectious disease consultation recommended. Implement contact precautions. Consider escalation to reserve antibiotics (carbapenems, colistin) if warranted.",
        "icd10": "Z16.39",
        "nih_url": "https://www.cdc.gov/antimicrobial-resistance/",
    },
    {
        "condition": "Antibiotic Resistance Alert",
        "logic": "One or more antibiotics show resistance on susceptibility testing",
        "severity": "HIGH",
        "recommendation": "Antibiotic resistance detected. Prescribe ONLY from the Sensitive antibiotics list. Do NOT prescribe resistant drugs — treatment failure is likely. Document resistance pattern in patient record for future reference.",
        "icd10": "Z16",
        "nih_url": "https://www.cdc.gov/antimicrobial-resistance/",
    },
    {
        "condition": "Gram-Negative Infection",
        "logic": "Gram-negative organism isolated (E. coli, Klebsiella, Pseudomonas, etc.)",
        "severity": "HIGH",
        "recommendation": "Gram-negative infection confirmed. These organisms can produce extended-spectrum beta-lactamases (ESBL). If resistant to 3rd-gen cephalosporins, suspect ESBL producer — carbapenems may be required. Monitor renal function during aminoglycoside therapy.",
        "icd10": "A49.9",
        "nih_url": "https://www.cdc.gov/antimicrobial-resistance/",
    },
]

# Known gram-negative organisms
GRAM_NEGATIVE_ORGANISMS = [
    "escherichia coli", "e. coli", "klebsiella", "proteus",
    "pseudomonas", "acinetobacter", "enterobacter", "citrobacter",
    "serratia", "morganella", "salmonella", "shigella",
]


def evaluate_microbiology_conditions(micro) -> List[DetectedCondition]:
    """
    Evaluate clinical rules specifically for microbiology culture & sensitivity data.

    Args:
        micro: MicrobiologyResult from the microbiology parser
    Returns:
        List of DetectedCondition objects for detected infection patterns
    """
    if micro is None:
        return []

    detected = []
    resistant_drugs = [a for a in micro.antibiotics if a.status == "Resistant"]
    sensitive_drugs = [a for a in micro.antibiotics if a.status == "Sensitive"]

    # Rule 1: Confirmed UTI (urine specimen + significant colony count)
    if micro.organism and micro.specimen_type.lower() == "urine" and micro.is_significant:
        rule = MICROBIOLOGY_RULES[0]
        sensitive_options = ", ".join(d.name for d in sensitive_drugs[:5])
        resistant_list = ", ".join(d.name for d in resistant_drugs[:5])
        custom_rec = (
            f"{rule['recommendation']} "
            f"Effective antibiotics: {sensitive_options}. "
            f"DO NOT prescribe: {resistant_list}."
        ) if sensitive_drugs else rule['recommendation']
        detected.append(DetectedCondition(
            condition=f"{rule['condition']} — {micro.organism}",
            logic=f"{rule['logic']} — {micro.organism} at {micro.colony_count}",
            severity=rule["severity"],
            supporting_tests=["Organism Isolated (Urine)", "Colony Count"],
            recommendation=custom_rec,
        ))
        logger.warning(
            f"CONDITION DETECTED: {rule['condition']} [{rule['severity']}] "
            f"(ICD-10: {rule.get('icd10', 'N/A')}) — {micro.organism}"
        )

    # Rule 1b: Bacterial infection (non-urinary)
    elif micro.organism and micro.specimen_type.lower() != "urine":
        rule = MICROBIOLOGY_RULES[1]
        detected.append(DetectedCondition(
            condition=f"{rule['condition']} — {micro.organism}",
            logic=f"Organism '{micro.organism}' isolated from {micro.specimen_type}",
            severity=rule["severity"],
            supporting_tests=["Organism Isolated"],
            recommendation=rule["recommendation"],
        ))

    # Rule 2: Multi-Drug Resistance (≥3 resistant)
    if len(resistant_drugs) >= 3:
        rule = MICROBIOLOGY_RULES[2]
        drug_names = ", ".join(d.name for d in resistant_drugs)
        detected.append(DetectedCondition(
            condition=rule["condition"],
            logic=f"Resistant to {len(resistant_drugs)} antibiotics: {drug_names}",
            severity=rule["severity"],
            supporting_tests=[f"{d.name} (Resistance)" for d in resistant_drugs[:5]],
            recommendation=rule["recommendation"],
        ))
        logger.warning(
            f"MDR CONDITION: {len(resistant_drugs)} drugs resistant — "
            f"{drug_names}"
        )

    # Rule 3: Any resistance detected (but not already covered by MDR)
    elif resistant_drugs:
        rule = MICROBIOLOGY_RULES[3]
        drug_names = ", ".join(d.name for d in resistant_drugs)
        detected.append(DetectedCondition(
            condition=rule["condition"],
            logic=f"Resistant to: {drug_names}",
            severity=rule["severity"],
            supporting_tests=[f"{d.name} (Resistance)" for d in resistant_drugs],
            recommendation=rule["recommendation"],
        ))

    # Rule 4: Gram-negative organism
    if micro.organism:
        org_lower = micro.organism.lower()
        is_gram_neg = any(gn in org_lower for gn in GRAM_NEGATIVE_ORGANISMS)
        if is_gram_neg:
            rule = MICROBIOLOGY_RULES[4]
            # Check for ESBL pattern (resistant to 3rd-gen cephalosporins)
            cephalosporin_3rd = {"ceftriaxone", "cefotaxime", "ceftazidime", "cefixime", "cefepime"}
            resistant_ceph = [d.name for d in resistant_drugs if d.name.lower() in cephalosporin_3rd]
            esbl_note = ""
            if resistant_ceph:
                esbl_note = f" ESBL SUSPECTED: Resistant to 3rd-gen cephalosporins ({', '.join(resistant_ceph)})."
            detected.append(DetectedCondition(
                condition=f"{rule['condition']} — {micro.organism}",
                logic=f"Gram-negative organism '{micro.organism}' isolated",
                severity="CRITICAL" if resistant_ceph else rule["severity"],
                supporting_tests=["Organism Isolated"],
                recommendation=f"{rule['recommendation']}{esbl_note}",
            ))

    logger.info(f"Microbiology rules: {len(detected)} conditions detected")
    return detected

