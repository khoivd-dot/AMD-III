"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const PH = "(?:PATIENT|CLINICIAN|MRN|DATE_OF_BIRTH|EMAIL|PHONE|ADDRESS)_\\d+";
const marked = (t) => esc(t).replace(new RegExp(`\\[${PH}\\]`, "g"), (m) => `<mark class="ph">${m}</mark>`);
const icon = (id, cls = "") => `<svg class="i ${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;

// Numbers in a sentence, normalised so "1,5" and "1.5" compare equal. Placeholders are skipped.
const NUM = new RegExp(`(\\[${PH}\\])|(\\d+(?:[.,]\\d+)?)`, "g");
const norm = (n) => n.replace(",", ".");
const numsOf = (t) => new Set([...String(t || "").matchAll(NUM)].filter((m) => m[2]).map((m) => norm(m[2])));
// Escape text, mark placeholders, and highlight any number in `bad` so a reviewer sees exactly what changed.
function hl(t, bad) {
  let out = "", last = 0;
  for (const m of String(t || "").matchAll(NUM)) {
    out += esc(t.slice(last, m.index));
    if (m[1]) out += `<mark class="ph">${esc(m[1])}</mark>`;
    else out += bad && bad.has(norm(m[2])) ? `<mark class="diff" title="Differs from the English">${esc(m[2])}</mark>` : esc(m[2]);
    last = m.index + m[0].length;
  }
  return out + esc(String(t || "").slice(last));
}
const minus = (a, b) => new Set([...a].filter((x) => !b.has(x)));

const STAGES = [
  ["masking", "Mask identifiers", "Names, record numbers, dates of birth and phone numbers are replaced before any model sees the text.", "rules"],
  ["facts", "Build the fact ledger", "Every instruction, each with an exact quote from the source.", "model"],
  ["draft", "Write in plain language", "Grade 6 target. Every sentence cites the facts it restates.", "model"],
  ["translate", "Translate", "Drug names, numbers and contact details kept as written.", "model"],
  ["back_translate", "Back-translate", "The translation goes back into English so it can be checked.", "model"],
  ["judge", "Safety model review", "A second pass checks each sentence against its cited facts.", "model"],
  ["checks", "Deterministic checks", "Numbers, drug names, stop vs keep, coverage of every critical fact.", "rules"],
  ["ready", "Ready for a person to review", "Only flagged and high-risk lines go to the reviewer.", "human"],
];
const WHO = { model: "Model", rules: "Rules", human: "Person" };
const SECTION_ORDER = ["why", "medicines", "warning_signs", "appointments", "daily_care"];
const SECTION_ICON = { why: "hospital", medicines: "pill", warning_signs: "alert", appointments: "cal", daily_care: "heart" };
const MED_ORDER = ["stop", "hold", "changed", "new", "continue", "other"];
const CHECK_LABEL = { quote: "Fact found in source", numbers: "Numbers match the source", drug: "Medicine names match", meaning_polarity: "Stop vs keep taking", translation: "Translation present", translation_numbers: "Numbers kept in translation", back_numbers: "Back-translation numbers", back_drug: "Medicines kept in translation", back_translation: "Back-translation", translation_polarity: "Meaning kept in translation", model_check: "Safety model: wording", model_check_translation: "Safety model: translation", citation: "Cites a source fact", placeholder: "No invented names or contacts", cross_check: "Medicine list cross-check", translation_placeholder: "Contacts kept in translation", action: "Clear medicine action" };

const UI = {
  en: { why: "Why you were in hospital", medicines: "Your medicines", warning_signs: "Get help if…", appointments: "Your appointments", daily_care: "Taking care of yourself at home", title: "Your instructions for going home", read: "Read aloud", quiz: "Check your understanding", quizIntro: "A few quick questions. Wrong answers are fine: your nurse will go over them with you.", right: "Correct.", wrong: "Not quite. Your nurse has been asked to go over this with you.", checked: "Checked by", of: "Question {i} of {n}", next: "Next question", doneAll: "All done. You answered every question correctly.", doneSome: "All done. Your nurse will go over {n} item(s) with you before you leave.", emergency: "Emergency: act now", urgent: "Call your care team", med: { stop: "Stop taking", hold: "Pause for now", changed: "Changed", new: "New", continue: "Keep taking", other: "Other" } },
  es: { why: "Por qué estuvo en el hospital", medicines: "Sus medicamentos", warning_signs: "Pida ayuda si…", appointments: "Sus citas", daily_care: "Cómo cuidarse en casa", title: "Sus instrucciones para volver a casa", read: "Leer en voz alta", quiz: "Compruebe lo que entendió", quizIntro: "Unas preguntas rápidas. Si se equivoca, no pasa nada: su enfermera lo repasará con usted.", right: "Correcto.", wrong: "No exactamente. Su enfermera lo repasará con usted.", checked: "Revisado por", of: "Pregunta {i} de {n}", next: "Siguiente pregunta", doneAll: "Terminado. Respondió bien todas las preguntas.", doneSome: "Terminado. Su enfermera repasará {n} punto(s) con usted antes de que se vaya.", emergency: "Emergencia: actúe ya", urgent: "Llame a su equipo médico", med: { stop: "Deje de tomar", hold: "Pause por ahora", changed: "Cambió", new: "Nuevo", continue: "Siga tomando", other: "Otros" } },
  it: { why: "Perché è stato in ospedale", medicines: "I suoi farmaci", warning_signs: "Chieda aiuto se…", appointments: "I suoi appuntamenti", daily_care: "Come prendersi cura di sé a casa", title: "Le sue istruzioni per il ritorno a casa", read: "Leggi ad alta voce", quiz: "Verifichi cosa ha capito", quizIntro: "Alcune domande veloci. Se sbaglia va bene: l'infermiere le rivedrà con lei.", right: "Corretto.", wrong: "Non proprio. L'infermiere lo rivedrà con lei.", checked: "Controllato da", of: "Domanda {i} di {n}", next: "Domanda successiva", doneAll: "Finito. Ha risposto bene a tutte le domande.", doneSome: "Finito. L'infermiere rivedrà {n} punto/i con lei prima che vada a casa.", emergency: "Emergenza: agisca subito", urgent: "Chiami il suo team di cura", med: { stop: "Smetta di prendere", hold: "Sospenda per ora", changed: "Cambiato", new: "Nuovo", continue: "Continui a prendere", other: "Altro" } },
  vi: { why: "Lý do bạn nằm viện", medicines: "Thuốc của bạn", warning_signs: "Hãy tìm trợ giúp nếu…", appointments: "Lịch hẹn của bạn", daily_care: "Tự chăm sóc tại nhà", title: "Hướng dẫn khi về nhà", read: "Đọc to", quiz: "Kiểm tra mức hiểu", quizIntro: "Vài câu hỏi ngắn. Trả lời sai cũng không sao: y tá sẽ giải thích lại cho bạn.", right: "Đúng.", wrong: "Chưa đúng. Y tá sẽ giải thích lại cho bạn.", checked: "Đã kiểm tra bởi", of: "Câu {i} trên {n}", next: "Câu tiếp theo", doneAll: "Xong. Bạn đã trả lời đúng tất cả.", doneSome: "Xong. Y tá sẽ giải thích lại {n} mục cho bạn trước khi về.", emergency: "Cấp cứu: hành động ngay", urgent: "Gọi cho nhóm chăm sóc của bạn", med: { stop: "Ngừng dùng", hold: "Tạm ngừng", changed: "Thay đổi", new: "Mới", continue: "Tiếp tục dùng", other: "Khác" } },
  zh: { why: "您住院的原因", medicines: "您的药物", warning_signs: "出现以下情况请求助…", appointments: "您的预约", daily_care: "在家如何照顾自己", title: "您的出院指导", read: "朗读", quiz: "确认您是否理解", quizIntro: "几个简单问题。答错没关系，护士会再和您讲解。", right: "正确。", wrong: "不太对。护士会再和您讲解。", checked: "审核人", of: "第 {i} 题，共 {n} 题", next: "下一题", doneAll: "完成。您全部答对了。", doneSome: "完成。出院前护士会和您再讲解 {n} 项内容。", emergency: "紧急情况：立即行动", urgent: "联系您的医护团队", med: { stop: "停止服用", hold: "暂停服用", changed: "已更改", new: "新药", continue: "继续服用", other: "其他" } },
  fr: { why: "Pourquoi vous étiez à l'hôpital", medicines: "Vos médicaments", warning_signs: "Demandez de l'aide si…", appointments: "Vos rendez-vous", daily_care: "Prendre soin de vous à la maison", title: "Vos consignes pour le retour à la maison", read: "Lire à voix haute", quiz: "Vérifiez ce que vous avez compris", quizIntro: "Quelques questions rapides. Une erreur n'est pas grave : votre infirmière reverra ce point avec vous.", right: "Exact.", wrong: "Pas tout à fait. Votre infirmière reverra ce point avec vous.", checked: "Vérifié par", of: "Question {i} sur {n}", next: "Question suivante", doneAll: "Terminé. Vous avez tout bien répondu.", doneSome: "Terminé. Votre infirmière reverra {n} point(s) avec vous avant votre départ.", emergency: "Urgence : agissez tout de suite", urgent: "Appelez votre équipe soignante", med: { stop: "Arrêtez", hold: "En pause", changed: "Modifié", new: "Nouveau", continue: "Continuez", other: "Autre" } },
};
const SPEECH = { en: "en-US", es: "es-ES", it: "it-IT", vi: "vi-VN", zh: "zh-CN", fr: "fr-FR" };

const state = { meta: null, caseId: null, c: null, sample: null, packet: null, pLang: "tl", poll: null, started: 0, focus: 0, quiz: { i: 0, answers: {} } };

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

let toastTimer;
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast on${err ? " err" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("on"), 3200);
}

function show(view) {
  $$("#tabs button").forEach((b) => { const on = b.dataset.view === view; b.classList.toggle("active", on); b.setAttribute("aria-selected", on); });
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (view === "patient") loadPacket();
  window.scrollTo({ top: 0 });
}

// The stepper shows where the case is: later steps unlock as the case moves forward.
function updateTabs() {
  const c = state.c, ready = c && c.stage === "ready", signed = c && c.signoff;
  const tab = (v) => $(`#tabs button[data-view="${v}"]`);
  tab("nurse").classList.toggle("done", !!ready);
  tab("review").classList.toggle("done", !!signed);
  tab("patient").classList.toggle("done", !!(signed && c.quiz && c.quiz.length && c.quiz.every((q) => q.answer != null)));
  $$("#tabs button").forEach((b, i) => { $(".n", b).innerHTML = b.classList.contains("done") ? icon("check") : String(i + 1); });
  tab("review").title = ready ? "" : "Create a packet first";
  tab("patient").title = signed ? "" : "Unlocks after sign-off";
}

