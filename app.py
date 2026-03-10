import streamlit as st
from collections import defaultdict
from datetime import datetime
import pandas as pd
import math
import io
import json
import hashlib
from pathlib import Path

###############################################################################
# SHARED UTILITIES
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    return disp_vol * (2 if double_disp else 1)

def check_volume_warning(volume: float) -> str:
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    if volume > 4000:
        return "Consider splitting!"
    return ""

def format_number(num: float) -> str:
    if float(num).is_integer():
        return str(int(num))
    return f"{num:.4g}"

def choose_diluent(rtype: str, reagent_name: str = "", custom: str = "") -> str:
    if rtype in ["H2O2", "PB", "Polymer", "Vectaplex"]:
        return ""
    if rtype == "Opal":
        return "bondwash/blocker" if "780" in reagent_name else "amplifier"
    if rtype == "TSA-DIG":
        return "amplifier"
    if rtype == "Primary":
        return "bondwash/blocker"
    if rtype == "DAPI":
        return "TBS"
    if rtype == "Custom":
        return custom
    return ""

def split_row(row: dict, max_allowed=5000, dead_vol=150) -> list[dict]:
    try:
        total_vol = float(row["Total Volume (µL)"])
    except Exception:
        return [row]
    if total_vol <= max_allowed:
        return [row]

    base = row.get("__base_portion", total_vol - dead_vol)
    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        return [row]

    needed = math.ceil(base / max_portion)
    leftover = base
    try:
        dil = float(row["Dilution Factor"])
    except Exception:
        dil = 1.0

    out = []
    for i in range(needed):
        portion = min(leftover, max_portion)
        leftover -= portion
        tv = dead_vol + portion
        sv = tv / dil
        new = row.copy()
        new["Reagent"] += f" (Split {i+1}/{needed})"
        new["Total Volume (µL)"]   = format_number(tv)
        new["Stock Volume (µL)"]   = format_number(sv)
        new["Diluent Volume (µL)"] = format_number(tv - sv)
        new["Warning"]             = check_volume_warning(tv)
        out.append(new)
    return out

def _dl_name(ext: str) -> str:
    """Build a download filename: {config_name}_{YYYYMMDD_HHMM}.{ext}"""
    cfg = st.session_state.get("current_config_name", "reagent_prep")
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{cfg}_{ts}.{ext}"

TYPE_ORDER = ["H2O2", "PB", "Primary", "Polymer", "TSA-DIG", "Opal", "DAPI", "Vectaplex", "Custom"]
type_rank  = {t: i for i, t in enumerate(TYPE_ORDER)}

###############################################################################
# AUTH & CONFIG PERSISTENCE
###############################################################################

USERS_FILE  = Path("users.json")
CONFIGS_DIR = Path("saved_configs")


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}


