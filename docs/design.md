# Homeward design system: Lamplight

Going home from hospital is a stressful moment for patients and a busy one for nurses. The design has one idea behind it: **evergreen for trust, lamplight for home.** Calm, precise evergreen carries the clinical work. Warm lamplight appears only where home is: the illustrations, the lit window when a signed packet arrives, and the house at the end of the teach-back quiz.

Tokens live at the top of [`homeward/static/styles.css`](../homeward/static/styles.css). A visual portfolio with live motion demos is published alongside the hackathon material.

## Principles

1. **One decision at a time.** The reviewer sees only what needs a person, in a queue. The patient answers one question at a time.
2. **Uncertainty is visible.** Green, amber and red are reserved for safety states. Each always comes with an icon and a word, never colour alone (NHS rule).
3. **Motion explains a change.** It shows where something came from, what changed, or that an action worked. Nothing loops except "working" indicators.
4. **Legible first.** Atkinson Hyperlegible Next, generous patient text (18 px, 21 px with "Larger text"), and contrast of at least 4.5:1 for all text in both themes.
5. **Nothing loads from elsewhere.** Fonts, icons, illustrations and the one animation library are in the repo, so no page makes third-party requests. The UI sets no inline styles or scripts and works under a strict content security policy.

## Palette

| Token | Light | Dark | Role |
|---|---|---|---|
| Evergreen 900 | `#0B3B37` | `#0F2A27` | Patient header band, roofs, illustration line |
| Evergreen 700 (`--brand`) | `#0F766E` | `#3CC7B5` | Primary buttons, links, focus, progress |
| Evergreen 800 | `#0B5D57` | `#6FDCCD` | Hover and pressed |
| Seaglass | `#7DE3CF` | `#7DE3CF` | Accents on the dark band |
| Mist (`--brand-soft`) | `#E3F1EE` | `#11302B` | Selected states, icon tiles |
| Lamplight | `#F7C873` | `#F7C873` | Home and warmth in illustrations only, never a status |
| Linen (`--bg`) | `#F6F4EF` | `#0C1312` | Page background; a warm tint that cuts glare |
| Ink / Muted | `#14211F` / `#56635F` | `#E8EEEC` / `#9DABA6` | Text |

Signals, used only for safety states:

| Signal | Text on soft fill | White on solid fill | Meaning |
|---|---|---|---|
| Verified | `#1D7A3E` on `#E5F4EA` (4.7:1) | `#1D7A3E` (5.4:1) | Every check passed |
| Uncertain | `#9A5800` on `#FCF1DE` (5.0:1) | `#9A5800` (5.6:1) | A person should look |
| Blocked | `#B42318` on `#FDECEA` (5.8:1) | `#B42318` (6.6:1) | Cannot go out as written |
| High risk | `#4338CA` on `#ECEBFC` (6.7:1) | `#4338CA` (7.9:1) | Needs a named sign-off even when it passes |
| Emergency | | `#7A1710` (10.7:1) | "Call 911" care card |

Key text contrast: ink on linen 15.1:1, muted on white 6.3:1, white on evergreen 700 5.5:1, white on evergreen 900 12.4:1. Dark theme: ink 16.0:1, muted 7.3:1, brand on panel 8.3:1.

## Type

Atkinson Hyperlegible Next (Braille Institute, OFL), self-hosted variable font, weights 200 to 800. Vietnamese and Chinese fall back to the system font. Numbers are tabular so doses and times line up. Headings use `text-wrap: balance`.

## Layout

Each screen leads with what the person in front of it has to do next.

- **Header.** Brand on the left, the four steps in the centre, the model status on the right, all on one row on laptops. Below 1100 px the tagline and the status detail ("no GPU connected") drop away; the status keeps them in its tooltip. On phones the brand and status share a row, the four steps sit evenly below it with their names, and the bar scrolls away with the page rather than holding a fifth of the screen.
- **One set of numbers.** Only the four workflow steps are numbered. Card headings carry an icon instead, so "1 Choose the instructions" never competes with "1 Prepare".
- **Prepare.** Sample cards are equal height, with a one-line note on where the saved run came from ("Recorded on CPU, not AMD"; the full model, hardware and time are in the tooltip). When the checks finish, the result and "Open review" move to the top of the steps card and the steps fold into a compact checklist. On laptops the steps card stays in view while the nurse scrolls the form; on phones the page scrolls to it when the run starts.
- **Review.** A high-risk line that passed every check gets one quiet line ("High risk. Every check passed…") instead of a full warning box. It is routine, and the boxes are kept for what actually failed.
- **Results.** Teach-back alerts come first, full width, because they are the nurse's to-do before the patient leaves. With room, what the patient chose and what the packet says sit side by side. The model card lists only what was measured, so a scripted replay shows its mode and an honest note rather than a column of dashes. On phones the headline number spans the width and the other four pair up.
- **The patient's link** has no app bar. The packet's own header carries the name, and staff copy ("…patients can follow") never reaches the patient.

## Motion

| Token | Value | Used for |
|---|---|---|
| `--t-1` | 140 ms | Hover, press, toggles |
| `--t-2` | 240 ms | Toasts, small reveals, leaving a view |
| `--t-3` | 420 ms | Entering a view, cards coming in, a check popping in |
| `--t-4` | 900 ms | Bars filling, illustration drawing |
| `--ease-out` | `cubic-bezier(.22,1,.36,1)` | Things arriving |
| `--ease-in-out` | `cubic-bezier(.65,0,.35,1)` | Things moving across |
| `--ease-pop` | `cubic-bezier(.34,1.56,.64,1)` | Confirmations only |

