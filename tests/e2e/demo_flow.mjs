// End-to-end walk through the hero demo: nurse -> review -> sign-off -> patient quiz -> impact.
// Usage: node tests/e2e/demo_flow.mjs [baseUrl] [screenshotDir]
import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:8100";
const out = process.argv[3] || "docs/screenshots";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("dialog", (d) => d.accept(d.type() === "prompt" ? "Not relevant" : undefined));
// Full-page shots: unstick the header so it does not land mid-page in the image.
const shot = async (n) => {
  const tag = await page.addStyleTag({ content: ".top,.queue{position:static!important}.queue{max-height:none!important}.toast{display:none!important}" });
  await page.screenshot({ path: `${out}/${n}.png`, fullPage: true });
  await tag.evaluate((el) => el.remove());
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
const caseId = await page.evaluate(() => state.c.id);
const quiz = (await page.evaluate(async (id) => (await fetch(`/api/cases/${id}`)).json(), caseId)).quiz;
for (let i = 0; i < quiz.length; i++) {
  const correct = quiz[i].options.findIndex((o) => o.correct);
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
await page.setViewportSize({ width: 390, height: 844 });
await page.click('#tabs button[data-view="patient"]');
await page.waitForTimeout(500);
await page.addStyleTag({ content: ".toast{display:none!important}" });
await page.screenshot({ path: `${out}/6-patient-mobile.png` });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log("mobile horizontal overflow:", overflow);
console.log("page errors:", errors.length ? errors : "none");
await browser.close();
if (errors.length) process.exit(1);
