"""
ClinIQ - Mock Data Generator
===============================
Creates sample_report.pdf and medical_knowledge.txt
for testing the full pipeline without real patient data.
"""

import os
import sys


def create_sample_pdf(output_path="data/sample_report.pdf"):
    """Generate a realistic medical lab report PDF using ReportLab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                 fontSize=18, textColor=colors.HexColor('#1a5276'))
    header_style = ParagraphStyle('Header', parent=styles['Heading2'],
                                  fontSize=13, textColor=colors.HexColor('#2c3e50'),
                                  spaceAfter=6)
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10,
                                spaceBefore=2, spaceAfter=2)

    # === HEADER ===
    story.append(Paragraph("MedTech Diagnostics Laboratory", title_style))
    story.append(Paragraph("123 Healthcare Ave, Suite 400 | Phone: (555) 123-4567", info_style))
    story.append(HRFlowable(width="100%", color=colors.HexColor('#2980b9')))
    story.append(Spacer(1, 12))

    # === PATIENT INFO ===
    story.append(Paragraph("PATIENT LABORATORY REPORT", header_style))
    patient_info = [
        ["Patient Name:", "Jane Smith", "Date of Birth:", "03/15/1985"],
        ["MRN:", "MRN-2024-78432", "Collection Date:", "04/20/2026"],
        ["Ordering Physician:", "Dr. Robert Chen", "Report Date:", "04/21/2026"],
        ["Gender:", "Female", "Fasting:", "Yes (12 hours)"],
    ]
    pt = Table(patient_info, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    pt.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(pt)
    story.append(Spacer(1, 15))

    # === CBC ===
    story.append(Paragraph("COMPLETE BLOOD COUNT (CBC)", header_style))
    cbc_data = [
        ["Test", "Result", "Units", "Reference Range", "Flag"],
        ["Hemoglobin", "10.2", "g/dL", "12.0 - 17.5", "LOW"],
        ["Hematocrit", "31.5", "%", "36.0 - 54.0", "LOW"],
        ["White Blood Cells", "7.8", "x10^3/uL", "4.5 - 11.0", ""],
        ["Red Blood Cells", "3.9", "x10^6/uL", "4.0 - 5.5", "LOW"],
        ["Platelet Count", "245", "x10^3/uL", "150 - 400", ""],
        ["MCV", "82.0", "fL", "80.0 - 100.0", ""],
        ["MCH", "26.5", "pg", "27.0 - 33.0", "LOW"],
    ]
    story.append(_make_table(cbc_data))
    story.append(Spacer(1, 15))

    # === METABOLIC PANEL ===
    story.append(Paragraph("COMPREHENSIVE METABOLIC PANEL", header_style))
    cmp_data = [
        ["Test", "Result", "Units", "Reference Range", "Flag"],
        ["Glucose", "142", "mg/dL", "70 - 100", "HIGH"],
        ["BUN", "18", "mg/dL", "7 - 20", ""],
        ["Creatinine", "0.9", "mg/dL", "0.6 - 1.2", ""],
        ["Sodium", "140", "mEq/L", "136 - 145", ""],
        ["Potassium", "4.2", "mEq/L", "3.5 - 5.0", ""],
        ["Calcium", "9.5", "mg/dL", "8.5 - 10.5", ""],
        ["Total Protein", "7.1", "g/dL", "6.0 - 8.3", ""],
        ["Albumin", "4.0", "g/dL", "3.4 - 5.4", ""],
        ["ALT", "32", "U/L", "7 - 56", ""],
        ["AST", "28", "U/L", "10 - 40", ""],
    ]
    story.append(_make_table(cmp_data))
    story.append(Spacer(1, 15))

    # === DIABETES MARKERS ===
    story.append(Paragraph("DIABETES MARKERS", header_style))
    dm_data = [
        ["Test", "Result", "Units", "Reference Range", "Flag"],
        ["HbA1c", "7.2", "%", "4.0 - 5.6", "HIGH"],
    ]
    story.append(_make_table(dm_data))
    story.append(Spacer(1, 15))

    # === LIPID PANEL ===
    story.append(Paragraph("LIPID PANEL", header_style))
    lipid_data = [
        ["Test", "Result", "Units", "Reference Range", "Flag"],
        ["Total Cholesterol", "252", "mg/dL", "0 - 200", "HIGH"],
        ["LDL Cholesterol", "168", "mg/dL", "0 - 100", "HIGH"],
        ["HDL Cholesterol", "38", "mg/dL", "40 - 60", "LOW"],
        ["Triglycerides", "180", "mg/dL", "0 - 150", "HIGH"],
    ]
    story.append(_make_table(lipid_data))
    story.append(Spacer(1, 15))

    # === THYROID + VITAMINS ===
    story.append(Paragraph("THYROID & VITAMINS", header_style))
    tv_data = [
        ["Test", "Result", "Units", "Reference Range", "Flag"],
        ["TSH", "2.5", "mIU/L", "0.4 - 4.0", ""],
        ["Vitamin D", "12", "ng/mL", "30 - 100", "LOW"],
        ["Vitamin B12", "350", "pg/mL", "200 - 900", ""],
        ["Ferritin", "10", "ng/mL", "12 - 300", "LOW"],
        ["Iron", "45", "ug/dL", "60 - 170", "LOW"],
    ]
    story.append(_make_table(tv_data))
    story.append(Spacer(1, 15))

    # === INFLAMMATORY ===
    story.append(Paragraph("INFLAMMATORY MARKERS", header_style))
    inf_data = [
        ["Test", "Result", "Units", "Reference Range", "Flag"],
        ["CRP", "5.2", "mg/L", "0.0 - 3.0", "HIGH"],
        ["ESR", "22", "mm/hr", "0 - 20", "HIGH"],
    ]
    story.append(_make_table(inf_data))

    doc.build(story)
    print(f"Created: {output_path}")


def _make_table(data):
    """Create a styled medical report table."""
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import Table, TableStyle

    t = Table(data, colWidths=[2*inch, 1*inch, 1*inch, 1.5*inch, 0.7*inch])
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]
    # Highlight flag column
    for i, row in enumerate(data[1:], 1):
        if row[-1] == "HIGH":
            style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#e74c3c')))
            style.append(('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'))
        elif row[-1] == "LOW":
            style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#2980b9')))
            style.append(('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'))
    t.setStyle(TableStyle(style))
    return t


def create_knowledge_base(output_path="data/medical_knowledge.txt"):
    """Create a mini medical knowledge base for RAG indexing."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    content = """Hemoglobin and Anemia
