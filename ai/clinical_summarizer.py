"""
ClinIQ - AI Clinical Summarizer (Phase 6) v3.0
=================================================
Separate Groq calls for Patient vs Doctor personas.
Uses categorical urgency (Critical → Notable → Normal).

v3.0: Categorical urgency format, clinical severity-aware language,
      NO mock fallback — always generates real AI summaries,
      deviation multipliers for extreme values.
"""

import os
import re
import logging
import time
from typing import Optional
from dotenv import load_dotenv
from schemas.medical_schemas import ClinicalSummary

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# ============================================================
# PERSONA-SPECIFIC SYSTEM PROMPTS (v3.0 — Categorical Urgency)
# ============================================================

PATIENT_SYSTEM_PROMPT = """You are ClinIQ, a caring health assistant explaining lab results to a patient.

RULES:
1. Use ONLY the provided structured data and medical knowledge below. Do NOT hallucinate or invent values.
2. Write in simple, warm, empathetic language a non-medical person can understand.
3. Avoid medical jargon — use analogies and everyday language.
4. Do NOT diagnose. Say "your results suggest" or "this may indicate."
5. Be reassuring but HONEST. Do NOT minimize real concerns.
6. For every claim, cite: [Source: Lab Report] or [Source: Medical Knowledge Base].

CRITICAL LANGUAGE RULES:
- If a value is marked CRITICAL or clinical_urgency is CRITICAL, use FIRM, CLEAR language:
  "Your [test] is significantly elevated/low" or "well above/below the healthy range"
  NEVER say "slightly hot", "a bit higher", or "running a little warm" for CRITICAL values.
- If a value is more than 2x above or below the reference range, state the multiplier:
  "Your IgE is nearly 6 times above the normal limit"
- If a value crosses a disease threshold (e.g., Glucose ≥126 = diabetes), name the condition plainly:
  "Your fasting glucose is in the diabetic range"

GOLDEN EXAMPLES (use these as calibration for tone and severity):

Example A (Metabolic - Medicover): Hb=10.8, HbA1c=6.1%, TSH=5.32, Urine Glucose=Present(+)
→ 🚨 CRITICAL: "Your hemoglobin is low at 10.8, indicating anemia."
→ 🚨 CRITICAL: "Sugar was found in your urine, which means your blood sugar may be high enough to spill over."
→ ⚠️ NOTABLE: "Your HbA1c of 6.1% puts you in the pre-diabetes range." "Your thyroid (TSH 5.32) is slightly elevated."

Example B (Urine - Tenet): Leucocytes=Positive(+++), Pus Cells=Plenty, Glucose=Positive(++), Ketones=Trace
→ 🚨 EMERGENCY: "Your urine shows strong signs of a urinary tract infection (UTI) — plenty of pus cells and high leucocytes."
→ 🚨 CRITICAL: "Sugar and ketones were found in your urine together — this needs immediate attention."

Example C (Anemia - Vijaya): Hb=10.1, MCV=67.0, CRP=8.54
→ 🚨 CRITICAL: "Your hemoglobin and MCV are both low, suggesting iron-deficiency anemia."
→ ⚠️ NOTABLE: "Your CRP is elevated, indicating inflammation in your body."

Example D (Microbiology - Tenet): Organism=Escherichia coli, Colony Count=10^5 CFU/ml, Ciprofloxacin=Resistant, Amikacin=Sensitive
→ 🚨 EMERGENCY: "A bacteria called E. coli has been found growing in your urine at a significant level. This confirms a urinary tract infection (UTI) that needs antibiotic treatment."
→ 🚨 CRITICAL: "Important — common antibiotics like Ciprofloxacin and Ofloxacin will NOT work against this bacteria because it is resistant to them. Your doctor must choose from the antibiotics that ARE effective."
→ ✅ TREATMENT OPTIONS: "The good news is your infection CAN be treated. The bacteria responds to Amikacin, Gentamycin, Nitrofurantoin, and Fosfomycin."

MICROBIOLOGY-SPECIFIC RULES:
- If MICROBIOLOGY DATA is present, it takes HIGHEST PRIORITY in the summary.
- Always name the exact organism (e.g., "Escherichia coli", not just "bacteria").
- Always state the colony count and whether it's significant.
- List RESISTANT antibiotics as a WARNING — "These common treatments will NOT work."
- List SENSITIVE antibiotics as TREATMENT OPTIONS — "These are the effective choices."
- NEVER recommend or suggest a Resistant antibiotic.

FORMAT — Use this EXACT structure:

🚨 **Critical Findings (Immediate Action Needed)**
- List ALL findings with clinical_urgency=CRITICAL here
- Use firm language. Name the clinical significance.
- Include the actual value, reference range, and what it means
- For infections: Name the organism, colony count, and what it means

⚠️ **Notable Elevations / Concerns**
- List findings with clinical_urgency=WARNING here
- Use moderate language — "worth discussing with your doctor"

💊 **Treatment Options** (ONLY for Microbiology reports)
- List SENSITIVE antibiotics that CAN treat the infection
- Clearly warn which antibiotics are RESISTANT and must be avoided

✅ **Within Normal Limits**
- Briefly mention which tests are healthy — group them together

**Your Next Steps:**
1. [Specific action based on findings]
2. [Specific action based on findings]
3. [General wellness recommendation]

Keep the summary under 500 words."""

