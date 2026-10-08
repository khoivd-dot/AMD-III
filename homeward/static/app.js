"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const marked = (t) => esc(t).replace(/\[(PATIENT|CLINICIAN|MRN|DATE_OF_BIRTH|EMAIL|PHONE|ADDRESS)_\d+\]/g, (m) => `<mark class="ph">${m}</mark>`);

const STAGES = [
  ["masking", "Mask identifiers", "Names, record numbers, dates of birth and phone numbers are replaced before any model sees the text."],
  ["facts", "Build the fact ledger", "The model lists every instruction, each with an exact quote from the source."],
  ["draft", "Write in plain language", "Grade 6 target. Every sentence cites the facts it restates."],
  ["translate", "Translate", "Drug names, numbers and contact details kept as written."],
  ["back_translate", "Back-translate", "A second pass turns the translation back into English for checking."],
  ["judge", "Safety model review", "The model checks each sentence against its cited facts."],
  ["checks", "Deterministic checks", "Numbers, drug names, stop vs keep, coverage of every critical fact."],
  ["ready", "Ready for human review", ""],
];
const SECTION_ORDER = ["why", "medicines", "warning_signs", "appointments", "daily_care"];
const SECTION_ICON = { why: "🏥", medicines: "💊", warning_signs: "🚨", appointments: "📅", daily_care: "🏠" };
const UI = {
  en: { why: "Why you were in hospital", medicines: "Your medicines", warning_signs: "Get help if…", appointments: "Your appointments", daily_care: "Taking care of yourself at home", title: "Your instructions for going home", read: "Read aloud", quiz: "Check your understanding", quizIntro: "A few quick questions. Wrong answers are fine: your nurse will go over them with you.", right: "Correct.", wrong: "Not quite. Your nurse has been asked to go over this with you." },
  es: { why: "Por qué estuvo en el hospital", medicines: "Sus medicamentos", warning_signs: "Pida ayuda si…", appointments: "Sus citas", daily_care: "Cómo cuidarse en casa", title: "Sus instrucciones para volver a casa", read: "Leer en voz alta", quiz: "Compruebe lo que entendió", quizIntro: "Unas preguntas rápidas. Si se equivoca, no pasa nada: su enfermera lo repasará con usted.", right: "Correcto.", wrong: "No exactamente. Su enfermera lo repasará con usted." },
  it: { why: "Perché è stato in ospedale", medicines: "I suoi farmaci", warning_signs: "Chieda aiuto se…", appointments: "I suoi appuntamenti", daily_care: "Come prendersi cura di sé a casa", title: "Le sue istruzioni per il ritorno a casa", read: "Leggi ad alta voce", quiz: "Verifichi cosa ha capito", quizIntro: "Alcune domande veloci. Se sbaglia va bene: l'infermiere le rivedrà con lei.", right: "Corretto.", wrong: "Non proprio. L'infermiere lo rivedrà con lei." },
  vi: { why: "Lý do bạn nằm viện", medicines: "Thuốc của bạn", warning_signs: "Hãy tìm trợ giúp nếu…", appointments: "Lịch hẹn của bạn", daily_care: "Tự chăm sóc tại nhà", title: "Hướng dẫn khi về nhà", read: "Đọc to", quiz: "Kiểm tra mức hiểu", quizIntro: "Vài câu hỏi ngắn. Trả lời sai cũng không sao: y tá sẽ giải thích lại cho bạn.", right: "Đúng.", wrong: "Chưa đúng. Y tá sẽ giải thích lại cho bạn." },
  zh: { why: "您住院的原因", medicines: "您的药物", warning_signs: "出现以下情况请求助…", appointments: "您的预约", daily_care: "在家如何照顾自己", title: "您的出院指导", read: "朗读", quiz: "确认您是否理解", quizIntro: "几个简单问题。答错没关系，护士会再和您讲解。", right: "正确。", wrong: "不太对。护士会再和您讲解。" },
  fr: { why: "Pourquoi vous étiez à l'hôpital", medicines: "Vos médicaments", warning_signs: "Demandez de l'aide si…", appointments: "Vos rendez-vous", daily_care: "Prendre soin de vous à la maison", title: "Vos consignes pour le retour à la maison", read: "Lire à voix haute", quiz: "Vérifiez ce que vous avez compris", quizIntro: "Quelques questions rapides. Une erreur n'est pas grave : votre infirmière reverra ce point avec vous.", right: "Exact.", wrong: "Pas tout à fait. Votre infirmière reverra ce point avec vous." },
};
const SPEECH = { en: "en-US", es: "es-ES", it: "it-IT", vi: "vi-VN", zh: "zh-CN", fr: "fr-FR" };