// ------------------------------------------------------------------ setup
async function init() {
  $$("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  state.meta = await api("/api/meta");
  const llm = state.meta.llm;
  const mode = $("#mode");
  if (llm.mode === "live") {
    mode.textContent = `Live · ${llm.model.split("/").pop()} on ${llm.hardware}`;
  } else {
    mode.textContent = "Sample runs · no GPU connected";
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
    b.setAttribute("role", "listitem");
    b.disabled = !s.available;
    const tag = s.replay ? (s.replay.source === "recorded" ? `Recorded on ${s.replay.hardware || "AMD"}` : "Scripted sample run") : (s.available ? "" : "Needs the AMD endpoint");
    b.innerHTML = `<b>${esc(state.meta.languages[s.language])}</b>${esc(s.title.replace(/, [A-Z][a-z]+$/, ""))}<span class="tag">${esc(tag)}</span>`;
    b.onclick = () => pickSample(s.id, b);
    box.appendChild(b);
  });
  renderStages(null);
  updateTabs();
  $("#run").onclick = start;
  $("#signoff").onclick = signOff;
  $("#only-flagged").onchange = renderReview;
  $("#p-print").onclick = () => window.print();
  $("#p-size").onclick = (e) => { const on = $("#patient-body").classList.toggle("big"); e.currentTarget.setAttribute("aria-pressed", on); };
  $("#file").onchange = (e) => { $("#file-name").textContent = e.target.files[0] ? e.target.files[0].name : ""; };
  try { $("#reviewer").value = localStorage.getItem("hw-reviewer") || ""; } catch (e) { /* storage blocked */ }
  $("#reviewer").onchange = (e) => { try { localStorage.setItem("hw-reviewer", e.target.value); } catch (err) { /* ignore */ } };
  document.addEventListener("keydown", reviewKeys);
}

