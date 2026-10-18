// End-to-end walk through the hero demo: nurse -> review -> sign-off -> patient quiz -> impact -> patient's link.
// Usage: node tests/e2e/demo_flow.mjs [baseUrl] [screenshotDir]
import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:8100";
const out = process.argv[3] || "docs/screenshots";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
// Anything the content security policy blocks would silently break a screen, so it fails the run.
const cspWatch = (p) => p.on("console", (m) => { if (m.type() === "error" && /Content Security Policy/i.test(m.text())) errors.push(m.text()); });
cspWatch(page);
page.on("dialog", (d) => d.accept(d.type() === "prompt" ? "Not relevant" : undefined));
// Full-page shots: unstick the header so it does not land mid-page in the image.
// Let entrance animations and count-ups finish first, so the image shows the settled screen.
const settle = (p) => p.evaluate(() => Promise.all(document.getAnimations()
  .filter((a) => a.effect && a.effect.getComputedTiming().endTime !== Infinity).map((a) => a.finished.catch(() => {})))
  .then(() => new Promise((r) => setTimeout(r, 900))));
const shot = async (n) => {
  await settle(page);
  // Set through the CSSOM rather than a <style> tag, which the app's content security policy would refuse.
  const unstick = (on) => page.evaluate((on) => {
    document.querySelectorAll(".top, .queue, #progress-card").forEach((el) => { el.style.position = on ? "static" : ""; if (el.matches(".queue")) el.style.maxHeight = on ? "none" : ""; });
    document.querySelector(".toast").style.display = on ? "none" : "";
  }, on);
  await unstick(true);
  await page.screenshot({ path: `${out}/${n}.png`, fullPage: true, animations: "disabled" });
  await unstick(false);
};

await page.goto(base);
await page.getByText("Heart failure, new and changed medicines").click();
await page.click("#run");
await page.waitForSelector("#go-review", { timeout: 20000 });
await shot("1-prepare");

await page.click("#go-review");
await page.fill("#reviewer", "RN Sam Lee");
await page.dispatchEvent("#reviewer", "change");
await shot("2-review-before");

// Fix the translation error in S12 (15 litres -> 1,5 litres).
const s12 = page.locator('.sentence[data-id="S12"]');
await s12.locator(".edit").click();
await s12.locator(".ed-tl").fill("No beba más de 1,5 litros de líquido al día.");
await s12.locator(".save").click();
await page.waitForTimeout(300);

// Clarify the ibuprofen "hold" (S5).
const s5 = page.locator('.sentence[data-id="S5"]');
await s5.locator(".edit").click();
await s5.locator(".ed-en").fill("Do not take ibuprofen until your heart doctor checks your kidneys again and says it is OK.");
await s5.locator(".ed-tl").fill("No tome ibuprofen hasta que su cardiólogo vuelva a revisar sus riñones y le diga que puede tomarlo.");
await s5.locator(".save").click();
await page.waitForTimeout(300);

// Restore the missing warning sign with the model's suggested wording.
const om = page.locator('.omission[data-fact="F9"]');
await om.locator(".suggest").click();
await page.waitForTimeout(400);
await om.locator(".add").click();
await page.waitForTimeout(300);

// Approve the remaining high-risk sentences.
for (let i = 0; i < 20; i++) {
  const btn = page.locator(".approve:not([disabled])").first();
  if (!(await btn.count())) break;
  await btn.click();
  await page.waitForTimeout(200);
}
await shot("3-review-after");
const blockers = await page.textContent("#blockers");
console.log("blockers:", blockers.trim());
await page.click("#signoff");
await page.waitForSelector("#patient-body:not(.hidden)", { timeout: 5000 });
await page.waitForTimeout(300);