const state = { meta: null, caseId: null, c: null, sample: null, packet: null, pLang: "tl", poll: null };

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

function show(view) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (view === "patient") loadPacket();
  window.scrollTo({ top: 0 });
}

// ------------------------------------------------------------------ setup
async function init() {
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  state.meta = await api("/api/meta");
  const llm = state.meta.llm;
  const mode = $("#mode");
  if (llm.mode === "live") {
    mode.textContent = `Live · ${llm.model.split("/").pop()} on ${llm.hardware}`;
  } else {
    mode.textContent = "Sample runs only · no GPU connected";
    mode.classList.add("replay");
    mode.title = "The AMD endpoint is switched off. Sample cases replay their saved model outputs; the checks, review and quiz run live.";
  }
  const sel = $("#language");
  Object.entries(state.meta.languages).forEach(([k, v]) => sel.add(new Option(v, k)));
  sel.add(new Option("Other language (route to interpreter)", "other"));
  const box = $("#samples");
  state.meta.samples.forEach((s) => {
    const b = document.createElement("button");
    b.className = "sample";
    b.disabled = !s.available;
    const tag = s.replay ? (s.replay.source === "recorded" ? `Recorded on ${s.replay.hardware || "AMD"}` : "Scripted sample run") : (s.available ? "" : "Needs the AMD endpoint");
    b.innerHTML = `<b>${esc(state.meta.languages[s.language])}</b>${esc(s.title)}<span class="tag">${esc(tag)}</span>`;
    b.onclick = () => pickSample(s.id, b);
    box.appendChild(b);
  });
  renderStages(null);
  $("#run").onclick = start;
  $("#signoff").onclick = signOff;
  $("#only-flagged").onchange = renderReview;
  $("#p-print").onclick = () => window.print();
  try { $("#reviewer").value = localStorage.getItem("hw-reviewer") || ""; } catch (e) { /* storage blocked */ }
  $("#reviewer").onchange = (e) => { try { localStorage.setItem("hw-reviewer", e.target.value); } catch (err) { /* ignore */ } };
}

async function pickSample(id, btn) {
  const s = await api(`/api/samples/${id}`);
  state.sample = s;
  $("#source").value = s.source;
  $("#language").value = s.language;
  $("#pname").value = s.patient_name || "";
  document.querySelectorAll(".sample").forEach((b) => b.classList.toggle("selected", b === btn));
}

async function start() {
  const source = $("#source").value;
  const language = $("#language").value;
  const file = $("#file").files[0];
  $("#run-error").classList.add("hidden");
  $("#run").disabled = true;
  try {
    let r;
    if (file) {
      const fd = new FormData();
      fd.append("file", file); fd.append("language", language); fd.append("patient_name", $("#pname").value);
      r = await api("/api/cases/upload", { method: "POST", body: fd });
    } else {
      const sampleId = state.sample && state.sample.source === source ? state.sample.id : null;
      r = await post("/api/cases", { source, language, patient_name: $("#pname").value, sample_id: sampleId });
    }
    state.caseId = r.id; state.packet = null;
    clearInterval(state.poll);
    state.poll = setInterval(refresh, 600);
    refresh();
  } catch (e) {
    showError(e.message);
    $("#run").disabled = false;
  }
}