async function pickSample(id, btn) {
  const s = await api(`/api/samples/${id}`);
  state.sample = s;
  $("#source").value = s.source;
  $("#language").value = s.language;
  $("#pname").value = s.patient_name || "";
  $$(".sample").forEach((b) => b.classList.toggle("selected", b === btn));
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
    state.caseId = r.id; state.packet = null; state.started = Date.now(); state.quiz = { i: 0, answers: {} };
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
  updateTabs();
  if (c.stage === "error") showError(c.error);
  if (c.stage === "ready") { renderLedger(); renderReview(); renderImpact(); }
}

// ------------------------------------------------------------------ prepare
function renderStages(c) {
  const order = STAGES.map((s) => s[0]);
  const skip = c && c.language === "en" ? ["translate", "back_translate"] : [];
  const idx = c ? order.indexOf(c.stage) : -1;
  $("#stages").innerHTML = STAGES.filter((s) => !skip.includes(s[0])).map(([k, t, d, who]) => {
    const i = order.indexOf(k);
    const cls = !c ? "" : c.stage === "ready" || i < idx ? "done" : i === idx ? "now" : "";
    return `<li class="${cls}"><span class="dot">${icon("check")}</span><div>${esc(t)}<span class="who ${who}">${WHO[who]}</span><small>${esc(d)}</small></div></li>`;
  }).join("");
  $("#elapsed").textContent = c && state.started ? `${((Date.now() - state.started) / 1000).toFixed(1)} s` : "";
  const sum = $("#run-summary");
  if (c && c.stage === "ready") {
    const m = c.metrics;
    const red = m.by_status.red, amber = m.by_status.amber, high = Math.max(0, m.sentences_flagged - red - amber), auto = m.sentences - m.sentences_flagged;
    const pct = (n) => `${(100 * n / Math.max(1, m.sentences)).toFixed(1)}%`;
    const route = c.route === "interpreter" ? `<div class="error">Routed to a professional interpreter: ${c.language_name in state.meta.languages ? "too many sentences failed checks" : "this language is not supported for automatic translation"}. The English packet and fact ledger are still ready.</div>` : "";
    sum.innerHTML = `${route}<div class="triage">
      <h3>${m.sentences_flagged + m.omissions} items need a person, ${auto} sentences verified</h3>
      <div class="stack" role="img" aria-label="${auto} verified, ${high} high risk, ${amber} uncertain, ${red} blocked">
        <i class="g" style="width:${pct(auto)}"></i><i class="h" style="width:${pct(high)}"></i><i class="a" style="width:${pct(amber)}"></i><i class="r" style="width:${pct(red)}"></i></div>
      <div class="legend"><span style="--c:var(--green)">${auto} verified</span><span style="--c:var(--violet)">${high} high risk</span><span style="--c:var(--amber)">${amber} uncertain</span><span style="--c:var(--red)">${red} blocked</span>${m.omissions ? `<span style="--c:var(--red-deep)">${m.omissions} missing</span>` : ""}</div>
      <button class="primary lg block" id="go-review">Open review ${icon("arrow")}</button></div>`;
    $("#go-review").onclick = () => show("review");
  } else sum.innerHTML = "";
}