Where it is used:

- **Changing view.** The page slides in the direction of the workflow, using View Transitions where supported. Elsewhere it fades up.
- **Opening the app.** The path from hospital to home draws itself, a walker follows it, and the window lights up. This plays once.
- **Running the pipeline.** Each step fills in, and the trail between steps grows. The current step pulses, and a soft shine runs across its name while it works. When the last step is done, the result rises in above the steps.
- **Reviewing.** Cards come in one after another when the view opens, but not on every re-render. When the queue, the sentence list or the audit trail changes (an approval, an edit, "Only show flagged"), items glide from where they were to where they now sit, and new ones fade in, so a reviewer can see what moved. An approved card flashes green and its queue check pops. The sign-off button pulses twice when it becomes available, and a seal draws itself after sign-off.
- **Long queues.** The review queue fades at the top or bottom edge when there is more to scroll.
- **Patient packet.** The porch light comes on when a signed packet arrives. The quiz is a path of stepping stones that ends at the house, which lights up on the last answer. While a section is read aloud, its button shows a level meter and works as a stop button.
- **Results.** The numbers count up and the bars grow. When a nurse marks a teach-back alert as gone over, it flashes green and folds down to who went over it, when, and their note.

With `prefers-reduced-motion`, every animation and transition is off, and each screen shows its final state. The glide library is not even loaded then.

## Moving around

Each step has its own address (`#prepare`, `#review`, `#patient`, `#results`), so the browser's Back and Forward buttons move between steps, and a reload keeps the case and the step. Leaving the page with unsaved text in an edit box asks first. The patient's private link has no steps and ignores these addresses.

## Checks

`node tests/e2e/demo_flow.mjs <url> <dir>` walks the whole demo in Playwright and fails on any page error or content-security-policy block. It also sweeps every screen (laptop and phone, light and dark, and the patient's link) for:

- text contrast of at least 4.5:1, measured against the real backgrounds behind each piece of text;
- an accessible name on every button, link and field;
- touch targets of at least 24 by 24 px on phones.

`LAYOUT_DIR=<dir>` adds screenshots at 320, 360 and 1280 px in light, dark and reduced motion.

## Libraries

Six open-source projects were checked for malware and for what they could add (14 October 2026). None contained malware. The full report, with what was scanned and how, is in the hackathon design folder (`repo-vetting.md`).

| Project | Used | Why |
|---|---|---|
| [GSAP](https://gsap.com) 3.15.0, Flip plugin | Staff screens | The glide when lists change. Vendored in `homeward/static/vendor/gsap/` with its notice (GSAP Standard License, no charge). Loaded only on staff screens and never under reduced motion, so patient pages stay light. Flip runs in `simple` mode so it never writes a `style` attribute that the security policy would block. |
| [Playwright](https://playwright.dev) | Tests only | The end-to-end walk, the accessibility sweep and the screenshots. |
| [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines) (Vercel Labs, MIT) | As a checklist | Led to the step addresses, the unsaved-text warning, theme colours, field names, `touch-action`, `scroll-padding` and `translate="no"` on the brand. |
| [React Bits](https://reactbits.dev) | Ideas only | The working-step shine and the queue edge fades are rebuilt in plain CSS. No code is copied: its licence (MIT with Commons Clause) does not allow redistributing ported components. |
| [Lenis](https://lenis.darkroom.engineering) | Not in the app | Smooth scrolling takes over the page's own scroll, which gets in the way of keyboard, zoom and screen-reader use. It is used only on the design portfolio page. |
| [Vanta](https://www.vantajs.com) | No | A looping WebGL background drains phone batteries, adds about 600 KB of three.js, and is decoration rather than explanation. It has also had no commits since 2023. |

## Illustrations

The illustrations are drawn in-house as inline SVG: flat shapes, a 2.5 px evergreen line, mist and linen fills, and lamplight only for the lit window and the sun. They are decorative (`aria-hidden`) and themed by CSS tokens, so they work in dark mode and make no image requests.

- **The way home** (Prepare): hospital, path, house.
- **Porch light** (patient header).
- **Spot illustrations** for empty states: a clipboard, a locked house and a chart.

## Research behind it

- NHS digital service manual, [colour](https://service-manual.nhs.uk/design-system/styles/colour): never rely on colour alone, aim for AAA, and use a tinted background to reduce glare.
- Better (Better.care), [animation and motion in healthcare applications](https://www.better.care/?p=2458): use motion for feedback, attention and orientation, and prefer "less delight, more usability".
- Val Head, [How fast should your UI animations be?](https://valhead.com/?p=2978): 200 to 500 ms, with the shorter end for smaller elements.
- UXmatters, [Designing calm UX](https://www.uxmatters.com/mt/archives/2025/05/designing-calm-ux-principles-for-reducing-users-anxiety.php): progressive disclosure, a stable structure, reassuring copy, and immediate feedback.
- Paul Lewis, [FLIP your animations](https://aerotwist.com/blog/flip-your-animations/): measure first and last positions, then animate the difference with transforms only.
- Vercel, [Web Interface Guidelines](https://vercel.com/design/guidelines): the checklist behind the URL, form and touch fixes.
- Chrome for Developers, [View transitions in 2025](https://developer.chrome.com/blog/view-transitions-in-2025): same-document transitions in Chrome 111+, Safari 18+ and Firefox 144+.
