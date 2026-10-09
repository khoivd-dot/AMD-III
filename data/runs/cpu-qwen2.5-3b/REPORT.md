# Real model runs: cpu-qwen2.5-3b

Model: **Qwen2.5-3B-Instruct (Q4_K_M GGUF)**. Hardware: **GitHub Actions CPU runner · llama.cpp (not AMD)**. Recorded 2026-10-09 00:04 UTC.

| Case | Sentences | Green | Amber | Red | Missing items | Medicine cross-check | Model calls | Model time | Output tokens/s |
|---|---|---|---|---|---|---|---|---|---|
| af-binh-vi | 5 | 3 | 0 | 2 | 0 | 0 | 5 | 138.65 s | 15.3 |
| copd-pierre-fr | 9 | 9 | 0 | 0 | 0 | 0 | 5 | 242.49 s | 11.1 |
| dm-ana-es | 5 | 4 | 0 | 1 | 0 | 0 | 5 | 271.52 s | 9.0 |
| hf-maria-es | 9 | 9 | 0 | 0 | 0 | 0 | 5 | 355.92 s | 9.2 |
| knee-giulia-it | failed: facts: model call failed (Unterminated string starting at: line 419 column 20 (char 12749)) | | | | | | | | |

## af-binh-vi

- **S4 red**: You must follow-up with Cardiology clinic with [CLINICIAN_1] in 2 weeks. Primary care in 1 week. / Bạn cần phải theo dõi với Trung tâm Tim mạch với [CLINICIAN_1] trong hai tuần tới. Tim mạch trong một tuần tới.  
  Numbers differ after translation: {1, 2} vs none.
- **S5 red**: You must not stop taking Aspirin 81 mg without talking to your doctor. Do not hold Aspirin until your doctor says to restart. / Bạn không được停止服用Aspirin 81 mg mà không nói chuyện với bác sĩ của bạn. Không ngưng Aspirin cho đến khi bác sĩ nói bắt đầu lại.  
  Safety model: contradicts. Sentence contradicts the facts.

## copd-pierre-fr

Nothing flagged.

## dm-ana-es

- **S5 red**: You should check your glucose levels at least 4 times a day. You should eat a balanced diet and avoid skipping meals. You should stay hydrated and get regular exercise. / Deberás chequear tus niveles de glucosa al menos cuatro veces al día. Deberás comer una dieta equilibrada y evitar pasar por alto las comidas. Deberás mantener hidratado y hacer ejercicio regularmente.  
  Number 4 is not in the cited source.; Numbers differ after translation: {4} vs none.; Safety model: unsupported. Adds information about new diagnoses not in the facts.

## hf-maria-es

Nothing flagged.