function renderLedger() {
  const c = state.c;
  $("#ledger-card").classList.remove("hidden");
  $("#masked").innerHTML = marked(c.source_masked);
  $("#med-issues").innerHTML = c.med_issues.map((m) => `<div class="error">${esc(m.message)} <span class="fine">Line: ${esc(m.line)}</span></div>`).join("");
  $("#ledger").innerHTML = `<tr><th>ID</th><th>Kind</th><th>Instruction</th><th>Risk</th><th>Check</th></tr>` + c.facts.map((f) => `
    <tr><td class="fine">${f.id}</td><td>${esc(f.kind.replace("_", " "))}${f.med_action ? `<br><span class="pill action ${f.med_action}">${f.med_action}</span>` : ""}</td>
    <td>${marked(f.detail)}<div class="quote">“${marked(f.source_quote)}”</div></td>
    <td>${f.risk === "high" ? '<span class="pill high">High risk</span>' : ""}</td>
    <td><span class="pill ${f.status}">${f.status === "green" ? icon("check") + "In source" : f.status === "amber" ? "Check" : "Not in source"}</span>
    ${f.checks.filter((k) => k.status !== "pass").map((k) => `<div class="fine">${esc(k.message)}</div>`).join("")}</td></tr>`).join("");
}

// ------------------------------------------------------------------ review
function reviewer() {
  const v = $("#reviewer").value.trim();
  if (!v) { $("#reviewer").focus(); throw new Error("Enter the reviewer's name first."); }
  return v;
}

async function act(fn, msg) {
  try { setCase(await fn()); if (msg) toast(msg); } catch (e) { toast(e.message, true); }
}

function queueItems(c) {
  const live = c.sentences.filter((s) => !s.removed);
  const items = c.omissions.map((o) => ({ id: o.fact_id, anchor: `om-${o.fact_id}`, cls: "red", done: false, label: `Missing: ${c.facts.find((f) => f.id === o.fact_id)?.detail || o.message}` }));
  SECTION_ORDER.flatMap((sec) => live.filter((s) => s.section === sec)).forEach((s) => {
    const reviewed = s.review && s.review.state;
    if (!s.needs_review && !reviewed) return;
    items.push({ id: s.id, anchor: `s-${s.id}`, cls: !s.needs_review ? "done" : s.status === "green" ? "high" : s.status, done: !s.needs_review, label: s.text_en });
  });
  return items;
}