Hemoglobin is the protein in red blood cells that carries oxygen throughout the body. Normal levels are 12.0-17.5 g/dL for adults. Low hemoglobin (below 12 g/dL in women, 13 g/dL in men) indicates anemia, which can cause fatigue, weakness, shortness of breath, and pale skin. Common causes include iron deficiency, vitamin B12 deficiency, chronic disease, and blood loss. Treatment depends on the underlying cause and may include iron supplements, dietary changes, or further investigation for GI bleeding. Severe anemia (Hb < 8 g/dL) may require blood transfusion.

---

Glucose and Diabetes Mellitus
Fasting blood glucose measures the amount of sugar in the blood after an overnight fast. Normal fasting glucose is 70-100 mg/dL. Pre-diabetes is indicated by fasting glucose of 100-125 mg/dL. Diabetes mellitus is diagnosed when fasting glucose exceeds 126 mg/dL on two separate occasions. Persistently elevated glucose damages blood vessels, nerves, kidneys, and eyes over time. Management includes lifestyle modifications (diet, exercise), oral medications (metformin), and possibly insulin therapy. Regular monitoring with HbA1c every 3 months is recommended.

---

HbA1c (Glycated Hemoglobin)
HbA1c reflects average blood sugar levels over the past 2-3 months. Normal HbA1c is below 5.7%. Pre-diabetes range is 5.7-6.4%. Diabetes is diagnosed at HbA1c of 6.5% or higher. An HbA1c of 7% corresponds to an average blood glucose of approximately 154 mg/dL. The American Diabetes Association recommends a target HbA1c of less than 7% for most adults with diabetes. Every 1% reduction in HbA1c reduces the risk of microvascular complications by approximately 37%.

---