def _save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _persist_config(name: str):
    """Save current session under {name}_{timestamp}.json for the logged-in user."""
    user = st.session_state.get("logged_in_user")
    if not user:
        return None
    CONFIGS_DIR.mkdir(exist_ok=True)
    user_dir = CONFIGS_DIR / user
    user_dir.mkdir(exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M")
    full_name = f"{name}_{ts}"
    data = {
        "dispense_vol": st.session_state.get("dispense_vol_input", 150),
        "dead_vol":     st.session_state.get("dead_vol_input",     150),
        "mp_slides":    st.session_state.get("mp_slides", []),
    }
    (user_dir / f"{full_name}.json").write_text(json.dumps(data, indent=2, default=list))
    st.session_state["current_config_name"] = full_name
    return full_name


def login_sidebar() -> "str | None":
    """Render login/register in sidebar. Returns username when authenticated."""
    st.session_state.setdefault("logged_in_user", None)
    user = st.session_state["logged_in_user"]

    with st.sidebar:
        st.header("👤 Account")
        if user:
            st.success(f"Logged in as **{user}**")
            if st.button("Logout", key="logout_btn"):
                st.session_state["logged_in_user"] = None
                st.rerun()
            return user

        tab_in, tab_reg = st.tabs(["Login", "Register"])

        with tab_in:
            uname = st.text_input("Username", key="login_uname")
            pw    = st.text_input("Password", type="password", key="login_pw")
            if st.button("Login", key="login_btn"):
                users = _load_users()
                if uname in users and users[uname] == _hash(pw):
                    st.session_state["logged_in_user"] = uname
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        with tab_reg:
            new_u  = st.text_input("Choose Username",  key="reg_uname")
            new_p  = st.text_input("Password",         type="password", key="reg_pw")
            new_p2 = st.text_input("Confirm Password", type="password", key="reg_pw2")
            if st.button("Create Account", key="reg_btn"):
                if not new_u.strip():
                    st.error("Enter a username.")
                elif new_p != new_p2:
                    st.error("Passwords don't match.")
                else:
                    users = _load_users()
                    if new_u in users:
                        st.error("Username already taken.")
                    else:
                        users[new_u] = _hash(new_p)
                        _save_users(users)
                        st.success("Account created! Please log in.")

    return None


def config_sidebar(username: str):
    """Manual save/load of named configurations in sidebar."""
    CONFIGS_DIR.mkdir(exist_ok=True)
    user_dir = CONFIGS_DIR / username
    user_dir.mkdir(exist_ok=True)

    with st.sidebar:
        st.markdown("---")
        st.header("💾 Configurations")

        # ── Manual save ───────────────────────────────────────────────────────
        st.subheader("Save current session")
        cfg_name = st.text_input("Config name", key="cfg_save_name",
                                  placeholder="e.g. 6plex_CD3_CD8")
        if st.button("💾 Save", key="cfg_save_btn"):
            if not cfg_name.strip():
                st.error("Enter a config name.")
            else:
                saved = _persist_config(cfg_name.strip())
                st.success(f"Saved as '{saved}'")

        # ── Load ──────────────────────────────────────────────────────────────
        st.subheader("Load saved session")
        saved_list = sorted(f.stem for f in user_dir.glob("*.json"))
        if not saved_list:
            st.info("No saved configurations yet.")
            return

        sel = st.selectbox("Select config", saved_list, key="cfg_load_sel")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 Load", key="cfg_load_btn"):
                data = json.loads((user_dir / f"{sel}.json").read_text())
                st.session_state["dispense_vol_input"] = data.get("dispense_vol", 150)
                st.session_state["dead_vol_input"]     = data.get("dead_vol",     150)
                st.session_state["mp_slides"]          = data.get("mp_slides", [])
                # Reset computed state
                for k in ("mp_final_rows", "mp_final_rows_unsplit"):
                    st.session_state[k] = []
                for k in ("mp_pot_named", "mp_split_done"):
                    st.session_state[k] = False
                st.session_state["mp_pot_names"] = {}
                st.session_state["current_config_name"] = sel
                st.success(f"Loaded '{sel}' — review slides, then compute.")
                st.rerun()
        with col2:
            if st.button("🗑 Delete", key="cfg_del_btn"):
                (user_dir / f"{sel}.json").unlink(missing_ok=True)
                st.success(f"Deleted '{sel}'")
                st.rerun()

###############################################################################
# PLEX FLOW  (single-plex = multi-plex with 1 plex configured)
###############################################################################

def plex_flow(dispense_vol: float, dead_vol: float):
    st.session_state.setdefault("mp_slides",             [])
    st.session_state.setdefault("mp_final_rows_unsplit", [])
    st.session_state.setdefault("mp_final_rows",         [])
    st.session_state.setdefault("mp_pot_names",          {})
    st.session_state.setdefault("mp_pot_named",          False)
    st.session_state.setdefault("mp_split_done",         False)
    st.session_state.setdefault("mp_show_autosave",      False)

    # ── Add Slide UI ───────────────────────────────────────────────────────────
    st.subheader("Add Slide")
    # Explicit keys on every widget prevent index-shift state loss when
    # conditional sub-widgets (DAPI, Custom) are toggled.
    mp_h2o2      = st.checkbox("Use H2O2?",                          True,  key="mp_h2o2_cb")
    mp_pb_before = st.checkbox("Use PB before primary?",             True,  key="mp_pb_before_cb")
    mp_pb_after  = st.checkbox("Use PB after opal?",                 False, key="mp_pb_after_cb")
    mp_neg       = st.checkbox("Negative Control? (skip all primary)", False, key="mp_neg_cb")

    mp_use_dapi = st.checkbox("Use DAPI?", False, key="mp_dapi_cb")
    mp_dd = 1000.0; mp_db = False
    if mp_use_dapi:
        mp_dd = st.number_input("DAPI Dilution Fold", 1.0, 1000.0, key="mp_dapi_dil")
        mp_db = st.checkbox("2× DAPI?", False, key="mp_dapi_dbl")

    mp_use_cust = st.checkbox("Use Custom Reagent?", False, key="mp_cust_cb")
    mp_cn = ""; mp_cd = 1.0; mp_cb = False; mp_ci = ""
    if mp_use_cust:
        mp_cn = st.text_input("Custom Name",                    key="mp_cust_name")
        mp_cd = st.number_input("Custom Dilution Fold", 1.0, 1000.0, key="mp_cust_dil")
        mp_cb = st.checkbox("2× Custom?", False,                key="mp_cust_dbl")
        mp_ci = st.text_input("Custom Diluent", "bondwash/blocker", key="mp_cust_dilu")

    mp_vect = st.checkbox("Use Vectaplex?", False, key="mp_vect_cb")
    mp_vdb = False
    if mp_vect:
        mp_vdb = st.checkbox("2× Vectaplex?", False, key="mp_vect_dbl")

    mp_n = int(st.number_input("Number of plexes", 1, 8, 1, key="mp_n_input"))

    used_opals = set(); warn_pos = False; warn_dup = False
    plex_list  = []
    st.write("#### Configure Each Plex")
    for i in range(mp_n):
        st.markdown(f"**Plex {i+1}**")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            pname = st.text_input(f"Primary (#{i+1})", key=f"mp_pn_{i}")
        with c2:
            pdil = st.number_input(f"Prim Dil (#{i+1})", 1.0, 1000.0, key=f"mp_pd_{i}")
        with c3:
            pdb  = st.checkbox("2× Primary?", False, key=f"mp_pdb_{i}")

        c4, c5 = st.columns([2, 1])
        with c4:
            poly = st.selectbox(f"Polymer (#{i+1})",
                                ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"],
                                key=f"mp_poly_{i}")
        with c5:
            pdb2 = st.checkbox("2× Polymer?", False, key=f"mp_pdb2_{i}")

        c6, c7, c8 = st.columns([2, 1, 1])
        with c6:
            opal = st.selectbox(f"Opal (#{i+1})",
                                ["480", "520", "540", "570", "620", "650", "690", "780", "others"],
                                key=f"mp_opal_{i}")
        with c7:
            odil = st.number_input(f"Opal Dil (#{i+1})", 1.0, 1000.0, key=f"mp_odil_{i}")
        with c8:
            odb  = st.checkbox("2× Opal?", False, key=f"mp_odb_{i}")

        if opal not in ["others", "780"] and opal in used_opals:
            warn_dup = True
        used_opals.add(opal)
        if opal == "780" and i < mp_n - 1:
            warn_pos = True

        tsa = False; tsd = 1000.0; tsb = False
        if opal == "780":
            tsa = st.checkbox(f"Use TSA-DIG? (#{i+1})", key=f"mp_tsa_{i}")
            if tsa:
                tsd = st.number_input(f"TSA Dil (#{i+1})", 1.0, 1000.0, key=f"mp_tsd_{i}")
                tsb = st.checkbox("2× TSA?", False, key=f"mp_tsb_{i}")

        plex_list.append({
            "primary_name": pname.strip(),
            "primary_dil":  pdil,
            "primary_dbl":  pdb,
            "polymer":      poly,
            "polymer_dbl":  pdb2,
            "opal":         opal,
            "opal_dil":     odil,
            "opal_dbl":     odb,
            "tsa_used":     tsa,
            "tsa_dil":      tsd,
            "tsa_dbl":      tsb,
        })

    if st.button("Add Slide"):
        if warn_pos:
            st.error("Opal 780 must be the last plex.")
        elif warn_dup:
            st.error("Duplicate non-780 Opal.")
        elif mp_use_cust and not mp_cn.strip():
            st.warning("Enter custom reagent name or uncheck Custom.")
        else:
            st.session_state["mp_slides"].append({
                "h2o2":         mp_h2o2,
                "pb_before":    mp_pb_before,
                "pb_after":     mp_pb_after,
                "neg":          mp_neg,
                "use_dapi":     mp_use_dapi, "dapi_dil":  mp_dd,          "dapi_dbl":     mp_db,
                "use_custom":   mp_use_cust, "cust_name": mp_cn.strip(),  "cust_dil":     mp_cd,
                "cust_dbl":     mp_cb,       "cust_dilu": mp_ci.strip(),
                "vectaplex":    mp_vect,     "vectaplex_dbl": mp_vdb,
                "plex_list":    plex_list,
            })
            st.success("Slide added.")

    # ── Current Slides display ─────────────────────────────────────────────────
    st.write("#### Current Slides")

    def _badge(label, bg, fg="white"):
        return (f'<span style="background:{bg};color:{fg};padding:2px 8px;'
                f'border-radius:10px;font-size:12px;margin:2px;display:inline-block">'
                f'{label}</span>')

    for i, sl in enumerate(st.session_state["mp_slides"]):
        n_plex = len(sl["plex_list"])
        label  = "Single-Plex" if n_plex == 1 else f"{n_plex}-Plex"
        with st.expander(f"Slide #{i+1} — {label}", expanded=True):
            flags = []
            if sl["h2o2"]:       flags.append(_badge("H2O2",      "#78909c"))
            if sl["pb_before"]:  flags.append(_badge("PB-before", "#42a5f5"))
            if sl["pb_after"]:   flags.append(_badge("PB-after",  "#29b6f6"))
            if sl["neg"]:        flags.append(_badge("NEG CTRL",  "#ef5350"))
            if sl["vectaplex"]:
                flags.append(_badge(
                    f"Vectaplex{'(2×)' if sl['vectaplex_dbl'] else ''}", "#66bb6a"))
            if sl["use_dapi"]:
                flags.append(_badge(
                    f"DAPI 1:{sl['dapi_dil']:.4g}{'(2×)' if sl['dapi_dbl'] else ''}", "#5c6bc0"))
            if sl["use_custom"]:
                flags.append(_badge(f"Custom:{sl['cust_name']}", "#8d6e63"))
            st.markdown(" ".join(flags) or "_No global flags_", unsafe_allow_html=True)
            st.markdown("---")

            for j, px in enumerate(sl["plex_list"], start=1):
                parts = []
                if sl["neg"]:
                    parts.append(_badge("Primary: skipped", "#bdbdbd", "#333"))
                else:
                    lbl = f"Primary: {px['primary_name'] or '(unnamed)'} 1:{px['primary_dil']:.4g}"
                    if px["primary_dbl"]: lbl += " (2×)"
                    parts.append(_badge(lbl, "#ff7043"))

                poly_lbl = f"Polymer: {px['polymer']}"
                if px["polymer_dbl"]: poly_lbl += " (2×)"
                parts.append(_badge(poly_lbl, "#ffd54f", "#333"))

                if px["opal"] == "780" and px["tsa_used"]:
                    tsa_lbl = f"TSA-DIG 1:{px['tsa_dil']:.4g}"
                    if px["tsa_dbl"]: tsa_lbl += " (2×)"
                    parts.append(_badge(tsa_lbl, "#ab47bc"))

                opal_lbl = f"Opal-{px['opal']} 1:{px['opal_dil']:.4g}"
                if px["opal_dbl"]: opal_lbl += " (2×)"
                parts.append(_badge(opal_lbl, "#00acc1"))

                arrow = ' <span style="color:#aaa">→</span> '
                st.markdown(f"<b>Plex {j}:</b> " + arrow.join(parts), unsafe_allow_html=True)

            st.markdown("")
            if st.button(f"🗑 Remove Slide #{i+1}", key=f"rem_mp_{i}"):
                st.session_state["mp_slides"].pop(i)
                st.rerun()

    # ── Build Usage ────────────────────────────────────────────────────────────
    def build_table():
        um, summary = defaultdict(list), []
        for idx, sl in enumerate(st.session_state["mp_slides"], start=1):
            seq = []
            if sl["h2o2"]:
                um[("H2O2", "H2O2", 1.0, False, "")].append(
                    calc_dispense_portion(dispense_vol, False))
                seq.append("H2O2")
            for pi, px in enumerate(sl["plex_list"], start=1):
                if sl["pb_before"]:
                    um[("PB", "PB", 1.0, False, "")].append(
                        calc_dispense_portion(dispense_vol, False))
                    seq.append("PB(before)")
                nm = px["primary_name"] or f"P{pi}"
                if not sl["neg"]:
                    um[(nm, "Primary", px["primary_dil"], px["primary_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, px["primary_dbl"]))
                seq.append(f"Primary({nm})")
                poly_k = f"Polymer-{px['polymer']}"
                um[(poly_k, "Polymer", 1.0, px["polymer_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, px["polymer_dbl"]))
                seq.append(poly_k)

                if px["opal"] == "780":
                    if px["tsa_used"]:
                        um[("TSA-DIG", "TSA-DIG", px["tsa_dil"], px["tsa_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, px["tsa_dbl"]))
                        seq.append("TSA-DIG")
                    if sl["vectaplex"]:
                        p = calc_dispense_portion(dispense_vol, sl["vectaplex_dbl"])
                        um[("Vectaplex A", "Vectaplex", 1.0, False, "")].append(p)
                        um[("Vectaplex B", "Vectaplex", 1.0, False, "")].append(p)
                        seq.append("Vectaplex(A+B)")
                    op_name = "Opal-780"
                else:
                    op_name = f"Opal-{px['opal']}"
                um[(op_name, "Opal", px["opal_dil"], px["opal_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, px["opal_dbl"]))
                seq.append(op_name)
                if sl["vectaplex"] and px["opal"] != "780":
                    p = calc_dispense_portion(dispense_vol, sl["vectaplex_dbl"])
                    um[("Vectaplex A", "Vectaplex", 1.0, False, "")].append(p)
                    um[("Vectaplex B", "Vectaplex", 1.0, False, "")].append(p)
                    seq.append("Vectaplex(A+B)")
                if sl["pb_after"]:
                    um[("PB", "PB", 1.0, False, "")].append(
                        calc_dispense_portion(dispense_vol, False))
                    seq.append("PB(after)")

            if sl["use_dapi"]:
                um[("DAPI", "DAPI", sl["dapi_dil"], sl["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sl["dapi_dbl"]))
                seq.append("DAPI")
            if sl["use_custom"]:
                cn, cd, cb, ci = sl["cust_name"], sl["cust_dil"], sl["cust_dbl"], sl["cust_dilu"]
                um[(cn, "Custom", cd, cb, ci)].append(calc_dispense_portion(dispense_vol, cb))
                seq.append(f"Custom({cn})")
            summary.append({"Slide": idx, "Sequence": " → ".join(seq)})

        st.subheader("Slide Summary")
        st.table(summary)

        out = []
        for (rname, rtype, dil, dbl, cdi), pts in um.items():
            s    = sum(pts)
            tv   = dead_vol + s
            sv   = tv / dil
            wr   = check_volume_warning(tv)
            dilu = cdi if rtype == "Custom" else choose_diluent(rtype, rname, cdi)
            out.append({
                "Reagent":             rname,
                "Type":                rtype,
                "Dilution Factor":     format_number(dil),
                "Double Disp?":        "Yes" if dbl else "No",
                "Diluent":             dilu,
                "Total Volume (µL)":   format_number(tv),
                "Stock Volume (µL)":   format_number(sv),
                "Diluent Volume (µL)": format_number(tv - sv),
                "Warning":             wr,
                "__base_portion":      s,
            })
        st.session_state["mp_final_rows_unsplit"] = out
        st.session_state["mp_split_done"]         = False
        st.session_state["mp_final_rows"]         = out

    # ── Compute Button ─────────────────────────────────────────────────────────
    if st.button("Compute Table"):
        build_table()
        st.session_state["mp_pot_named"]     = False
        st.session_state["mp_show_autosave"] = False
        st.success("Computed — now name your pots.")

    # ── Pot Naming ─────────────────────────────────────────────────────────────
    final = st.session_state.get("mp_final_rows", [])
    if final and not st.session_state["mp_pot_named"]:
        st.subheader("Name Your Pots")
        with st.form("mp_pot_form"):
            if not st.session_state["mp_pot_names"]:
                st.session_state["mp_pot_names"] = {r["Reagent"]: r["Reagent"] for r in final}
            for reagent in st.session_state["mp_pot_names"]:
                st.session_state["mp_pot_names"][reagent] = st.text_input(
                    label=reagent,
                    value=st.session_state["mp_pot_names"][reagent],
                    key=f"mp_pot_{reagent}"
                )
            if st.form_submit_button("Save Pot Names"):
                st.session_state["mp_pot_named"]     = True
                st.session_state["mp_show_autosave"] = True
                st.success("Pot names saved.")

    # ── Auto-save prompt after pot naming ──────────────────────────────────────
    if st.session_state.get("mp_show_autosave") and st.session_state.get("mp_pot_named"):
        st.info("💾 Save this configuration before downloading?")
        with st.form("mp_autosave_form"):
            auto_name = st.text_input("Config name",
                                      placeholder="e.g. 6plex_CD3_CD8_run1",
                                      key="mp_autosave_name")
            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("💾 Save"):
                    if not auto_name.strip():
                        st.warning("Enter a config name.")
                    else:
                        saved = _persist_config(auto_name.strip())
                        st.session_state["mp_show_autosave"] = False
                        st.success(f"Saved as '{saved}'")
                        st.rerun()
            with c2:
                if st.form_submit_button("Skip"):
                    st.session_state["mp_show_autosave"] = False
                    st.rerun()

    # ── Splitting Prompt ───────────────────────────────────────────────────────
    rows  = st.session_state.get("mp_final_rows", [])
    needs = any(r["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"] for r in rows)
    if st.session_state["mp_pot_named"] and needs and not st.session_state["mp_split_done"]:
        if st.button("Split Rows >4000 µL?"):
            new = []
            for r in rows:
                if r["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"]:
                    new.extend(split_row(r, max_allowed=4000, dead_vol=dead_vol))
                else:
                    new.append(r)
            st.session_state["mp_final_rows"] = new
            st.session_state["mp_split_done"] = True
            st.success("Splitting done — see updated table.")

    # ── Final Table & Exports ─────────────────────────────────────────────────
    if st.session_state["mp_pot_named"]:
        df = pd.DataFrame(st.session_state["mp_final_rows"]).drop(
            columns=["__base_portion"], errors="ignore")
        pn = st.session_state["mp_pot_names"]
        df.insert(0, "Pot Name",
                  df["Reagent"].map(lambda r: pn.get(r, pn.get(r.split(" (")[0], r.split(" (")[0]))))
        df["__rk"] = df["Type"].map(lambda x: type_rank.get(x, 9999))
        df.sort_values(by=["__rk", "Pot Name"], inplace=True)
        df.drop("__rk", axis=1, inplace=True)

        def hl(r):
            v = float(r["Total Volume (µL)"])
            if v > 6000: return ["background-color:#ffcccc"] * len(r)
            if v > 4000: return ["background-color:#ffffcc"] * len(r)
            return [""] * len(r)

        st.subheader("Reagent Preparation Table")
        st.write(df.style.apply(hl, axis=1).to_html(), unsafe_allow_html=True)
        if len(df) > 29:
            st.error(f"{len(df)} pots exceed 29-pot limit!")

        # Downloads with config-name + timestamp in filename
        st.download_button("⬇️ CSV", df.to_csv(index=False).encode(),
                           _dl_name("csv"), "text/csv")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="ReagentPrep")
        st.download_button("⬇️ Excel", buf.getvalue(),
                           _dl_name("xlsx"),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("<button onclick='window.print()'>🖨 Print Table</button>",
                    unsafe_allow_html=True)

        st.subheader("Plex Sequence Guide")
        guide = []
        for si, sl in enumerate(st.session_state["mp_slides"], start=1):
            parts = []
            for px in sl["plex_list"]:
                base = px["primary_name"] or ""
                parts.append(pn.get(base, base))
                parts.append(pn.get(f"Polymer-{px['polymer']}", f"Polymer-{px['polymer']}"))
                parts.append(pn.get(f"Opal-{px['opal']}", f"Opal-{px['opal']}"))
            guide.append({"Slide": si, "Sequence": " → ".join(parts)})
        st.table(pd.DataFrame(guide))

###############################################################################
# MAIN APP
###############################################################################

def main():
    st.title("BondRX Opal Reagent Prep Bot, Created by Jacky@Ramachandran Lab, V1.2")

    user = login_sidebar()
    if not user:
        st.info("👈 Please log in (or create an account) using the sidebar.")
        st.stop()

    config_sidebar(user)

    st.header("Global Settings")
    dispense_vol = st.number_input("Dispense Volume (µL)", min_value=1, max_value=9999,
                                   value=150, key="dispense_vol_input")
    dead_vol     = st.number_input("Dead Volume (µL)",     min_value=0, max_value=9999,
                                   value=150, key="dead_vol_input")
    st.write("---")

    plex_flow(dispense_vol, dead_vol)

if __name__ == "__main__":
    main()
