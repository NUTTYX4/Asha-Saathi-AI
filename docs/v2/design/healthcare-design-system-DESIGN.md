# DESIGN.md — Maternal & Women's Healthcare Design System

> **Codename:** Nurture
> **Version:** 1.0.0
> **Theme:** Light mode only
> **Audience:** AI coding agents, front-end engineers and product designers building web applications for maternity, pregnancy, antenatal and postnatal care, gynaecology, appointments, patient records and clinician dashboards.

---

## 0. How to Use This Document

This file is the single source of truth for visual and interaction design. When building any interface for this product:

1. **Use tokens, never raw values.** Every colour, size, radius, shadow and duration in code must reference a token from §17 (`tokens.json` in §17.1, CSS custom properties in §17.2). Raw hex values, pixel values or ad-hoc shadows in component code are defects.
2. **Use semantic tokens before primitive tokens.** Components consume semantic tokens (`--color-text-primary`, `--color-action-primary-bg`). Primitive tokens (`--color-berry-600`) are only used to define semantic tokens or in rare, documented exceptions.
3. **Requirement keywords.** **MUST** = mandatory, failing it is a bug. **SHOULD** = default behaviour, deviate only with a documented reason. **MAY** = optional.
4. **When this document is silent,** choose the option that is calmer, clearer, more accessible and more private.
5. **Do not introduce** dark mode, new brand colours, new font families, gradients on text, or decorative effects not specified here.

### Table of Contents

