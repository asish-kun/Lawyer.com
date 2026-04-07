---
name: Brief AI v2 Upgrade
overview: Upgrade the Legal Brief Analyzer with new extraction fields (deadlines, action flags, contacts, summary), rewrite agent prompts for natural language, redesign the UI with a light-first professional gold theme with dark mode toggle, and add visual chart-based breakdowns for layman readability.
todos:
  - id: d1-move-plan
    content: Move old roadmap plan file into Development planning/ folder
    status: done
  - id: a1-schema
    content: Add KeyDate, ContactInfo, expand BriefExtraction with summary, document_type, action_required, key_dates, contacts
    status: done
  - id: a2-extractor-prompt
    content: Update extractor prompt to extract new fields (summary, doc type, dates, contacts, action flag)
    status: done
  - id: a3-tone-prompts
    content: Rewrite weakness, counterargument, and synthesizer prompts for natural human-like prose
    status: done
  - id: a4-assessment-label
    content: Clarify overall_assessment to Case Strength in schema description and synthesizer prompt
    status: done
  - id: b1-theme-css
    content: "Full CSS rewrite: light/dark mode variables, gold accent, warm tones, no pure white/black"
    status: done
  - id: b2-theme-toggle
    content: Add theme toggle button to header with localStorage persistence
    status: done
  - id: c1-action-banner
    content: Build action-required banner, document summary card, key dates strip in results header
    status: done
  - id: c2-overview-contacts
    content: Add contacts card and document type badge to overview/summary tab
    status: done
  - id: c3-claim-chart
    content: Add Chart.js horizontal bar chart for claim weakness scores
    status: done
  - id: c4-risk-matrix
    content: Add 2x2 risk matrix visual on Strategy tab
    status: done
  - id: c5-render-update
    content: Update app.js to render all new fields, charts, tabs, and theme logic
    status: done
  - id: e2e-test
    content: End-to-end test with sample brief PDF through full updated pipeline and UI
    status: done
  - id: e2e-popular-cases
    content: Download popular 2025/2026 court cases (Anthropic v DOW, OpenAI copyright MDL, Google ad tech antitrust) and test
    status: done
isProject: false
---

# Brief AI v2 Upgrade

## Phase A -- Backend: Schema & Agent Prompt Changes

These changes touch `app/schemas.py`, all four prompt files, and `app/state.py`. The goal is to extract richer information and produce more natural, human-readable output.

### A1. Expand `BriefExtraction` schema — DONE

Added new fields to `app/schemas.py`:

```python
class KeyDate(BaseModel):
    description: str  # e.g. "Response deadline", "Hearing date"
    date: str         # as written in the document
    urgency: str = Field(description="past_due, urgent, upcoming, or informational")

class ContactInfo(BaseModel):
    name: str
    role: str         # "Filing attorney", "Clerk of Court", "Opposing counsel"
    organization: str = ""
    phone: str = ""
    address: str = ""

class BriefExtraction(BaseModel):
    # -- NEW FIELDS --
    summary: str = Field(description="2-3 sentence plain-English overview of this document")
    document_type: str = Field(description="motion, notice, complaint, brief, order, fine, subpoena, etc.")
    action_required: bool = Field(description="True if the recipient must take action")
    action_description: str = Field(default="", description="What action is needed, if any")
    key_dates: List[KeyDate] = Field(default_factory=list)
    contacts: List[ContactInfo] = Field(default_factory=list)
    # -- EXISTING FIELDS (unchanged) --
    parties, claims, facts, relief_sought, jurisdiction, case_type, procedural_posture
```

### A2. Update Extractor prompt — DONE

`app/prompts/extractor.py` — rewrote with instructions to extract:

- A plain-English document summary (what this document IS and what it CONTAINS)
- Document type classification and action-required flag
- All dates/deadlines mentioned (filing deadlines, hearing dates, response windows) with urgency classification
- Contact information (attorneys, clerks, court addresses found in the document)

### A3. Rewrite Weakness, Counterargument, and Synthesizer prompts for natural language — DONE

Rewrote all three prompt files:

- `app/prompts/weakness.py` — now reads like a senior consultant's memo to a partner. Direct language, varied sentence structure, no robotic enumeration.
- `app/prompts/counterargument.py` — reframed as a devil's advocate litigator. Flips search queries, names specific vulnerabilities, gives concrete preemption advice.
- `app/prompts/synthesizer.py` — written as a senior partner's strategy memo. Leads with what matters most, avoids filler, uses plain action language.

### A4. Clarify `overall_assessment` semantics — DONE

- Changed `StrategyReport.overall_assessment` Field description to: `"Case strength rating: 'strong', 'moderate', or 'weak' — this judges the STRENGTH OF THE CASE, not the quality of the analysis"`
- Synthesizer prompt now says "Rate the overall CASE STRENGTH"
- Frontend badge now renders as "Case Strength: strong/moderate/weak"

---

## Phase B -- Frontend: Theme Overhaul

