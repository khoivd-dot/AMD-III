"""Five new discharge documents (red-team cases). Not in the app's samples."""

CASES = {}

CASES["rt-af-hoa-vi"] = dict(
    language="vi", patient_name="Nguyen Thi Hoa",
    title="New atrial fibrillation on apixaban, Vietnamese",
    source="""DISCHARGE INSTRUCTIONS - Bayview Medical Center, Cardiology
Patient: Nguyen Thi Hoa   MRN: 4471-0938   DOB: 06/11/1951
Attending: Dr. Priya Rao
Daughter / caregiver at bedside: Linh Nguyen, cell 408-555-0172
Discharge date: 10/09/2026

Diagnosis: New-onset atrial fibrillation with RVR, rate controlled. CHA2DS2-VASc 4.

MEDICATIONS
NEW: Apixaban 5 mg PO BID, about 12 hours apart. Do not skip doses. Do not stop unless your cardiologist tells you to.
NEW: Metoprolol tartrate 25 mg PO BID. Hold a dose if heart rate below 55 or you feel faint, and call the clinic.
STOP: Aspirin 81 mg daily - apixaban replaces it; taking both raises bleeding risk.
HOLD: Hydrochlorothiazide 25 mg daily - sodium was low (128). Do not take until your sodium is rechecked and Dr. Rao tells you to restart.
NEW: Acetaminophen 500 mg PO q6h only if needed for pain. Max 3000 mg in 24 hours. Avoid ibuprofen and naproxen.

Return precautions: Call 911 for sudden weakness or numbness on one side, face drooping, trouble speaking, or chest pain. Go to the Emergency Department for black or bloody stools, vomiting blood, or any head injury. Call the anticoagulation clinic at (408) 555-0199 for a nosebleed that lasts more than 10 minutes or blood in the urine.

Activity: Use a soft toothbrush and an electric razor. Limit alcohol to 1 drink a day.

Follow-up: Cardiology clinic with Dr. Rao on 10/22/2026 at 2:15 PM. Lab (sodium recheck, BMP) on 10/13/2026 at the outpatient lab.
""")

CASES["rt-dm-chen-zh"] = dict(
    language="zh", patient_name="Chen Jianguo",
    title="Type 2 diabetes starting insulin glargine with correction scale, Chinese",
    source="""DISCHARGE INSTRUCTIONS - Lakeshore Hospital, Medicine 5 West
Patient: Chen Jianguo (陈建国)   MRN: 20577311   DOB: 01/23/1958
Attending: Dr. Marcus Webb
Discharge date: 10/09/2026

Diagnosis: Type 2 diabetes, uncontrolled (A1c 11.2%), admitted with hyperglycemia. Acute kidney injury, improving (creatinine 1.8 -> 1.4).

MEDICATIONS
NEW: Insulin glargine (Lantus) 14 units subcut once daily at bedtime (9 PM).
NEW: Insulin lispro (Humalog) correction scale subcut before meals: glucose 151-200 give 2 units; 201-250 give 4 units; 251-300 give 6 units; above 300 give 8 units and call the diabetes nurse line.
HOLD: Metformin 1000 mg BID - hold until kidney function is rechecked on 10/16/2026. Dr. Webb will tell you when to restart.
STOP: Glipizide 10 mg daily - stop; with insulin it can cause low blood sugar.
CONTINUE: Lisinopril 10 mg daily.

Check fingerstick glucose before each meal and at bedtime; write every value in the log.
Low blood sugar: if glucose is below 70 mg/dL, take 15 g of fast sugar (4 glucose tablets or 4 oz juice) and recheck in 15 minutes.
Return precautions: Go to the Emergency Department or call 911 for confusion, passing out, or glucose below 70 that does not come up after 2 treatments. Call the diabetes nurse line at 312-555-0148 if 2 readings in a row are above 300 or if you are sick and cannot eat.

Diet: Consistent carbohydrates, about 45-60 g per meal. No sugary drinks.

Follow-up: Diabetes education class on 10/13/2026 at 1:00 PM. Endocrinology clinic with Dr. Webb on 10/20/2026 at 9:40 AM. Kidney blood test on 10/16/2026.
""")