function renderReview() {
  const c = state.c;
  if (!c || c.stage !== "ready") return;
  $("#review-empty").classList.add("hidden");
  $("#review-body").classList.remove("hidden");
  const m = c.metrics;
  const tl = c.language !== "en";
  const items = queueItems(c);
  const done = items.filter((i) => i.done).length;
  const open = c.blockers.length;
  const total = done + open;
  $("#q-bar").style.width = `${total ? 100 * done / total : 100}%`;
  $("#q-count").textContent = `${done} of ${total} resolved`;
  $("#review-stats").innerHTML = `
    <div class="red"><b>${m.by_status.red}</b>blocked</div>
    <div class="amber"><b>${m.by_status.amber}</b>uncertain</div>
    <div class="high"><b>${m.high_risk}</b>high risk</div>
    <div class="red"><b>${m.omissions}</b>missing</div>
    <div class="green"><b>${m.sentences - m.sentences_flagged}</b>auto-verified</div>
    <div><b>${m.sentences}</b>sentences</div>`;
  const qIcon = { red: "x", amber: "warn", high: "shield", done: "check" };
  $("#queue").innerHTML = items.map((i) => `<li class="${i.cls}"><a href="#${i.anchor}" data-anchor="${i.anchor}"><span class="ic">${icon(qIcon[i.cls] || "warn")}</span><span class="lbl">${esc(i.label)}</span><span class="id">${esc(i.id)}</span></a></li>`).join("");
  $$("#queue a").forEach((a) => a.onclick = (e) => { e.preventDefault(); focusCard(document.getElementById(a.dataset.anchor)); });

  const signed = c.signoff;
  $("#signoff").disabled = !!signed || open > 0;
  $("#blockers").className = "blockers" + (open || signed ? "" : " ok");
  $("#blockers").innerHTML = signed ? `<span class="reviewed">${icon("check")} Signed off by ${esc(signed.by)}. The packet is with the patient.</span>`
    : open ? `${open} item${open > 1 ? "s" : ""} still need${open > 1 ? "" : "s"} a decision before sign-off.` : "Everything that needs a person has been reviewed. Ready to sign off.";

  const facts = Object.fromEntries(c.facts.map((f) => [f.id, f]));
  $("#omissions").innerHTML = c.omissions.map((o) => `
    <div class="card omission" id="om-${o.fact_id}" data-fact="${o.fact_id}" tabindex="-1">
      <div class="tag">${icon("x")} Missing from the packet · ${o.fact_id}</div>
      <p>${marked(o.message)}</p>
      <div class="ev">${icon("quote")}<div><b>${o.fact_id}</b>“${marked(facts[o.fact_id].source_quote)}”</div></div>
      <div class="editor">
        <label>English<textarea rows="2" class="add-en">${esc(facts[o.fact_id].detail)}</textarea></label>
        ${tl ? `<label>${esc(c.language_name)}<textarea rows="2" class="add-tl" placeholder="Use “Suggest wording” or type the translation"></textarea></label>` : ""}
      </div>
      <div class="actions">
        <button class="small primary add">${icon("check")} Add to packet</button>
        <button class="small suggest">Suggest wording with the model</button>
        <span class="spacer"></span>
        <button class="small ghost dismiss">Not needed for this patient</button>
      </div>
      <div class="dismiss-box hidden"><input class="dismiss-reason" placeholder="Why does the patient not need this? (goes in the audit trail)"><button class="small confirm-dismiss">Dismiss</button></div>
    </div>`).join("");
  $$(".omission").forEach((el) => {
    const fid = el.dataset.fact;
    $(".suggest", el).onclick = async (e) => {
      const b = e.currentTarget; b.disabled = true; b.textContent = "Asking the model…";
      try {
        const s = await post(`/api/cases/${c.id}/suggest/${fid}`);
        $(".add-en", el).value = s.text_en;
        if (tl && $(".add-tl", el)) $(".add-tl", el).value = s.text_tl || "";
        toast("Suggested wording filled in. It is re-checked when you add it.");
      } catch (err) { toast(err.message, true); }
      b.disabled = false; b.textContent = "Suggest wording with the model";
    };
    $(".add", el).onclick = () => {
      if (tl && !$(".add-tl", el).value.trim()) { $(".add-tl", el).focus(); return toast(`Add the ${c.language_name} wording first, or use “Suggest wording”.`, true); }
      act(() => post(`/api/cases/${c.id}/sentences`, { reviewer: reviewer(), fact_id: fid, text_en: $(".add-en", el).value, text_tl: tl ? $(".add-tl", el).value : null }), `Added ${fid} to the packet`);
    };
    $(".dismiss", el).onclick = () => { $(".dismiss-box", el).classList.toggle("hidden"); $(".dismiss-reason", el).focus(); };
    $(".confirm-dismiss", el).onclick = () => {
      const reason = $(".dismiss-reason", el).value.trim();
      if (!reason) return toast("Say why the patient does not need this.", true);
      act(() => post(`/api/cases/${c.id}/facts/${fid}/dismiss`, { reviewer: reviewer(), reason }), `Dismissed ${fid}`);
    };
  });

  const only = $("#only-flagged").checked;
  const live = c.sentences.filter((s) => !s.removed);
  const shown = SECTION_ORDER.flatMap((sec) => live.filter((s) => s.section === sec))
    .filter((s) => !only || s.needs_review || (s.review && s.review.state));
  $("#sentences").innerHTML = shown.map((s) => sentenceCard(s, facts, tl)).join("") ||
    `<div class="card empty-ok">${icon("check")}<p>Nothing needs a person. ${live.length} sentences passed every check.</p></div>`;
  $$(".sentence").forEach((el) => {
    const sid = el.dataset.id;
    const btn = (cls, fn) => { const b = $(cls, el); if (b) b.onclick = fn; };
    btn(".approve", () => act(() => post(`/api/cases/${c.id}/sentences/${sid}/approve`, { reviewer: reviewer() }), `${sid} approved`));
    btn(".remove", () => { if (confirm("Remove this sentence from the packet?")) act(() => post(`/api/cases/${c.id}/sentences/${sid}/remove`, { reviewer: reviewer() }), `${sid} removed`); });
    btn(".edit", () => { const ed = $(".editor", el); ed.classList.toggle("hidden"); if (!ed.classList.contains("hidden")) $("textarea", ed).focus(); });
    btn(".save", () => act(() => post(`/api/cases/${c.id}/sentences/${sid}/edit`, { reviewer: reviewer(), text_en: $(".ed-en", el).value, text_tl: tl ? $(".ed-tl", el).value : null }), `${sid} saved and re-checked`));
  });
}

