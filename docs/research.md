# AMD Developer Hackathon: ACT III, research notes

Checked 2026-10-08 against the live event page and linked pages. Anything not listed under "Verified" is unknown.

## Verified event facts
Source: https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii

- Hybrid. Online build 12 to 18 October 2026, on-site 17 to 18 October in Rome (Link Campus University), Milan (SmartCityLab Milano) and Imperia (IMPERIAWARE). Travel not covered. Page meta says the event ends 18 October 2026. Exact submission deadline and timezone are not on the page yet.
- Five tracks. Ours is Track 2, Health and Wellbeing (partner: Vibe Generation).
- Hard requirement for every project: "run a meaningful part of its workload on AMD infrastructure or AMD hardware", and that AMD part "must be part of the working product shown to the judges". Options: AMD Developer Cloud, Instinct GPUs, ROCm, Ryzen AI, Radeon.
- No model is mandated outside the Evolus track. Teams pick their own models and frameworks.
- Credits: $100 AMD Developer Cloud credit for new AMD AI Developer Program members (about 50 hours of one MI300X at $1.99/hr). A payment card must be on file before a GPU droplet can be created. Credits usually expire 30 days after they are applied. A powered-off droplet still bills; it must be destroyed.
- Approval needs the AMD AI Developer Program sign-up as well as lablab.ai enrolment.
- Prize pool $12,000+, no breakdown. PwC Italy / Vibe Generation special prize (AirPods for the team) judged on strategic thinking and quantified value, technical execution and AI orchestration, taste and originality.
- Judging: Application of Technology (model integration), Presentation, Business Value, Originality.
- Submission: title, short and long description, track, tags, cover image, video (5 minutes max, under 300 MB, as a link), slides, public GitHub repo, demo platform and live app URL, working prototype.
- Not found anywhere: whether code written before kickoff (12 Oct) is allowed. Ask on the lablab Discord before submitting. Safe path: keep a clean commit history that starts at or after kickoff, or disclose prior work in the long description.

## AMD Developer Cloud quick path (from the lablab tutorial)
Source: https://lablab.ai/ai-tutorials/amd-developer-cloud-host-llm-vllm
1. Join the AMD AI Developer Program, sign in to AMD Developer Cloud, add a card under Billing.
2. Create GPU Droplet, region ATL1, plan 1x MI300X (192 GB HBM3), image "vLLM Quick Start", add an SSH key.
3. `ssh root@IP`, then `docker exec -it rocm /bin/bash`.
4. `python -m vllm.entrypoints.openai.api_server --model <model> --host 0.0.0.0 --port 8000 ...`
5. OpenAI-compatible base URL `http://IP:8000/v1`. No auth by default and port 8000 is public, so add `--api-key` and keep the key in an env var.

## The pain point we picked: discharge instructions

Evidence (all checked against the source pages listed):
- Comprehension is low for everyone and worse with a language barrier. Karliner et al., Medical Care 2012 (308 patients): overall only 48% knew their medication category, 56% knew their follow-up appointment type; limited English proficiency patients knew medication category 45% vs 54% and follow-up appointment type 50% vs 66%. https://pmc.ncbi.nlm.nih.gov/articles/PMC3311126
- Written instructions sit far above patients' reading level. Mayo Clinic trauma study (American Journal of Surgery, 2016): notes written at about a 10th-grade level while only about a quarter of patients had the reading skills to understand them; the AMA recommends 6th grade. Rewriting the templates to grade 8.5 cut post-discharge phone calls from 22 to 9 per 100 patients. https://www.foxnews.com/health/patients-leaving-hospitals-often-dont-understand-care-plans and https://www.news-medical.net/news/20171026/Easier-to-read-discharge-instructions-improve-patientse28099-understanding-of-their-own-recovery-care.aspx
- In the ED, "reasons to return" were the worst understood item; standardised readable instructions improved it. Russell et al., WestJEM 2024. https://westjem.com/?p=22351
- LLMs fix readability but are not safe unchecked. Zaretsky et al., JAMA Network Open 2024 (GPT-4, 50 NYU discharge summaries): grade level 11.0 to 6.2, understandability (PEMAT) 13% to 81%, but 18% of physician reviews raised a potential safety concern, 24% of reviews found omissions and 4% hallucinations. The authors conclude physician review is needed before release. https://pmc.ncbi.nlm.nih.gov/articles/PMC10928500
- Machine translation fails exactly where it hurts. Khoong et al., JAMA Internal Medicine 2019: Google Translate was 92% accurate for Spanish and 81% for Chinese ED discharge instructions; "hold the kidney medicine" became "keep taking" the medication in Chinese, which the authors called life threatening. https://www.ucsf.edu/news/2019/02/413376/google-translates-doctors-orders-spanish-and-chinese-few-significant-errors

The gap: tools can already simplify and translate. Nobody makes the result trustworthy enough for a nurse to hand over without re-reading everything, and nobody checks that the patient actually understood. That is what we build.

## Ideas considered
| Idea | Pain | Why not first |
|---|---|---|
| **Homeward: verified plain-language, multilingual discharge instructions with teach-back** | Low comprehension, language barriers, unsafe AI rewrites | Picked. Strongest evidence, natural "uncertainty + human review" story, clean AMD angle (self-hosted open model, PHI never leaves) |
| Pre-visit intake interpreter (patient answers in own language, clinician gets structured English summary) | Intake time, language | Crowded space, harder to show measurable gain in a 5-minute video |
| Medication reconciliation assistant (home list vs discharge list) | Med discrepancies at transitions | Folded into Homeward as the medication change table (new / changed / stop / hold / continue) |
| Prior-authorisation packet builder | Admin burden | US-specific, judges are in Italy, weaker patient story |
| Appointment prep companion | Patients forget questions | Lower stakes, less originality |