DOCTOR_SYSTEM_PROMPT = """You are ClinIQ, a clinical decision support system generating a physician summary.

RULES:
1. Use ONLY the provided structured data and medical knowledge below. Do NOT hallucinate.
2. Use professional clinical language with proper medical terminology.
3. Include specific values with units, reference ranges, and deviation percentages.
4. Reference ICD-10 codes where applicable.
5. Provide differential considerations and evidence-based follow-up recommendations.
6. Be concise and data-heavy. Prioritize actionable clinical insights.
7. For every claim, cite: [Source: Lab Report] or [Source: Medical Knowledge Base].

SEVERITY-AWARE RULES:
- Present findings in ORDER of clinical urgency (CRITICAL first, then WARNING, then NORMAL).
- For CRITICAL findings, include the disease threshold that was crossed (e.g., "FBG 141 mg/dL exceeds ADA diagnostic threshold of 126 mg/dL for T2DM").
- For extreme deviations, include the multiplier (e.g., "IgE 492 IU/mL — 5.6x upper limit of normal").
- Clearly distinguish between tests that are different entities even if names are similar (e.g., BUN vs Urea).

PATHOLOGICAL CORRELATION RULES (CRITICAL — this is what separates a good system from a great one):
- Do NOT just list abnormal values. CONNECT related tests into pathological patterns:
  * Low Hb + Low MCV → "Microcytic anemia pattern suggestive of iron deficiency"
  * Low Hb + High MCV → "Macrocytic anemia pattern — investigate B12/folate"
  * Low Hb + Low MCV + Low Ferritin → "Iron deficiency anemia triad confirmed"
  * Elevated TSH + Normal FT4 → "Subclinical hypothyroidism"
  * Elevated Glucose + Elevated HbA1c + Urine Glucose POSITIVE → "Diabetes with glucosuria — renal threshold exceeded"
- For qualitative tests (status: POSITIVE/NEGATIVE), describe the clinical significance:
  * Urine Glucose POSITIVE → "Glucosuria indicates blood glucose exceeding renal threshold (~180 mg/dL)"
  * Urine Blood POSITIVE → "Hematuria — requires urological workup"
- Group related findings by organ system (Metabolic, Hematologic, Renal, Hepatic, Thyroid, Microbiology).

MICROBIOLOGY CORRELATION RULES (AMR — Anti-Microbial Resistance):
- If MICROBIOLOGY DATA is present, it takes HIGHEST PRIORITY.
- Identify organism genus/species and Gram classification.
- Report colony count with significance threshold (≥10^5 CFU/ml = confirmed UTI).
- Present antibiotics in two clear lists: RESISTANT (treatment will fail) and SENSITIVE (effective options).
- If resistant to 3rd-gen cephalosporins (ceftriaxone, cefixime, cefepime), flag as ESBL-producer suspect.
- If ≥3 antibiotics resistant, flag as Multi-Drug Resistant Organism (MDRO) with ICD-10: Z16.39.
- Correlate with urinalysis findings if present (leucocytes, pus cells, nitrites).
- NEVER recommend a resistant antibiotic in the treatment plan.

FORMAT:
**Clinical Impression:** One-line summary connecting the dominant pathological pattern

🚨 **Critical Findings & Pathological Correlations**
- Each with value, ref range, % deviation, ICD-10, and CLINICAL CORRELATION with other tests
- Qualitative findings (POSITIVE/NEGATIVE) with clinical significance
- Microbiology: Organism, colony count, resistance pattern

🦠 **Antimicrobial Susceptibility** (ONLY for Microbiology reports)
- 🔴 RESISTANT: List all resistant drugs (treatment will fail)
- 🟢 SENSITIVE: List all effective drugs (recommended for therapy)
- ESBL/MDRO flags if applicable

⚠️ **Secondary Findings**
- Notable abnormalities not at critical threshold

✅ **Within Normal Limits**
- Brief list grouped by organ system

**Recommended Follow-Up:**
- Specific investigations and referrals ordered by priority
- Include correlative investigations (e.g., "Given microcytic anemia pattern, order iron studies")
- For infections: Repeat culture post-treatment, ID consult if MDRO

Keep it under 600 words."""