function sentenceCard(s, facts, tl) {
  const failing = s.checks.filter((k) => k.status !== "pass");
  const passing = s.checks.filter((k) => k.status === "pass");
  const label = { red: "Blocked", amber: "Uncertain", green: "Verified" }[s.status];
  const sIcon = { red: "x", amber: "warn", green: "check" }[s.status];
  const reviewed = s.review && s.review.state ? `<span class="reviewed">${icon("check")}${s.review.state === "approved" ? "Approved" : "Edited"} by ${esc(s.review.by)}</span>` : "";
  const highOnly = s.risk === "high" && s.status === "green";
  // Point at the exact numbers that moved, rather than asking the reviewer to spot them.
  const failed = new Set(failing.filter((k) => k.status === "fail").map((k) => k.name));
  const en = numsOf(s.text_en), tlN = numsOf(s.text_tl), back = numsOf(s.back_en);
  const badTl = failed.has("translation_numbers") ? minus(tlN, en) : null;
  const badBack = failed.has("back_numbers") ? minus(back, en) : null;
  const badEn = failed.has("translation_numbers") ? minus(en, tlN) : null;
  const why = failing.length ? `<div class="reason ${s.status}">${icon(sIcon)}<div><b>${s.status === "red" ? "Blocked: edit or remove" : "Why this needs a look"}</b><ul>${failing.map((k) => `<li>${esc(k.message)}</li>`).join("")}</ul></div></div>`
    : highOnly ? `<div class="reason high">${icon("shield")}<div><b>High-risk instruction</b>Every check passed, but a person must confirm medicine changes and warning signs.</div></div>` : "";
  const evidence = s.fact_ids.map((id) => facts[id]
    ? `<div class="ev">${icon("quote")}<div><b>${id}</b>“${marked(facts[id].source_quote)}”</div></div>`
    : `<div class="ev">${icon("warn")}<div><b>${esc(id)}</b>Cites a fact that does not exist.</div></div>`).join("");
  return `<div class="card sentence ${s.status} ${s.review && s.review.state && !s.needs_review ? "done" : ""}" id="s-${s.id}" data-id="${s.id}" tabindex="-1">
    <div class="s-head"><span class="pill ${s.status}">${icon(sIcon)}${label}</span>${s.risk === "high" ? `<span class="pill high">${icon("shield")}High risk</span>` : ""}
      <span class="id">${s.id}</span>${reviewed}<span class="sec">${esc(UI.en[s.section] || s.section)}</span></div>
    ${why}
    <div class="s-text">
      <div><div class="lang">English</div><p>${hl(s.text_en, badEn)}</p></div>
      ${tl ? `<div><div class="lang">${esc(state.c.language_name)}</div><p>${hl(s.text_tl, badTl)}</p>${s.back_en ? `<div class="back">Back-translation: ${hl(s.back_en, badBack)}</div>` : ""}</div>` : ""}
    </div>
    <div class="evidence">${evidence}</div>
    ${passing.length ? `<details class="passed"><summary>${icon("check")}${passing.length} check${passing.length > 1 ? "s" : ""} passed</summary><ul>${passing.map((k) => `<li>${esc(CHECK_LABEL[k.name] || k.name)}</li>`).join("")}</ul></details>` : ""}
    ${state.c.signoff ? "" : `<div class="actions">
      ${s.needs_review ? `<button class="small primary approve" ${s.status === "red" ? "disabled title='Blocked sentences must be edited or removed'" : ""}>${icon("check")} Approve</button>` : ""}
      <button class="small edit">Edit</button><span class="spacer"></span><button class="small ghost danger remove">Remove</button></div>
    <div class="editor hidden">
      <label>English<textarea rows="2" class="ed-en">${esc(s.text_en)}</textarea></label>
      ${tl ? `<label>${esc(state.c.language_name)}<textarea rows="2" class="ed-tl">${esc(s.text_tl)}</textarea></label>` : ""}
      <div><button class="small primary save">Save and re-check</button></div>
    </div>`}
  </div>`;
}

function focusCard(el) {
  if (!el) return;
  $$(".sentence.focus, .omission.focus").forEach((x) => x.classList.remove("focus"));
  el.classList.add("focus");
  el.focus({ preventScroll: true });
  el.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  $$("#queue a").forEach((a) => a.classList.toggle("cur", a.dataset.anchor === el.id));
}

// J/K to move between cards, A to approve, E to edit: the reviewer never has to reach for the mouse.
function reviewKeys(e) {
  if (!$("#view-review").classList.contains("active") || e.metaKey || e.ctrlKey || e.altKey) return;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
  const cards = $$("#review-body .omission, #review-body .sentence");
  if (!cards.length) return;
  let i = cards.findIndex((x) => x.classList.contains("focus"));
  const k = e.key.toLowerCase();
  if (k === "j" || k === "k") {
    i = k === "j" ? Math.min(cards.length - 1, i + 1) : Math.max(0, i - 1);
    focusCard(cards[i]); e.preventDefault();
  } else if (k === "a" && i >= 0) {
    const b = $(".approve:not([disabled]), .add", cards[i]); if (b) { b.click(); e.preventDefault(); }
  } else if (k === "e" && i >= 0) {
    const b = $(".edit", cards[i]); if (b) { b.click(); e.preventDefault(); }
  }
}