Vitamin D Deficiency
Vitamin D is essential for calcium absorption, bone health, immune function, and mood regulation. Normal levels are 30-100 ng/mL. Deficiency (below 20 ng/mL) is extremely common, affecting up to 42% of US adults. Symptoms include fatigue, bone pain, muscle weakness, and depression. Severe deficiency increases risk of osteoporosis, fractures, and may be associated with increased cardiovascular risk. Treatment typically involves supplementation with Vitamin D3 at 2000-4000 IU daily for mild deficiency, or 50,000 IU weekly for 8 weeks for severe deficiency, followed by maintenance dosing. Sun exposure of 15-20 minutes daily can also help.

---

Cholesterol and Cardiovascular Risk
Total cholesterol should ideally be below 200 mg/dL. LDL (bad) cholesterol should be below 100 mg/dL for optimal health. HDL (good) cholesterol should be above 40 mg/dL for men and 50 mg/dL for women. Triglycerides should be below 150 mg/dL. Elevated LDL cholesterol is a major risk factor for atherosclerosis, heart attack, and stroke. The 2018 ACC/AHA guidelines recommend statin therapy for patients with LDL above 190 mg/dL, those with diabetes aged 40-75, and those with a 10-year ASCVD risk of 7.5% or higher. Lifestyle modifications include reduced saturated fat intake, regular exercise, and weight management.

---

Thyroid Function (TSH)
TSH (Thyroid Stimulating Hormone) is the primary screening test for thyroid disorders. Normal range is 0.4-4.0 mIU/L. Elevated TSH (above 4.5) suggests hypothyroidism, which causes fatigue, weight gain, cold intolerance, constipation, and dry skin. Low TSH (below 0.4) suggests hyperthyroidism, which causes weight loss, rapid heartbeat, anxiety, tremor, and heat intolerance. Subclinical hypothyroidism (TSH 4.5-10 with normal Free T4) may be monitored or treated based on symptoms. Levothyroxine is the standard treatment for hypothyroidism.

---

Iron Deficiency and Ferritin
Iron is essential for hemoglobin production and oxygen transport. Serum iron levels should be 60-170 ug/dL. Ferritin is the storage form of iron; normal levels are 12-300 ng/mL. Low ferritin (below 12 ng/mL) is the most sensitive indicator of iron deficiency, even before hemoglobin drops. Iron deficiency is the most common nutritional deficiency worldwide, affecting approximately 2 billion people. Causes include inadequate dietary intake, malabsorption (celiac disease), and chronic blood loss (menstruation, GI bleeding). Treatment includes oral iron supplements (ferrous sulfate 325mg daily) taken on an empty stomach with vitamin C to enhance absorption. Parenteral iron may be needed for severe deficiency or malabsorption.

---

C-Reactive Protein (CRP) and Inflammation
CRP is an acute-phase protein produced by the liver in response to inflammation. Normal CRP is below 3 mg/L. Elevated CRP indicates systemic inflammation, which can be caused by infection, autoimmune disease, tissue injury, or chronic conditions. High-sensitivity CRP (hs-CRP) above 3 mg/L is associated with increased cardiovascular risk. CRP levels above 10 mg/L suggest significant active inflammation requiring investigation. CRP is a non-specific marker and must be interpreted in clinical context alongside other findings.

---

Kidney Function (Creatinine and BUN)
Creatinine is a waste product from normal muscle metabolism, filtered by the kidneys. Normal creatinine is 0.6-1.2 mg/dL. BUN (Blood Urea Nitrogen) normal range is 7-20 mg/dL. Elevated creatinine and BUN suggest impaired kidney function. The eGFR (estimated Glomerular Filtration Rate) calculated from creatinine is the best overall measure of kidney function. Normal eGFR is above 90 mL/min. Stage 3 CKD is defined as eGFR 30-59, and Stage 5 (kidney failure) is eGFR below 15. Causes of elevated creatinine include dehydration, diabetes, hypertension, and kidney disease. Annual screening is recommended for patients with diabetes or hypertension.

---