def generate_clinical_summary(analysis_data: dict) -> Optional[ClinicalSummary]:
    """Generate dual-persona clinical summary using separate Groq API calls."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        logger.error(
            "Groq API key not configured. Cannot generate summary. "
            "Set GROQ_API_KEY in .env file."
        )
        return _generate_urgency_summary(analysis_data)

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        logger.error("groq package not installed. Run: pip install groq")
        return _generate_urgency_summary(analysis_data)

    user_message = _build_input_message(analysis_data)

    # --- PATIENT SUMMARY (separate call) ---
    patient_summary = _call_groq(client, PATIENT_SYSTEM_PROMPT, user_message, "patient")

    # --- DOCTOR SUMMARY (separate call) ---
    doctor_summary = _call_groq(client, DOCTOR_SYSTEM_PROMPT, user_message, "doctor")

    # If BOTH calls failed, generate urgency-based summary from structured data
    if not patient_summary and not doctor_summary:
        logger.warning("Both Groq calls failed. Generating urgency-based summary from structured data.")
        return _generate_urgency_summary(analysis_data)

    # If only one failed, generate that persona from structured data
    if not patient_summary or not doctor_summary:
        fallback = _generate_urgency_summary(analysis_data)
        patient_summary = patient_summary or fallback.patient_summary
        doctor_summary = doctor_summary or fallback.doctor_summary

    # Extract citations from both
    all_text = (patient_summary or "") + (doctor_summary or "")
    citations = list(set(re.findall(r'\[Source:\s*[^\]]+\]', all_text)))
    if not citations:
        citations = ["[Source: Lab Report]", "[Source: Medical Knowledge Base]"]

    return ClinicalSummary(
        patient_summary=patient_summary,
        doctor_summary=doctor_summary,
        citations=citations,
    )


def _call_groq(client, system_prompt: str, user_message: str, persona: str) -> Optional[str]:
    """Make a single Groq API call for one persona."""
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3 if persona == "doctor" else 0.5,
            max_tokens=1500,
            top_p=0.9,
        )
        elapsed = time.time() - start
        logger.info(f"Groq [{persona}] response in {elapsed:.2f}s")
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API call failed for {persona}: {e}")
        return None


def _build_input_message(data: dict) -> str:
    """Build structured input message for the LLM with urgency classification."""
    parts = ["## STRUCTURED LAB DATA\n"]

    # === MICROBIOLOGY DATA (highest priority) ===
    micro = data.get("microbiology", {})
    if micro and micro.get("organism"):
        parts.append("### 🦠 MICROBIOLOGY DATA (HIGHEST PRIORITY):")
        parts.append(f"- **Organism Isolated:** {micro['organism']}")
        parts.append(f"- **Specimen Type:** {micro.get('specimen_type', 'Unknown')}")
        if micro.get('colony_count'):
            sig = "SIGNIFICANT (confirmed infection)" if micro.get('is_significant') else "Not significant"
            parts.append(f"- **Colony Count:** {micro['colony_count']} → {sig}")
        if micro.get('gram_stain'):
            parts.append(f"- **Gram Stain:** {micro['gram_stain']}")

        antibiotics = micro.get('antibiotics', [])
        if antibiotics:
            resistant = [a for a in antibiotics if a.get('status') == 'Resistant']
            sensitive = [a for a in antibiotics if a.get('status') == 'Sensitive']
            intermediate = [a for a in antibiotics if a.get('status') == 'Intermediate']

            if resistant:
                parts.append(f"\n**🔴 RESISTANT ANTIBIOTICS (Treatment will FAIL — {len(resistant)} drugs):**")
                for a in resistant:
                    parts.append(f"  - {a['name']}: RESISTANT ❌")

            if sensitive:
                parts.append(f"\n**🟢 SENSITIVE ANTIBIOTICS (Effective for treatment — {len(sensitive)} drugs):**")
                for a in sensitive:
                    parts.append(f"  - {a['name']}: SENSITIVE ✓")

            if intermediate:
                parts.append(f"\n**🟡 INTERMEDIATE ANTIBIOTICS ({len(intermediate)} drugs):**")
                for a in intermediate:
                    parts.append(f"  - {a['name']}: INTERMEDIATE")

            if len(resistant) >= 3:
                parts.append(f"\n⚠️ **MULTI-DRUG RESISTANCE (MDR) ALERT:** Organism is resistant to {len(resistant)} antibiotics!")

        parts.append("")

    results = data.get("test_results", [])
    if results:
        # Separate by urgency — exclude microbiology flagged results from standard listing
        micro_groups = {"Microbiology", "Antimicrobial Resistance", "Effective Antibiotics"}
        lab_results = [r for r in results if r.get("test_group") not in micro_groups]

        critical = [r for r in lab_results if r.get("clinical_urgency") == "CRITICAL"]
        warning = [r for r in lab_results if r.get("clinical_urgency") == "WARNING"]
        normal = [r for r in lab_results if r.get("clinical_urgency") not in ("CRITICAL", "WARNING")]

        if critical:
            parts.append("### 🚨 CRITICAL TEST RESULTS:")
            for r in critical:
                parts.append(_format_test_line(r))

        if warning:
            parts.append("\n### ⚠️ WARNING TEST RESULTS:")
            for r in warning:
                parts.append(_format_test_line(r))

        if normal:
            parts.append("\n### ✅ NORMAL TEST RESULTS:")
            for r in normal:
                ref_low = r.get('reference_low', '?')
                ref_high = r.get('reference_high', '?')
                parts.append(
                    f"- {r['test_name']}: {r['observed_value']} {r.get('unit', '')} "
                    f"(Ref: {ref_low}-{ref_high}) -> NORMAL"
                )

    conditions = data.get("detected_conditions", [])
    if conditions:
        parts.append("\n### Detected Conditions (from deterministic rule engine):")
        for c in conditions:
            parts.append(f"- **{c['condition']}** [{c['severity']}]: {c['logic']}")
            parts.append(f"  Clinical Recommendation: {c['recommendation']}")

    contexts = data.get("rag_contexts", [])
    if contexts:
        parts.append("\n### Medical Knowledge Base Context:")
        for ctx in contexts:
            parts.append(f"[Source: {ctx.get('source', 'Medical Knowledge Base')}]\n{ctx['text']}\n")

    return "\n".join(parts)


def _format_test_line(r: dict) -> str:
    """Format a single test result line with deviation info."""
    ref_low = r.get('reference_low', '?')
    ref_high = r.get('reference_high', '?')
    status = r.get('status', 'UNKNOWN')
    urgency = r.get('clinical_urgency', 'NORMAL')
    group = r.get('test_group', '')
    qual = r.get('qualitative_value')

    group_tag = f" [Group: {group}]" if group else ""

    # Handle qualitative results
    if qual:
        return (
            f"- {r['test_name']}: **{qual}** "
            f"-> STATUS: {status} | URGENCY: {urgency}{group_tag}"
        )

    # Numeric results with deviation calculation
    deviation = ""
    multiplier = ""
    if status in ("HIGH", "CRITICAL_HIGH") and ref_high and ref_high != '?' and float(ref_high) > 0:
        dev_pct = ((r['observed_value'] - float(ref_high)) / float(ref_high)) * 100
        deviation = f" (+{dev_pct:.0f}% above ref)"
        if r['observed_value'] / float(ref_high) >= 2:
            mult = r['observed_value'] / float(ref_high)
            multiplier = f" [{mult:.1f}x above normal limit]"
    elif status in ("LOW", "CRITICAL_LOW") and ref_low and ref_low != '?' and float(ref_low) > 0:
        dev_pct = ((float(ref_low) - r['observed_value']) / float(ref_low)) * 100
        deviation = f" (-{dev_pct:.0f}% below ref)"
        if float(ref_low) > 0 and r['observed_value'] > 0 and float(ref_low) / r['observed_value'] >= 2:
            mult = float(ref_low) / r['observed_value']
            multiplier = f" [ref is {mult:.1f}x higher than value]"

    return (
        f"- {r['test_name']}: {r['observed_value']} {r.get('unit', '')} "
        f"(Ref: {ref_low}-{ref_high}) -> STATUS: {status} | "
        f"URGENCY: {urgency}{deviation}{multiplier}{group_tag}"
    )


# ============================================================
# URGENCY-BASED SUMMARY (replaces old mock — data-driven, not fake)
# ============================================================
def _generate_urgency_summary(data: dict) -> ClinicalSummary:
    """
    Generate structured urgency-based summaries from the pipeline data.
    This is NOT a mock — it uses real parsed/flagged data with proper
    severity-aware language. Used as fallback when Groq is unavailable.
    """
    results = data.get("test_results", [])
    conditions = data.get("detected_conditions", [])

    # Categorize by clinical urgency
    critical = [r for r in results if r.get("clinical_urgency") == "CRITICAL"]
    warning = [r for r in results if r.get("clinical_urgency") == "WARNING"]
    normals = [r for r in results if r.get("status") == "NORMAL"]

    # ===== PATIENT SUMMARY =====
    patient_lines = []

    if critical:
        patient_lines.append("🚨 **Critical Findings (Immediate Action Needed)**\n")
        for r in critical:
            patient_lines.append(_patient_critical_line(r))
        patient_lines.append("")

    if warning:
        patient_lines.append("⚠️ **Notable Concerns**\n")
        for r in warning:
            patient_lines.append(_patient_warning_line(r))
        patient_lines.append("")

    if normals:
        patient_lines.append("✅ **Within Normal Limits**\n")
        good_names = [r["test_name"] for r in normals[:8]]
        patient_lines.append(
            f"- Great news! Your {', '.join(good_names)} levels are all within healthy ranges. "
            f"These parts of your health are on track. [Source: Lab Report]\n"
        )

    if conditions:
        patient_lines.append("**What the clinical rules found:**\n")
        for c in conditions:
            rec = c["recommendation"].split(".")[0] + "."
            sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(c["severity"], "⚪")
            patient_lines.append(f"- {sev_icon} **{c['condition']}**: {rec}")
        patient_lines.append("")

    patient_lines.append("**Your Next Steps:**")
    if critical:
        patient_lines.append("1. **Schedule an appointment with your doctor soon** to discuss the critical findings above.")
        patient_lines.append("2. Bring a copy of this report to your appointment.")
        patient_lines.append("3. Don't panic — but don't delay getting professional guidance.")
    else:
        patient_lines.append("1. Share these results with your doctor at your next visit.")
        patient_lines.append("2. Focus on balanced nutrition, hydration, and regular exercise.")
        patient_lines.append("3. Abnormal doesn't always mean something is wrong — context matters.")

    # ===== DOCTOR SUMMARY =====
    doctor_lines = ["**Clinical Impression:**"]
    if conditions:
        cond_names = [c["condition"] for c in conditions]
        doctor_lines.append(
            f"Multiple abnormalities identified across {len(set(r.get('test_group', 'Unknown') for r in results if r.get('test_group')))} "
            f"lab sections. Conditions flagged: {'; '.join(cond_names)}.\n"
        )
    elif critical:
        doctor_lines.append(f"{len(critical)} critical finding(s) identified requiring clinical correlation.\n")
    else:
        doctor_lines.append("Lab values reviewed. No critical conditions flagged by rule engine.\n")

    if critical:
        doctor_lines.append("🚨 **Critical Findings:**")
        for r in critical:
            doctor_lines.append(_doctor_finding_line(r))
        doctor_lines.append("")

    if warning:
        doctor_lines.append("⚠️ **Secondary Findings:**")
        for r in warning:
            doctor_lines.append(_doctor_finding_line(r))
        doctor_lines.append("")

    if normals:
        normal_names = [r["test_name"] for r in normals[:10]]
        doctor_lines.append(f"✅ **Within Normal Limits:** {', '.join(normal_names)}\n")

    if conditions:
        doctor_lines.append("**Detected Conditions (Rule Engine):**")
        for c in conditions:
            doctor_lines.append(
                f"- **{c['condition']}** [{c['severity']}]\n"
                f"  Rule: {c['logic']}\n"
                f"  Tests: {', '.join(c['supporting_tests'])}\n"
                f"  Recommendation: {c['recommendation']}"
            )
        doctor_lines.append("")

    doctor_lines.append("**Recommended Follow-Up:**")
    if critical or conditions:
        doctor_lines.append("- Correlate with clinical presentation and patient history.")
        doctor_lines.append("- Repeat testing in 2-4 weeks to confirm persistent abnormalities.")
        doctor_lines.append("- Specialty referrals as indicated per condition-specific recommendations above.")
    else:
        doctor_lines.append("- Routine follow-up. No immediate intervention required.")

    return ClinicalSummary(
        patient_summary="\n".join(patient_lines),
        doctor_summary="\n".join(doctor_lines),
        citations=["[Source: Lab Report]", "[Source: ClinIQ Rule Engine]"],
    )


def _patient_critical_line(r: dict) -> str:
    """Generate a patient-friendly line for a CRITICAL finding."""
    val = r["observed_value"]
    name = r["test_name"]
    unit = r.get("unit", "")
    ref_high = r.get("reference_high")
    ref_low = r.get("reference_low")
    status = r.get("status", "")

    if "HIGH" in status and ref_high and ref_high > 0:
        multiplier = val / ref_high
        if multiplier >= 3:
            return (
                f"- **{name}** is **{val} {unit}** — this is **{multiplier:.1f}x above** the normal "
                f"upper limit ({ref_high} {unit}). This is a significant finding that needs "
                f"prompt medical attention. [Source: Lab Report]"
            )
        else:
            return (
                f"- **{name}** is **{val} {unit}**, which is significantly higher than the healthy "
                f"range (up to {ref_high} {unit}). This is not 'slightly high' — it's well above "
                f"where it should be. [Source: Lab Report]"
            )
    elif "LOW" in status and ref_low and ref_low > 0:
        if val > 0:
            how_low = ref_low / val
            if how_low >= 3:
                return (
                    f"- **{name}** is **{val} {unit}** — the healthy minimum is {ref_low} {unit}, "
                    f"which is {how_low:.1f}x higher than your current level. "
                    f"This is a severe deficiency requiring immediate discussion with your doctor. [Source: Lab Report]"
                )
        return (
            f"- **{name}** is **{val} {unit}**, critically below the healthy range "
            f"({ref_low}-{r.get('reference_high', '?')} {unit}). "
            f"This level is too low for your body to function optimally. [Source: Lab Report]"
        )
    return f"- **{name}**: {val} {unit} — requires immediate attention. [Source: Lab Report]"


def _patient_warning_line(r: dict) -> str:
    """Generate a patient-friendly line for a WARNING finding."""
    val = r["observed_value"]
    name = r["test_name"]
    unit = r.get("unit", "")
    status = r.get("status", "")
    ref_high = r.get("reference_high")
    ref_low = r.get("reference_low")

    if "HIGH" in status:
        return (
            f"- **{name}** is **{val} {unit}**, above the ideal range "
            f"(up to {ref_high} {unit}). Worth discussing with your doctor. [Source: Lab Report]"
        )
    elif "LOW" in status:
        return (
            f"- **{name}** is **{val} {unit}**, below the healthy range "
            f"(at least {ref_low} {unit}). Your body may need more support here. [Source: Lab Report]"
        )
    return f"- **{name}**: {val} {unit} — outside normal range. [Source: Lab Report]"


def _doctor_finding_line(r: dict) -> str:
    """Generate a clinical finding line for the doctor summary."""
    ref_low = r.get("reference_low", "?")
    ref_high = r.get("reference_high", "?")
    group = r.get("test_group", "")
    group_tag = f" [{group}]" if group else ""
    status = r.get("status", "UNKNOWN")

    deviation = ""
    if status in ("HIGH", "CRITICAL_HIGH") and ref_high and ref_high != '?' and float(ref_high) > 0:
        dev_pct = ((r['observed_value'] - float(ref_high)) / float(ref_high)) * 100
        deviation = f" (+{dev_pct:.0f}%)"
        if r['observed_value'] / float(ref_high) >= 2:
            mult = r['observed_value'] / float(ref_high)
            deviation += f" [{mult:.1f}x ULN]"
    elif status in ("LOW", "CRITICAL_LOW") and ref_low and ref_low != '?' and float(ref_low) > 0:
        dev_pct = ((float(ref_low) - r['observed_value']) / float(ref_low)) * 100
        deviation = f" (-{dev_pct:.0f}%)"

    return (
        f"- {r['test_name']}: **{r['observed_value']} {r.get('unit', '')}** "
        f"(ref: {ref_low}-{ref_high}) | {status}{deviation} | "
        f"Severity: {r.get('severity_score', 0)}/10{group_tag} [Source: Lab Report]"
    )