function showError(msg) { const el = $("#run-error"); el.textContent = msg; el.classList.remove("hidden"); }

async function refresh() {
  if (!state.caseId) return;
  const c = await api(`/api/cases/${state.caseId}`);
  setCase(c);
  if (["ready", "error"].includes(c.stage)) { clearInterval(state.poll); $("#run").disabled = false; }
}

function setCase(c) {
  state.c = c;
  renderStages(c);
  if (c.stage === "error") showError(c.error);
  if (c.stage === "ready") { renderLedger(); renderReview(); renderImpact(); }
}

// ------------------------------------------------------------------ nurse
function renderStages(c) {
  const order = STAGES.map((s) => s[0]);
  const skip = c && c.language === "en" ? ["translate", "back_translate"] : [];
  const idx = c ? order.indexOf(c.stage) : -1;
  $("#stages").innerHTML = STAGES.filter((s) => !skip.includes(s[0])).map(([k, t, d]) => {
    const i = order.indexOf(k);
    const cls = !c ? "" : c.stage === "ready" || i < idx ? "done" : i === idx ? "now" : "";
    return `<li class="${cls}"><span class="dot"></span><div>${esc(t)}<small>${esc(d)}</small></div></li>`;
  }).join("");
  const sum = $("#run-summary");
  if (c && c.stage === "ready") {
    const m = c.metrics;
    const route = c.route === "interpreter" ? `<div class="error">Routed to a professional interpreter: ${c.language_name in state.meta.languages ? "too many sentences failed checks" : "this language is not supported for automatic translation"}. The English packet and fact ledger are still ready.</div>` : "";
    sum.innerHTML = `${route}<p><b>${m.sentences}</b> sentences, <b>${m.sentences_flagged}</b> need a human, <b>${m.omissions}</b> missing items.</p><button class="primary" id="go-review">Open review</button>`;
    $("#go-review").onclick = () => show("review");
  } else sum.innerHTML = "";
}

function renderLedger() {
  const c = state.c;
  $("#ledger-card").classList.remove("hidden");
  $("#masked").innerHTML = marked(c.source_masked);
  $("#med-issues").innerHTML = c.med_issues.map((m) => `<div class="error">${esc(m.message)} <span class="fine">Line: ${esc(m.line)}</span></div>`).join("");
  $("#ledger").innerHTML = `<tr><th>ID</th><th>Kind</th><th>Instruction</th><th>Risk</th><th>Check</th></tr>` + c.facts.map((f) => `
    <tr><td>${f.id}</td><td>${esc(f.kind.replace("_", " "))}${f.med_action ? `<br><span class="pill action ${f.med_action}">${f.med_action}</span>` : ""}</td>
    <td>${marked(f.detail)}<div class="quote">“${marked(f.source_quote)}”</div></td>
    <td>${f.risk === "high" ? '<span class="pill high">High risk</span>' : ""}</td>
    <td><span class="pill ${f.status}">${f.status === "green" ? "Found in source" : f.status === "amber" ? "Check" : "Not in source"}</span>
    ${f.checks.filter((k) => k.status !== "pass").map((k) => `<div class="fine">${esc(k.message)}</div>`).join("")}</td></tr>`).join("");
}

// ------------------------------------------------------------------ review
function reviewer() {
  const v = $("#reviewer").value.trim();
  if (!v) { $("#reviewer").focus(); throw new Error("Enter the reviewer's name first."); }
  return v;
}

async function act(fn) {
  try { setCase(await fn()); } catch (e) { alert(e.message); }
}

