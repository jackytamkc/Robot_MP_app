### Robot_MP_app V1.2 — updated 10/03/2026
App link: https://ramachandranlabrobot.streamlit.app/

App built for BondRX autostaining robot multiplex reagent prep list. Set up your slides and reagents, and the app calculates all volumes needed for your run.

---

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## User Instructions

**Global Settings**
Set Dispense Volume and Dead Volume before configuring slides. Default values (150 µL each) are for BondRX. For BondIII (older model) set dead volume to 600 µL.

**Adding Slides**
- Set "Number of plexes" — use 1 for single-plex, 2–8 for multi-plex. Single-plex is no longer a separate mode.
- Configure H2O2, Protein Block, DAPI, Custom, and Vectaplex at the slide level.
- Configure Primary, Polymer, Opal (and TSA-DIG if Opal 780) per plex.
- Click **Add Slide**. Repeat for each slide in your run.

**Computing**
Click **Compute Table** to calculate all reagent volumes. Volumes >4000 µL are flagged yellow; >6000 µL flagged red.

**Pot Naming**
After computing, assign pot labels to each reagent. You will be prompted to save the configuration after naming pots.

**Splitting**
If any reagent exceeds 4000 µL, a split button appears to divide it across multiple pots (each with its own dead volume).

**Exports**
Download as CSV or Excel. Filenames include your config name and a date-time stamp (e.g. `6plex_CD3_CD8_20260310_1430.csv`).

**Login & Saved Configurations**
Create an account to save and reload configurations. Configs are saved per user with a timestamp. Load a previous config, make minimal changes, and recompute — no need to re-enter everything from scratch.

---

## Changelog

### V1.2 — 2026-03-10
- **User login & accounts** — register/login via sidebar; sessions are isolated per user
- **Save & load configurations** — save named configs with date-time stamps; reload and edit
- **Auto-save prompt** — after saving pot names, app prompts to save the full configuration
- **Merged single/multi-plex flow** — one unified flow; set plexes = 1 for single-plex
- **Download filenames** — CSV/Excel files now named `{config}_{YYYYMMDD_HHMM}.{ext}`
- **Slide cards** — current slides shown as expandable colour-coded cards with per-plex badges
- **Widget key fix** — fixed state-loss bug where Vectaplex/DAPI checkboxes reset on rerender

### V1.1 — 2025-05-16
- Splitting warning threshold changed from 5000 to 4000 µL
- Reagent types grouped and sorted in output table
- CSV / Excel export and print function

### V1.0
- Single-plex and multi-plex modules