1. [Brand Foundations](#1-brand-foundations)
2. [Colour System](#2-colour-system)
3. [Typography](#3-typography)
4. [Spacing](#4-spacing)
5. [Border Radius](#5-border-radius)
6. [Shadows, Elevation & Layering](#6-shadows-elevation--layering)
7. [Layout & Responsive Grid](#7-layout--responsive-grid)
8. [Iconography & Imagery](#8-iconography--imagery)
9. [Motion](#9-motion)
10. [Core Components](#10-core-components)
11. [Healthcare Components](#11-healthcare-components)
12. [Content & Microcopy](#12-content--microcopy)
13. [Accessibility (WCAG 2.2 AA)](#13-accessibility-wcag-22-aa)
14. [Responsive Behaviour](#14-responsive-behaviour)
15. [Privacy-Conscious Display](#15-privacy-conscious-display)
16. [Health Status Communication](#16-health-status-communication)
17. [Token Reference (JSON, CSS & Tailwind)](#17-token-reference-json-css--tailwind)
18. [Implementation Checklist](#18-implementation-checklist)

---

## 1. Brand Foundations

### 1.1 Brand Personality

| Trait | What it means in the UI | What it is **not** |
|---|---|---|
| **Warm** | Soft warm-neutral canvas, rounded corners, human photography, encouraging copy. | Saccharine, pink-everything, baby-themed. |
| **Reassuring** | Predictable layouts, clear next steps, calm status colours, no surprises. | Vague, hiding important information. |
| **Expert** | Precise data display, consistent terminology, clinical accuracy. | Cold, jargon-heavy, intimidating. |
| **Respectful** | Inclusive language, privacy by default, user stays in control. | Patronising, presumptive about family structure or outcome. |
| **Modern & minimal** | Generous whitespace, one primary action per view, restrained colour. | Sparse to the point of hiding features; trendy for its own sake. |

### 1.2 Design Principles

1. **Calm before clever.** Patients may be anxious, tired, in pain or grieving. Every screen should lower cognitive load: one primary action, short sentences, obvious hierarchy.
2. **Clarity is care.** Health information must be unambiguous. Always pair numbers with units, dates with context ("in 3 days"), and status colour with text and an icon.
3. **Never alarm without a path.** If something needs attention, say what it is, why it matters, and exactly what to do next.
4. **Private by default.** Show the minimum personal health information needed for the task. Sensitive details are revealed on intent, not by default.
5. **Grown-up warmth.** Warmth comes from colour temperature, typography, roundness and tone of voice — never from cartoons, baby clip-art or excessive pastel.
6. **Accessible is the baseline.** WCAG 2.2 AA is a floor, not a goal. Pregnancy can affect vision, dexterity and concentration; design for that.
7. **Two audiences, one system.** Patient-facing views favour reassurance and guidance; clinician-facing views favour density and speed. Both use the same tokens with different density settings (§7.6).

### 1.3 Brand Colour Roles

| Brand colour | Hex | Name | Role |
|---|---|---|---|
| Primary | `#902C4E` | **Berry** | Primary actions, links, active navigation, focus rings, key brand moments. |
| Secondary | `#D4E990` | **Lime** | Supportive highlights, secondary buttons (with dark text), positive milestones, progress fills, decorative accents. |

These two values are fixed and **MUST NOT** be altered, tinted for the "brand" token, or substituted.

---

## 2. Colour System

### 2.1 Primitive Palette

Primitive tokens follow `--color-{family}-{step}`. Steps run 50 (lightest) to 900 (darkest). The supplied brand colours are anchored at `berry-600` and `lime-300`.

#### Berry (Primary)

| Token | Hex | Notes |
|---|---|---|
| `--color-berry-50` | `#FBF2F5` | Brand-tinted background |
| `--color-berry-100` | `#F6E1E8` | Selected/active background |
| `--color-berry-200` | `#EDC3D1` | Subtle border on brand surfaces |
| `--color-berry-300` | `#DE96AE` | Decorative only |
| `--color-berry-400` | `#C76287` | Decorative / charts only (3.8:1 on white — not for text) |
| `--color-berry-500` | `#A93D63` | Charts, large text only |
| **`--color-berry-600`** | **`#902C4E`** | **Brand primary** (7.91:1 on white) |
| `--color-berry-700` | `#7A2442` | Hover state (9.73:1 on white) |
| `--color-berry-800` | `#631D36` | Pressed state (11.93:1 on white) |
| `--color-berry-900` | `#4A1528` | Deepest brand tone |

#### Lime (Secondary)

| Token | Hex | Notes |
|---|---|---|
| `--color-lime-50` | `#F9FCEC` | Very subtle positive background |
| `--color-lime-100` | `#F1F8D6` | Accent-subtle background |
| `--color-lime-200` | `#E5F1B6` | Hover on lime-100 |
| **`--color-lime-300`** | **`#D4E990`** | **Brand secondary** (1.32:1 on white — background use only) |
| `--color-lime-400` | `#BDD86A` | Secondary button hover |
| `--color-lime-500` | `#A9C95A` | Secondary button pressed |
| `--color-lime-600` | `#7D9A2F` | Graphics/progress strokes only (3.21:1 on white — not for text) |
| `--color-lime-700` | `#5E7522` | Lime-family text on white (5.19:1) |
| `--color-lime-800` | `#45561A` | Text on lime-100/300 |
| `--color-lime-900` | `#2F3B12` | **Default text colour on any lime background** (9.03:1 on lime-300) |

#### Warm Neutral

| Token | Hex | Notes |
|---|---|---|
| `--color-neutral-0` | `#FFFFFF` | Surfaces |
| `--color-neutral-25` | `#FDFBFA` | Subtle surface |
| `--color-neutral-50` | `#FAF7F5` | App canvas |
| `--color-neutral-100` | `#F3EEEB` | Sunken surface, table header, skeleton base |
| `--color-neutral-200` | `#E7E0DC` | Dividers, decorative borders |
| `--color-neutral-300` | `#D5CCC7` | Disabled borders |
| `--color-neutral-400` | `#A89D97` | Disabled text/icons (exempt from contrast per WCAG) |
| `--color-neutral-500` | `#8C807A` | Form control borders (3.83:1 on white — meets 3:1 non-text) |
| `--color-neutral-600` | `#756A64` | Tertiary text (5.25:1 on white) |
| `--color-neutral-700` | `#5E544F` | Secondary text (7.35:1 on white) |
| `--color-neutral-800` | `#463E3A` | Strong secondary text, tooltip background |
| `--color-neutral-900` | `#1F1A18` | Primary text (17.22:1 on white) |

#### Status Families

| Family | 50 (bg) | 200 (border) | 600 (fg / solid) | 700 (strong text) |
|---|---|---|---|---|
| Success (green) | `#E8F5EE` | `#A6D9BC` | `#1E7A4C` | `#16603B` |
| Warning (amber) | `#FEF4E2` | `#F5CF8A` | `#9A5B00` | `#7A4800` |
| Error (red) | `#FDECEA` | `#F4B4AE` | `#B42318` | `#912018` |
| Info (blue) | `#EAF2FB` | `#A9C8EE` | `#1F5FA8` | `#184B85` |

Token names: `--color-success-50`, `--color-success-200`, `--color-success-600`, `--color-success-700` (and the same for `warning`, `error`, `info`).

> **Error red vs Berry:** Berry is a brand colour, not an error colour. Error states always use the `error` family and are always paired with an icon and text, so they are never confused with brand elements.

### 2.2 Semantic Tokens

Components **MUST** use these. Naming: `--color-{category}-{role}[-{state}]`.

#### Backgrounds & Surfaces

| Token | Value | Usage |
|---|---|---|
| `--color-bg-canvas` | `neutral-50` `#FAF7F5` | Page/app background behind cards |
| `--color-bg-surface` | `neutral-0` `#FFFFFF` | Cards, inputs, modals, tables |
| `--color-bg-surface-subtle` | `neutral-25` `#FDFBFA` | Nested panels inside a card |
| `--color-bg-surface-sunken` | `neutral-100` `#F3EEEB` | Table headers, code/ID chips, read-only fields |
| `--color-bg-surface-hover` | `neutral-50` `#FAF7F5` | Hover on rows, list items, ghost buttons |
| `--color-bg-brand-subtle` | `berry-50` `#FBF2F5` | Highlight panels, welcome banners |
| `--color-bg-brand-muted` | `berry-100` `#F6E1E8` | Selected nav item, selected row, active tab pill |
| `--color-bg-accent` | `lime-300` `#D4E990` | Secondary button, milestone highlights, progress fill |
| `--color-bg-accent-subtle` | `lime-100` `#F1F8D6` | Positive info panels, "completed" visit background |
| `--color-bg-overlay` | `rgba(31, 26, 24, 0.48)` | Modal scrim |
| `--color-bg-inverse` | `neutral-800` `#463E3A` | Tooltips, toasts |
| `--color-bg-disabled` | `neutral-100` `#F3EEEB` | Disabled controls |

#### Text

| Token | Value | Contrast on white | Usage |
|---|---|---|---|
| `--color-text-primary` | `#1F1A18` | 17.22:1 | Body text, headings |
| `--color-text-secondary` | `#5E544F` | 7.35:1 | Supporting text, labels in dense UIs |
| `--color-text-tertiary` | `#756A64` | 5.25:1 | Hints, timestamps, placeholders |
| `--color-text-disabled` | `#A89D97` | 2.65:1 | Disabled only (WCAG-exempt). Never for meaningful content. |
| `--color-text-brand` | `#902C4E` | 7.91:1 | Links, brand emphasis, active nav label |
| `--color-text-brand-hover` | `#7A2442` | 9.73:1 | Link hover |
| `--color-text-inverse` | `#FFFFFF` | — | Text on berry, status solids, inverse surfaces |
| `--color-text-on-accent` | `#2F3B12` | 9.03:1 on lime-300 | **All** text and icons on lime backgrounds |
| `--color-text-success` | `#16603B` | 7.58:1 | Success text |
| `--color-text-warning` | `#7A4800` | 7.62:1 | Warning text |
| `--color-text-error` | `#B42318` | 6.57:1 | Error text, validation messages |
| `--color-text-info` | `#184B85` | ≥7:1 | Info text |

#### Borders

| Token | Value | Usage |
|---|---|---|
| `--color-border-subtle` | `neutral-200` `#E7E0DC` | Card outlines, dividers (decorative; not relied on for meaning) |
| `--color-border-default` | `neutral-500` `#8C807A` | Inputs, checkboxes, radios, selects — meets 3:1 non-text contrast |
| `--color-border-strong` | `neutral-700` `#5E544F` | Input hover |
| `--color-border-brand` | `berry-600` `#902C4E` | Selected cards, active input |
| `--color-border-accent` | `lime-600` `#7D9A2F` | Milestone/progress outlines (graphic only) |
| `--color-border-disabled` | `neutral-300` `#D5CCC7` | Disabled controls |
| `--color-border-error` | `error-600` `#B42318` | Invalid inputs |
| `--color-focus-ring` | `berry-600` `#902C4E` | Focus indicator on all interactive elements |

#### Actions

| Token | Value |
|---|---|
| `--color-action-primary-bg` | `#902C4E` |
| `--color-action-primary-bg-hover` | `#7A2442` |
| `--color-action-primary-bg-active` | `#631D36` |
| `--color-action-primary-text` | `#FFFFFF` |
| `--color-action-secondary-bg` | `#D4E990` |
| `--color-action-secondary-bg-hover` | `#BDD86A` |
| `--color-action-secondary-bg-active` | `#A9C95A` |
| `--color-action-secondary-text` | `#2F3B12` |
| `--color-action-outline-border` | `#902C4E` |
| `--color-action-outline-text` | `#902C4E` |
| `--color-action-outline-bg-hover` | `#FBF2F5` |
| `--color-action-ghost-text` | `#5E544F` |
| `--color-action-ghost-bg-hover` | `#F3EEEB` |
| `--color-action-destructive-bg` | `#B42318` |
| `--color-action-destructive-bg-hover` | `#912018` |
| `--color-action-disabled-bg` | `#F3EEEB` |
| `--color-action-disabled-text` | `#A89D97` |

#### Status (Feedback)

For each of `success`, `warning`, `error`, `info`:

| Token pattern | Maps to | Usage |
|---|---|---|
| `--color-status-{name}-bg` | `{name}-50` | Alert/badge background |
| `--color-status-{name}-border` | `{name}-200` | Alert border |
| `--color-status-{name}-icon` | `{name}-600` | Icon fill |
| `--color-status-{name}-text` | `{name}-700` | Text inside the alert/badge |
| `--color-status-{name}-solid` | `{name}-600` | Solid badge bg (with white text) |

Plus `--color-status-neutral-bg` `#F3EEEB`, `--color-status-neutral-text` `#463E3A`, `--color-status-neutral-icon` `#5E544F`.

#### Data Visualisation

Use in this order for multi-series charts. Pair every series with a label or pattern; never rely on colour alone.

| Token | Hex | Notes |
|---|---|---|
| `--color-chart-1` | `#902C4E` | Primary series (e.g. patient's readings) |
| `--color-chart-2` | `#1F5FA8` | Comparison series |
| `--color-chart-3` | `#7D9A2F` | Lime family, ≥3:1 for strokes |
| `--color-chart-4` | `#9A5B00` | Amber |
| `--color-chart-5` | `#5E544F` | Neutral |
| `--color-chart-range` | `#F1F8D6` | Shaded "expected range" band |
| `--color-chart-grid` | `#E7E0DC` | Gridlines |

### 2.3 Verified Contrast Pairs

All values computed with the WCAG 2.x relative luminance formula.

| Foreground | Background | Ratio | Passes |
|---|---|---|---|
| `#FFFFFF` | `#902C4E` berry-600 | 7.91:1 | AAA text |
| `#FFFFFF` | `#7A2442` berry-700 | 9.73:1 | AAA text |
| `#902C4E` | `#FFFFFF` | 7.91:1 | AAA text |
| `#902C4E` | `#FAF7F5` canvas | 7.41:1 | AAA text |
| `#902C4E` | `#F6E1E8` berry-100 | 6.35:1 | AA text |
| `#902C4E` | `#D4E990` lime-300 | 5.97:1 | AA text |
| `#2F3B12` | `#D4E990` lime-300 | 9.03:1 | AAA text |
| `#2F3B12` | `#BDD86A` lime-400 | 7.52:1 | AAA text |
| `#2F3B12` | `#A9C95A` lime-500 | 6.37:1 | AA text |
| `#1F1A18` | `#D4E990` lime-300 | 13.01:1 | AAA text |
| `#45561A` | `#F1F8D6` lime-100 | 7.36:1 | AAA text |
| `#1F1A18` | `#FFFFFF` | 17.22:1 | AAA text |
| `#5E544F` | `#FFFFFF` | 7.35:1 | AAA text |
| `#5E544F` | `#F3EEEB` | 6.38:1 | AA text |
| `#756A64` | `#FFFFFF` | 5.25:1 | AA text |
| `#756A64` | `#FAF7F5` | 4.92:1 | AA text |
| `#756A64` | `#F3EEEB` | 4.56:1 | AA text (minimum — use secondary text if in doubt) |
| `#8C807A` | `#FFFFFF` | 3.83:1 | 3:1 non-text (control borders) |
| `#8C807A` | `#FAF7F5` | 3.59:1 | 3:1 non-text |
| `#FFFFFF` | `#1E7A4C` success-600 | 5.33:1 | AA text |
| `#FFFFFF` | `#9A5B00` warning-600 | 5.43:1 | AA text |
| `#FFFFFF` | `#B42318` error-600 | 6.57:1 | AA text |
| `#FFFFFF` | `#1F5FA8` info-600 | 6.44:1 | AA text |
| `#16603B` | `#E8F5EE` | 6.76:1 | AA text |
| `#7A4800` | `#FEF4E2` | 6.99:1 | AA text |
| `#912018` | `#FDECEA` | 7.58:1 | AAA text |
| `#184B85` | `#EAF2FB` | 7.80:1 | AAA text |
| `#FFFFFF` | `#463E3A` inverse | 10.44:1 | AAA text |

### 2.4 Colour Usage Rules

1. **Lime is never paired with white text.** White on `#D4E990` is 1.32:1. Any text or icon on any lime background (`lime-50`–`lime-500`) **MUST** use `--color-text-on-accent` (`#2F3B12`) or `--color-text-primary`. Lint rule: flag `color: #FFF` inside any element whose background is a lime token.
2. **Lime is never used as text or icon colour on white/canvas.** Use `lime-700` (`#5E7522`) or darker if lime-family text is genuinely needed.
3. **Lime is never used to communicate "success" on its own.** Lime is a brand accent; success is the green status family. Lime MAY decorate positive moments (milestone reached, visit completed) when accompanied by text.
4. **Berry is the only colour for primary actions.** One primary (berry) button per view region.
5. **Colour proportion target:** ~75% neutrals (canvas, surface, text), ~15% berry (actions, nav, headings accents), ~7% lime (highlights, progress), ~3% status colours.
6. **No gradients** on text, buttons or form controls. A single subtle gradient MAY be used in marketing/hero banners: `linear-gradient(135deg, #FBF2F5 0%, #F1F8D6 100%)`.
7. **Status colour always ships with an icon and a text label** (WCAG 1.4.1 Use of Colour).
8. **Light mode only.** Do not add `prefers-color-scheme: dark` styles. Set `color-scheme: light;` on `:root`.

---

## 3. Typography

### 3.1 Font Families

**Mulish is the only typeface** in this design system. It is used for all text: headings, body, labels, data, metrics and identifiers. Do not add a second font family (including monospace fonts).

| Token | Value |
|---|---|
| `--font-sans` | `'Mulish', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif` |

The fallbacks in the stack exist only for the moment before Mulish loads (or if it fails to load); they are not alternative design fonts.

**Identifiers** (reference numbers, health IDs, prescription and batch codes) also use Mulish, set with the `--text-id-sm` style: weight 600, `font-variant-numeric: tabular-nums slashed-zero;`, letter-spacing 0.04em, grouped in blocks of 3–4 characters (`4821 0937`). Where codes mix letters and digits, avoid ambiguous characters (`0/O`, `1/l/I`) in the code format itself.

**Loading:** Self-host or load Mulish (variable, weights 400–800) with `font-display: swap`. Preload the 400 and 700 weights.

```html



```

### 3.2 Font Weights

| Token | Value | Usage |
|---|---|---|
| `--font-weight-regular` | 400 | Body text |
| `--font-weight-medium` | 500 | Captions, table cells needing slight emphasis |
| `--font-weight-semibold` | 600 | Labels, buttons, small headings |
| `--font-weight-bold` | 700 | Headings, metric values |
| `--font-weight-extrabold` | 800 | Display only (marketing/hero). Never in app UI body. |

### 3.3 Type Scale

Base size: 16px (`1rem`). All sizes in `rem`. Line-heights are unitless or in rem to align to the 4px grid.

| Token | Size | Line height | Weight | Letter spacing | Usage |
|---|---|---|---|---|---|
| `--text-display-lg` | 3rem / 48px | 3.5rem / 56px | 700 | -0.02em | Marketing hero only |
| `--text-display-md` | 2.5rem / 40px | 3rem / 48px | 700 | -0.02em | Landing page section heads |
| `--text-heading-xl` | 2rem / 32px | 2.5rem / 40px | 700 | -0.01em | Page title (H1) |
| `--text-heading-lg` | 1.75rem / 28px | 2.25rem / 36px | 700 | -0.01em | Section title (H2) |
| `--text-heading-md` | 1.5rem / 24px | 2rem / 32px | 600 | -0.005em | Card group / sub-section (H3) |
| `--text-heading-sm` | 1.25rem / 20px | 1.75rem / 28px | 600 | 0 | Card title (H4) |
| `--text-heading-xs` | 1.125rem / 18px | 1.625rem / 26px | 600 | 0 | Small card title, dialog section (H5) |
| `--text-body-lg` | 1.125rem / 18px | 1.75rem / 28px | 400 | 0 | Health education articles, intros |
| `--text-body-md` | 1rem / 16px | 1.5rem / 24px | 400 | 0 | **Default body**, input text |
| `--text-body-sm` | 0.875rem / 14px | 1.25rem / 20px | 400 | 0 | Supporting text, table cells (clinician) |
| `--text-label-lg` | 1rem / 16px | 1.5rem / 24px | 600 | 0 | Large buttons, prominent labels |
| `--text-label-md` | 0.875rem / 14px | 1.25rem / 20px | 600 | 0 | Form labels, buttons, tabs |
| `--text-label-sm` | 0.75rem / 12px | 1rem / 16px | 600 | 0.04em | Overlines (uppercase), badges |
| `--text-caption` | 0.75rem / 12px | 1rem / 16px | 500 | 0.01em | Timestamps, metadata |
| `--text-metric-xl` | 2.25rem / 36px | 2.75rem / 44px | 700 | -0.01em | Headline health metric value |
| `--text-metric-lg` | 1.75rem / 28px | 2.25rem / 36px | 700 | -0.01em | Dashboard widget value |
| `--text-id-sm` | 0.875rem / 14px | 1.25rem / 20px | 600 | 0.04em | IDs, reference codes (tabular, slashed zero) |

**Responsive heading scale** — below `md` (768px):

| Token | Mobile size / line height |
|---|---|
| `--text-display-lg` | 2.25rem / 2.75rem |
| `--text-display-md` | 2rem / 2.5rem |
| `--text-heading-xl` | 1.75rem / 2.25rem |
| `--text-heading-lg` | 1.5rem / 2rem |
| `--text-heading-md` | 1.25rem / 1.75rem |

### 3.4 Typography Rules

- **Minimum sizes:** Patient-facing body text ≥ 16px. Clinical values (dosages, readings, dates) ≥ 14px in any context. 12px only for non-essential metadata (timestamps, overlines, badge labels).
- **Input text MUST be 16px** to prevent iOS auto-zoom.
- **Line length:** 45–75 characters for reading content (`max-width: 68ch`).
- **Numbers:** Use `font-variant-numeric: tabular-nums;` for tables, metrics, times and doses so columns align.
- **Headings** are sentence case ("Upcoming appointments", not "Upcoming Appointments"). No all-caps headings; uppercase is permitted only for `--text-label-sm` overlines.
- **Heading colour** is `--color-text-primary`. Berry headings are reserved for brand moments (hero, empty-state title) — not every heading.
- **Do not** use italics for emphasis in clinical content; use semibold.
- **Text must reflow** at 200% zoom and support user text-spacing overrides (WCAG 1.4.12): never set fixed heights on text containers.

---

## 4. Spacing

Base unit: **4px**. Token pattern: `--space-{n}` where `n × 4px` (except `0-5`).

| Token | Value | Common usage |
|---|---|---|
| `--space-0` | 0 | — |
| `--space-0-5` | 2px | Icon/text optical nudge, badge vertical padding |
| `--space-1` | 4px | Tight gaps between inline elements |
| `--space-2` | 8px | Icon-to-label gap, chip gap, compact padding |
| `--space-3` | 12px | Input horizontal padding, list item gap |
| `--space-4` | 16px | Default component padding, mobile page gutter, card gap (mobile) |
| `--space-5` | 20px | Card padding (compact) |
| `--space-6` | 24px | Card padding (default), grid gutter, form field gap |
| `--space-8` | 32px | Section gap inside a page, tablet page margin |
| `--space-10` | 40px | Large section gap |
| `--space-12` | 48px | Page section separation (desktop) |
| `--space-16` | 64px | Hero padding, major section |
| `--space-20` | 80px | Marketing sections |
| `--space-24` | 96px | Marketing sections (desktop) |

### Spacing Rules

- **Stack spacing inside forms:** 24px between fields (`--space-6`), 8px between label and control (`--space-2`), 4px–8px between control and helper/error text.
- **Card internal spacing:** 24px padding desktop, 16px–20px mobile; 16px between card sections.
- **Related items closer than unrelated items** (proximity). A heading sits 8px above its content and ≥ 32px below the previous section.
- Never use arbitrary values like `13px` or `18px` for spacing.

---

## 5. Border Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-none` | 0 | Table cells, full-bleed media |
| `--radius-xs` | 4px | Checkboxes, small chips inside dense tables |
| `--radius-sm` | 6px | Tooltips, ID chips, small tags |
| `--radius-md` | 10px | **Buttons, inputs, selects, date fields, dropdown menus** |
| `--radius-lg` | 16px | **Cards**, alerts, popovers, date-picker panel |
| `--radius-xl` | 24px | Dialogs/modals, hero panels, dashboard feature widgets |
| `--radius-full` | 9999px | Badges, pills, avatars, toggles, progress bars, radio buttons |

**Rules**

- Nested radius: inner radius ≈ outer radius − padding, rounded down to the nearest token (minimum `--radius-sm`). E.g. a `--radius-lg` (16px) card with 8px padding → inner element uses `--radius-sm` (6px); with 24px padding the inner element may use any token up to `--radius-lg`.
- Do not mix pill buttons and 10px buttons in the same view. Buttons are `--radius-md` by default; `--radius-full` is reserved for chips, badges and toggles.
- Bottom sheets on mobile: `--radius-xl` top corners only.

---

## 6. Shadows, Elevation & Layering

Shadows are warm-tinted (based on `neutral-900` `#1F1A18`), soft and low-contrast. Elevation is expressed primarily through surface colour (white on warm canvas) and borders; shadows supplement it.

| Token | Value | Level | Usage |
|---|---|---|---|
| `--shadow-none` | `none` | 0 | Flat cards on canvas with `--color-border-subtle` |
| `--shadow-xs` | `0 1px 2px rgba(31, 26, 24, 0.06)` | 1 | Inputs, resting buttons (outline variant) |
| `--shadow-sm` | `0 1px 3px rgba(31, 26, 24, 0.08), 0 1px 2px rgba(31, 26, 24, 0.04)` | 1 | **Default card** |
| `--shadow-md` | `0 4px 12px rgba(31, 26, 24, 0.08), 0 2px 4px rgba(31, 26, 24, 0.04)` | 2 | Hovered interactive cards, dropdowns, popovers |
| `--shadow-lg` | `0 12px 24px rgba(31, 26, 24, 0.10), 0 4px 8px rgba(31, 26, 24, 0.04)` | 3 | Date-picker panel, toasts, sticky headers on scroll |
| `--shadow-xl` | `0 24px 48px rgba(31, 26, 24, 0.14), 0 8px 16px rgba(31, 26, 24, 0.06)` | 4 | Modals, dialogs, bottom sheets |
| `--shadow-focus` | `0 0 0 2px #FFFFFF, 0 0 0 4px #902C4E` | — | Focus ring (see §13.3) |
| `--shadow-focus-error` | `0 0 0 2px #FFFFFF, 0 0 0 4px #B42318` | — | Focus ring on invalid inputs |

### Z-Index Scale

| Token | Value | Usage |
|---|---|---|
| `--z-base` | 0 | Page content |
| `--z-raised` | 10 | Sticky table headers, raised cards |
| `--z-sticky` | 100 | Sticky top bar, sticky action bar |
| `--z-sidebar` | 200 | Mobile navigation drawer |
| `--z-dropdown` | 300 | Selects, menus, date pickers, popovers |
| `--z-overlay` | 400 | Modal scrim |
| `--z-modal` | 410 | Modal dialog |
| `--z-toast` | 500 | Toast notifications |
| `--z-tooltip` | 600 | Tooltips |

---

## 7. Layout & Responsive Grid

### 7.1 Breakpoints

Mobile-first; use `min-width` media queries.

| Token | Min width | Target |
|---|---|---|
| `--bp-xs` | 0 | Phones |
| `--bp-sm` | 640px | Large phones |
| `--bp-md` | 768px | Tablets (portrait) |
| `--bp-lg` | 1024px | Tablets (landscape), small laptops |
| `--bp-xl` | 1280px | Desktops |
| `--bp-2xl` | 1536px | Large desktops / clinic monitors |

### 7.2 Grid

| Range | Columns | Gutter | Outer margin |
|---|---|---|---|
| 0–639 | 4 | 16px | 16px |
| 640–767 | 4 | 16px | 24px |
| 768–1023 | 8 | 24px | 32px |
| 1024–1279 | 12 | 24px | 32px |
| ≥1280 | 12 | 24px | 40px (content max-width applies) |

### 7.3 Containers

| Token | Value | Usage |
|---|---|---|
| `--container-sm` | 640px | Auth, single-task forms, booking steps |
| `--container-md` | 768px | Reading content, health education articles |
| `--container-lg` | 1024px | Patient portal pages |
| `--container-xl` | 1280px | Default app content max width |
| `--container-2xl` | 1440px | Clinician dashboards, wide tables |
| `--content-measure` | 68ch | Long-form text width |

### 7.4 App Shell

| Token | Value |
|---|---|
| `--layout-topbar-height` | 64px (56px below `md`) |
| `--layout-sidebar-width` | 264px |
| `--layout-sidebar-width-collapsed` | 72px |
| `--layout-bottom-nav-height` | 64px + `env(safe-area-inset-bottom)` |
| `--layout-action-bar-height` | 72px (sticky form footer) |

Structure:

```
┌──────────────────────────────────────────────────────┐
│ Top bar (64px): logo · search · notifications · user │
├────────────┬─────────────────────────────────────────┤
│ Sidebar    │ Canvas (#FAF7F5)                         │
│ 264px      │  Page header (H1 + primary action)       │
│ (#FFFFFF)  │  Content grid (cards on #FFFFFF)         │
│            │                                          │
└────────────┴─────────────────────────────────────────┘
Mobile (<1024px): sidebar becomes a drawer; patient app uses bottom nav (max 5 items).
```

### 7.5 Page Patterns

- **Patient dashboard:** 12-col; primary column 8 cols (next appointment, pregnancy progress, tasks), secondary column 4 cols (messages, reminders, education). Stacks to one column below `lg`.
- **Clinician dashboard:** full-width 12-col at `--container-2xl`; KPI widgets in a 4-up row (3-col each), patient list table below, detail drawer on the right (480px).
- **Forms / booking flows:** single column in `--container-sm`, step indicator at top, sticky action bar at bottom on mobile.
- **Records / detail pages:** header card with patient summary, then tabs, then sections.

### 7.6 Density

| Mode | Applied to | Row height | Card padding | Body size |
|---|---|---|---|---|
| `comfortable` (default) | Patient-facing | 56px | 24px | 16px |
| `compact` | Clinician dashboards, tables | 44px | 16px | 14px |

Set via `data-density="compact"` on a container; components read density-scoped tokens. Minimum interactive target remains 24×24px (WCAG 2.5.8) in compact mode; 44×44px in comfortable mode.

---

## 8. Iconography & Imagery

### 8.1 Icons

- **Library:** [Lucide](https://lucide.dev) (outline style). Do not mix icon libraries.
- **Stroke width:** 1.75px at 20px and 24px; 2px at 16px.
- **Sizes:** `--icon-sm` 16px (inline with 14px text), `--icon-md` 20px (default, buttons, inputs), `--icon-lg` 24px (nav, card headers), `--icon-xl` 32px (feature tiles), `--icon-2xl` 48px (empty states, within a 96px tinted circle).
- **Colour:** inherits `currentColor`. Default `--color-text-secondary`; active/brand `--color-text-brand`; on lime backgrounds `--color-text-on-accent`.
- **Decorative icons** get `aria-hidden="true"`. **Icon-only buttons** MUST have an `aria-label` and a tooltip.
- **Recommended mappings:**

| Concept | Lucide icon |
|---|---|
| Appointment | `calendar-days` |
| Video consultation | `video` |
| In-person visit | `map-pin` |
| Clinician | `stethoscope` |
| Pregnancy / baby progress | `baby` (sparingly), `heart-pulse` |
| Medication / prescription | `pill` |
| Results / records | `file-text`, `clipboard-list` |
| Blood pressure | `activity` |
| Weight | `scale` |
| Messages | `message-circle` |
| Education | `book-open` |
| Privacy / hidden data | `eye-off`, `lock` |
| Success | `circle-check` |
| Warning | `triangle-alert` |
| Error | `circle-alert` |
| Info | `info` |

### 8.2 Imagery

- **Photography:** real, diverse people across ethnicity, age, body type, ability and family structure (solo parents, same-sex couples, surrogacy, adoption). Natural light, warm tones, candid moments. Clinicians shown as approachable professionals.
- **Avoid:** stock clichés (hands forming a heart on a bump), overly glossy/perfect imagery, newborns in distressing contexts, imagery that assumes a positive pregnancy outcome on general screens, clinical gore, needles in close-up.
- **Illustration:** flat, simple shapes using berry-100/200, lime-100/300 and neutral-200; no outlines thicker than 2px; no faces with exaggerated features; no cartoon babies or storks. Used for empty states and onboarding only.
- **Image treatment:** `--radius-lg` corners; `object-fit: cover`; always provide `alt` text (descriptive for content images, `alt=""` for decorative).
- **Medical diagrams** (fetal development, anatomy) are respectful, anatomically accurate and neutral in colour; offer them behind a "Show diagram" control in contexts where they may be unwanted.
- **Avatars:** circular (`--radius-full`), sizes 24/32/40/56/80px. Fallback = initials on `--color-bg-brand-muted` with `--color-text-brand`, semibold.

---

## 9. Motion

| Token | Value | Usage |
|---|---|---|
| `--duration-instant` | 100ms | Hover colour changes |
| `--duration-fast` | 150ms | Buttons, toggles, checkboxes |
| `--duration-normal` | 200ms | Dropdowns, tooltips, tabs |
| `--duration-slow` | 300ms | Modals, drawers, toasts |
| `--easing-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Most transitions |
| `--easing-enter` | `cubic-bezier(0, 0, 0, 1)` | Elements entering |
| `--easing-exit` | `cubic-bezier(0.3, 0, 1, 1)` | Elements leaving |

- Motion is subtle and functional: fades and ≤ 8px translations. No bouncing, no spring overshoot, no confetti for clinical events.
- **MUST** respect `prefers-reduced-motion: reduce` — disable transforms and set durations to `0.01ms`; keep opacity changes only.
- No auto-playing carousels. No animation that loops longer than 5 seconds (except loading spinners while loading).

---

## 10. Core Components

Every component specification includes anatomy, variants, sizes, states and rules. All interactive components support these states unless stated otherwise: **default, hover, focus-visible, active/pressed, disabled**, and where relevant **loading, selected, invalid, read-only**.

### 10.1 Buttons

**Anatomy:** container · optional leading icon · label · optional trailing icon · optional spinner.

**Sizes**

| Size | Height | Padding X | Font | Icon | Gap |
|---|---|---|---|---|---|
| `sm` | 32px | 12px | `--text-label-md` (14px) | 16px | 6px |
| `md` (default) | 40px | 16px | `--text-label-md` (14px) | 20px | 8px |
| `lg` | 48px | 20px | `--text-label-lg` (16px) | 20px | 8px |

Patient-facing mobile views SHOULD use `lg`. `sm` is for dense clinician tables only and MUST keep a 24×24 minimum target (use padding or a pseudo-element hit area to reach 44×44 on touch devices).

Radius `--radius-md`. Font weight 600. Min width 80px for text buttons.

**Variants**

| Variant | Background | Text | Border | Hover | Active | Use for |
|---|---|---|---|---|---|---|
| `primary` | `#902C4E` | `#FFFFFF` | none | bg `#7A2442` | bg `#631D36` | The single most important action ("Book appointment", "Save") |
| `secondary` | `#D4E990` | `#2F3B12` | none | bg `#BDD86A` | bg `#A9C95A` | Supportive positive action ("Add to calendar", "Log reading") |
| `outline` | `#FFFFFF` | `#902C4E` | 1.5px `#902C4E` | bg `#FBF2F5` | bg `#F6E1E8` | Secondary actions alongside primary ("Reschedule") |
| `ghost` | transparent | `#5E544F` | none | bg `#F3EEEB`, text `#1F1A18` | bg `#E7E0DC` | Tertiary/low-emphasis actions, toolbars |
| `destructive` | `#B42318` | `#FFFFFF` | none | bg `#912018` | bg `#912018` + inset shadow | Irreversible actions ("Cancel appointment") — only inside confirmation dialogs |
| `destructive-outline` | `#FFFFFF` | `#B42318` | 1.5px `#B42318` | bg `#FDECEA` | bg `#FDECEA` | Initiating a destructive flow from a page |
| `link` | transparent | `#902C4E` | none; underline | text `#7A2442` | text `#631D36` | Inline navigation |

**States**

| State | Treatment |
|---|---|
| Focus-visible | `box-shadow: var(--shadow-focus)`; no outline removal without replacement |
| Disabled | bg `#F3EEEB`, text `#A89D97`, border `#D5CCC7` (outline variants), `cursor: not-allowed`. Use `aria-disabled="true"` when the button must stay focusable to explain why. |
| Loading | Label replaced by "Booking…"-style text or kept with a 16px spinner before it; width locked; `aria-busy="true"`; click ignored. |

**Rules**

- One `primary` per view region. Primary sits on the right in dialogs/action bars on desktop; full-width and stacked (primary on top) on mobile.
- Labels are verbs + noun: "Book appointment", not "Submit" or "OK".
- Never use lime `secondary` with white text; never place a `secondary` button on a lime surface.
- Icon-only buttons: square (32/40/48), `aria-label` required, tooltip on hover/focus.

### 10.2 Inputs & Form Controls

**Anatomy:** label (above) · optional "(optional)" marker · helper text · control · validation message · optional character count.

| Property | Value |
|---|---|
| Height | 48px (default), 40px (`compact`) |
| Padding | 0 12px (text); 12px for textarea |
| Font | `--text-body-md` 16px, `--color-text-primary` |
| Background | `--color-bg-surface` |
| Border | 1px `--color-border-default` (`#8C807A`) |
| Radius | `--radius-md` |
| Placeholder | `--color-text-tertiary`; examples only ("e.g. 07700 900123"), never a label replacement |
| Label | `--text-label-md`, `--color-text-primary`, 8px above control |
| Helper text | `--text-body-sm`, `--color-text-secondary`, 4px below control |
| Textarea | min-height 120px, vertical resize only |

**States**

| State | Border | Background | Other |
|---|---|---|---|
| Default | 1px `#8C807A` | `#FFFFFF` | — |
| Hover | 1px `#5E544F` | `#FFFFFF` | — |
| Focus | 1px `#902C4E` | `#FFFFFF` | `--shadow-focus` |
| Filled | 1px `#8C807A` | `#FFFFFF` | — |
| Invalid | 1px `#B42318` + `inset 0 0 0 1px #B42318` (2px visual weight, no layout shift); focus uses `--shadow-focus-error` | `#FFFFFF` | `circle-alert` icon + message in `--color-text-error`; `aria-invalid="true"`; `aria-describedby` → message id |
| Disabled | 1px `#D5CCC7` | `#F3EEEB` | text `#A89D97` |
| Read-only | 1px `#E7E0DC` | `#F3EEEB` | text `#1F1A18`; still selectable/copyable |

**Rules**

- Labels are always visible (no floating labels, no placeholder-as-label).
- Mark **optional** fields with "(optional)", not required fields with asterisks. If most fields are optional, mark required ones with "(required)".
- Use correct `type`, `inputmode` and `autocomplete` (`tel`, `email`, `bday`, `postal-code`, `given-name`, `family-name`).
- Group related inputs with `` + ``.
- Units sit inside the control as a suffix adornment (e.g. "kg", "mmHg") with `aria-describedby` referencing the unit.
- Toggle switch: 44×24 track `--radius-full`, off track `#8C807A`, on track `#902C4E`, 20px white thumb, label to the left. Use for instant-effect settings only (e.g. "Appointment reminders").

**Validation**

- Validate on blur for format, on submit for completeness. Do not validate while the user is still typing for the first time.
- On submit with errors: show an **error summary** alert at the top of the form (`role="alert"`, focus moved to it) listing each error as a link to its field; also show inline messages.
- Error messages say what to do: "Enter your date of birth, for example 27 3 1990", not "Invalid input".
- Successful save: inline confirmation or toast; don't use green borders on every valid field.

### 10.3 Selects & Dropdowns

- **Native ``** is preferred for simple lists (≤ 15 options) and on mobile. Style the closed state like an input with a 20px `chevron-down` icon at 12px from the right.
- **Custom listbox / combobox** for searchable lists (clinicians, medications, clinics). Follow the WAI-ARIA combobox pattern: `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`.
- **Menu panel:** bg `--color-bg-surface`, 1px `--color-border-subtle`, `--radius-md`, `--shadow-md`, padding 4px, max-height 320px with scroll, offset 4px from trigger.
- **Option:** min-height 40px (44px touch), padding 8px 12px, `--text-body-md`. Hover/active-descendant bg `#FAF7F5`; selected bg `#F6E1E8`, text `#902C4E`, trailing `check` icon.
- **Keyboard:** ↑/↓ moves, Enter selects, Esc closes and returns focus, Home/End jump, type-ahead filters.
- **Action menus** (e.g. "More actions" kebab): `role="menu"`, destructive items last, separated by a divider, text `--color-text-error`.

### 10.4 Date Pickers

Healthcare dates are high-stakes (due dates, last menstrual period, appointment times). Use the right control for the task:

| Task | Control |
|---|---|
| Date of birth, LMP, known past dates | **Three separate fields** (Day / Month / Year), numeric `inputmode`, `autocomplete="bday-day"` etc. No calendar. |
| Appointment booking | **Calendar grid + time-slot list** |
| Date ranges (clinician reports) | Two date inputs with calendar popovers |

**Calendar panel**

| Property | Value |
|---|---|
| Container | `--color-bg-surface`, `--radius-lg`, `--shadow-lg`, padding 16px, width 320px |
| Header | Month + year (`--text-heading-xs`), previous/next icon buttons (40px) |
| Weekday row | `--text-label-sm`, `--color-text-tertiary`, abbreviated ("Mo"), with `abbr` full name |
| Day cell | 40×40px (44×44 on touch), `--radius-full`, `--text-body-sm` tabular |
| Today | 1.5px border `#902C4E`, text `#902C4E` |
| Selected | bg `#902C4E`, text `#FFFFFF`, semibold |
| Available (booking) | text `#1F1A18`; small 4px lime-600 dot beneath |
| Unavailable / disabled | text `#A89D97`, strike-through not used; `aria-disabled="true"` |
| Hover | bg `#F6E1E8` |
| In-range (ranges) | bg `#FBF2F5` |

**Time slots:** chips in a wrapping grid, 44px tall, `--radius-md`, 1px `--color-border-default`; selected = berry fill with white text and a `check` icon. Group by Morning / Afternoon / Evening. Show the timezone if users may be in a different one.

**Rules**

- Grid uses `role="grid"`; arrow keys move by day, PageUp/PageDown by month, Home/End to week start/end, Enter selects.
- Always show the selected date in words: "Thursday 12 March 2026, 10:30am".
- Date format: `D MMMM YYYY` in UI ("12 March 2026"); never ambiguous numeric formats like 03/12/26. Week starts on Monday unless the locale dictates otherwise.

### 10.5 Checkboxes & Radio Buttons

| Property | Checkbox | Radio |
|---|---|---|
| Control size | 20×20px | 20×20px |
| Radius | `--radius-xs` (4px) | `--radius-full` |
| Border | 1.5px `#8C807A` | 1.5px `#8C807A` |
| Checked | bg `#902C4E`, white 14px `check` icon | border `#902C4E`, 10px inner dot `#902C4E` |
| Indeterminate | bg `#902C4E`, white 12px bar | — |
| Hover | border `#5E544F` | border `#5E544F` |
| Focus | `--shadow-focus` on control | same |
| Disabled | border `#D5CCC7`, bg `#F3EEEB`; checked bg `#D5CCC7` | same |
| Invalid | border `#B42318` + group-level error message | same |
| Label | `--text-body-md`, 12px gap from control | same |
| Hit area | Whole row (control + label) ≥ 44px tall | same |

**Choice cards** (large radio/checkbox tiles, e.g. "Video call" vs "In person"): card with 1px `--color-border-default`, `--radius-lg`, padding 16px, icon + title + description. Selected: 2px `#902C4E` border, bg `#FBF2F5`, check indicator top-right. Never indicate selection by colour alone — the control/check icon must be visible.

**Rules:** radios for single choice from 2–6 options, a select beyond that. Always wrap in `fieldset` + `legend`. Consent checkboxes are never pre-ticked.

### 10.6 Cards

| Property | Value |
|---|---|
| Background | `--color-bg-surface` |
| Border | 1px `--color-border-subtle` |
| Radius | `--radius-lg` |
| Shadow | `--shadow-sm` |
| Padding | 24px (`comfortable`), 16px (`compact`, mobile ≤ 20px) |
| Header | Title `--text-heading-sm`, optional overline `--text-label-sm` uppercase `--color-text-tertiary`, optional action (ghost button/link) right-aligned |
| Section divider | 1px `--color-border-subtle`, 16px vertical margin |
| Footer | Actions right-aligned (desktop), full-width (mobile) |

**Variants**

| Variant | Treatment | Use |
|---|---|---|
| `default` | As above | Most content |
| `interactive` | Hover: `--shadow-md`, border `#D5CCC7`; focus-visible ring; whole card is one link/button with a single accessible name | Navigational cards |
| `selected` | 2px `#902C4E` border, bg `#FFFFFF` | Selection within lists |
| `brand` | bg `--color-bg-brand-subtle`, border `#EDC3D1` | Welcome, featured content |
| `accent` | bg `--color-bg-accent-subtle`, border `#E5F1B6`, text `#2F3B12`/`#1F1A18` | Positive milestones, completed tasks |
| `flat` | No shadow, bg `--color-bg-surface-subtle` | Nested content inside another card |

**Rules:** don't nest shadowed cards inside shadowed cards (use `flat`). A clickable card must not contain other interactive elements unless it uses the "stretched link" pattern with secondary buttons raised above it (`position: relative; z-index: 1`).

### 10.7 Badges & Status Indicators

**Badge**

| Property | Value |
|---|---|
| Height | 24px (md), 20px (sm) |
| Padding | 0 10px (md), 0 8px (sm) |
| Radius | `--radius-full` |
| Font | `--text-label-sm` without uppercase, 12px, weight 600 |
| Icon | optional 14px leading icon or 6px dot |

| Variant | Background | Text | Use |
|---|---|---|---|
| `neutral` | `#F3EEEB` | `#463E3A` | Draft, Not started |
| `brand` | `#F6E1E8` | `#7A2442` | New, Primary category |
| `accent` | `#D4E990` | `#2F3B12` | Milestone, Completed visit (decorative positive) |
| `success` | `#E8F5EE` | `#16603B` | Confirmed, Within range, Collected |
| `warning` | `#FEF4E2` | `#7A4800` | Review recommended, Due soon, Pending |
| `error` | `#FDECEA` | `#912018` | Urgent, Overdue, Failed |
| `info` | `#EAF2FB` | `#184B85` | Information, In progress |
| `solid-*` | `{status}-600` | `#FFFFFF` | High-emphasis counts on clinician views only |

**Status dot:** 8px circle + text label (always). **Count badge** (notifications): min 20×20px, `--radius-full`, bg `#902C4E`, text white 12px semibold; "99+" cap; accessible name "3 unread messages".

**Rules:** max one badge per item title; status text uses plain words ("Confirmed", not "CONF"); badges never carry the only copy of critical information.

### 10.8 Navigation & Sidebars

**Sidebar (desktop ≥ 1024px)**

| Property | Value |
|---|---|
| Width | 264px; collapsible to 72px (icons + tooltips) |
| Background | `--color-bg-surface`, right border 1px `--color-border-subtle` |
| Padding | 16px 12px |
| Section label | `--text-label-sm` uppercase, `--color-text-tertiary`, 24px top margin |
| Nav item | 44px tall, padding 0 12px, `--radius-md`, 24px icon + `--text-label-lg` label, 12px gap |
| Default | text `#5E544F`, icon `#5E544F` |
| Hover | bg `#FAF7F5`, text `#1F1A18` |
| Active (current page) | bg `#F6E1E8`, text `#902C4E`, icon `#902C4E`, weight 700, 3px berry left indicator; `aria-current="page"` |
| Focus | `--shadow-focus` inset by 2px |
| Footer | User profile summary, "Help & support", "Sign out" |

**Top bar:** 64px, bg `--color-bg-surface`, bottom border 1px `--color-border-subtle`, gains `--shadow-lg` only when content scrolls under it. Contains logo, global search (clinician), notifications, profile menu.

**Bottom navigation (patient mobile < 768px):** 3–5 items, 64px + safe area, icon (24px) above label (12px semibold); active item text/icon `#902C4E` with a 32×4px berry indicator pill above the icon.

**Mobile drawer (< 1024px, clinician):** slides from left, 296px max (or 85vw), `--shadow-xl`, scrim `--color-bg-overlay`, focus trapped, Esc closes.

**Breadcrumbs:** `--text-body-sm`, separator `chevron-right` 16px `#756A64`, current page `--color-text-primary` not linked.

**Skip link:** first focusable element: "Skip to main content", visible on focus, berry bg with white text.

**Recommended patient IA:** Home · Appointments · My pregnancy (or "My care" when not pregnant) · Messages · Records. Profile & settings in the profile menu.

### 10.9 Tabs

| Property | Value |
|---|---|
| Style | Underline tabs (default); pill tabs (`segmented`) for 2–4 view toggles |
| Tab height | 44px, padding 0 16px |
| Font | `--text-label-md` (14px) semibold; 16px on patient views |
| Default text | `#5E544F` |
| Hover | text `#1F1A18`, bg `#FAF7F5` |
| Selected (underline) | text `#902C4E`, 3px bottom border `#902C4E`, `--radius-full` on indicator ends |
| Tab list border | 1px bottom `--color-border-subtle` |
| Segmented container | bg `#F3EEEB`, `--radius-md`, padding 4px; selected segment bg `#FFFFFF`, `--shadow-xs`, text `#1F1A18` |
| Disabled | text `#A89D97` |

**Behaviour:** WAI-ARIA tabs pattern (`role="tablist"`, `tab`, `tabpanel`, `aria-selected`, `aria-controls`). ←/→ moves between tabs, Home/End jump. Automatic activation for instant panels; manual (Enter/Space) when panels load data. On mobile, the tab list scrolls horizontally with fade edges; no more than 6 tabs. Optional count after label: "Results (2)".

### 10.10 Dialogs & Modals

| Property | Value |
|---|---|
| Sizes | `sm` 400px (confirmations), `md` 560px (forms), `lg` 720px (detail/review) |
| Max height | `calc(100vh - 64px)`; body scrolls, header and footer fixed |
| Background | `--color-bg-surface`, `--radius-xl`, `--shadow-xl` |
| Padding | 24px (header/body/footer); 20px on mobile |
| Header | Title `--text-heading-sm`, close icon button (40px, `aria-label="Close"`) top-right |
| Footer | Actions right-aligned, 12px gap; primary rightmost |
| Scrim | `--color-bg-overlay`, click closes only for non-destructive, non-form dialogs |
| Mobile (< 640px) | Becomes a bottom sheet: full width, top radius 24px, drag handle 40×4px `#D5CCC7`; or full screen for long forms |
| Motion | Fade + 8px translateY, `--duration-slow`, `--easing-enter` |

**Accessibility:** use `` or `role="dialog"` + `aria-modal="true"`, `aria-labelledby` (title), `aria-describedby` (body). Focus moves to the first focusable element (or the dialog title for read-only content); focus is trapped; Esc closes; focus returns to the trigger on close. Background is `inert`.

**Confirmation dialog pattern** (e.g. cancelling an appointment):
- Title states the action as a question: "Cancel your appointment on 12 March?"
- Body explains consequences: "Your slot will be offered to someone else. You can book a new appointment at any time."
- Actions: `ghost` "Keep appointment" + `destructive` "Cancel appointment". Never "Yes/No".

**Rules:** no modal on page load (except session-timeout warnings); no stacked modals; never put critical health information only in a modal that can be dismissed without reading.

### 10.11 Alerts & Notifications

**Inline alert (banner within page)**

| Property | Value |
|---|---|
| Layout | 20px icon · title (`--text-label-lg`) · body (`--text-body-sm`/`md`) · optional actions · optional close |
| Background / border / icon / text | `--color-status-{type}-bg` / 1px `--color-status-{type}-border` + 4px left border `{type}-600` / `--color-status-{type}-icon` / `--color-text-primary` for body, `{type}-700` for title |
| Radius | `--radius-lg` |
| Padding | 16px |
| Types | `info`, `success`, `warning`, `error`, plus `brand` (berry-50 bg, berry-600 icon) for non-status announcements |

**Toast**

| Property | Value |
|---|---|
| Position | Bottom-right (desktop, 24px offset), bottom-centre above bottom nav (mobile) |
| Style | bg `--color-bg-inverse` `#463E3A`, text `#FFFFFF`, `--radius-md`, `--shadow-lg`, max-width 400px, padding 12px 16px |
| Status icon | Use `{type}-200` tints for icons on dark bg (e.g. success icon `#A6D9BC`) |
| Duration | 6s minimum; persistent if it contains an action; pause on hover/focus |
| Max visible | 3, stacked newest on top |
| ARIA | `role="status"` (polite) for success/info; `role="alert"` only for errors |

**System-level banner:** full-width, top of content, for service status ("Video consultations are currently unavailable. We're working on it."). Not dismissible while the issue persists.

**Rules:**
- Errors in a form use the error summary pattern (§10.2), not toasts.
- Never use toasts for clinical results or anything the user must act on.
- Notification centre items: unread indicator 8px berry dot + bold title; read items regular weight.

### 10.12 Tables

| Property | Value |
|---|---|
| Container | Card (`--radius-lg`, border subtle), `overflow-x: auto` with visible scroll affordance |
| Header row | bg `--color-bg-surface-sunken` `#F3EEEB`, `--text-label-md`, `--color-text-secondary`, height 44px, sticky on scroll |
| Body row | height 56px (`comfortable`) / 44px (`compact`); `--text-body-sm` (clinician) or `--text-body-md` (patient); bottom border 1px `--color-border-subtle` |
| Cell padding | 0 16px; first/last cell 24px |
| Numeric columns | Right-aligned, `tabular-nums`, unit in header ("Weight (kg)") |
| Hover | bg `#FAF7F5` |
| Selected | bg `#FBF2F5`, checkbox checked |
| Sort | Header button with `arrow-up-down` / `arrow-up` / `arrow-down` icon; `aria-sort` on `th` |
| Row actions | Kebab menu in last column or ghost icon buttons; visible on focus, not only hover |
| Pagination | Bottom; "Showing 1–20 of 134 patients"; page size 20/50/100 |
| Empty | Empty state (§10.14) inside the table body spanning all columns |
| Loading | 5 skeleton rows matching column widths |

**Responsive:** below `md`, convert rows to stacked cards (label: value pairs) rather than horizontal scrolling for patient-facing tables. Clinician tables MAY scroll horizontally with the first column (patient name) sticky.

**Semantics:** real ``, `` (can be visually hidden), ``. Do not build tables from divs.

### 10.13 Tooltips

| Property | Value |
|---|---|
| Background | `--color-bg-inverse` `#463E3A` |
| Text | `#FFFFFF`, `--text-body-sm`, max-width 280px |
| Padding | 6px 10px |
| Radius | `--radius-sm` |
| Arrow | 6px |
| Delay | 300ms show on hover, immediate on focus; 100ms hide |
| Offset | 8px from trigger |

**Rules:** tooltips label or briefly describe (≤ 1 sentence); never contain interactive content or essential information. They appear on hover **and** keyboard focus, are dismissible with Esc without moving focus, and stay visible while hovered (WCAG 1.4.13). Use `aria-describedby` (or `aria-label` for icon buttons). For medical term explanations, prefer an inline "What is this?" toggle or popover with focusable content.

### 10.14 Empty States

**Anatomy:** illustration or 48px icon in a 96px circle (`--color-bg-brand-subtle` with berry icon, or `--color-bg-accent-subtle` with `#45561A` icon) · title `--text-heading-sm` · body `--text-body-md` `--color-text-secondary`, max 2 lines · optional primary or outline action. Centred, max-width 400px, 48px vertical padding.

| Context | Title | Body | Action |
|---|---|---|---|
| No appointments | "No upcoming appointments" | "When you book an appointment, it'll appear here." | "Book an appointment" |
| No messages | "Your inbox is clear" | "Messages from your care team will appear here." | — |
| No results yet | "No results yet" | "We'll let you know as soon as your results are ready. This usually takes 3–5 working days." | — |
| Search, no match | "No patients match "Jo Smi"" | "Check the spelling or search by date of birth or health ID." | "Clear search" |
| Error loading | "We couldn't load your records" | "This is on our side. Please try again in a moment." | "Try again" |

**Rules:** never blame the user; always explain what will make content appear; don't use celebratory illustrations for empty clinical lists.

### 10.15 Loading States

| Pattern | When | Spec |
|---|---|---|
| **Skeleton** | Initial page/section load (> 300ms expected) | Blocks bg `#F3EEEB`, `--radius-sm` (text) / `--radius-lg` (cards); shimmer gradient `#F3EEEB → #FAF7F5 → #F3EEEB` 1.5s linear infinite; shimmer disabled under reduced motion; match final layout dimensions to prevent layout shift |
| **Spinner** | Inline actions, buttons | 16/20/24px, 2px stroke, track `#E7E0DC`, arc `#902C4E` (on berry buttons: track `rgba(255,255,255,0.35)`, arc `#FFFFFF`); 0.8s rotation |
| **Progress bar** | Uploads, multi-step tasks with known progress | 8px height, `--radius-full`, track `#F3EEEB`, fill `#902C4E` (task) or `#D4E990` with `#7D9A2F` 1px border (milestone progress); `role="progressbar"` with `aria-valuenow`/`min`/`max` |
| **Full-page** | Rare: initial app boot | Centred logo + spinner + "Getting things ready…" |

**Rules:** don't show a loader for < 300ms (delay its appearance); after 10s show reassurance text ("This is taking longer than usual…"); announce completion politely for screen readers (`aria-live="polite"`); containers being loaded get `aria-busy="true"`.

---

## 11. Healthcare Components

All healthcare components are built from core components and tokens above. Each MUST follow the privacy rules (§15) and status language (§16).

### 11.1 Appointment Card

**Purpose:** show a single appointment with its key details and next actions.

**Anatomy**

```
┌───────────────────────────────────────────────────────┐
│ [Date block]  Antenatal check-up         [Badge]      │
│  THU          with Midwife Amara Okafor               │
│  12           🕑 10:30am – 11:00am (30 min)           │
│  MAR          📍 Riverside Clinic, Room 4  | 🎥 Video │
│ ───────────────────────────────────────────────────── │
│ What to bring: urine sample, maternity notes          │
│ [Join video call] [Reschedule]  [Add to calendar]     │
└───────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| Date block | 64×72px, `--radius-md`, bg `--color-bg-brand-subtle`, weekday `--text-label-sm` uppercase `#7A2442`, day `--text-heading-md` `#902C4E`, month `--text-label-sm` uppercase |
| Title | Appointment type, `--text-heading-xs` |
| Clinician | "with {role} {name}" `--text-body-sm` secondary |
| Time | Icon `clock` 16px + time range + duration; include timezone if relevant |
| Location | `map-pin` + clinic name (link to directions) **or** `video` + "Video consultation" |
| Preparation | Optional `flat` section, `--text-body-sm` |
| Actions | Primary contextual action (see states) + outline/ghost secondary |

**States**

| State | Badge | Visual change | Primary action |
|---|---|---|---|
| Upcoming | `success` "Confirmed" | default | "View details" / "Reschedule" (outline) |
| Pending confirmation | `warning` "Awaiting confirmation" | — | "View request" |
| Today | `brand` "Today" | 2px `#902C4E` left border; date block bg `#902C4E`, text white | "Check in" or "Join video call" (primary, enabled 10 min before) |
| In progress | `info` "In progress" | — | "Rejoin call" |
| Completed | `accent` "Completed" | date block bg `--color-bg-surface-sunken` | "View summary" |
| Cancelled | `neutral` "Cancelled" | title `--color-text-secondary`, no strike-through on details | "Book again" |
| Not attended | `neutral` "Not attended" | — | "Rebook appointment" (use non-judgmental wording; never "No-show" in patient views) |

**Rules:** time and date are always in words + numerals; the accessible name of the card is "{Type} on {full date} at {time}"; cancel is a `destructive-outline` behind a confirmation dialog, not a primary button. **Compact variant** (list rows, clinician schedule): single row, 64px tall, time on the left in `tabular-nums`, patient initials avatar, type, status badge.

### 11.2 Doctor / Specialist Profile Card

| Element | Spec |
|---|---|
| Avatar | 56px (list) / 80px (detail), circular; photo or initials fallback |
| Name | `--text-heading-xs`; title prefix ("Dr", "Midwife") |
| Role & specialty | `--text-body-sm` secondary: "Consultant Obstetrician · Maternal-fetal medicine" |
| Credentials | Optional `--text-caption` tertiary: registration body + number masked unless public |
| Languages | Chips (neutral badge): "English", "Yoruba", "French" |
| Pronouns | Optional, shown after name in secondary text if provided by the clinician |
| Availability | `success` dot + "Next available: Tue 17 Mar, 9:00am" or `neutral` "No availability this month" |
| Consultation types | Icons + labels: "In person", "Video", "Phone" |
| Actions | Primary "Book with Dr Patel"; ghost "View profile" |
| Bio (detail view) | `--text-body-md`, ≤ 80 words, first person welcome tone |

**Variants:** `list` (horizontal, avatar left), `grid` (vertical, centred avatar, 280px min width), `selected` (in booking flow; selected card styling §10.6).
**Rules:** no star ratings on clinicians in clinical contexts; no clinician personal contact details; photos must be professional and consented.

### 11.3 Consultation Summary

**Purpose:** a readable record of what happened at a visit, written for the patient.

**Structure (in order):**

1. **Header:** consultation type, date, clinician, location/mode, duration. Overline "Consultation summary".
2. **Key takeaways** — `brand` card variant; max 3 bullet points in plain language. This is the first content block.
3. **What we discussed** — body text, `--text-body-md`, measure 68ch.
4. **Measurements taken** — Health Metric chips (§11.9) in a 2–4 column grid.
5. **Plan & next steps** — numbered list; each step with owner ("You", "Your midwife") and due date.
6. **Prescriptions** — Prescription Cards (§11.8) in compact variant.
7. **Referrals & tests ordered** — list with status badges.
8. **Next appointment** — compact Appointment Card.
9. **Footer actions:** "Download PDF" (outline), "Message your care team" (ghost), "Print" (ghost). Footer meta: "Summary written by Midwife Amara Okafor · Last updated 12 Mar 2026, 2:14pm".

**Rules:** clinical terms have plain-language explanations on first use ("pre-eclampsia (a condition that affects blood pressure in pregnancy)"); clinician-only notes are never rendered in the patient view; long summaries offer an in-page table of contents. Print stylesheet: remove nav, use black text, keep the berry logo, add page numbers and patient name + masked ID in the header.

### 11.4 Patient Information Card

**Used in:** clinician views (patient header, list detail) and patient profile.

| Element | Spec |
|---|---|
| Avatar | 56px initials (photos only if patient-uploaded) |
| Name | Preferred name first, `--text-heading-sm`; legal name in secondary text if different ("Legal name: …") |
| Pronouns | If provided, after name |
| Key identifiers | Age + DOB ("34 years · 27 Mar 1992"), masked health ID in an ID chip (`--text-id-sm`, `--color-bg-surface-sunken`, `--radius-sm`): `•••• •• 4821` with "Show" toggle |
| Pregnancy status | e.g. "28 weeks + 3 days · Due 14 Jun 2026" with `brand` badge "Trimester 3" |
| Care team | "Lead midwife: …", "Consultant: …" |
| Alerts | Allergies and critical flags in a dedicated row, `error`-tinted badges with icons: "Allergy: Penicillin". Never hidden behind a toggle. |
| Contact | Phone/email masked by default in clinician list views; full on detail with audit-logged reveal |
| Actions | "Open record", "Message", "Book appointment" |

**Variants:** `header` (full-width sticky summary at top of a patient record, 1 row on desktop), `card` (dashboard), `compact` (table row/list).
**Rules:** allergies/critical alerts always visible; sensitive categories (§15.3) never appear on this card; no patient data in browser tab title beyond initials (§15).

### 11.5 Pregnancy Milestone Card

**Purpose:** show progress through pregnancy with warmth and accuracy, without being childish.

```
┌──────────────────────────────────────────────────────┐
│ OVERLINE: YOUR PREGNANCY                              │
│ 24 weeks + 3 days                    [Trimester 2]    │
│ ████████████████░░░░░░░░░░░ 61%  ·  Due 18 Jul 2026  │
│ 1st ─────────── 2nd ●───────── 3rd                    │
│ ──────────────────────────────────────────────────── │
│ This week: Your baby's hearing is developing.        │
│ Coming up: Glucose screening (24–28 weeks)           │
│ [Read about week 24]                                  │
└──────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| Container | `brand` card variant or default card with lime progress |
| Gestational age | `--text-metric-lg`, `--color-text-primary`; format "24 weeks + 3 days" (screen-reader text identical; never "24+3" alone in patient views) |
| Trimester badge | `brand` badge |
| Progress bar | 12px, `--radius-full`, track `#F3EEEB`, fill `#D4E990` with 1px `#7D9A2F` border; trimester ticks at 13 and 27 weeks (`#5E544F`, 2px); `role="progressbar"`, `aria-valuetext="24 weeks and 3 days of 40 weeks"` |
| Due date | "Due 18 Jul 2026" + helper "(estimated)" |
| This week | 1–2 sentences, `--text-body-md`; optional tasteful illustration (line art, no cartoon) |
| Coming up | Next screening/visit with date range |
| Action | Link to education content |
| Milestone reached | `accent` card variant, `circle-check` icon in `#45561A`, title "You've reached 28 weeks" — no confetti |

**Sensitivity rules (MUST):**
- Provide a user setting to **pause or hide pregnancy progress content**. Respect it everywhere (dashboard, emails, push).
- If a pregnancy loss, termination or stillbirth is recorded, **immediately suppress** all milestone, size-comparison and countdown content and switch to supportive care content. Never show "Congratulations" or progress automatically after a change in pregnancy status.
- Size comparisons (e.g. "about the size of a melon") are **off by default** and opt-in.
- Don't assume gender of baby, number of babies, or that the user is the person who is pregnant (support partner/surrogate views with "Your baby" vs "The baby" copy configuration).

### 11.6 Antenatal Visit Tracker

**Purpose:** show the schedule of antenatal appointments and screenings across the pregnancy.

**Pattern:** vertical timeline (mobile and desktop); horizontal stepper allowed ≥ `lg` when ≤ 8 visible steps.

| Step state | Marker (24px circle) | Connector | Label | Badge |
|---|---|---|---|---|
| Completed | bg `#D4E990`, `check` icon `#2F3B12`, border 1px `#7D9A2F` | solid 2px `#7D9A2F` | `--color-text-primary` | `accent` "Completed" |
| Current / next | bg `#902C4E`, white step number, focus-ring-like halo `0 0 0 4px #F6E1E8` | dashed 2px `#D5CCC7` after | semibold `--color-text-primary` | `brand` "Next: 12 Mar" |
| Upcoming | bg `#FFFFFF`, 2px `#8C807A` border, number `#5E544F` | dashed 2px `#D5CCC7` | `--color-text-secondary` | — |
| Needs booking | bg `#FFFFFF`, 2px `#9A5B00` border, `calendar-plus` icon | dashed | primary | `warning` "Book by 20 Mar" + "Book now" link |
| Missed / not attended | bg `#F3EEEB`, `minus` icon `#5E544F` | — | secondary | `neutral` "Not attended" + "Rebook" |
| Not applicable / declined | bg `#F3EEEB`, `x` icon | — | secondary | `neutral` "Declined" |

**Each step shows:** week range ("16 weeks"), visit name ("Antenatal check-up"), what happens (expandable), date (if booked), outcome summary link (if completed).

**Rules:** the list is an ordered list (``); each step's state is in text (visually hidden if needed: "Completed", "Next appointment"); never show red for a missed visit in patient views; postnatal schedule uses the same component titled "Postnatal check-ins".

### 11.7 Medical History Sections

**Pattern:** accordion sections inside a card, grouped by category.

| Element | Spec |
|---|---|
| Section header | 56px button, `--text-heading-xs`, leading category icon, trailing `chevron-down` (rotates 180°), count badge ("3"), last updated caption |
| Expanded content | 16px padding, list of entries |
| Entry | Title (condition/procedure) `--text-label-lg`; date or date range; status badge (`info` "Active", `neutral` "Resolved"); notes `--text-body-sm` secondary; source ("Recorded by Dr Patel") |
| Empty section | Inline text "No {category} recorded" + "Add" link if patient-editable |

**Standard categories (in order):** Allergies & alerts (always expanded, never collapsible) · Current conditions · Previous pregnancies (obstetric history) · Gynaecological history · Surgeries & procedures · Medications (links to prescriptions) · Family history · Immunisations · Lifestyle.

**Sensitive categories** (termination, miscarriage, fertility treatment, sexual health, mental health, safeguarding): collapsed by default, header shows "Sensitive information — select to view" with `lock` icon, content revealed on click, reveal not persisted across sessions (§15.3).

**Accessibility:** WAI-ARIA accordion (`button` with `aria-expanded`, `aria-controls`); multiple sections can be open; "Expand all / Collapse all" control at top.

### 11.8 Prescription Card

| Element | Spec |
|---|---|
| Icon | `pill` 24px in 40px circle `--color-bg-brand-subtle` |
| Medication name | Generic name `--text-heading-xs`; brand name in secondary text |
| Strength & form | "400 micrograms · tablet" — always with units spelled in full or standard abbreviation (mg, mcg → prefer "micrograms" in patient view to avoid mg/mcg confusion) |
| Dosage instructions | `--text-body-md`, plain language: "Take 1 tablet once a day" |
| Schedule | Optional time chips ("Morning") |
| Duration | "Until 12 weeks of pregnancy" / "Ongoing" |
| Prescriber & date | `--text-caption` tertiary |
| Refills / supply | Progress bar (berry fill) "18 of 28 tablets left (estimate)" |
| Status badge | `success` "Active", `warning` "Running low", `neutral` "Completed", `neutral` "Stopped", `info` "Ready to collect" |
| Safety info | Pregnancy/breastfeeding safety note as `info` inline alert if provided by clinician |
| Reference | Prescription ID in an ID chip (`--text-id-sm`) |
| Actions | "Request repeat" (secondary), "View leaflet" (link), "Report a side effect" (ghost) |

**Rules:** never truncate dosage instructions; numbers and units must not break across lines (`white-space: nowrap` on "400 micrograms"); use leading zeros for decimals ("0.5 mg") and never trailing zeros ("5 mg", not "5.0 mg"); stopped medications move to a "Past medications" section.

### 11.9 Health Metric Display

**Purpose:** show a reading (blood pressure, weight, blood glucose, haemoglobin, fetal heart rate, temperature, symphysis-fundal height) with context.

**Variants**

| Variant | Use | Layout |
|---|---|---|
| `tile` | Dashboard widget | Label · value · unit · status · trend · last updated |
| `chip` | Inside summaries | Label + value + unit inline, status icon |
| `chart` | Detail view | Line chart with expected-range band + data table toggle |

**Tile spec**

| Element | Spec |
|---|---|
| Label | `--text-label-md` secondary + icon (e.g. `activity` for BP) |
| Value | `--text-metric-lg` (`--text-metric-xl` on detail), `tabular-nums`, `--color-text-primary` (never coloured by status) |
| Unit | `--text-body-md` secondary, 4px after value: "118/76 mmHg" |
| Status | Badge with icon + text (§16 vocabulary) |
| Expected range | `--text-caption`: "Expected range: below 140/90" |
| Trend | `trending-up`/`trending-down`/`minus` icon + text "Up 1.2 kg since last visit". Direction is described neutrally; no green/red arrows implying good/bad. |
| Last updated | `--text-caption` tertiary: "Measured 12 Mar, 10:42am at clinic" or "Self-reported" |
| Action | "Log a reading" (secondary button) for self-monitored metrics |

**Chart rules:** expected range shaded `--color-chart-range` with a legend; patient readings in `--color-chart-1` with 6px point markers; out-of-range points use a distinct marker shape (triangle) plus annotation, not just colour; axis labels `--text-caption`; always offer "View as table"; charts have a text summary (``): "Your blood pressure has stayed within the expected range over your last 6 readings."

**Weight in pregnancy:** neutral presentation only. No status colour, no "gain/loss" judgement words in patient view; show only when the clinician has enabled weight tracking for that patient.

### 11.10 Patient Dashboard Widgets

All widgets are cards with a consistent header (icon + title + optional "View all" link) and a minimum height of 160px. Grid: 8-col primary + 4-col secondary on desktop; single column on mobile in the priority order below.

| Priority | Widget | Content | Empty state |
|---|---|---|---|
| 1 | **Greeting & next step** | "Good morning, Ana" + the single most relevant next action (e.g. "Your glucose screening is due — book by 20 Mar"). `brand` card variant. | "You're all caught up" |
| 2 | **Next appointment** | Appointment Card (today/upcoming state) | "No upcoming appointments" + Book |
| 3 | **Pregnancy progress** | Pregnancy Milestone Card (respecting hide setting) | Hidden entirely when not applicable/paused |
| 4 | **Tasks & reminders** | Checklist (max 5): forms to complete, readings to log, tests to book; each with due date | "Nothing to do right now" |
| 5 | **Latest readings** | 2–3 Health Metric tiles | "No readings yet" + Log reading |
| 6 | **Messages** | Last 3 threads: sender, generic preview, time, unread dot | "Your inbox is clear" |
| 7 | **Medications** | Active prescriptions (compact) | "No current medications" |
| 8 | **Learn** | 2–3 education articles relevant to stage; image 16:9, title, read time | — |
| — | **Get help now** (persistent) | Small `flat` card: "Worried about something? Call your maternity unit: 0123 456 789. In an emergency, call 999." Always visible; localise numbers. | — |

**Clinician dashboard widgets:** Today's clinic list (compact appointment rows), KPI tiles (patients seen, pending results, overdue tasks — value + label + delta), Flagged results queue (table with `warning`/`error` badges, sorted by urgency), Messages needing reply, Referrals pending.

---

## 12. Content & Microcopy

### 12.1 Voice & Tone

| Principle | Do | Don't |
|---|---|---|
| Warm, not over-familiar | "Hi Ana, here's what's coming up." | "Hey mama! 💕" |
| Clear, not clinical | "Your blood test results are ready." | "Haematology panel resulted." |
| Calm, not alarming | "This reading is higher than expected. Please call your maternity unit today." | "WARNING: Abnormal BP!" |
| Supportive, not patronising | "You can change this at any time." | "Don't worry, it's easy!" |
| Inclusive | "You and your baby", "your partner or support person" | "Mum and dad", "your husband" |
| Direct | "Book your 20-week scan" | "Click here to proceed with booking" |

- Write at a reading age of 9–11 (UK) / grade 6–8 (US) for patient content.
- Use "you" and "your"; use "we" for the service.
- Sentence case everywhere. No exclamation marks in clinical contexts; at most one in celebratory moments.
- Avoid euphemisms that cause confusion; explain medical terms in plain language on first use.
- Use gender-inclusive language in general content ("pregnant people", "women and birthing people" where appropriate) while respecting how each user describes themselves (user-set pronouns and terms).
- No emoji in product UI.

### 12.2 Microcopy Patterns

| Situation | Copy |
|---|---|
| Booking confirmed | "You're booked in. We've sent the details to your email." |
| Reschedule | "Choose a new time. Your current appointment stays booked until you confirm." |
| Cancel confirmation | "Cancel your appointment on 12 March?" / "Keep appointment" / "Cancel appointment" |
| Form saved | "Your changes have been saved." |
| Session timeout warning | "For your privacy, we'll sign you out in 2 minutes. Do you want to stay signed in?" |
| Result ready (notification) | "You have a new update in your account." (no clinical detail — §15) |
| Generic error | "Something went wrong on our side. Please try again. If it keeps happening, call us on 0123 456 789." |
| Offline | "You're offline. We'll save your changes when you're back online." |
| Loading long | "Still working on it — thanks for your patience." |
| Pregnancy loss support entry | "We're so sorry. Your care team is here for you. You can choose what you see in your account." |

### 12.3 Validation Messages

Format: **what's wrong + how to fix it**, in a calm voice. Message appears below the field, in `--color-text-error` with a `circle-alert` icon.

| Field | Error copy |
|---|---|
| Required (generic) | "Enter your {field name}" / "Select {option type}" |
| Date of birth | "Date of birth must be in the past" / "Enter a real date, for example 27 3 1990" |
| LMP | "Date of your last period must be in the past 10 months" |
| Phone | "Enter a phone number, like 07700 900123" |
| Email | "Enter an email address in the correct format, like name@example.com" |
| Reading out of physiological bounds | "Check this number — blood pressure is usually between 60 and 250" |
| Time slot taken | "Sorry, this time has just been booked by someone else. Please choose another time." |
| Consent | "Confirm you've read the information to continue" |

---

## 13. Accessibility (WCAG 2.2 AA)

### 13.1 Targets

- **Conformance:** WCAG 2.2 Level AA for all patient and clinician interfaces. AAA contrast (7:1) for body text where the tokens allow (default text tokens achieve this).
- **Testing:** automated (axe-core in CI, zero violations), manual keyboard pass, screen reader pass (NVDA + Firefox, VoiceOver + Safari iOS/macOS), 200% and 400% zoom, Windows High Contrast / forced-colors mode.

### 13.2 Requirements Checklist

| WCAG criterion | Implementation rule |
|---|---|
| 1.1.1 Non-text content | Meaningful images have alt text; charts have text summaries + data tables. |
| 1.3.1 Info & relationships | Semantic HTML: headings in order (one `h1`), lists, tables, `fieldset/legend`, landmarks (`header`, `nav`, `main`, `aside`, `footer`). |
| 1.4.1 Use of colour | Status = colour + icon + text. Links in body text are underlined. |
| 1.4.3 / 1.4.6 Contrast | Text ≥ 4.5:1 (≥ 3:1 for ≥ 24px or ≥ 18.66px bold). Use pairs in §2.3. |
| 1.4.10 Reflow | No horizontal scroll at 320px width (except data tables/charts). |
| 1.4.11 Non-text contrast | Control boundaries and focus indicators ≥ 3:1 (`#8C807A` border, berry focus ring). |
| 1.4.12 Text spacing | No clipping when line-height 1.5, letter-spacing 0.12em, word-spacing 0.16em are applied. |
| 1.4.13 Content on hover/focus | Tooltips/popovers dismissible (Esc), hoverable, persistent. |
| 2.1.1 Keyboard | Every action operable by keyboard; no keyboard traps except modal focus traps with Esc. |
| 2.4.1 Bypass blocks | "Skip to main content" link. |
| 2.4.3 Focus order | DOM order matches visual order. |
| 2.4.7 / 2.4.11 Focus visible / not obscured | Focus ring always visible; sticky headers/footers must not cover the focused element (`scroll-padding-top: 80px; scroll-padding-bottom: 88px`). |
| 2.5.7 Dragging movements | Any drag (e.g. reordering, sliders) has a click/tap alternative. |
| 2.5.8 Target size | ≥ 24×24px minimum; 44×44px for patient-facing touch targets. |
| 3.2.6 Consistent help | "Help & support" and urgent contact in the same location on every page. |
| 3.3.1 / 3.3.3 Error identification & suggestion | Inline messages + error summary with fix suggestions. |
| 3.3.7 Redundant entry | Don't ask for the same information twice in a flow; pre-fill from profile. |
| 3.3.8 Accessible authentication | Allow password managers & paste; no cognitive tests; support passkeys / magic links. |
| 4.1.2 Name, role, value | Custom widgets follow WAI-ARIA Authoring Practices. |
| 4.1.3 Status messages | Toasts and async updates via `aria-live` regions. |

### 13.3 Focus States

```css
:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
  border-radius: inherit;
}
/* For elements where outline-offset is clipped (inputs inside overflow containers) */
.input:focus-visible { outline: none; border-color: var(--color-focus-ring); box-shadow: var(--shadow-focus); }
/* Forced colours */
@media (forced-colors: active) { :focus-visible { outline: 2px solid CanvasText; } }
```

- The focus ring is **berry `#902C4E`, 2px, 2px offset** on every interactive element (contrast 7.91:1 against white, 7.41:1 against canvas).
- On berry backgrounds (primary buttons), the 2px white gap in `--shadow-focus` separates the ring from the button.
- Never `outline: none` without a replacement. Style focus with `:focus-visible` so keyboard users always see the ring, while mouse clicks on buttons don't leave a lingering ring (text inputs show focus on click too, which browsers handle automatically).

### 13.4 Keyboard Navigation Map

| Component | Keys |
|---|---|
| Buttons / links | Tab, Enter (Space for buttons) |
| Checkbox | Space |
| Radio group | Tab into group, ↑/↓/←/→ move & select |
| Select / combobox | ↓ open, ↑/↓ navigate, Enter select, Esc close, type-ahead |
| Tabs | ←/→, Home/End, (Enter/Space if manual activation) |
| Accordion | Enter/Space toggle; Tab between headers |
| Date grid | Arrows (day), PageUp/PageDown (month), Shift+PageUp/Down (year), Home/End (week), Enter select, Esc close |
| Dialog | Tab cycles within, Esc closes |
| Menu | ↑/↓, Enter, Esc, Home/End |
| Table sort | Tab to header button, Enter |

### 13.5 Health-Specific Accessibility

- Support users with pregnancy-related visual changes, fatigue and nausea: generous spacing, no flashing, stable layouts, save-and-return-later on long forms.
- Long forms are split into steps of ≤ 7 questions, with progress ("Step 2 of 5") and autosave.
- Never time-limit tasks except security session timeouts, which warn ≥ 2 minutes ahead and allow extension (WCAG 2.2.1).
- Provide "Read aloud"-friendly structure (headings and short paragraphs) for education content; support browser translation (`lang` attributes correct).

---

## 14. Responsive Behaviour

| Component | < 640px | 640–1023px | ≥ 1024px |
|---|---|---|---|
| Navigation | Bottom nav (patient) / drawer (clinician) | Drawer or collapsed sidebar (72px) | Full sidebar (264px) |
| Page header | H1 + primary action full-width below | H1 + action inline | H1 + action inline |
| Cards grid | 1 column, 16px gap | 2 columns, 24px gap | 2–4 columns per pattern, 24px gap |
| Dialogs | Bottom sheet / full-screen | Centred, max 90vw | Centred, fixed sizes |
| Tables | Stacked cards (patient) / horizontal scroll with sticky first column (clinician) | Horizontal scroll | Full table |
| Forms | Single column, sticky bottom action bar, `lg` buttons full-width | Single column, `--container-sm` | Single column `--container-sm`, or 2 columns for short paired fields (first/last name) |
| Date picker | Full-width bottom sheet | Popover | Popover |
| Tabs | Horizontal scroll | Full | Full |
| Health metric tiles | 1 column (or 2 for chips) | 2 columns | 3–4 columns |
| Antenatal tracker | Vertical timeline | Vertical timeline | Horizontal stepper if ≤ 8 steps, else vertical |

**Rules**

- Mobile-first CSS; test at 320, 375, 768, 1024, 1280, 1536px.
- Respect safe areas (`env(safe-area-inset-*)`) for sticky bottom elements.
- Touch targets ≥ 44×44px on touch devices (`@media (pointer: coarse)`).
- Content priority is preserved across breakpoints — nothing clinically important is hidden on mobile; secondary content may collapse into accordions.
- Orientation is not locked.

---

## 15. Privacy-Conscious Display

Reproductive and maternal health data is highly sensitive. These rules are **MUST** unless legal/clinical governance states otherwise.

### 15.1 Minimise by Default

- Show only the data required for the current task. Lists show initials or preferred first name + last initial in shared/clinician list contexts where full identity isn't needed.
- **Masked identifiers:** health IDs, NHS/MRN numbers, insurance numbers show the last 4 characters: `•••• •• 4821`. A "Show" toggle (`eye` / `eye-off` icon button, `aria-pressed`) reveals the full value; auto re-mask after 30 seconds or on navigation.
- **Contact details:** masked in lists (`a••••@gmail.com`, `•••• ••• 123`), full on detail pages.
- **Date of birth** shown as age in lists; full DOB in detail views.

### 15.2 Surfaces Outside the App

- **Browser tab title:** never contains patient names, conditions or results. Use "Appointments · Nurture" not "Ana Lopez – Miscarriage follow-up".
- **Notifications, emails, SMS, push:** generic by default ("You have a new message from your care team"), no clinical detail, no appointment type for sensitive clinics (gynaecology, sexual health, early pregnancy unit). Users MAY opt in to detailed previews.
- **URLs and analytics:** no personal or health information in URLs, query strings, page names or analytics events. Use opaque IDs.
- **Calendar exports:** event titles generic by default ("Appointment at Riverside Clinic"), with an option to add detail.
- **Clipboard / screenshots:** sensitive values can be copied only via explicit "Copy" buttons; consider `-webkit-user-select` only for masked values.

### 15.3 Sensitive Categories

Termination of pregnancy, pregnancy loss, fertility treatment, sexual health, STI results, mental health, domestic abuse/safeguarding, gender identity history.

- Collapsed by default with a `lock` icon and label "Sensitive information — select to view".
- Reveal is per-session and not remembered.
- Never surfaced on dashboards, patient information cards, notifications or search previews.
- **Safeguarding:** pages about domestic abuse show a visible, always-reachable "Quick exit" button (sticky top-right, `outline` variant with `log-out` icon, first in tab order after the skip link). It replaces the page with a neutral site via `location.replace()` so the page is removed from back-button history.

### 15.4 Shared Screens & Shared Devices

- **Privacy mode toggle** (clinician top bar): blurs patient names and identifiers in lists (`filter: blur(6px)` on marked fields + `aria-hidden` replaced by "Hidden" text) for screen sharing or public-facing monitors.
- Session timeout: patient 15 minutes idle, clinician per policy; warning dialog 2 minutes before.
- "Sign out" always one click from the profile menu; signing out clears cached data.
- Print/PDF views include a confidentiality footer: "Confidential — contains personal health information."

### 15.5 Proxy & Partner Access

- When a partner, carer or parent views on behalf of the patient, show a persistent `info` banner: "You're viewing Ana's account as her nominated partner." Scope visible data to what the patient granted.

---

## 16. Health Status Communication

### 16.1 Status Vocabulary (Patient-facing)

| Level | Badge variant | Icon | Label | Supporting copy pattern |
|---|---|---|---|---|
| Normal | `success` | `circle-check` | "Within expected range" | "This is within the range we'd expect at this stage." |
| Informational | `info` | `info` | "For your information" | "No action needed. Your midwife will talk to you about this at your next appointment." |
| Review | `warning` | `triangle-alert` | "Worth discussing" | "This is a little outside the expected range. We'll review it at your next appointment on 12 March. If you feel unwell before then, call us." |
| Act soon | `warning` (with strong title) | `triangle-alert` | "Please contact us today" | "Please call your maternity unit today on 0123 456 789 so we can check things over." |
| Urgent | `error` | `circle-alert` | "Get help now" | "Call your maternity unit now on 0123 456 789. If you can't get through or feel very unwell, call 999." |
| Pending | `neutral` | `clock` | "Awaiting results" | "We'll let you know when your results are ready, usually within 5 working days." |

### 16.2 Rules

1. **Red is reserved** for urgent clinical states and system errors. An ordinary out-of-range reading is **amber**, not red.
2. **Every non-normal status includes a next step** (who to contact, when, how) and contact details where action is time-sensitive.
3. **Values are never colour-coded** themselves; status lives in the adjacent badge so numbers stay readable.
4. **Results that require a conversation** (e.g. abnormal screening results, pregnancy loss findings) are **not released automatically** to the patient view before the clinician has spoken with them, unless policy requires immediate release; in that case show "Your clinician will contact you to talk through this result" above the result.
5. **Avoid alarming vocabulary** in patient views: not "abnormal", "critical", "failed", "high risk", "positive" (without context). Use "outside the expected range", "needs a closer look", "we'd like to check". Clinician views may use standard clinical terminology ("Abnormal", "Critical", "High risk") with the same badge colours.
6. **Explain risk in natural frequencies** ("1 in 150 chance"), never percentages alone, and include what happens next.
7. **No countdowns or pulsing animations** for health warnings.
8. **Urgent banners** use the `error` inline alert at the top of the relevant page, are not dismissible until acknowledged ("I understand" button), and are announced with `role="alert"`.
9. **Emergency signposting** (the "Get help now" card) appears consistently in the same place on every patient page (WCAG 3.2.6) and is localised.

### 16.3 Clinician Flags

| Flag | Badge | Sort weight |
|---|---|---|
| Critical | `solid-error` "Critical" + `circle-alert` | 1 |
| Abnormal | `error` "Abnormal" | 2 |
| Borderline | `warning` "Borderline" | 3 |
| Normal | `success` "Normal" | 4 |
| Pending | `neutral` "Pending" | 5 |

Flagged queues default-sort by severity then age. Acknowledging a flag records clinician + timestamp, shown as `--text-caption`.

---

## 17. Token Reference (JSON, CSS & Tailwind)

All three formats below hold **the same values**. `tokens.json` (§17.1) is the source for tools and importers; the CSS (§17.2) is what web code consumes.

### 17.1 tokens.json (machine-readable)

Extraction rules this block follows, so design-system importers can read it:

- Every family is a **list** of `{"name", "value", "usage"}` entries (not a nested name-to-value map).
- Every value is **literal**: hex, `rgba()` or a length. No `var()`, no named colours, no `color-mix()`.
- Token names are unique across families and use only letters, digits, `-`, `_` and `.`.
- Colour has a single `light` theme (this system is light mode only).
- Mulish is a hosted Google font, so it is named in `type.families` with no font file.

```json
{
  "name": "Nurture",
  "version": 1,
  "color": {
    "themes": [{"id": "light", "name": "Light"}],
    "tokens": [
      {"name": "berry-50", "value": {"light": "#FBF2F5"}, "usage": "Brand-tinted background."},
      {"name": "berry-100", "value": {"light": "#F6E1E8"}, "usage": "Selected and active backgrounds."},
      {"name": "berry-200", "value": {"light": "#EDC3D1"}, "usage": "Subtle border on brand surfaces."},
      {"name": "berry-300", "value": {"light": "#DE96AE"}, "usage": "Decorative only."},
      {"name": "berry-400", "value": {"light": "#C76287"}, "usage": "Decorative and charts only; not for text (3.8:1 on white)."},
      {"name": "berry-500", "value": {"light": "#A93D63"}, "usage": "Charts and large text only."},
      {"name": "berry-600", "value": {"light": "#902C4E"}, "usage": "Brand primary. Primary actions, links, focus ring (7.91:1 on white)."},
      {"name": "berry-700", "value": {"light": "#7A2442"}, "usage": "Primary hover; brand text hover (9.73:1 on white)."},
      {"name": "berry-800", "value": {"light": "#631D36"}, "usage": "Primary pressed (11.93:1 on white)."},
      {"name": "berry-900", "value": {"light": "#4A1528"}, "usage": "Deepest brand tone."},
      {"name": "lime-50", "value": {"light": "#F9FCEC"}, "usage": "Very subtle positive background."},
      {"name": "lime-100", "value": {"light": "#F1F8D6"}, "usage": "Accent-subtle background."},
      {"name": "lime-200", "value": {"light": "#E5F1B6"}, "usage": "Hover on lime-100."},
      {"name": "lime-300", "value": {"light": "#D4E990"}, "usage": "Brand secondary. Backgrounds only, always with lime-900 text; never white text (1.32:1)."},
      {"name": "lime-400", "value": {"light": "#BDD86A"}, "usage": "Secondary button hover (lime-900 text 7.52:1)."},
      {"name": "lime-500", "value": {"light": "#A9C95A"}, "usage": "Secondary button pressed (lime-900 text 6.37:1)."},
      {"name": "lime-600", "value": {"light": "#7D9A2F"}, "usage": "Progress strokes and graphics only; not for text (3.21:1 on white)."},
      {"name": "lime-700", "value": {"light": "#5E7522"}, "usage": "Lime-family text on white (5.19:1)."},
      {"name": "lime-800", "value": {"light": "#45561A"}, "usage": "Text on lime-100 and lime-300."},
      {"name": "lime-900", "value": {"light": "#2F3B12"}, "usage": "Text and icons on any lime background (9.03:1 on lime-300)."},
      {"name": "neutral-0", "value": {"light": "#FFFFFF"}, "usage": "Surfaces."},
      {"name": "neutral-25", "value": {"light": "#FDFBFA"}, "usage": "Subtle surface."},
      {"name": "neutral-50", "value": {"light": "#FAF7F5"}, "usage": "App canvas."},
      {"name": "neutral-100", "value": {"light": "#F3EEEB"}, "usage": "Sunken surface, table header, skeleton base."},
      {"name": "neutral-200", "value": {"light": "#E7E0DC"}, "usage": "Dividers and decorative borders."},
      {"name": "neutral-300", "value": {"light": "#D5CCC7"}, "usage": "Disabled borders."},
      {"name": "neutral-400", "value": {"light": "#A89D97"}, "usage": "Disabled text and icons only (WCAG-exempt)."},
      {"name": "neutral-500", "value": {"light": "#8C807A"}, "usage": "Form control borders (3.83:1 on white)."},
      {"name": "neutral-600", "value": {"light": "#756A64"}, "usage": "Tertiary text (5.25:1 on white)."},
      {"name": "neutral-700", "value": {"light": "#5E544F"}, "usage": "Secondary text (7.35:1 on white)."},
      {"name": "neutral-800", "value": {"light": "#463E3A"}, "usage": "Tooltip and toast background; strong secondary text."},
      {"name": "neutral-900", "value": {"light": "#1F1A18"}, "usage": "Primary text (17.22:1 on white)."},
      {"name": "success-50", "value": {"light": "#E8F5EE"}, "usage": "Success background (alerts, badges)."},
      {"name": "success-200", "value": {"light": "#A6D9BC"}, "usage": "Success border."},
      {"name": "success-600", "value": {"light": "#1E7A4C"}, "usage": "Success icon and solid badge background (white text passes AA)."},
      {"name": "success-700", "value": {"light": "#16603B"}, "usage": "Success text on white and on success-50."},
      {"name": "warning-50", "value": {"light": "#FEF4E2"}, "usage": "Warning background (alerts, badges)."},
      {"name": "warning-200", "value": {"light": "#F5CF8A"}, "usage": "Warning border."},
      {"name": "warning-600", "value": {"light": "#9A5B00"}, "usage": "Warning icon and solid badge background (white text passes AA)."},
      {"name": "warning-700", "value": {"light": "#7A4800"}, "usage": "Warning text on white and on warning-50."},
      {"name": "error-50", "value": {"light": "#FDECEA"}, "usage": "Error background (alerts, badges)."},
      {"name": "error-200", "value": {"light": "#F4B4AE"}, "usage": "Error border."},
      {"name": "error-600", "value": {"light": "#B42318"}, "usage": "Error icon and solid badge background (white text passes AA)."},
      {"name": "error-700", "value": {"light": "#912018"}, "usage": "Error text on white and on error-50."},
      {"name": "info-50", "value": {"light": "#EAF2FB"}, "usage": "Info background (alerts, badges)."},
      {"name": "info-200", "value": {"light": "#A9C8EE"}, "usage": "Info border."},
      {"name": "info-600", "value": {"light": "#1F5FA8"}, "usage": "Info icon and solid badge background (white text passes AA)."},
      {"name": "info-700", "value": {"light": "#184B85"}, "usage": "Info text on white and on info-50."},
      {"name": "bg-canvas", "value": {"light": "#FAF7F5"}, "usage": "Page and app background behind cards."},
      {"name": "bg-surface", "value": {"light": "#FFFFFF"}, "usage": "Cards, inputs, modals, tables."},
      {"name": "bg-surface-subtle", "value": {"light": "#FDFBFA"}, "usage": "Nested panels inside a card."},
      {"name": "bg-surface-sunken", "value": {"light": "#F3EEEB"}, "usage": "Table headers, ID chips, read-only fields."},
      {"name": "bg-surface-hover", "value": {"light": "#FAF7F5"}, "usage": "Hover on rows, list items, ghost buttons."},
      {"name": "bg-brand-subtle", "value": {"light": "#FBF2F5"}, "usage": "Highlight panels, welcome banners."},
      {"name": "bg-brand-muted", "value": {"light": "#F6E1E8"}, "usage": "Selected nav item, selected row, active tab."},
      {"name": "bg-accent", "value": {"light": "#D4E990"}, "usage": "Secondary button, milestone highlights, progress fill. Use text-on-accent."},
      {"name": "bg-accent-subtle", "value": {"light": "#F1F8D6"}, "usage": "Positive info panels, completed visits."},
      {"name": "bg-overlay", "value": {"light": "rgba(31, 26, 24, 0.48)"}, "usage": "Modal scrim."},
      {"name": "bg-inverse", "value": {"light": "#463E3A"}, "usage": "Tooltips and toasts."},
      {"name": "bg-disabled", "value": {"light": "#F3EEEB"}, "usage": "Disabled controls."},
      {"name": "text-primary", "value": {"light": "#1F1A18"}, "usage": "Body text and headings (17.22:1 on white)."},
      {"name": "text-secondary", "value": {"light": "#5E544F"}, "usage": "Supporting text and labels (7.35:1 on white)."},
      {"name": "text-tertiary", "value": {"light": "#756A64"}, "usage": "Hints, timestamps, placeholders (5.25:1 on white)."},
      {"name": "text-disabled", "value": {"light": "#A89D97"}, "usage": "Disabled text only."},
      {"name": "text-brand", "value": {"light": "#902C4E"}, "usage": "Links and brand emphasis (7.91:1 on white)."},
      {"name": "text-brand-hover", "value": {"light": "#7A2442"}, "usage": "Link hover."},
      {"name": "text-inverse", "value": {"light": "#FFFFFF"}, "usage": "Text on berry, status solids and inverse surfaces."},
      {"name": "text-on-accent", "value": {"light": "#2F3B12"}, "usage": "All text and icons on lime backgrounds."},
      {"name": "text-success", "value": {"light": "#16603B"}, "usage": "Success text."},
      {"name": "text-warning", "value": {"light": "#7A4800"}, "usage": "Warning text."},
      {"name": "text-error", "value": {"light": "#B42318"}, "usage": "Error and validation text (6.57:1 on white)."},
      {"name": "text-info", "value": {"light": "#184B85"}, "usage": "Info text."},
      {"name": "border-subtle", "value": {"light": "#E7E0DC"}, "usage": "Card outlines and dividers (decorative)."},
      {"name": "border-default", "value": {"light": "#8C807A"}, "usage": "Inputs, checkboxes, radios, selects (3:1 non-text)."},
      {"name": "border-strong", "value": {"light": "#5E544F"}, "usage": "Input hover."},
      {"name": "border-brand", "value": {"light": "#902C4E"}, "usage": "Selected cards, active input."},
      {"name": "border-accent", "value": {"light": "#7D9A2F"}, "usage": "Milestone and progress outlines."},
      {"name": "border-disabled", "value": {"light": "#D5CCC7"}, "usage": "Disabled controls."},
      {"name": "border-error", "value": {"light": "#B42318"}, "usage": "Invalid inputs."},
      {"name": "focus-ring", "value": {"light": "#902C4E"}, "usage": "Focus indicator on every interactive element."},
      {"name": "action-primary-bg", "value": {"light": "#902C4E"}, "usage": "Primary button background, with text-inverse."},
      {"name": "action-primary-bg-hover", "value": {"light": "#7A2442"}, "usage": "Primary button hover."},
      {"name": "action-primary-bg-active", "value": {"light": "#631D36"}, "usage": "Primary button pressed."},
      {"name": "action-secondary-bg", "value": {"light": "#D4E990"}, "usage": "Secondary button background, with text-on-accent."},
      {"name": "action-secondary-bg-hover", "value": {"light": "#BDD86A"}, "usage": "Secondary button hover."},
      {"name": "action-secondary-bg-active", "value": {"light": "#A9C95A"}, "usage": "Secondary button pressed."},
      {"name": "action-outline-bg-hover", "value": {"light": "#FBF2F5"}, "usage": "Outline button hover background."},
      {"name": "action-ghost-bg-hover", "value": {"light": "#F3EEEB"}, "usage": "Ghost button hover background."},
      {"name": "action-destructive-bg", "value": {"light": "#B42318"}, "usage": "Destructive button background, with text-inverse."},
      {"name": "action-destructive-bg-hover", "value": {"light": "#912018"}, "usage": "Destructive button hover."},
      {"name": "action-primary-text", "value": {"light": "#FFFFFF"}, "usage": "Text on primary buttons."},
      {"name": "action-secondary-text", "value": {"light": "#2F3B12"}, "usage": "Text on secondary (lime) buttons."},
      {"name": "action-outline-border", "value": {"light": "#902C4E"}, "usage": "Outline button border."},
      {"name": "action-outline-text", "value": {"light": "#902C4E"}, "usage": "Outline button text."},
      {"name": "action-ghost-text", "value": {"light": "#5E544F"}, "usage": "Ghost button text."},
      {"name": "action-disabled-bg", "value": {"light": "#F3EEEB"}, "usage": "Disabled button background."},
      {"name": "action-disabled-text", "value": {"light": "#A89D97"}, "usage": "Disabled button text."},
      {"name": "status-success-bg", "value": {"light": "#E8F5EE"}, "usage": "Success alert and badge background."},
      {"name": "status-success-border", "value": {"light": "#A6D9BC"}, "usage": "Success alert border."},
      {"name": "status-success-icon", "value": {"light": "#1E7A4C"}, "usage": "Success icon."},
      {"name": "status-success-text", "value": {"light": "#16603B"}, "usage": "Success text inside alerts and badges."},
      {"name": "status-success-solid", "value": {"light": "#1E7A4C"}, "usage": "Success solid badge background, with white text."},
      {"name": "status-warning-bg", "value": {"light": "#FEF4E2"}, "usage": "Warning alert and badge background."},
      {"name": "status-warning-border", "value": {"light": "#F5CF8A"}, "usage": "Warning alert border."},
      {"name": "status-warning-icon", "value": {"light": "#9A5B00"}, "usage": "Warning icon."},
      {"name": "status-warning-text", "value": {"light": "#7A4800"}, "usage": "Warning text inside alerts and badges."},
      {"name": "status-warning-solid", "value": {"light": "#9A5B00"}, "usage": "Warning solid badge background, with white text."},
      {"name": "status-error-bg", "value": {"light": "#FDECEA"}, "usage": "Error alert and badge background."},
      {"name": "status-error-border", "value": {"light": "#F4B4AE"}, "usage": "Error alert border."},
      {"name": "status-error-icon", "value": {"light": "#B42318"}, "usage": "Error icon."},
      {"name": "status-error-text", "value": {"light": "#912018"}, "usage": "Error text inside alerts and badges."},
      {"name": "status-error-solid", "value": {"light": "#B42318"}, "usage": "Error solid badge background, with white text."},
      {"name": "status-info-bg", "value": {"light": "#EAF2FB"}, "usage": "Info alert and badge background."},
      {"name": "status-info-border", "value": {"light": "#A9C8EE"}, "usage": "Info alert border."},
      {"name": "status-info-icon", "value": {"light": "#1F5FA8"}, "usage": "Info icon."},
      {"name": "status-info-text", "value": {"light": "#184B85"}, "usage": "Info text inside alerts and badges."},
      {"name": "status-info-solid", "value": {"light": "#1F5FA8"}, "usage": "Info solid badge background, with white text."},
      {"name": "status-neutral-bg", "value": {"light": "#F3EEEB"}, "usage": "Neutral badge background."},
      {"name": "status-neutral-text", "value": {"light": "#463E3A"}, "usage": "Neutral badge text."},
      {"name": "status-neutral-icon", "value": {"light": "#5E544F"}, "usage": "Neutral status icon."},
      {"name": "chart-1", "value": {"light": "#902C4E"}, "usage": "Primary data series."},
      {"name": "chart-2", "value": {"light": "#1F5FA8"}, "usage": "Comparison series."},
      {"name": "chart-3", "value": {"light": "#7D9A2F"}, "usage": "Third series (strokes only)."},
      {"name": "chart-4", "value": {"light": "#9A5B00"}, "usage": "Fourth series."},
      {"name": "chart-5", "value": {"light": "#5E544F"}, "usage": "Neutral series."},
      {"name": "chart-range", "value": {"light": "#F1F8D6"}, "usage": "Expected-range band."},
      {"name": "chart-grid", "value": {"light": "#E7E0DC"}, "usage": "Gridlines."}
    ]
  },
  "type": {
    "fonts": [],
    "families": {"sans": "\"Mulish\", ui-sans-serif, system-ui, -apple-system, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif"},
    "groups": [
      {"name": "Display", "family": "sans", "styles": [
          {"name": "display-lg", "fontSize": "48px", "lineHeight": "56px", "fontWeight": 700, "letterSpacing": "-0.02em", "usage": "Marketing hero only. 36px/44px below 768px."},
          {"name": "display-md", "fontSize": "40px", "lineHeight": "48px", "fontWeight": 700, "letterSpacing": "-0.02em", "usage": "Landing section heads. 32px/40px below 768px."}
        ]},
      {"name": "Headings", "family": "sans", "styles": [
          {"name": "heading-xl", "fontSize": "32px", "lineHeight": "40px", "fontWeight": 700, "letterSpacing": "-0.01em", "usage": "Page title (H1). 28px/36px below 768px."},
          {"name": "heading-lg", "fontSize": "28px", "lineHeight": "36px", "fontWeight": 700, "letterSpacing": "-0.01em", "usage": "Section title (H2). 24px/32px below 768px."},
          {"name": "heading-md", "fontSize": "24px", "lineHeight": "32px", "fontWeight": 600, "letterSpacing": "-0.005em", "usage": "Sub-section (H3). 20px/28px below 768px."},
          {"name": "heading-sm", "fontSize": "20px", "lineHeight": "28px", "fontWeight": 600, "usage": "Card title (H4)."},
          {"name": "heading-xs", "fontSize": "18px", "lineHeight": "26px", "fontWeight": 600, "usage": "Small card title (H5)."}
        ]},
      {"name": "Body", "family": "sans", "styles": [
          {"name": "body-lg", "fontSize": "18px", "lineHeight": "28px", "fontWeight": 400, "usage": "Education articles, intros."},
          {"name": "body-md", "fontSize": "16px", "lineHeight": "24px", "fontWeight": 400, "usage": "Default body and input text."},
          {"name": "body-sm", "fontSize": "14px", "lineHeight": "20px", "fontWeight": 400, "usage": "Supporting text, clinician table cells."}
        ]},
      {"name": "Labels", "family": "sans", "styles": [
          {"name": "label-lg", "fontSize": "16px", "lineHeight": "24px", "fontWeight": 600, "usage": "Large buttons, nav items."},
          {"name": "label-md", "fontSize": "14px", "lineHeight": "20px", "fontWeight": 600, "usage": "Form labels, buttons, tabs."},
          {"name": "label-sm", "fontSize": "12px", "lineHeight": "16px", "fontWeight": 600, "letterSpacing": "0.04em", "usage": "Overlines (uppercase) and badges."},
          {"name": "caption", "fontSize": "12px", "lineHeight": "16px", "fontWeight": 500, "letterSpacing": "0.01em", "usage": "Timestamps and metadata only."}
        ]},
      {"name": "Data", "family": "sans", "styles": [
          {"name": "metric-xl", "fontSize": "36px", "lineHeight": "44px", "fontWeight": 700, "letterSpacing": "-0.01em", "usage": "Headline health metric (tabular numbers)."},
          {"name": "metric-lg", "fontSize": "28px", "lineHeight": "36px", "fontWeight": 700, "letterSpacing": "-0.01em", "usage": "Dashboard widget value (tabular numbers)."},
          {"name": "id-sm", "fontSize": "14px", "lineHeight": "20px", "fontWeight": 600, "letterSpacing": "0.04em", "usage": "IDs and reference codes (tabular, slashed zero)."}
        ]}
    ]
  },
  "spacing": {"tokens": [
    {"name": "space-0", "value": "0px", "usage": "No space."},
    {"name": "space-0-5", "value": "2px", "usage": "Optical nudges, badge vertical padding."},
    {"name": "space-1", "value": "4px", "usage": "Tight inline gaps."},
    {"name": "space-2", "value": "8px", "usage": "Icon-to-label gap; label-to-control gap."},
    {"name": "space-3", "value": "12px", "usage": "Input horizontal padding, list gaps."},
    {"name": "space-4", "value": "16px", "usage": "Default component padding, mobile gutter."},
    {"name": "space-5", "value": "20px", "usage": "Compact card padding."},
    {"name": "space-6", "value": "24px", "usage": "Card padding, grid gutter, form field gap."},
    {"name": "space-8", "value": "32px", "usage": "Section gap, tablet page margin."},
    {"name": "space-10", "value": "40px", "usage": "Large section gap."},
    {"name": "space-12", "value": "48px", "usage": "Page section separation."},
    {"name": "space-16", "value": "64px", "usage": "Hero padding."},
    {"name": "space-20", "value": "80px", "usage": "Marketing sections."},
    {"name": "space-24", "value": "96px", "usage": "Marketing sections (desktop)."}
  ]},
  "radius": {"tokens": [
    {"name": "radius-none", "value": "0px", "usage": "Table cells, full-bleed media."},
    {"name": "radius-xs", "value": "4px", "usage": "Checkboxes, dense chips."},
    {"name": "radius-sm", "value": "6px", "usage": "Tooltips, ID chips, small tags."},
    {"name": "radius-md", "value": "10px", "usage": "Buttons, inputs, selects, menus."},
    {"name": "radius-lg", "value": "16px", "usage": "Cards, alerts, popovers."},
    {"name": "radius-xl", "value": "24px", "usage": "Dialogs, hero panels, feature widgets."},
    {"name": "radius-full", "value": "9999px", "usage": "Badges, pills, avatars, toggles, radios."}
  ]},
  "shadow": {"tokens": [
    {"name": "shadow-xs", "value": "0 1px 2px rgba(31, 26, 24, 0.06)", "usage": "Inputs, outline buttons."},
    {"name": "shadow-sm", "value": "0 1px 3px rgba(31, 26, 24, 0.08), 0 1px 2px rgba(31, 26, 24, 0.04)", "usage": "Default card."},
    {"name": "shadow-md", "value": "0 4px 12px rgba(31, 26, 24, 0.08), 0 2px 4px rgba(31, 26, 24, 0.04)", "usage": "Hovered cards, dropdowns, popovers."},
    {"name": "shadow-lg", "value": "0 12px 24px rgba(31, 26, 24, 0.10), 0 4px 8px rgba(31, 26, 24, 0.04)", "usage": "Date picker, toasts, sticky header on scroll."},
    {"name": "shadow-xl", "value": "0 24px 48px rgba(31, 26, 24, 0.14), 0 8px 16px rgba(31, 26, 24, 0.06)", "usage": "Modals, bottom sheets."},
    {"name": "shadow-focus", "value": "0 0 0 2px #FFFFFF, 0 0 0 4px #902C4E", "usage": "Focus ring."},
    {"name": "shadow-focus-error", "value": "0 0 0 2px #FFFFFF, 0 0 0 4px #B42318", "usage": "Focus ring on invalid inputs."}
  ]}
}
```

### 17.2 CSS Custom Properties

One declaration per line, literal values only (prefix `--color-` is added to every colour token name from §17.1).

```css
:root {
  color-scheme: light;

  /* Colour */
  --color-berry-50: #FBF2F5;
  --color-berry-100: #F6E1E8;
  --color-berry-200: #EDC3D1;
  --color-berry-300: #DE96AE;
  --color-berry-400: #C76287;
  --color-berry-500: #A93D63;
  --color-berry-600: #902C4E;
  --color-berry-700: #7A2442;
  --color-berry-800: #631D36;
  --color-berry-900: #4A1528;
  --color-lime-50: #F9FCEC;
  --color-lime-100: #F1F8D6;
  --color-lime-200: #E5F1B6;
  --color-lime-300: #D4E990;
  --color-lime-400: #BDD86A;
  --color-lime-500: #A9C95A;
  --color-lime-600: #7D9A2F;
  --color-lime-700: #5E7522;
  --color-lime-800: #45561A;
  --color-lime-900: #2F3B12;
  --color-neutral-0: #FFFFFF;
  --color-neutral-25: #FDFBFA;
  --color-neutral-50: #FAF7F5;
  --color-neutral-100: #F3EEEB;
  --color-neutral-200: #E7E0DC;
  --color-neutral-300: #D5CCC7;
  --color-neutral-400: #A89D97;
  --color-neutral-500: #8C807A;
  --color-neutral-600: #756A64;
  --color-neutral-700: #5E544F;
  --color-neutral-800: #463E3A;
  --color-neutral-900: #1F1A18;
  --color-success-50: #E8F5EE;
  --color-success-200: #A6D9BC;
  --color-success-600: #1E7A4C;
  --color-success-700: #16603B;
  --color-warning-50: #FEF4E2;
  --color-warning-200: #F5CF8A;
  --color-warning-600: #9A5B00;
  --color-warning-700: #7A4800;
  --color-error-50: #FDECEA;
  --color-error-200: #F4B4AE;
  --color-error-600: #B42318;
  --color-error-700: #912018;
  --color-info-50: #EAF2FB;
  --color-info-200: #A9C8EE;
  --color-info-600: #1F5FA8;
  --color-info-700: #184B85;
  --color-bg-canvas: #FAF7F5;
  --color-bg-surface: #FFFFFF;
  --color-bg-surface-subtle: #FDFBFA;
  --color-bg-surface-sunken: #F3EEEB;
  --color-bg-surface-hover: #FAF7F5;
  --color-bg-brand-subtle: #FBF2F5;
  --color-bg-brand-muted: #F6E1E8;
  --color-bg-accent: #D4E990;
  --color-bg-accent-subtle: #F1F8D6;
  --color-bg-overlay: rgba(31, 26, 24, 0.48);
  --color-bg-inverse: #463E3A;
  --color-bg-disabled: #F3EEEB;
  --color-text-primary: #1F1A18;
  --color-text-secondary: #5E544F;
  --color-text-tertiary: #756A64;
  --color-text-disabled: #A89D97;
  --color-text-brand: #902C4E;
  --color-text-brand-hover: #7A2442;
  --color-text-inverse: #FFFFFF;
  --color-text-on-accent: #2F3B12;
  --color-text-success: #16603B;
  --color-text-warning: #7A4800;
  --color-text-error: #B42318;
  --color-text-info: #184B85;
  --color-border-subtle: #E7E0DC;
  --color-border-default: #8C807A;
  --color-border-strong: #5E544F;
  --color-border-brand: #902C4E;
  --color-border-accent: #7D9A2F;
  --color-border-disabled: #D5CCC7;
  --color-border-error: #B42318;
  --color-focus-ring: #902C4E;
  --color-action-primary-bg: #902C4E;
  --color-action-primary-bg-hover: #7A2442;
  --color-action-primary-bg-active: #631D36;
  --color-action-secondary-bg: #D4E990;
  --color-action-secondary-bg-hover: #BDD86A;
  --color-action-secondary-bg-active: #A9C95A;
  --color-action-outline-bg-hover: #FBF2F5;
  --color-action-ghost-bg-hover: #F3EEEB;
  --color-action-destructive-bg: #B42318;
  --color-action-destructive-bg-hover: #912018;
  --color-action-primary-text: #FFFFFF;
  --color-action-secondary-text: #2F3B12;
  --color-action-outline-border: #902C4E;
  --color-action-outline-text: #902C4E;
  --color-action-ghost-text: #5E544F;
  --color-action-disabled-bg: #F3EEEB;
  --color-action-disabled-text: #A89D97;
  --color-status-success-bg: #E8F5EE;
  --color-status-success-border: #A6D9BC;
  --color-status-success-icon: #1E7A4C;
  --color-status-success-text: #16603B;
  --color-status-success-solid: #1E7A4C;
  --color-status-warning-bg: #FEF4E2;
  --color-status-warning-border: #F5CF8A;
  --color-status-warning-icon: #9A5B00;
  --color-status-warning-text: #7A4800;
  --color-status-warning-solid: #9A5B00;
  --color-status-error-bg: #FDECEA;
  --color-status-error-border: #F4B4AE;
  --color-status-error-icon: #B42318;
  --color-status-error-text: #912018;
  --color-status-error-solid: #B42318;
  --color-status-info-bg: #EAF2FB;
  --color-status-info-border: #A9C8EE;
  --color-status-info-icon: #1F5FA8;
  --color-status-info-text: #184B85;
  --color-status-info-solid: #1F5FA8;
  --color-status-neutral-bg: #F3EEEB;
  --color-status-neutral-text: #463E3A;
  --color-status-neutral-icon: #5E544F;
  --color-chart-1: #902C4E;
  --color-chart-2: #1F5FA8;
  --color-chart-3: #7D9A2F;
  --color-chart-4: #9A5B00;
  --color-chart-5: #5E544F;
  --color-chart-range: #F1F8D6;
  --color-chart-grid: #E7E0DC;

  /* Typography */
  --font-sans: 'Mulish', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  --font-weight-extrabold: 800;
  --text-display-lg: 48px;
  --leading-display-lg: 56px;
  --text-display-md: 40px;
  --leading-display-md: 48px;
  --text-heading-xl: 32px;
  --leading-heading-xl: 40px;
  --text-heading-lg: 28px;
  --leading-heading-lg: 36px;
  --text-heading-md: 24px;
  --leading-heading-md: 32px;
  --text-heading-sm: 20px;
  --leading-heading-sm: 28px;
  --text-heading-xs: 18px;
  --leading-heading-xs: 26px;
  --text-body-lg: 18px;
  --leading-body-lg: 28px;
  --text-body-md: 16px;
  --leading-body-md: 24px;
  --text-body-sm: 14px;
  --leading-body-sm: 20px;
  --text-label-lg: 16px;
  --leading-label-lg: 24px;
  --text-label-md: 14px;
  --leading-label-md: 20px;
  --text-label-sm: 12px;
  --leading-label-sm: 16px;
  --text-caption: 12px;
  --leading-caption: 16px;
  --text-metric-xl: 36px;
  --leading-metric-xl: 44px;
  --text-metric-lg: 28px;
  --leading-metric-lg: 36px;
  --text-id-sm: 14px;
  --leading-id-sm: 20px;

  /* Spacing */
  --space-0: 0px;
  --space-0-5: 2px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;

  /* Radius */
  --radius-none: 0px;
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --radius-full: 9999px;

  /* Shadow */
  --shadow-xs: 0 1px 2px rgba(31, 26, 24, 0.06);
  --shadow-sm: 0 1px 3px rgba(31, 26, 24, 0.08), 0 1px 2px rgba(31, 26, 24, 0.04);
  --shadow-md: 0 4px 12px rgba(31, 26, 24, 0.08), 0 2px 4px rgba(31, 26, 24, 0.04);
  --shadow-lg: 0 12px 24px rgba(31, 26, 24, 0.10), 0 4px 8px rgba(31, 26, 24, 0.04);
  --shadow-xl: 0 24px 48px rgba(31, 26, 24, 0.14), 0 8px 16px rgba(31, 26, 24, 0.06);
  --shadow-focus: 0 0 0 2px #FFFFFF, 0 0 0 4px #902C4E;
  --shadow-focus-error: 0 0 0 2px #FFFFFF, 0 0 0 4px #B42318;

  /* Z-index */
  --z-base: 0;
  --z-raised: 10;
  --z-sticky: 100;
  --z-sidebar: 200;
  --z-dropdown: 300;
  --z-overlay: 400;
  --z-modal: 410;
  --z-toast: 500;
  --z-tooltip: 600;

  /* Motion */
  --duration-instant: 100ms;
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --easing-standard: cubic-bezier(0.2, 0, 0, 1);
  --easing-enter: cubic-bezier(0, 0, 0, 1);
  --easing-exit: cubic-bezier(0.3, 0, 1, 1);

  /* Layout */
  --container-sm: 640px;
  --container-md: 768px;
  --container-lg: 1024px;
  --container-xl: 1280px;
  --container-2xl: 1440px;
  --content-measure: 68ch;
  --layout-topbar-height: 64px;
  --layout-sidebar-width: 264px;
  --layout-sidebar-width-collapsed: 72px;
  --layout-bottom-nav-height: 64px;
  --layout-action-bar-height: 72px;

  /* Icons and controls */
  --icon-sm: 16px;
  --icon-md: 20px;
  --icon-lg: 24px;
  --icon-xl: 32px;
  --icon-2xl: 48px;
  --control-height-sm: 32px;
  --control-height-md: 40px;
  --control-height-lg: 48px;
  --target-min: 24px;
  --target-touch: 44px;
}

@media (max-width: 767px) {
  :root {
    --text-display-lg: 2.25rem; --leading-display-lg: 2.75rem;
    --text-display-md: 2rem;    --leading-display-md: 2.5rem;
    --text-heading-xl: 1.75rem; --leading-heading-xl: 2.25rem;
    --text-heading-lg: 1.5rem;  --leading-heading-lg: 2rem;
    --text-heading-md: 1.25rem; --leading-heading-md: 1.75rem;
    --layout-topbar-height: 56px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* Base */
html { font-family: var(--font-sans); font-size: 100%; -webkit-text-size-adjust: 100%; }
body {
  background: var(--color-bg-canvas);
  color: var(--color-text-primary);
  font-size: var(--text-body-md);
  line-height: var(--leading-body-md);
  font-weight: var(--font-weight-regular);
  -webkit-font-smoothing: antialiased;
}
```

### 17.3 Tailwind CSS Mapping (optional)

If the project uses Tailwind, map tokens rather than using Tailwind's default palette. Default Tailwind colours (`pink-*`, `green-*`, etc.) **MUST NOT** be used.

```js
// tailwind.config.js (theme.extend excerpt)
// Light mode only: do not configure `darkMode` and do not use `dark:` variants.
module.exports = {
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: '#FFFFFF',
      berry:   { 50:'#FBF2F5',100:'#F6E1E8',200:'#EDC3D1',300:'#DE96AE',400:'#C76287',500:'#A93D63',600:'#902C4E',700:'#7A2442',800:'#631D36',900:'#4A1528' },
      lime:    { 50:'#F9FCEC',100:'#F1F8D6',200:'#E5F1B6',300:'#D4E990',400:'#BDD86A',500:'#A9C95A',600:'#7D9A2F',700:'#5E7522',800:'#45561A',900:'#2F3B12' },
      neutral: { 0:'#FFFFFF',25:'#FDFBFA',50:'#FAF7F5',100:'#F3EEEB',200:'#E7E0DC',300:'#D5CCC7',400:'#A89D97',500:'#8C807A',600:'#756A64',700:'#5E544F',800:'#463E3A',900:'#1F1A18' },
      success: { 50:'#E8F5EE',200:'#A6D9BC',600:'#1E7A4C',700:'#16603B' },
      warning: { 50:'#FEF4E2',200:'#F5CF8A',600:'#9A5B00',700:'#7A4800' },
      error:   { 50:'#FDECEA',200:'#F4B4AE',600:'#B42318',700:'#912018' },
      info:    { 50:'#EAF2FB',200:'#A9C8EE',600:'#1F5FA8',700:'#184B85' },
      // semantic aliases
      canvas: 'var(--color-bg-canvas)',
      surface: 'var(--color-bg-surface)',
      'text-primary': 'var(--color-text-primary)',
      'text-secondary': 'var(--color-text-secondary)',
      'text-tertiary': 'var(--color-text-tertiary)',
      'on-accent': 'var(--color-text-on-accent)',
    },
    fontFamily: {
      sans: ['Mulish', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Arial', 'sans-serif'],
    },
    borderRadius: { none:'0', xs:'4px', sm:'6px', md:'10px', lg:'16px', xl:'24px', full:'9999px' },
    extend: {
      spacing: { '0.5':'2px' }, // Tailwind's default 4px scale matches --space-*
      boxShadow: {
        xs: '0 1px 2px rgba(31,26,24,0.06)',
        sm: '0 1px 3px rgba(31,26,24,0.08), 0 1px 2px rgba(31,26,24,0.04)',
        md: '0 4px 12px rgba(31,26,24,0.08), 0 2px 4px rgba(31,26,24,0.04)',
        lg: '0 12px 24px rgba(31,26,24,0.10), 0 4px 8px rgba(31,26,24,0.04)',
        xl: '0 24px 48px rgba(31,26,24,0.14), 0 8px 16px rgba(31,26,24,0.06)',
        focus: '0 0 0 2px #FFFFFF, 0 0 0 4px #902C4E',
      },
      fontSize: {
        'display-lg': ['3rem', { lineHeight: '3.5rem', letterSpacing: '-0.02em', fontWeight: '700' }],
        'display-md': ['2.5rem', { lineHeight: '3rem', letterSpacing: '-0.02em', fontWeight: '700' }],
        'heading-xl': ['2rem', { lineHeight: '2.5rem', letterSpacing: '-0.01em', fontWeight: '700' }],
        'heading-lg': ['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.01em', fontWeight: '700' }],
        'heading-md': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.005em', fontWeight: '600' }],
        'heading-sm': ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        'heading-xs': ['1.125rem', { lineHeight: '1.625rem', fontWeight: '600' }],
        'body-lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'body-md': ['1rem', { lineHeight: '1.5rem' }],
        'body-sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'label-lg': ['1rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        'label-md': ['0.875rem', { lineHeight: '1.25rem', fontWeight: '600' }],
        'label-sm': ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.04em', fontWeight: '600' }],
        caption: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.01em', fontWeight: '500' }],
        'metric-xl': ['2.25rem', { lineHeight: '2.75rem', letterSpacing: '-0.01em', fontWeight: '700' }],
        'metric-lg': ['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.01em', fontWeight: '700' }],
      },
      screens: { sm:'640px', md:'768px', lg:'1024px', xl:'1280px', '2xl':'1536px' },
    },
  },
};
```

> Tailwind v4 projects: declare the same values in an `@theme { ... }` block using the CSS variable names from §17.2, and do not add a `dark` variant.

### 17.4 Token Naming Convention

```
--{category}-{property|family}-{role|step}-{state}

category: color | text | leading | font | space | radius | shadow | z | duration | easing | container | layout | icon | control | target
examples: --color-berry-600, --color-text-secondary, --color-action-primary-bg-hover,
          --color-status-warning-text, --space-6, --radius-lg, --shadow-md, --text-heading-sm
```

- Primitive colour tokens: `--color-{family}-{step}`.
- Semantic colour tokens: `--color-{bg|text|border|action|status|chart|focus}-{role}[-{state}]`.
- States are always the last segment: `-hover`, `-active`, `-disabled`, `-selected`.
- Component tokens (if needed) are scoped: `--button-primary-bg: var(--color-action-primary-bg);` and must only reference semantic tokens.

---

## 18. Implementation Checklist

Run through this before shipping any screen.

### Visual & Tokens
- [ ] Only tokens from §17 are used; no raw hex/px values in components.
- [ ] Canvas `#FAF7F5`, surfaces `#FFFFFF`, text `#1F1A18`.
- [ ] Exactly one primary (berry) button per view region.
- [ ] Lime backgrounds use `#2F3B12` text; no white text on lime; no lime text on white.
- [ ] Mulish is the only font family loaded and used (no other typefaces, including monospace).
- [ ] No dark mode styles, no new brand colours, no gradients on controls.

### Accessibility
- [ ] All text pairs appear in §2.3 or are verified ≥ 4.5:1.
- [ ] Visible berry focus ring on every interactive element; not obscured by sticky elements.
- [ ] Full keyboard operability per §13.4; logical focus order.
- [ ] Targets ≥ 24×24px (≥ 44×44px on patient touch views).
- [ ] Status communicated by text + icon + colour.
- [ ] Forms: visible labels, error summary, inline errors with `aria-describedby`, correct `autocomplete`.
- [ ] Charts have text summaries and table alternatives.
- [ ] Reduced motion respected; no flashing content.
- [ ] axe-core: zero violations; screen reader spot-check done.

### Healthcare & Content
- [ ] Copy is warm, plain-language, sentence case, no blame, no alarming words in patient views.
- [ ] Every non-normal health status has a clear next step and contact route.
- [ ] Red used only for urgent clinical or system errors.
- [ ] Pregnancy content respects pause/hide settings and pregnancy-status changes.
- [ ] Dates in unambiguous format ("12 March 2026"); doses with full units.

### Privacy
- [ ] Identifiers masked by default with reveal control.
- [ ] No PHI in tab titles, URLs, analytics, notifications or calendar exports.
- [ ] Sensitive categories collapsed and excluded from summaries.
- [ ] Session timeout warning implemented.

### Responsive
- [ ] Tested at 320, 375, 768, 1024, 1280, 1536px; no horizontal page scroll at 320px.
- [ ] Navigation pattern correct for breakpoint (bottom nav / drawer / sidebar).
- [ ] Dialogs become bottom sheets on small screens; sticky action bars respect safe areas.