function renderReview() {
  const c = state.c;
  if (!c || c.stage !== "ready") return;
  $("#review-empty").classList.add("hidden");
  $("#review-body").classList.remove("hidden");
  const m = c.metrics;
  const tl = c.language !== "en";
  $("#review-stats").innerHTML = `
    <div><b>${m.sentences}</b>sentences</div>
    <div><b style="color:var(--red)">${m.by_status.red}</b>blocked</div>
    <div><b style="color:var(--amber)">${m.by_status.amber}</b>uncertain</div>
    <div><b style="color:var(--blue)">${m.high_risk}</b>high risk</div>
    <div><b>${m.omissions}</b>missing</div>
    <div><b>${m.sentences - m.sentences_flagged}</b>verified, no review needed</div>`;
  const signed = c.signoff;
  $("#signoff").disabled = !!signed || c.blockers.length > 0;
  $("#blockers").className = "blockers" + (c.blockers.length || signed ? "" : " ok");
  $("#blockers").innerHTML = signed ? `<span class="reviewed">Signed off by ${esc(signed.by)}. The packet is with the patient.</span>`
    : c.blockers.length ? `Still open: ${c.blockers.length} item(s). ${esc(c.blockers.slice(0, 3).join(" "))}${c.blockers.length > 3 ? " …" : ""}` : "Everything that needs a human has been reviewed. Ready to sign off.";

  const facts = Object.fromEntries(c.facts.map((f) => [f.id, f]));
  $("#omissions").innerHTML = c.omissions.map((o) => `
    <div class="card omission" data-fact="${o.fact_id}">
      <h3>Missing from the packet · ${o.fact_id}</h3>
      <p>${marked(o.message)}</p>
      <div class="fine">Source: “${marked(facts[o.fact_id].source_quote)}”</div>
      <div class="editor">
        <label>English<textarea rows="2" class="add-en">${esc(facts[o.fact_id].detail)}</textarea></label>
        ${tl ? `<label>${esc(c.language_name)}<textarea rows="2" class="add-tl"></textarea></label>` : ""}
      </div>
      <div class="actions">
        <button class="small suggest">Suggest wording with the model</button>
        <button class="small primary add">Add to packet</button>
        <button class="small dismiss">Not needed for this patient…</button>
      </div>
    </div>`).join("");
  document.querySelectorAll(".omission").forEach((el) => {
    const fid = el.dataset.fact;
    $(".suggest", el).onclick = async () => {
      try {
        const s = await post(`/api/cases/${c.id}/suggest/${fid}`);
        $(".add-en", el).value = s.text_en;
        if (tl && $(".add-tl", el)) $(".add-tl", el).value = s.text_tl || "";
      } catch (e) { alert(e.message); }
    };
    $(".add", el).onclick = () => act(() => post(`/api/cases/${c.id}/sentences`, { reviewer: reviewer(), fact_id: fid, text_en: $(".add-en", el).value, text_tl: tl ? $(".add-tl", el).value : null }));
    $(".dismiss", el).onclick = () => {
      const reason = prompt("Why does the patient not need this?");
      if (reason) act(() => post(`/api/cases/${c.id}/facts/${fid}/dismiss`, { reviewer: reviewer(), reason }));
    };
  });

  const only = $("#only-flagged").checked;
  const live = c.sentences.filter((s) => !s.removed);
  const shown = SECTION_ORDER.flatMap((sec) => live.filter((s) => s.section === sec))
    .filter((s) => !only || s.needs_review || (s.review && s.review.state));
  $("#sentences").innerHTML = shown.map((s) => sentenceCard(s, facts, tl)).join("") ||
    `<div class="empty">Nothing needs a human. ${live.length} sentences passed every check.</div>`;
  document.querySelectorAll(".sentence").forEach((el) => {
    const sid = el.dataset.id;
    const btn = (cls, fn) => { const b = $(cls, el); if (b) b.onclick = fn; };
    btn(".approve", () => act(() => post(`/api/cases/${c.id}/sentences/${sid}/approve`, { reviewer: reviewer() })));
    btn(".remove", () => { if (confirm("Remove this sentence from the packet?")) act(() => post(`/api/cases/${c.id}/sentences/${sid}/remove`, { reviewer: reviewer() })); });
    btn(".edit", () => $(".editor", el).classList.toggle("hidden"));
    btn(".save", () => act(() => post(`/api/cases/${c.id}/sentences/${sid}/edit`, { reviewer: reviewer(), text_en: $(".ed-en", el).value, text_tl: tl ? $(".ed-tl", el).value : null })));
  });
}