Complete redesign of `styles.css` color system. Both modes avoid pure white (#fff) and pure black (#000), using warm tones.

### B1. New color system with CSS custom properties and `[data-theme]` — DONE

**Light mode (default):**

- Background: warm linen `#F5F3EF` (not white)
- Card surface: `#FFFEF9` (warm near-white)
- Text: warm charcoal `#2C2825` (not black)
- Muted text: `#78716C`
- Accent: solid gold `#B8860B` (dark goldenrod)
- Accent hover: `#9A7209`
- Border: `#E2DDD4`
- Success/warning/danger: muted professional tones

**Dark mode (toggle):**

- Background: warm dark `#1C1B19` (not black)
- Card surface: `#2C2A24`
- Text: warm off-white `#E7E5E0` (not white)
- Muted text: `#8C877E`
- Accent: lighter gold `#D4A843` for contrast on dark
- Border: `#3D3A32`

### B2. Theme toggle — DONE

Added a sun/moon toggle button to the site header. Preference stored in `localStorage`. Applied via `<html data-theme="light|dark">`. All CSS variables reference `[data-theme]` selectors.

### B3. Typography and layout refinements — DONE

- Kept DM Sans + JetBrains Mono
- Updated header branding: "Brief**AI**" with gold accent
- Updated the primary button to solid gold
- Updated badges, pills, and interactive elements to use the gold palette
- Adjusted ambient glow for both modes (subtle gold radial)

---

## Phase C -- Results Screen Redesign

Major changes to the results UI to be more visual and layman-friendly.

### C1. New results header with action banner — DONE

Before tabs, the results screen now shows:

- **Action Required banner** (red with warning icon) if `action_required === true`, with `action_description`
- **Document Summary card** — the plain-English `summary` from the extractor, with a gold document type badge pill
- **Key Dates strip** — horizontally scrollable chips of `key_dates`, sorted by urgency, with color-coded urgency labels and border tints
- **Case Strength badge** relabeled: "Case Strength: Strong/Moderate/Weak"

### C2. New Overview tab additions — DONE

- **Contacts card** in the bento grid showing extracted contacts with avatar initials, name, role, organization, phone, and address
- **Document Type** gold badge pill in the summary card

### C3. Visual claim strength chart (Chart.js) — DONE

Added a **horizontal bar chart** on the Weaknesses tab showing all claims with their weakness scores on a color-coded 0-1 scale (green for strong, amber for moderate, red for weak). Chart.js loaded from CDN. Chart re-renders on theme toggle to update colors.

### C4. Risk matrix visual on Strategy tab — DONE

Added a **2x2 risk grid** (Likelihood vs. Impact) at the top of the Strategy tab. Weakness scores and counterargument severities are mapped into four quadrants (Critical, Monitor, Mitigate, Low) as labeled dots with color-coded markers.

### C5. Updated rendering in app.js — DONE

- All new render functions wired: `renderActionBanner`, `renderSummaryCard`, `renderDatesStrip`, `renderContacts`, `renderWeaknessChart`, `renderRiskMatrix`
- Chart.js re-renders on theme toggle with correct colors
- SSE pipeline step metadata now includes `dates` and `contacts` counts
- `app/api.py` `_summarize_node_output` updated to emit new extractor field counts

---

## Phase D -- Housekeeping

### D1. Move old plan document — DONE

Moved `legal_brief_analyzer_roadmap_ff2cbc9d.plan.md` to `Development planning/v1_roadmap.md`.

---

## Phase E -- Testing

### E2E Test with sample briefs — DONE

Tested with **Anthropic PBC v. U.S. Department of War (2026)** — a 48-page constitutional complaint. Results:

| Field | Result |
|-------|--------|
| Summary | Clear 2-sentence overview of the complaint |
| Document type | `complaint` |
| Action required | `true` — defendants must respond |
| Key dates | 5 dates (2 past-due deadlines, 3 informational) |
| Contacts | 9 WilmerHale attorneys with phone numbers and addresses |
| Parties | 37 (Anthropic + 36 defendants) |
| Claims | 5 (APA, First Amendment, ultra vires, due process, APA sanctions) |
| Weaknesses | 5 reports scored |
| Counterarguments | 5 predictions (1 critical, 4 moderate) |
| Strategy | Assessment: "weak", 4 actions, 3 risks, 3 focus areas |
| SSE streaming | All events fire with new field counts |

### Popular 2025/2026 cases downloaded — DONE

Three high-profile court documents added to `sample_briefs/`:

| File | Case | Size |
|------|------|------|
| `anthropic_v_dept_of_war_2026.pdf` | Anthropic PBC v. U.S. Dept of War — constitutional challenge (NDCA) | 722 KB |
| `openai_copyright_consolidated_2025.pdf` | In re OpenAI Copyright Infringement MDL — Authors Guild class action (SDNY) | 322 KB |
| `google_adtech_antitrust_opinion_2025.pdf` | United States v. Google LLC — Judge Brinkema ad tech monopoly opinion (EDVA) | 770 KB |

---

## File change summary

**Backend (6 files):**

- `app/schemas.py` — added `KeyDate`, `ContactInfo`, expanded `BriefExtraction`, clarified `overall_assessment`
- `app/prompts/extractor.py` — rewrote to extract new fields
- `app/prompts/weakness.py` — rewrote for natural language tone
- `app/prompts/counterargument.py` — rewrote for natural language tone
- `app/prompts/synthesizer.py` — rewrote for natural language tone + case strength clarification
- `app/api.py` — updated `_summarize_node_output` to include dates/contacts counts

**Frontend (3 files):**

- `frontend/index.html` — new results structure, Chart.js CDN, theme toggle, action banner, summary card, dates strip, contacts card, chart canvas, risk matrix container
- `frontend/styles.css` — full theme overhaul with light/dark CSS variables, gold accent, all new component styles
- `frontend/app.js` — render new fields, Chart.js chart, risk matrix, theme toggle with chart re-render, localStorage persistence

**Test data (3 files):**

- `sample_briefs/anthropic_v_dept_of_war_2026.pdf`
- `sample_briefs/openai_copyright_consolidated_2025.pdf`
- `sample_briefs/google_adtech_antitrust_opinion_2025.pdf`

**Housekeeping (1 move):**

- Old plan moved to `Development planning/v1_roadmap.md`
