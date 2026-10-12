# Homeward design system: Lamplight

Going home from hospital is a stressful moment for patients and a busy one for nurses. The design has one idea behind it: **evergreen for trust, lamplight for home.** Calm, precise evergreen carries the clinical work. Warm lamplight appears only where home is: the illustrations, the lit window when a signed packet arrives, and the house at the end of the teach-back quiz.

Tokens live at the top of [`homeward/static/styles.css`](../homeward/static/styles.css). A visual portfolio with live motion demos is published alongside the hackathon material.

## Principles

1. **One decision at a time.** The reviewer sees only what needs a person, in a queue. The patient answers one question at a time.
2. **Uncertainty is visible.** Green, amber and red are reserved for safety states. Each always comes with an icon and a word, never colour alone (NHS rule).
3. **Motion explains a change.** It shows where something came from, what changed, or that an action worked. Nothing loops except "working" indicators.
4. **Legible first.** Atkinson Hyperlegible Next, generous patient text (18 px, 21 px with "Larger text"), and contrast of at least 4.5:1 for all text in both themes.
5. **Nothing loads from elsewhere.** Fonts, icons and illustrations are in the repo, so patient pages make no third-party requests. The UI sets no inline styles or scripts and works under a strict content security policy.

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
- **Running the pipeline.** Each step fills in, and the trail between steps grows. The current step pulses.
- **Reviewing.** Cards come in one after another when the view opens, but not on every re-render. An approved card flashes green and its queue check pops. The sign-off button pulses twice when it becomes available, and a seal draws itself after sign-off.
- **Patient packet.** The porch light comes on when a signed packet arrives. The quiz is a path of stepping stones that ends at the house, which lights up on the last answer. While a section is read aloud, its button shows a level meter and works as a stop button.
- **Results.** The numbers count up and the bars grow. When a nurse marks a teach-back alert as gone over, it flashes green and folds down to who went over it, when, and their note.

With `prefers-reduced-motion`, every animation and transition is off, and each screen shows its final state.

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
- Chrome for Developers, [View transitions in 2025](https://developer.chrome.com/blog/view-transitions-in-2025): same-document transitions in Chrome 111+, Safari 18+ and Firefox 144+.