function sentenceCard(s, facts, tl) {
  const failing = s.checks.filter((k) => k.status !== "pass");
  const passing = s.checks.filter((k) => k.status === "pass").length;
  const label = { red: "Blocked", amber: "Uncertain", green: "Verified" }[s.status];
  const reviewed = s.review && s.review.state ? `<span class="reviewed">${s.review.state === "approved" ? "Approved" : "Edited"} by ${esc(s.review.by)}</span>` : "";
  const why = s.risk === "high" && s.status === "green" ? `<li class="warn">High-risk instruction: a person must confirm it even though every check passed.</li>` : "";
  return `<div class="card sentence ${s.status} ${s.review && s.review.state && !s.needs_review ? "done" : ""}" data-id="${s.id}">
    <div class="s-head"><span class="pill ${s.status}">${label}</span>${s.risk === "high" ? '<span class="pill high">High risk</span>' : ""}
      <span>${s.id}</span>${reviewed}<span class="sec">${esc(UI.en[s.section] || s.section)}</span></div>
    <div class="s-text">
      <div><div class="lang">English</div><p>${marked(s.text_en)}</p></div>
      ${tl ? `<div><div class="lang">${esc(state.c.language_name)}</div><p>${marked(s.text_tl)}</p>${s.back_en ? `<div class="back">Back-translation: ${marked(s.back_en)}</div>` : ""}</div>` : ""}
    </div>
    <ul class="checks">${failing.map((k) => `<li class="${k.status}">${esc(k.message)}</li>`).join("")}${why}<li class="pass">${passing} check(s) passed</li></ul>
    <div class="facts-cited">${s.fact_ids.map((id) => facts[id] ? `<span class="chip" title="${esc(facts[id].source_quote)}">${id} · ${esc(facts[id].kind.replace("_", " "))}</span>` : `<span class="chip">${esc(id)} · unknown</span>`).join("")}</div>
    ${state.c.signoff ? "" : `<div class="actions">
      ${s.needs_review ? `<button class="small primary approve" ${s.status === "red" ? "disabled title='Blocked sentences must be edited or removed'" : ""}>Approve</button>` : ""}
      <button class="small edit">Edit</button><button class="small danger remove">Remove</button></div>
    <div class="editor hidden">
      <label>English<textarea rows="2" class="ed-en">${esc(s.text_en)}</textarea></label>
      ${tl ? `<label>${esc(state.c.language_name)}<textarea rows="2" class="ed-tl">${esc(s.text_tl)}</textarea></label>` : ""}
      <div><button class="small primary save">Save and re-check</button></div>
    </div>`}
  </div>`;
}

async function signOff() {
  const c = state.c;
  try {
    setCase(await post(`/api/cases/${c.id}/signoff`, { reviewer: reviewer() }));
    show("patient");
  } catch (e) { alert(e.message); }
}

// ------------------------------------------------------------------ patient
async function loadPacket() {
  const c = state.c;
  if (!c || !c.signoff) return;
  try { state.packet = await api(`/api/cases/${c.id}/packet`); } catch (e) { return; }
  $("#patient-empty").classList.add("hidden");
  $("#patient-body").classList.remove("hidden");
  renderPacket();
}