CASES["rt-copd-moreau-fr"] = dict(
    language="fr", patient_name="Jean-Luc Moreau",
    title="COPD exacerbation, prednisone taper and inhaler changes, French",
    source="""DISCHARGE INSTRUCTIONS - Harbor Pulmonary Unit
Patient: Jean-Luc Moreau   MRN: 61-224-907   DOB: 09/30/1949
Attending: Dr. Ngozi Okafor
Discharge date: 10/09/2026

Diagnosis: COPD exacerbation, likely viral trigger. SpO2 92% on room air at rest at discharge.

MEDICATIONS
NEW: Prednisone taper by mouth with breakfast: 40 mg daily x 3 days, then 30 mg daily x 3 days, then 20 mg daily x 3 days, then 10 mg daily x 3 days, then stop. Last dose 10/20/2026.
NEW: Fluticasone/salmeterol (Advair Diskus) 250/50 mcg, 1 inhalation BID. Rinse mouth and spit after each use.
STOP: Fluticasone (Flovent) 110 mcg inhaler - replaced by Advair. Do not use both.
CONTINUE: Tiotropium (Spiriva) 18 mcg, inhale 1 capsule once daily.
CONTINUE: Albuterol HFA 90 mcg, 2 puffs every 4 hours only if needed for shortness of breath or wheezing.
NEW: Azithromycin 250 mg PO once daily x 4 more days (last dose 10/12/2026).

Home oxygen: 2 L/min by nasal cannula during sleep and when walking.
Return precautions: Call 911 for severe shortness of breath, blue or gray lips, or confusion. Call the pulmonary clinic at 617-555-0133 if you need albuterol more often than every 4 hours, have a fever above 38.5 C, or cough up more yellow or green mucus.
Do not smoke. Do not smoke near oxygen.

Follow-up: Pulmonary clinic with Dr. Okafor on 10/24/2026 at 11:00 AM. Pulmonary rehab intake call within 1 week.
""")

CASES["rt-asthma-mateo-es"] = dict(
    language="es", patient_name="Mateo Hernandez",
    title="Pediatric asthma, instructions for the caregiver, Spanish",
    source="""PEDIATRIC DISCHARGE INSTRUCTIONS - Children's Hospital of South Florida
Patient: Mateo Hernandez   Age: 6 y   Weight: 22 kg (48.5 lb)   MRN: CH-0091847
Parent/guardian: Rosa Hernandez (mother), phone (305) 555-0123
Attending: Dr. Elena Alvarez
Discharge date: 10/09/2026

Diagnosis: Moderate asthma exacerbation triggered by a cold. Responded to albuterol and steroids.

MEDICATIONS (give to your child)
NEW: Prednisolone oral solution 15 mg/5 mL: give 7 mL (21 mg) by mouth once daily in the morning with food for 3 more days. Last dose 10/12/2026.
NEW: Fluticasone HFA 44 mcg: 2 puffs with spacer twice daily, every day, even when your child is well. Rinse mouth after.
Albuterol HFA 90 mcg: 4 puffs with spacer every 4 hours while awake for the next 2 days, then 2-4 puffs every 4 hours only if needed for cough, wheeze, or hard breathing.
HOLD: Montelukast 5 mg chewable at bedtime - hold because of nightmares and mood changes. Do not restart until the pulmonologist reviews it.

Return precautions: Call 911 if your child's lips or face turn blue or gray, your child is struggling to breathe or cannot talk, or is very sleepy and hard to wake. Go to the Emergency Department if your child needs albuterol more often than every 4 hours or the ribs pull in with each breath. Call the pediatric clinic at (305) 555-0187 for fever above 102 F or if your child is not drinking.

Home: No smoking in the home or car. Give the school a copy of the asthma action plan.

Follow-up: Pediatrician Dr. Alvarez on 10/14/2026 at 3:30 PM. Pediatric pulmonology referral sent; the office will call you.
""")

CASES["rt-appy-huy-vi"] = dict(
    language="vi", patient_name="Pham Quoc Huy",
    title="After laparoscopic appendectomy, opioid only if needed, Vietnamese",
    source="""DISCHARGE INSTRUCTIONS - General Surgery, Northgate Hospital
Patient: Pham Quoc Huy   MRN: 88310452   DOB: 02/17/1992
Surgeon: Dr. Minh Tran
Discharge date: 10/09/2026

Procedure: Laparoscopic appendectomy on 10/08/2026 for acute appendicitis, not perforated.

MEDICATIONS
NEW: Acetaminophen 1000 mg PO every 8 hours for pain. Do not take more than 3000 mg in 24 hours, including cold or flu products that contain acetaminophen.
NEW: Oxycodone 5 mg PO every 6 hours only if needed for severe pain not relieved by acetaminophen. Max 4 tablets in 24 hours. Dispensed 12 tablets, no refills.
NEW: Docusate 100 mg PO twice daily while taking oxycodone.
HOLD: Lisinopril 10 mg daily - blood pressure was low after surgery. Do not take until your primary care doctor rechecks your blood pressure.

Do not drive, drink alcohol, or operate machinery while taking oxycodone.
Wound care: Keep the 3 small incisions clean and dry for 48 hours, then you may shower. Leave the skin glue alone; it will peel off. No baths, hot tubs or swimming for 2 weeks.
Activity: Walk several times a day. No lifting more than 10 lb (4.5 kg) for 2 weeks.

Return precautions: Call 911 for severe belly pain with fainting or trouble breathing. Call the surgery clinic at (206) 555-0164 for fever above 101.5 F, redness, pus or drainage from an incision, vomiting that will not stop, or no bowel movement in 3 days.

Pending: Pathology report on the appendix; the clinic will call you with the result.
Follow-up: Surgery clinic with Dr. Tran on 10/20/2026 at 8:45 AM. Primary care within 1 week for blood pressure check.
""")
