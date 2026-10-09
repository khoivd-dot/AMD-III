# Real model runs: cpu-qwen2.5-3b

Model: **Qwen2.5-3B-Instruct (Q4_K_M GGUF)**. Hardware: **GitHub Actions CPU runner · llama.cpp (not AMD)**. Recorded 2026-10-09 00:04 UTC.

| Case | Sentences | Green | Amber | Red | Missing items | Medicine cross-check | Model calls | Model time | Output tokens/s |
|---|---|---|---|---|---|---|---|---|---|
| af-binh-vi | 5 | 2 | 0 | 3 | 2 | 0 | 5 | 138.65 s | 15.3 |
| copd-pierre-fr | 9 | 6 | 2 | 1 | 1 | 0 | 5 | 242.49 s | 11.1 |
| dm-ana-es | 5 | 4 | 0 | 1 | 4 | 0 | 5 | 271.52 s | 9.0 |
| hf-maria-es | 9 | 9 | 0 | 0 | 3 | 0 | 5 | 355.92 s | 9.2 |
| knee-giulia-it | failed: facts: model call failed (Unterminated string starting at: line 419 column 20 (char 12749)) | | | | | | | | |

## af-binh-vi

- **Missing** F1: Apixaban: the clinician's 12 (“Apixaban 5 mg by mouth twice daily, about 12 hours apart. Do not skip doses. Do not stop without talking to your cardiologist.”) is never stated.
- **Missing** F3: No sentence clearly tells the patient to stop Aspirin.
- **Fact F1**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F2**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F3**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F4**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **S3 red**: You must use a soft toothbrush and an electric razor. Avoid ibuprofen and naproxen; use acetaminophen for pain. Call 911 for sudden weakness, trouble speaking, chest pain, or fainting. Go to the Emergency Department for black or bloody stools, vomiting blood, or a head injury. / Bạn cần phải sử dụng bàn chải đánh răng mềm và máy cạo râu điện. Không sử dụng ibuprofen và naproxen; sử dụng acetaminophen để giảm đau. Gọi 911 nếu bạn cảm thấy yếu đột ngột, khó nói, đau ngực hoặc晕倒. Đi đến Trung tâm Khẩn cấp nếu có phân đen hoặc máu trong phân, nôn máu hoặc chấn thương đầu.  
  Translation contains text in another writing system (“晕倒”).
- **S4 red**: You must follow-up with Cardiology clinic with [CLINICIAN_1] in 2 weeks. Primary care in 1 week. / Bạn cần phải theo dõi với Trung tâm Tim mạch với [CLINICIAN_1] trong hai tuần tới. Tim mạch trong một tuần tới.  
  Numbers differ after translation: {1, 2} vs none.
- **S5 red**: You must not stop taking Aspirin 81 mg without talking to your doctor. Do not hold Aspirin until your doctor says to restart. / Bạn không được停止服用Aspirin 81 mg mà không nói chuyện với bác sĩ của bạn. Không ngưng Aspirin cho đến khi bác sĩ nói bắt đầu lại.  
  Source says stop Aspirin; this reads as keep taking it.; Translation contains text in another writing system (“停止服用”).; Safety model: contradicts. Sentence contradicts the facts.

## copd-pierre-fr

- **Missing** R1: Not explained to the patient: Smoking cessation clinic referral sent
- **Fact F2**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F3**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F4**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F5**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F7**: Model labelled this 'diagnosis'; the text reads as warning sign. Checked as that.
- **Fact F8**: Model labelled this 'diagnosis'; the text reads as warning sign. Checked as that.
- **Fact F9**: Model labelled this 'diagnosis'; the text reads as follow up. Checked as that.
- **Fact F10**: Model labelled this 'diagnosis'; the text reads as follow up. Checked as that.
- **Fact R1**: The model did not list this instruction; the rule check found it in the source.
- **S3 amber**: You must take Tiotropium 2 puffs once a day. / Vous devez prendre les Tiotropium à 2 pincettes une fois par jour.  
  Could not find the unit for 2 puff in the translation. Check it reads correctly.
- **S4 amber**: You must use Albuterol inhaler 2 puffs every 4 hours as needed for shortness of breath. / Vous devez utiliser l'inhalateur Albuterol à 2 pincettes à chaque 4 heures selon les besoins pour la difficultés d'inspiration.  
  Could not find the unit for 2 puff in the translation. Check it reads correctly.
- **S8 red**: You must follow-up with the pulmonary rehabilitation intake on November 4, 2026. / Vous devez suivre avec l'entrée de l'intervention de réhabilitation pulmonaire le 11/04/2026.  
  Dates differ after translation: 4 Nov 2026 vs 11 Apr 2026 as a French reader would read them. Write the month as a word.

## dm-ana-es

- **Missing** R1: Not explained to the patient: Check blood glucose before each meal and at bedtime
- **Missing** R2: Not explained to the patient: Record all values
- **Missing** R3: Not explained to the patient: Never skip insulin glargine, even if you are not eating
- **Missing** R4: Not explained to the patient: Call the diabetes team if you are sick and cannot eat
- **Fact F3**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F4**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F5**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F7**: Model labelled this 'diagnosis'; the text reads as warning sign. Checked as that.
- **Fact F8**: Model labelled this 'diagnosis'; the text reads as follow up. Checked as that.
- **Fact R1**: The model did not list this instruction; the rule check found it in the source.
- **Fact R2**: The model did not list this instruction; the rule check found it in the source.
- **Fact R3**: The model did not list this instruction; the rule check found it in the source.
- **Fact R4**: The model did not list this instruction; the rule check found it in the source.
- **S5 red**: You should check your glucose levels at least 4 times a day. You should eat a balanced diet and avoid skipping meals. You should stay hydrated and get regular exercise. / Deberás chequear tus niveles de glucosa al menos cuatro veces al día. Deberás comer una dieta equilibrada y evitar pasar por alto las comidas. Deberás mantener hidratado y hacer ejercicio regularmente.  
  Number 4 is not in the cited source.; Numbers differ after translation: {4} vs none.; Safety model: unsupported. Adds information about new diagnoses not in the facts.

## hf-maria-es

- **Missing** F5: Not explained to the patient: Patient must take Sacubitril/valsartan 24/26 mg twice daily.
- **Missing** R1: Not explained to the patient: Sodium restriction < 2 g/day
- **Missing** R2: Not explained to the patient: Fluid restriction 1.5 L/day
- **Fact F1**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F2**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F3**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F4**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F5**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F6**: Model labelled this 'diagnosis'; the text reads as medication. Checked as that.
- **Fact F7**: Model labelled this 'diagnosis'; the text reads as warning sign. Checked as that.
- **Fact F8**: Model labelled this 'diagnosis'; the text reads as warning sign. Checked as that.
- **Fact F11**: Model labelled this 'diagnosis'; the text reads as follow up. Checked as that.
- **Fact F12**: Model labelled this 'diagnosis'; the text reads as follow up. Checked as that.
- **Fact R1**: The model did not list this instruction; the rule check found it in the source.
- **Fact R2**: The model did not list this instruction; the rule check found it in the source.