function renderPacket() {
  const p = state.packet;
  const tl = p.language !== "en" && p.language in UI;
  const ui = UI[tl && state.pLang !== "en" ? p.language : "en"];
  $("#p-title").textContent = ui.title;
  $("#p-signed").textContent = `✓ Checked by ${p.signoff.by}`;
  $("#p-lang").innerHTML = tl ? [["tl", p.language_name], ["both", "Both"], ["en", "English"]]
    .map(([k, l]) => `<button data-k="${k}" class="${state.pLang === k ? "on" : ""}">${esc(l)}</button>`).join("") : "";
  document.querySelectorAll("#p-lang button").forEach((b) => b.onclick = () => { state.pLang = b.dataset.k; renderPacket(); });
  const text = (s) => !tl || state.pLang === "en" ? esc(s.text_en)
    : state.pLang === "both" ? `${esc(s.text_tl)}<span class="en">${esc(s.text_en)}</span>` : esc(s.text_tl);
  $("#p-sections").innerHTML = SECTION_ORDER.filter((k) => p.sections[k]).map((k) => `
    <div class="card p-sec ${k}"><h2><span class="ico">${SECTION_ICON[k]}</span>${esc(ui[k])}<button class="small speak" data-sec="${k}">🔊 ${esc(ui.read)}</button></h2>
    <ul>${p.sections[k].map((s) => `<li class="${s.risk === "high" ? "high" : ""}">${text(s)}</li>`).join("")}</ul></div>`).join("");
  document.querySelectorAll(".speak").forEach((b) => b.onclick = () => speak(b.dataset.sec));
  const qui = UI[p.language in UI ? p.language : "en"];
  $("#q-title").textContent = qui.quiz;
  $("#q-intro").textContent = qui.quizIntro;
  $("#quiz").innerHTML = p.quiz.map((q) => `<div class="q" data-q="${q.id}"><p>${esc(q.question)}</p>
    ${q.options.map((o, i) => `<button class="opt" data-i="${i}">${esc(o.text)}</button>`).join("")}<div class="feedback"></div></div>`).join("");
  document.querySelectorAll(".q").forEach((el) => {
    el.querySelectorAll(".opt").forEach((b) => b.onclick = async () => {
      const r = await post(`/api/cases/${state.c.id}/quiz/${el.dataset.q}`, { choice: +b.dataset.i });
      el.querySelectorAll(".opt").forEach((o) => o.disabled = true);
      b.classList.add(r.correct ? "right" : "wrong");
      $(".feedback", el).textContent = r.correct ? qui.right : qui.wrong;
      refresh();
    });
  });
}