async function signOff() {
  const c = state.c;
  try {
    setCase(await post(`/api/cases/${c.id}/signoff`, { reviewer: reviewer() }));
    toast(`Signed off. The packet is released to the patient.`);
    show("patient");
  } catch (e) { toast(e.message, true); }
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
  const lang = tl && state.pLang !== "en" ? p.language : "en";
  const ui = UI[lang];
  $("#patient-body").dataset.lang = lang;
  $("#patient-body").lang = lang;
  $("#p-title").textContent = ui.title;
  const when = new Date(p.signoff.at * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  $("#p-signed").innerHTML = `${icon("shield")} ${esc(ui.checked)} ${esc(p.signoff.by)} · ${esc(when)}`;
  $("#p-lang").innerHTML = tl ? [["tl", p.language_name], ["both", "Both"], ["en", "English"]]
    .map(([k, l]) => `<button data-k="${k}" class="${state.pLang === k ? "on" : ""}" aria-pressed="${state.pLang === k}">${esc(l)}</button>`).join("") : "";
  $$("#p-lang button").forEach((b) => b.onclick = () => { state.pLang = b.dataset.k; renderPacket(); });
  const text = (s) => !tl || state.pLang === "en" ? esc(s.text_en)
    : state.pLang === "both" ? `${esc(s.text_tl)}<span class="en" lang="en">${esc(s.text_en)}</span>` : esc(s.text_tl);
  const li = (s) => `<li class="${s.risk === "high" ? "high" : ""}">${text(s)}</li>`;
  const body = (k, list) => {
    if (k === "medicines") {
      // Group by what changed, so "stop" and "new" can't hide in one long list.
      const groups = {};
      list.forEach((s) => (groups[MED_ORDER.includes(s.med_action) ? s.med_action : "other"] ||= []).push(s));
      return MED_ORDER.filter((a) => groups[a]).map((a) => `<div class="med-group ${a}"><h3><span class="med-badge ${a}">${esc(ui.med[a])}</span></h3><ul>${groups[a].map(li).join("")}</ul></div>`).join("");
    }
    if (k === "warning_signs") {
      const em = list.filter((s) => /\b(911|999|112|emergency)\b/i.test(s.text_en)), urg = list.filter((s) => !em.includes(s));
      return (em.length ? `<div class="care emergency"><h3>${icon("alert")}${esc(ui.emergency)}</h3><ul>${em.map(li).join("")}</ul></div>` : "")
        + (urg.length ? `<div class="care urgent"><h3>${icon("phone")}${esc(ui.urgent)}</h3><ul>${urg.map(li).join("")}</ul></div>` : "");
    }
    return `<ul>${list.map(li).join("")}</ul>`;
  };
  $("#p-sections").innerHTML = SECTION_ORDER.filter((k) => p.sections[k]).map((k) => `
    <section class="card p-sec ${k}"><h2><span class="ico">${icon(SECTION_ICON[k])}</span>${esc(ui[k])}<button class="small speak" data-sec="${k}" aria-label="${esc(ui.read)}">${icon("speaker")}<span>${esc(ui.read)}</span></button></h2>
    ${body(k, p.sections[k])}</section>`).join("");
  $$(".speak").forEach((b) => b.onclick = () => speak(b.dataset.sec));
  renderQuiz();
}

// One question at a time, big tap targets, progress you can see.
function renderQuiz() {
  const p = state.packet, qz = state.quiz;
  const qui = UI[p.language in UI ? p.language : "en"];
  const n = p.quiz.length;
  $("#q-title").textContent = qui.quiz;
  $("#q-intro").textContent = qui.quizIntro;
  const dots = `<div class="dots">${p.quiz.map((q, i) => `<i class="${q.id in qz.answers ? (qz.answers[q.id] ? "right" : "wrong") : i === qz.i ? "cur" : ""}"></i>`).join("")}</div>`;
  if (qz.i >= n) {
    const missed = Object.values(qz.answers).filter((v) => !v).length;
    $("#q-step").textContent = "";
    $("#quiz").innerHTML = `${dots}<div class="done-msg">${icon(missed ? "heart" : "check")}<p><b>${esc(missed ? qui.doneSome.replace("{n}", missed) : qui.doneAll)}</b></p></div>`;
    return;
  }
  const q = p.quiz[qz.i];
  $("#q-step").textContent = qui.of.replace("{i}", qz.i + 1).replace("{n}", n);
  $("#quiz").innerHTML = `${dots}<div class="q" data-q="${q.id}"><p>${esc(q.question)}</p>
    ${q.options.map((o, i) => `<button class="opt" data-i="${i}"><span class="k">${"ABCD"[i]}</span>${esc(o.text)}</button>`).join("")}
    <div class="feedback" aria-live="polite"></div></div>`;
  const el = $(".q");
  $$(".opt", el).forEach((b) => b.onclick = async () => {
    $$(".opt", el).forEach((o) => o.disabled = true);
    let r;
    try { r = await post(`/api/cases/${state.c.id}/quiz/${q.id}`, { choice: +b.dataset.i }); } catch (e) { toast(e.message, true); $$(".opt", el).forEach((o) => o.disabled = false); return; }
    qz.answers[q.id] = r.correct;
    b.classList.add(r.correct ? "right" : "wrong");
    const fb = $(".feedback", el);
    fb.className = `feedback ${r.correct ? "right" : "wrong"}`;
    fb.innerHTML = `${icon(r.correct ? "check" : "heart")}${esc(r.correct ? qui.right : qui.wrong)}`;
    const next = document.createElement("button");
    next.className = "primary q-next";
    next.innerHTML = `${esc(qz.i + 1 < n ? qui.next : "OK")} ${icon("arrow")}`;
    next.onclick = () => { qz.i += 1; renderQuiz(); };
    el.appendChild(next);
    next.focus();
    refresh();
  });
}

function speak(sec) {
  if (!("speechSynthesis" in window)) return toast("This browser cannot read aloud.", true);
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
    [`${m.source_grade} → ${m.output_grade ?? "–"}`, "Reading grade, source to packet. Target is 6 or lower."],
    [`${d.sentences - d.sentences_flagged}<small> / ${d.sentences}</small>`, `Draft sentences verified with no person needed (${share}%). The reviewer reads only the rest.`],
    [`${caughtTotal}`, `Problems in the model's draft stopped before the patient saw them (${alertsTotal} check alerts)`],
    [`${Object.values(m.phi_masked).reduce((a, b) => a + b, 0)}`, "Identifiers masked before any model call"],
    [m.seconds_to_signoff ? `${Math.round(m.seconds_to_signoff)}<small> s</small>` : "–", "From paste to signed-off packet"],
  ].map(([v, l]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join("");
  const scale = 14, pos = (g) => `${Math.min(100, 100 * Math.max(0, g) / scale)}%`;
  const gaugeRow = (label, g, color) => `<div><div class="gl"><span>${label}</span><span>Grade ${g ?? "–"}</span></div>
    <div class="track"><div class="fill" style="width:${pos(g || 0)};background:${color}"></div><div class="target" style="left:${pos(6)}"><span>Target 6</span></div></div></div>`;
  $("#grade").innerHTML = `<div class="gauge">${gaugeRow("Clinician's text", m.source_grade, "var(--amber)")}${gaugeRow("Patient packet (English)", m.output_grade, "var(--green)")}</div>
    <p class="fine">${m.source_words} words in, ${m.output_words} words out. The AMA recommends grade 6 for patient materials.</p>`;
  const labels = { numbers: "Number not in source", drug: "Medicine not in source", meaning_polarity: "Stop vs keep taking", translation_numbers: "Number changed in translation", back_numbers: "Back-translation numbers", back_drug: "Medicine lost in translation", translation_polarity: "Meaning flipped in translation", model_check: "Safety model: wording", model_check_translation: "Safety model: translation", citation: "No source behind sentence", placeholder: "Invented contact or name", quote: "Fact not found in source", cross_check: "Medicine list disagreement", translation_placeholder: "Contact lost in translation" };
  const rows = Object.entries(d.issues_caught).map(([k, v]) => [labels[k] || k, v]);
  if (d.omissions) rows.push(["Missing critical instruction", d.omissions]);
  if (d.med_issues) rows.push(["Medicine missing from ledger", d.med_issues]);
  rows.sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map((r) => r[1]));
  $("#caught").innerHTML = rows.length ? rows.map(([l, v]) => `<div class="bar"><span>${esc(l)}</span><div class="tr"><i style="width:${100 * v / max}%"></i></div><b>${v}</b></div>`).join("") + `<p class="fine">Counted on the model's first draft. ${m.checks_run} checks ran on ${m.facts} facts and ${m.sentences} sentences.</p>` : "<p>No problems found.</p>";
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
  $("#alerts").innerHTML = c.alerts.length ? c.alerts.map((a) => `<div class="alert-item">${icon("warn")}<span>${esc(a.message)}</span></div>`).join("") : '<p class="fine">No alerts yet. Wrong teach-back answers appear here so the nurse can re-explain before the patient leaves.</p>';
  $("#audit").innerHTML = c.audit.slice().reverse().map((a) => `<div><time>${new Date(a.at * 1000).toLocaleTimeString()}</time><span><b>${esc(a.actor)}</b> ${esc(a.action)} <span class="fine">${esc(a.detail)}</span></span></div>`).join("");
}

init().catch((e) => showError(e.message));