Liver Function Tests (ALT, AST)
ALT (Alanine Aminotransferase) and AST (Aspartate Aminotransferase) are enzymes found primarily in the liver. Normal ALT is 7-56 U/L and AST is 10-40 U/L. Elevated levels indicate liver cell damage or inflammation. Causes include hepatitis (viral, alcoholic, non-alcoholic fatty liver), medications (acetaminophen, statins), and biliary obstruction. ALT is more specific to the liver, while AST is also found in heart, muscle, and kidney. An AST/ALT ratio greater than 2:1 suggests alcoholic liver disease. Mildly elevated transaminases (less than 3x upper limit) in asymptomatic patients should be repeated in 3-6 months.

---

Complete Blood Count (CBC) Overview
The CBC is one of the most commonly ordered blood tests. It measures white blood cells (WBC 4.5-11.0 x10^3/uL), red blood cells (RBC 4.0-5.5 x10^6/uL), hemoglobin, hematocrit, and platelets (150-400 x10^3/uL). Elevated WBC may indicate infection, inflammation, or leukemia. Low WBC may suggest bone marrow problems or immunosuppression. Low platelets increase bleeding risk. The MCV (Mean Corpuscular Volume, normal 80-100 fL) helps classify anemia: low MCV suggests iron deficiency, high MCV suggests B12 or folate deficiency, normal MCV suggests chronic disease or acute blood loss.

---

ESR (Erythrocyte Sedimentation Rate)
ESR measures how quickly red blood cells settle in a test tube over one hour. Normal ESR is 0-20 mm/hr for adults. Elevated ESR is a non-specific indicator of inflammation, infection, or malignancy. Very high ESR (above 100 mm/hr) may suggest serious conditions such as multiple myeloma, temporal arteritis, or severe infection. ESR tends to rise with age and is generally higher in women. It is often used alongside CRP to monitor inflammatory conditions such as rheumatoid arthritis, lupus, and polymyalgia rheumatica.

---

Vitamin B12 Deficiency
Vitamin B12 (cobalamin) is essential for nerve function, DNA synthesis, and red blood cell formation. Normal levels are 200-900 pg/mL. Deficiency (below 200 pg/mL) can cause megaloblastic anemia, peripheral neuropathy, cognitive decline, and glossitis. Risk groups include vegans, elderly patients, those with pernicious anemia, and patients on metformin or proton pump inhibitors. Treatment involves B12 supplementation: oral cyanocobalamin 1000-2000 mcg daily or intramuscular injections weekly for 4 weeks then monthly. Neurological symptoms may be irreversible if treatment is delayed.

---

Hematocrit
Hematocrit measures the percentage of blood volume occupied by red blood cells. Normal range is 36-54% for adults. Low hematocrit indicates anemia and correlates with low hemoglobin. High hematocrit may indicate polycythemia, dehydration, or chronic hypoxia (e.g., living at high altitude, chronic lung disease). Hematocrit is approximately three times the hemoglobin value. A sudden drop in hematocrit may indicate acute blood loss requiring immediate evaluation.

---

Triglycerides
Triglycerides are a type of fat found in the blood. Normal levels are below 150 mg/dL. Borderline high is 150-199, high is 200-499, and very high is 500+ mg/dL. Elevated triglycerides increase cardiovascular risk and, when very high, can cause pancreatitis. Causes include obesity, diabetes, excess alcohol, high-carbohydrate diets, and certain medications. Management includes lifestyle changes (weight loss, reduced sugar and alcohol, increased omega-3 fatty acids) and potentially fibrate medications for severe elevation.

---

HDL Cholesterol
HDL (High-Density Lipoprotein) is known as good cholesterol because it helps remove LDL cholesterol from arteries. Normal HDL is above 40 mg/dL for men and 50 mg/dL for women. Low HDL is an independent risk factor for cardiovascular disease. Ways to increase HDL include regular aerobic exercise, moderate alcohol consumption, smoking cessation, weight loss, and consumption of healthy fats (olive oil, nuts, fatty fish). Very high HDL (above 100 mg/dL) may not always be protective and can sometimes indicate a genetic condition."""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {output_path}")


if __name__ == "__main__":
    print("ClinIQ - Generating mock data...")
    create_sample_pdf()
    create_knowledge_base()
    print("Done! Mock data created in data/ folder.")
