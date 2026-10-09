# Real model runs: cpu-qwen2.5-3b-v2

Model: **Qwen2.5-3B-Instruct (Q4_K_M GGUF)**. Hardware: **GitHub Actions CPU runner · llama.cpp (not AMD)**. Recorded 2026-10-09 00:43 UTC.

| Case | Sentences | Green | Amber | Red | Missing items | Medicine cross-check | Model calls | Model time | Output tokens/s |
|---|---|---|---|---|---|---|---|---|---|
| af-binh-vi | 8 | 6 | 0 | 2 | 3 | 0 | 8 | 337.82 s | 7.9 |
| copd-pierre-fr | 6 | 4 | 0 | 2 | 1 | 0 | 6 | 270.0 s | 8.1 |
| dm-ana-es | 9 | 8 | 0 | 1 | 1 | 0 | 7 | 432.34 s | 15.8 |
| hf-maria-es | 11 | 6 | 0 | 5 | 0 | 0 | 7 | 1085.86 s | 14.4 |
| knee-giulia-it | 10 | 7 | 0 | 3 | 0 | 0 | 5 | 432.53 s | 8.0 |

## af-binh-vi

- **Missing** F2: The dose of Apixaban (5 mg) is never stated.
- **Missing** F3: The dose of Diltiazem (120 mg) is never stated.
- **Missing** F5: The dose of Atorvastatin (40 mg) is never stated.
- **F5 red**: You need to see the Cardiology doctor in 2 weeks and the Primary care doctor in 1 week. / Bạn cần phải đi khám tim mạch trong hai tuần và khám bác sĩ chính trong một tuần.  
  Numbers differ after translation: {1, 2} vs none.
- **F7 red**: You should stop taking Aspirin. It raises the risk of bleeding, and Apixaban already protects against clots. / Bạn nên停止服用 Aspirin. Nó tăng nguy cơ chảy máu, và Apixaban đã bảo vệ chống lại cục máu đông.  
  Translation contains text in another writing system (“停止服用”).; Safety model: unsupported. Sentence adds 'stop taking Aspirin' which is not in the facts.

## copd-pierre-fr

- **Missing** F4: Ipratropium inhaler is cited but never named for the patient.
- **Fact F5**: Model labelled this 'other'; the text reads as follow up. Checked as that.
- **F3 red**: You will change Albuterol inhaler to 2 puffs every 4 hours as needed for shortness of breath. (F3, F5) / Vous changerez l'insuline Albuterol à 2 puffs toutes les 4 heures selon les besoins pour les difficultés respiratoires. (F3, F5)  
  “Only if needed” is lost in the translation.
- **F4 red**: Call 911 if you have severe shortness of breath, blue lips, or confusion. Call your doctor if you need albuterol more than every 4 hours or have a fever above 38.5 C. (F4, F6) / Appelez l'urgence si vous avez une difficultés respiratoire sévère, des lèvres bleues ou de la confusion. Appelez votre médecin si vous avez besoin d'Albuterol plus souvent toutes les 4 heures ou si vous avez une température supérieure à 38,5°C. (F4, F6)  
  Numbers differ after translation: {38.5, 4, 911} vs {38.5, 4}.; “Only if needed” is lost in the translation.; Back-translation numbers differ: {38.5, 4, 911} vs {38.5, 4}.

## dm-ana-es

- **Missing** R1: No sentence clearly tells the patient to stop metformin.
- **Fact F6**: Model labelled this 'activity'; the text reads as medication. Checked as that.
- **Fact R1**: The model did not list this instruction; the rule check found it in the source.
- **R1 red**: Metformin 500 mg - type 1 diabetes does not respond to metformin. / ¡Metformin 500 mg - el tipo 1 de diabetes no responde a metformin!  
  Safety model: unsupported. Sentence adds information not in the facts.

## hf-maria-es

- **F1 red**: You will start taking Spironolactone 25 mg once daily. / Tendrás que empezar a tomar Spironolactona 25 mg al día.  
  spironolactone lost in translation.
- **F2 red**: You will increase furosemide to 40 mg twice daily, 8 AM and 2 PM. / Tendrás que aumentar el furosemida a 40 mg al día, por la mañana y a la tarde.  
  Times differ after translation: 2:00, 8:00 vs none.; Back-translation numbers differ: {2, 40, 8} vs {40}.; furosemide lost in translation.
- **F3 red**: Pause taking Ibuprofen until kidney function is rechecked by your cardiologist. / Pausa la ibuprofeno hasta que se revise la función renal por tu cardiologista.  
  ibuprofen lost in translation.
- **F5 red**: You will start taking Sacubitril/valsartan 24/26 mg twice daily, do not take within 36 hours of your last Lisinopril dose. / Tendrás que empezar a tomar Sacubitril/valsartan 24/26 mg al día, no tomar dentro de 36 horas de tu última dosis de Lisinopril.  
  Back-translation numbers differ: {2, 24, 26, 36} vs {24, 26, 36}.
- **F8 red**: Call the heart failure clinic at [PHONE_1] if weight increases by more than 2 lb in one day or 5 lb in one week, or if leg swelling worsens. / Llama al centro de cardiología de corazón si el peso aumenta más de 2 libras en un día o 5 libras en una semana, o si el hinchaje de las piernas empeora.  
  Numbers differ after translation: {1, 2, 5} vs {2, 5}.; A name or contact detail was lost in translation.

## knee-giulia-it

- **Fact F8**: Model labelled this 'activity'; the text reads as follow up. Checked as that.
- **F1 red**: You will start taking Enoxaparin 40 mg subcutaneous injection once daily for 14 days to prevent blood clots, last dose on October 26, 2026. (F1) / Inizierai a prendere Enoxaparin 40 mg in iniezione sotto pelle una volta al giorno per 14 giorni per prevenire i blocchi sanguigni, l'ultima dose il 21 ottobre 2026. (F1)  
  Dates differ after translation: 26 Oct 2026 vs 21 Oct 2026 as a Italian reader would read them. Write the month as a word.
- **F2 red**: You will start taking Oxycodone 5 mg by mouth every 6 hours only if needed for severe pain, maximum 4 tablets in 24 hours. (F2) / Inizierai a prendere Oxycodone 5 mg per via orale solo se necessario per il dolore molto intenso, massimo 4 farmaci in 24 ore. (F2)  
  Numbers differ after translation: {24, 4, 5, 6} vs {24, 4, 5}.; Back-translation numbers differ: {24, 4, 5, 6} vs {24, 4, 5}.
- **F8 red**: Use the walker at all times for 2 weeks. Do the home exercises from physiotherapy 3 times a day. (F8) / Usa la caviglia a tutti i tempi per 2 settimane. Fai gli esercizi da casa tre volte al giorno con il fisioterapista. (F8)  
  Numbers differ after translation: {2, 3} vs {2}.