function speak(sec) {
  if (!("speechSynthesis" in window)) return alert("This browser cannot read aloud.");
  const p = state.packet;
  const useTl = p.language !== "en" && state.pLang !== "en";
  const u = new SpeechSynthesisUtterance(p.sections[sec].map((s) => useTl ? s.text_tl : s.text_en).join(" "));
  u.lang = SPEECH[useTl ? p.language : "en"] || "en-US";
  u.rate = 0.9;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

// ------------------------------------------------------------------ impact
function renderImpact() {
  const c = state.c, m = c.metrics;
  $("#impact-empty").classList.add("hidden");
  $("#impact-body").classList.remove("hidden");
  // "Caught" and "verified" describe the model's draft, before the reviewer fixed anything.
  const d = m.at_draft || m;
  const share = d.sentences ? Math.round(100 * (d.sentences - d.sentences_flagged) / d.sentences) : 0;
  const alertsTotal = Object.values(d.issues_caught).reduce((a, b) => a + b, 0);
  const caughtTotal = d.by_status.red + d.by_status.amber + d.omissions + d.med_issues;
  $("#kpis").innerHTML = [
    [`${m.source_grade} → ${m.output_grade ?? "–"}`, "Reading grade (Flesch-Kincaid). Target is 6 or lower."],
    [`${d.sentences - d.sentences_flagged}<small> / ${d.sentences}</small>`, `Draft sentences verified with no human needed (${share}%). The reviewer reads only the rest.`],
    [`${caughtTotal}`, `Problems in the model's draft stopped before the patient saw them (${alertsTotal} check alerts)`],
    [`${Object.values(m.phi_masked).reduce((a, b) => a + b, 0)}`, "Identifiers masked before any model call"],
    [m.seconds_to_signoff ? `${Math.round(m.seconds_to_signoff)}<small> s</small>` : "–", "From paste to signed-off packet"],
  ].map(([v, l]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join("");
  const labels = { numbers: "Number not in source", drug: "Medicine not in source", meaning_polarity: "Stop vs keep taking", translation_numbers: "Number changed in translation", back_numbers: "Back-translation numbers", back_drug: "Medicine lost in translation", translation_polarity: "Meaning flipped in translation", model_check: "Safety model: wording", model_check_translation: "Safety model: translation", citation: "No source behind sentence", placeholder: "Invented contact or name", quote: "Fact not found in source", cross_check: "Medicine list disagreement", translation_placeholder: "Contact lost in translation" };
  const rows = Object.entries(d.issues_caught).map(([k, v]) => [labels[k] || k, v]);
  if (d.omissions) rows.push(["Missing critical instruction", d.omissions]);
  if (d.med_issues) rows.push(["Medicine missing from ledger", d.med_issues]);
  const max = Math.max(1, ...rows.map((r) => r[1]));
  $("#caught").innerHTML = rows.length ? rows.map(([l, v]) => `<div class="bar"><span>${esc(l)}</span><i style="width:${Math.max(8, 160 * v / max)}px"></i><b>${v}</b></div>`).join("") + `<p class="fine">Counted on the model's first draft. ${m.checks_run} checks ran on ${m.facts} facts and ${m.sentences} sentences.</p>` : "<p>No problems found.</p>";
  const u = m.model, llm = state.meta.llm;
  const replay = llm.mode !== "live";
  const meta = (llm.cases || {})[c.sample_id] || {};
  $("#model").innerHTML = `<dl class="kv">
    <dt>Mode</dt><dd>${replay ? (meta.source === "recorded" ? `Replay of a recorded run (${esc(meta.recorded_at || "")})` : "Scripted sample run, no GPU connected") : "Live"}</dd>
    <dt>Model</dt><dd>${esc(replay ? meta.model || "–" : llm.model)}</dd>
    <dt>Hardware</dt><dd>${esc(replay ? meta.hardware || "–" : llm.hardware)}</dd>
    <dt>Model calls</dt><dd>${u.calls}</dd>
    <dt>Model time</dt><dd>${u.seconds ? u.seconds + " s" : "–"}</dd>
    <dt>Tokens</dt><dd>${u.prompt_tokens + u.completion_tokens || "–"}</dd>
    <dt>Throughput</dt><dd>${u.tokens_per_second ? u.tokens_per_second + " tokens/s" : "–"}</dd>
    <dt>GPU cost per packet</dt><dd>${m.gpu_cost_usd != null ? "$" + m.gpu_cost_usd.toFixed(4) + " at $1.99/h" : "–"}</dd>
  </dl><p class="fine">The model runs on a single AMD Instinct MI300X through vLLM and ROCm, inside infrastructure the hospital controls, so patient text never goes to a third-party API.</p>`;
  $("#alerts").innerHTML = c.alerts.length ? c.alerts.map((a) => `<div class="error">${esc(a.message)}</div>`).join("") : '<p class="fine">No alerts yet. Wrong teach-back answers appear here for the nurse.</p>';
  $("#audit").innerHTML = c.audit.slice().reverse().map((a) => `<div><time>${new Date(a.at * 1000).toLocaleTimeString()}</time><b>${esc(a.actor)}</b> ${esc(a.action)} <span class="fine">${esc(a.detail)}</span></div>`).join("");
}

init().catch((e) => showError(e.message));