// Answer the quiz one question at a time: first question wrong on purpose, the rest right.
// The answer key never leaves the server; the right option is the packet sentence the question quotes.
const caseId = await page.evaluate(() => state.c.id);
const pk = await page.evaluate(async (id) => (await fetch(`/api/cases/${id}/packet`)).json(), caseId);
const said = Object.fromEntries(Object.values(pk.sections).flat().map((s) => [s.id, s.text_tl || s.text_en]));
const quiz = pk.quiz;
for (let i = 0; i < quiz.length; i++) {
  const correct = quiz[i].options.findIndex((o) => o.text === said[quiz[i].sentence_id]);
  if (correct < 0) throw new Error(`No packet sentence matches question ${quiz[i].id}`);
  const pick = i === 0 ? (correct + 1) % quiz[i].options.length : correct;
  if (i === 0) await shot("4a-patient-question");
  await page.locator(".q .opt").nth(pick).click();
  await page.waitForSelector(".q-next");
  if (i === 0) await shot("4b-patient-feedback");
  await page.click(".q-next");
  await page.waitForTimeout(150);
}
await page.waitForTimeout(300);
await shot("4-patient");
await page.click('#tabs button[data-view="impact"]');
await page.waitForTimeout(300);
await shot("5-impact");
const kpis = await page.locator(".kpi").allTextContents();
console.log("kpis:", kpis.join(" | "));
console.log("alerts:", (await page.textContent("#alerts")).trim());
// Where the server records follow-ups, the nurse marks the alert as gone over, with a note.
if (await page.locator("#alerts form.al-ack").count()) {
  await page.locator("#alerts .ack-note").first().fill("Went over the new dose with teach-back.");
  await page.locator("#alerts .al-ack button").first().click();
  await page.waitForSelector("#alerts .alert-item.acked");
  console.log("alert acknowledged:", (await page.locator("#alerts .al-ack.done").first().textContent()).trim(), "|", (await page.textContent("#alerts-sum")).trim());
  await shot("5b-impact-acknowledged");
}
await page.setViewportSize({ width: 390, height: 844 });
await page.click('#tabs button[data-view="patient"]');
await page.waitForTimeout(500);
await page.evaluate(() => { document.querySelector(".toast").style.display = "none"; });
await settle(page);
await page.screenshot({ path: `${out}/6-patient-mobile.png`, animations: "disabled" });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log("mobile horizontal overflow:", overflow);

// The patient's own link, on a phone: their packet only, answers already given are kept.
const link = await page.getAttribute("#blockers .plink", "href");
const phone = await browser.newPage({ viewport: { width: 390, height: 844 } });
phone.on("pageerror", (e) => errors.push(e.message));
cspWatch(phone);
await phone.goto(new URL(link, base).href);
await phone.waitForSelector("#patient-body:not(.hidden)", { timeout: 5000 });
await settle(phone);
await phone.screenshot({ path: `${out}/7-patient-link.png`, animations: "disabled" });
console.log("patient link:", link.replace(/[\w-]{12,}$/, "<token>"), "| staff tabs shown:", await phone.isVisible("#tabs"),
  "| quiz:", (await phone.textContent("#quiz")).trim().slice(0, 60));
