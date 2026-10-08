// Renders docs/brand/cover.png and docs/brand/homeward-slides.pdf from their HTML sources.
// Usage (needs Playwright): node scripts/render_brand.mjs
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "docs", "brand");
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
await p.goto("file://" + path.join(dir, "cover.html"));
await p.screenshot({ path: path.join(dir, "cover.png") });
await p.goto("file://" + path.join(dir, "slides.html"));
await p.waitForTimeout(500);
await p.pdf({ path: path.join(dir, "homeward-slides.pdf"), width: "1600px", height: "900px", printBackground: true });
await b.close();