// Accessibility sweep on every view: text contrast (WCAG AA), a name on every control, and on phones
// touch targets of at least 24 by 24 px (WCAG 2.2 target size). Light and dark, laptop and phone.
const a11y = (p, where, phoneSize) => p.evaluate(({ where, phoneSize }) => {
  const bad = [];
  const parse = (c) => {
    let m = c.match(/^rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)$/);
    if (m) return [+m[1], +m[2], +m[3], m[4] == null ? 1 : +m[4]];
    m = c.match(/^color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.]+))?\)$/);
    if (m) return [m[1] * 255, m[2] * 255, m[3] * 255, m[4] == null ? 1 : +m[4]];
    return null;
  };
  const over = (f, b) => [0, 1, 2].map((i) => f[i] * f[3] + b[i] * (1 - f[3])).concat(1);
  const lum = (c) => { const l = c.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const name = (el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${el.classList.length ? "." + [...el.classList].join(".") : ""} "${(el.textContent || el.value || "").trim().slice(0, 30)}"`;
  // The background behind an element: composite every background colour up to the page. Gradients and images are skipped.
  const backdrop = (el) => {
    const layers = [], r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n), box = n.getBoundingClientRect();
      // A label placed outside its parent's box (a gauge's "Target" tag) does not sit on that parent's colour.
      if (n !== el && n !== document.body && n !== document.documentElement && !(x >= box.left && x <= box.right && y >= box.top && y <= box.bottom)) continue;
      if (cs.backgroundImage !== "none" && !n.matches(".queue-list")) return null;
      const c = parse(cs.backgroundColor);
      if (c === null) return null;
      if (c[3] > 0) layers.push(c);
      if (c[3] >= 1) break;
    }
    return layers.reverse().reduce((b, f) => over(f, b), [255, 255, 255, 1]);
  };
  const shown = (el) => el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && el.getClientRects().length;
  let checked = 0, skipped = 0;
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest("svg, .sprite, [aria-hidden=true], button:disabled, .hidden") || !shown(el)) continue;
    const text = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!text) continue;
    const cs = getComputedStyle(el), fg = parse(cs.color), bg = backdrop(el);
    if (!fg || !bg || fg[3] === 0) { skipped++; continue; }
    let alpha = fg[3];
    for (let n = el; n; n = n.parentElement) alpha *= +getComputedStyle(n).opacity;
    const size = parseFloat(cs.fontSize), bold = +cs.fontWeight >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    const r = ratio(over([fg[0], fg[1], fg[2], alpha], bg), bg);
    checked++;
    if (r < need - 0.01) bad.push(`${where}: contrast ${r.toFixed(2)} < ${need} on ${name(el)}`);
  }
  for (const el of document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, summary")) {
    if (!shown(el) || el.closest(".hidden, .sprite")) continue;
    const label = el.getAttribute("aria-label") || el.textContent.trim() || el.title || el.placeholder || (el.labels && [...el.labels].map((l) => l.textContent.trim()).join(""));
    if (!label) bad.push(`${where}: no accessible name on ${name(el)}`);
    if (phoneSize && el.type !== "file") {
      const box = el.getBoundingClientRect();
      // Links inside a sentence are exempt; everything else needs room for a fingertip.
      const inline = el.matches("a") && getComputedStyle(el).display === "inline";
      const hit = el.closest("label") ? el.closest("label").getBoundingClientRect() : box;
      if (!inline && (Math.max(box.width, hit.width) < 24 || Math.max(box.height, hit.height) < 24)) bad.push(`${where}: target ${Math.round(box.width)}x${Math.round(box.height)} px on ${name(el)}`);
    }
  }
  return { bad, checked, skipped };
}, { where, phoneSize });

const sweepA11y = async (p, label, views, phoneSize) => {
  let total = 0;
  for (const v of views) {
    if (v) { await p.click(`#tabs button[data-view="${v}"]`); }
    await settle(p);
    const r = await a11y(p, `${label} ${v || "patient link"}`, phoneSize);
    errors.push(...r.bad);
    total += r.checked;
  }
  return total;
};
const views = ["nurse", "review", "patient", "impact"];
let checkedText = await sweepA11y(page, "laptop light", views, false);
await page.emulateMedia({ colorScheme: "dark" });
checkedText += await sweepA11y(page, "laptop dark", views, false);
await page.setViewportSize({ width: 360, height: 740 });
checkedText += await sweepA11y(page, "phone dark", views, true);
await page.emulateMedia({ colorScheme: "light" });
checkedText += await sweepA11y(page, "phone light", views, true);
checkedText += await sweepA11y(phone, "phone", [null], true);
await phone.emulateMedia({ colorScheme: "dark" });
checkedText += await sweepA11y(phone, "phone dark", [null], true);
console.log("accessibility sweep:", checkedText, "text elements checked,", errors.filter((e) => /contrast|accessible name|target/.test(e)).length, "problems");

// Optional layout sweep (LAYOUT_DIR=dir): every view at phone and laptop sizes, light, dark and reduced motion.
if (process.env.LAYOUT_DIR) {
  const dir = process.env.LAYOUT_DIR;
  const passes = [["light", "no-preference", [320, 360, 1280]], ["dark", "no-preference", [360, 1280]], ["light", "reduce", [1280]]];
  for (const [scheme, motion, widths] of passes) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: motion });
    for (const w of widths) {
      await page.setViewportSize({ width: w, height: w > 800 ? 720 : 740 });
      for (const v of ["nurse", "review", "patient", "impact"]) {
        await page.click(`#tabs button[data-view="${v}"]`);
        await settle(page);
        if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) errors.push(`sideways scroll: ${v} at ${w}px, ${scheme}`);
        await page.screenshot({ path: `${dir}/${scheme}${motion === "reduce" ? "-still" : ""}-${w}-${v}.png`, fullPage: true, animations: "disabled" });
      }
    }
  }
  console.log("layout sweep:", dir);
}
console.log("page errors:", errors.length ? errors : "none");
await browser.close();
if (errors.length) process.exit(1);
