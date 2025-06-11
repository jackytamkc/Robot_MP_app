import streamlit as st
from collections import defaultdict
import pandas as pd
import math
import io

###############################################################################
# SHARED UTILITIES
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    """Volume portion for a single usage = disp_vol * 2 if double_disp else disp_vol."""
    return disp_vol * (2 if double_disp else 1)

def check_volume_warning(volume: float) -> str:
    """
    Return a warning label based on volume:
      > 6000 => "EXCEEDS 6000 µL limit!"
      > 5000 => "Consider splitting!"
      otherwise => ""
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 4000:
        return "Consider splitting!"
    return ""

def format_number(num: float) -> str:
    """
    Return a human-friendly representation:
      - If integer, no decimals
      - Otherwise, up to 4 significant digits
    """
    if float(num).is_integer():
        return str(int(num))
    else:
        return f"{num:.4g}"

def choose_diluent(
    rtype: str,
    reagent_name: str = "",   # <-- new parameter to detect if it's Opal-780
    custom: str = ""
) -> str:
    """
    Return default diluent for each reagent type:
      - "H2O2", "PB", "Polymer", "Vectaplex" => ""
      - "Opal" => "amplifier" (EXCEPT if it's Opal 780 => "bondwash/blocker")
      - "TSA-DIG" => "amplifier"
      - "Primary" => "bondwash/blocker"
      - "DAPI" => "TBS"
      - "Custom" => use the 'custom' string
      - else => ""
    """

    # 1) H2O2, PB, Polymer, Vectaplex => no diluent
    if rtype in ["H2O2", "PB", "Polymer", "Vectaplex"]:
        return ""

    # 2) If rtype == "Opal"
    #    - If reagent_name says "780" => bondwash/blocker
    #    - Else => amplifier
    elif rtype == "Opal":
        if "780" in reagent_name:
            return "bondwash/blocker"
        else:
            return "amplifier"

    # 3) TSA-DIG => amplifier
    elif rtype == "TSA-DIG":
        return "amplifier"

    # 4) Primary => bondwash/blocker
    elif rtype == "Primary":
        return "bondwash/blocker"

    # 5) DAPI => TBS
    elif rtype == "DAPI":
        return "TBS"

    # 6) Custom => user-provided
    elif rtype == "Custom":
        return custom

    # 7) Fallback
    return ""


def split_row(row_dict: dict, max_allowed=5000, dead_vol=150) -> list:
    """
    If row's total volume > max_allowed, split it into multiple sub-pots,
    each re-incurring dead_vol. We rely on an internal key "__base_portion"
    if present, else we do total_vol - dead_vol as fallback.
    We'll *not* display "__base_portion" in final table columns.
    """
    # parse total volume
    total_str = row_dict["Total Volume (µL)"]
    try:
        total_vol = float(total_str)
    except:
        total_vol = 0.0

    if total_vol <= max_allowed:
        return [row_dict]  # no splitting needed

    portion = row_dict.get("__base_portion", total_vol - dead_vol)
    if portion < 0:
        portion = 0

    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        # can't fix if dead_vol >= max_allowed
        return [row_dict]

    needed = math.ceil(portion / max_portion)
    new_rows = []
    leftover = portion

    # parse dilution factor
    try:
        dil_factor = float(row_dict["Dilution Factor"])
    except:
        dil_factor = 1.0

    for i in range(needed):
        sub_portion = min(leftover, max_portion)
        leftover -= sub_portion
        pot_total = dead_vol + sub_portion
        stock_vol = pot_total / dil_factor

        sub_row = row_dict.copy()
        sub_row["Reagent"] += f" (Split {i+1}/{needed})"
        sub_row["Total Volume (µL)"] = format_number(pot_total)
        sub_row["Stock Volume (µL)"] = format_number(stock_vol)
        sub_row["Diluent Volume (µL)"] = format_number(pot_total - stock_vol)
        new_warning = check_volume_warning(pot_total)
        sub_row["Warning"] = new_warning
        new_rows.append(sub_row)

    return new_rows

TYPE_ORDER = ["H2O2", "PB", "Primary", "Polymer", "TSA-DIG", "Opal", "DAPI", "Vectaplex", "Custom"]
type_rank  = {t:i for i,t in enumerate(TYPE_ORDER)}

###############################################################################
# SINGLE-PLEX FLOW
###############################################################################

def single_plex_flow(dispense_vol, dead_vol):
    import io
    from collections import defaultdict

    st.write("### Single-Plex Flow")

    # 1) Initialize session state
    if "sp_slides" not in st.session_state:
        st.session_state["sp_slides"] = []
    if "sp_final_rows" not in st.session_state:
        st.session_state["sp_final_rows"] = []
    if "sp_computed" not in st.session_state:
        st.session_state["sp_computed"] = False
    if "sp_pot_named" not in st.session_state:
        st.session_state["sp_pot_named"] = False
    if "sp_pot_names" not in st.session_state:
        st.session_state["sp_pot_names"] = {}

    # 2) Add slides UI
    st.subheader("Add Single-Plex Slide")
    sp_h2o2 = st.checkbox("Use H2O2?", value=True)
    sp_pb   = st.checkbox("Use Protein Block?", value=True)
    sp_neg  = st.checkbox("Negative Control? (skip primary)", value=False)

    sp_pname = st.text_input("Primary Name")
    sp_pdil  = st.number_input("Primary Dilution Fold", min_value=1.0, value=1000.0)
    sp_pdbl  = st.checkbox("Double-Dispense (Primary)?", value=False)

    sp_poly, sp_poly_db = st.selectbox("Polymer", ["Rabbit","Sheep","Goat","Mouse","Rat","Others"]), \
                          st.checkbox("2× Polymer?", value=False)

    sp_opal, sp_odil, sp_odbl = st.selectbox("Opal", ["480","520","540","570","620","650","690","780","others"]), \
                                st.number_input("Opal Dilution Fold", min_value=1.0, value=1000.0), \
                                st.checkbox("2× Opal?", value=False)

    sp_tsa = False; sp_tsdil = 1000.0; sp_tsdb = False
    if sp_opal == "780":
        sp_tsa = st.checkbox("Use TSA-DIG?")
        if sp_tsa:
            sp_tsdil = st.number_input("TSA-DIG Dilution Fold", min_value=1.0, value=1000.0)
            sp_tsdb  = st.checkbox("2× TSA-DIG?", value=False)

    sp_dapi = st.checkbox("Use DAPI?", value=False)
    sp_ddil = 1000.0; sp_ddb = False
    if sp_dapi:
        sp_ddil = st.number_input("DAPI Dilution Fold", min_value=1.0, value=1000.0)
        sp_ddb  = st.checkbox("2× DAPI?", value=False)

    sp_use_cust = st.checkbox("Use Custom Reagent?", value=False)
    sp_cname = ""; sp_cdil=1.0; sp_cdb=False; sp_cdilu=""
    if sp_use_cust:
        sp_cname = st.text_input("Custom Name")
        sp_cdil  = st.number_input("Custom Dilution Fold", min_value=1.0, value=1000.0)
        sp_cdb   = st.checkbox("2× Custom?", value=False)
        sp_cdilu = st.text_input("Custom Diluent", "bondwash/blocker")

    if st.button("Add Slide"):
        if not sp_neg and not sp_pname.strip():
            st.warning("Enter a primary name or check Negative Control.")
        elif sp_use_cust and not sp_cname.strip():
            st.warning("Enter a custom name or uncheck Custom.")
        else:
            st.session_state["sp_slides"].append({
                "H2O2": sp_h2o2, "PB": sp_pb, "Neg": sp_neg,
                "Primary": (sp_pname.strip(), sp_pdil, sp_pdbl),
                "Polymer": (sp_poly, sp_poly_db),
                "Opal":    (sp_opal, sp_odil, sp_odbl),
                "TSA":     (sp_tsa, sp_tsdil, sp_tsdb),
                "DAPI":    (sp_dapi, sp_ddil, sp_ddb),
                "Custom":  (sp_use_cust, sp_cname.strip(), sp_cdil, sp_cdb, sp_cdilu.strip())
            })
            st.success("Slide added.")

    # 3) Remove slides
    st.write("#### Current Slides")
    for i, sl in enumerate(st.session_state["sp_slides"]):
        c1, c2 = st.columns([4,1])
        with c1:
            st.write(f"Slide #{i+1}: Prim={sl['Primary'][0]}, Opal={sl['Opal'][0]}, Neg={sl['Neg']}")
        with c2:
            if st.button(f"Remove {i+1}", key=f"rem_sp_{i}"):
                st.session_state["sp_slides"].pop(i)
                st.experimental_rerun()

    # 4) Build final_rows logic
    def build_sp_table():
        um, summ = defaultdict(list), []
        for idx, sl in enumerate(st.session_state["sp_slides"], start=1):
            seq = []
            if sl["H2O2"]:
                um[("H2O2","H2O2",1.0,False,"")].append(calc_dispense_portion(dispense_vol, False)); seq.append("H2O2")
            if sl["PB"]:
                um[("PB","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol, False)); seq.append("PB")
            # Primary
            pname, pdil, pdbl = sl["Primary"]
            if not sl["Neg"]:
                um[(pname,"Primary",pdil,pdbl,"")].append(calc_dispense_portion(dispense_vol, pdbl))
                seq.append(f"Primary({pname})")
            else:
                seq.append("Primary(skipped)")
            # Polymer
            poly, poldb = sl["Polymer"]
            pname2 = f"Polymer-{poly}"
            um[(pname2,"Polymer",1.0,poldb,"")].append(calc_dispense_portion(dispense_vol, poldb))
            seq.append(pname2)
            # Opal
            op, odil, odbl = sl["Opal"]
            oname = f"Opal-{op}"
            um[(oname,"Opal",odil,odbl,"")].append(calc_dispense_portion(dispense_vol, odbl))
            seq.append(oname)
            # TSA
            tsa, tsdil, tsdbl = sl["TSA"]
            if tsa:
                um[("TSA-DIG","TSA-DIG",tsdil,tsdbl,"")].append(calc_dispense_portion(dispense_vol, tsdbl))
                seq.append("TSA-DIG")
            # DAPI
            dapi, ddil, ddb = sl["DAPI"]
            if dapi:
                um[("DAPI","DAPI",ddil,ddb,"")].append(calc_dispense_portion(dispense_vol, ddb))
                seq.append("DAPI")
            # Custom
            usec, cn, cdil2, cdb2, cdilu2 = sl["Custom"]
            if usec:
                um[(cn,"Custom",cdil2,cdb2,cdilu2)].append(calc_dispense_portion(dispense_vol, cdb2))
                seq.append(f"Custom({cn})")
            summ.append({"Slide": idx, "Sequence": " → ".join(seq)})

        st.subheader("Slide Summary")
        st.table(summ)

        final = []
        for (name, rtype, dil, dbl, cdi), pts in um.items():
            total_pts = sum(pts)
            tv = dead_vol + total_pts
            sv = tv / dil
            wr = check_volume_warning(tv)
            dilu = cdi if rtype=="Custom" else choose_diluent(rtype, name, cdi)
            final.append({
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": dilu,
                "Total Volume (µL)": format_number(tv),
                "Stock Volume (µL)": format_number(sv),
                "Diluent Volume (µL)": format_number(tv - sv),
                "Warning": wr,
                "_base_portion": total_pts
            })
        st.session_state["sp_final_rows"] = final

    # 5) Compute button
    if st.button("Compute Single-Plex Table"):
        build_sp_table()
        st.session_state["sp_computed"] = True
        st.session_state["sp_pot_named"] = False
        st.success("Computed—now name your pots.")

    # 6) Pot naming form
    if st.session_state.get("sp_computed") and not st.session_state.get("sp_pot_named"):
        st.subheader("Name Your Pots")
        with st.form("sp_pot_form"):
            if not st.session_state["sp_pot_names"]:
                st.session_state["sp_pot_names"] = {
                    r["Reagent"]: r["Reagent"]
                    for r in st.session_state["sp_final_rows"]
                }
            for reagent in st.session_state["sp_pot_names"]:
                key = f"sp_pot_{reagent}"
                st.session_state["sp_pot_names"][reagent] = st.text_input(
                    label=reagent,
                    value=st.session_state["sp_pot_names"][reagent],
                    key=key
                )
            if st.form_submit_button("Save Pot Names"):
                st.session_state["sp_pot_named"] = True
                st.success("Pot names saved—scroll down for your table.")
        return  # wait until naming is done

    # 7) Display final table & exports
    if st.session_state.get("sp_computed") and st.session_state.get("sp_pot_named"):
        fr = st.session_state["sp_final_rows"]
        df = pd.DataFrame(fr).drop(columns=["_base_portion"], errors="ignore")

        # Insert Pot Name column
        pot_names = st.session_state["sp_pot_names"]
        df.insert(0, "Pot Name", df["Reagent"].map(pot_names))

        # Group & sort
        TYPE_ORDER = ["H2O2","PB","Primary","Polymer","TSA-DIG","Opal","DAPI","Vectaplex","Custom"]
        rank = {t: i for i,t in enumerate(TYPE_ORDER)}
        df["__rk"] = df["Type"].map(lambda x: rank.get(x,9999))
        df.sort_values(by=["__rk","Pot Name"], inplace=True)
        df.drop(columns="__rk", inplace=True)

        # 29-pot limit
        if len(df) > 29:
            st.error(f"WARNING: {len(df)} total pots—exceeds 29-pot limit!")

        # Highlight
        def hl(row):
            v = float(row["Total Volume (µL)"])
            if v>6000: return ["background-color:#ffcccc"]*len(row)
            if v>4000: return ["background-color:#ffffcc"]*len(row)
            return [""]*len(row)

        st.subheader("Final Single-Plex Table")
        st.write(df.style.apply(hl,axis=1).to_html(), unsafe_allow_html=True)

        # Exports & Print
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv_bytes, "single_v1.1.csv", "text/csv")

        buf = io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="SinglePlex")
        st.download_button("⬇️ Download Excel", buf.getvalue(),
                           "single_v1.1.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown(
            "<button onclick='window.print()' style='padding:8px;font-size:16px;'>🖨 Print Table</button>",
            unsafe_allow_html=True
        )

        # Sequence Guide
        guide_seq = " → ".join(df["Pot Name"])
        st.subheader("Sequence Guide")
        st.write(f"Slide 1: {guide_seq}")

###############################################################################
# MULTI-PLEX FLOW
###############################################################################

def multi_plex_flow(dispense_vol, dead_vol):
    st.write("### Multi-Plex Flow")

    if "mp_slides" not in st.session_state:
        st.session_state["mp_slides"] = []

    # 1) Add Multi-Plex Slide
    st.subheader("Add Multi-Plex Slide")

    mp_h2o2 = st.checkbox("Use H2O2? (Multi-Plex)", value=True)
    mp_pb_before = st.checkbox("Use PB before each primary?", value=True)
    mp_pb_after  = st.checkbox("Use PB after each opal?", value=False)
    mp_neg = st.checkbox("Is this slide a Negative Control? (all primary will be skipped)", value=False)

    # DAPI
    mp_use_dapi = st.checkbox("Use DAPI? (Multi-Plex)", value=False)
    mp_dapi_dil = 1000.0
    mp_dapi_dbl = False
    if mp_use_dapi:
        mp_dapi_dil = st.number_input("DAPI Dil (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_dapi_dbl = st.checkbox("Double Dispense (DAPI)? (Multi-Plex)?", value=False)

    # custom
    mp_use_cust = st.checkbox("Use Custom Reagent? (Multi-Plex)", value=False)
    mp_cname    = ""
    mp_cdil     = 1.0
    mp_cdbl     = False
    mp_cdilu    = ""
    if mp_use_cust:
        mp_cname = st.text_input("Custom Name (Multi-Plex)", "")
        mp_cdil  = st.number_input("Custom Dil (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_cdbl  = st.checkbox("Double Dispense (Custom)? (Multi-Plex)", value=False)
        mp_cdilu = st.text_input("Custom Diluent (Multi-Plex)", "bondwash/blocker")

    # Vectaplex
    mp_vectaplex = st.checkbox("Use Vectaplex? (Multi-Plex)", value=False)
    mp_vect_dbl  = False
    if mp_vectaplex:
        mp_vect_dbl = st.checkbox("Double Dispense (Vectaplex)?", value=False)

    mp_nplex = st.number_input("Number of plex in this Multi-Plex slide?", min_value=1, max_value=8, value=2)

    plex_entries = []
    used_opals = set()
    warn_780_position = False
    warn_duplicate_opal = False

    st.write("#### Configure Each Plex")

    for i in range(mp_nplex):
        st.markdown(f"**Plex #{i+1}**")
        # Row1: Primary
        col1, col2, col3 = st.columns([2,1,1])
        with col1:
            pm_name = st.text_input(f"Primary (Plex {i+1})", key=f"mp_prim_{i}")
        with col2:
            pm_dil = st.number_input(f"Prim Dil (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_prim_dil_{i}")
        with col3:
            pm_dbl = st.checkbox(f"Double(Primary)?", value=False, key=f"mp_prim_dbl_{i}")

        # Row2: Polymer
        col4, col5 = st.columns([2,1])
        with col4:
            pm_poly_opts = ["Rabbit","Sheep","Goat","Mouse","Rat","Others"]
            pm_poly_sel  = st.selectbox(f"Polymer (Plex {i+1})", pm_poly_opts, key=f"mp_poly_{i}")
        with col5:
            pm_poly_dbl  = st.checkbox(f"Double(Polymer)?", value=False, key=f"mp_poly_dbl_{i}")

        # Row3: Opal
        col6, col7, col8 = st.columns([2,1,1])
        with col6:
            opal_opts = ["480","520","540","570","620","650","690","780","others"]
            pm_opal = st.selectbox(f"Opal (Plex {i+1})", opal_opts, key=f"mp_opal_{i}")
        with col7:
            pm_opal_dil = st.number_input(f"Opal Dil (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_opal_dil_{i}")
        with col8:
            pm_opal_dbl = st.checkbox("Double(Opal)?", value=False, key=f"mp_opal_dbl_{i}")

        # ensure unique opal unless "others" or "780"
        if pm_opal not in ["others","780"]:
            if pm_opal in used_opals:
                warn_duplicate_opal = True
            used_opals.add(pm_opal)

        if pm_opal=="780" and i<(mp_nplex-1):
            warn_780_position = True

        pm_tsa_used = False
        pm_tsa_dil  = 1000.0
        pm_tsa_dbl  = False
        if pm_opal=="780":
            st.markdown(f"(Plex {i+1}) => TSA-DIG?")
            pm_tsa_used = st.checkbox(f"Use TSA-DIG? (Plex {i+1})", key=f"mp_tsa_used_{i}")
            if pm_tsa_used:
                pm_tsa_dil = st.number_input(f"TSA-DIG Dil (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_tsa_dil_{i}")
                pm_tsa_dbl = st.checkbox(f"Double(TSA)? (Plex {i+1})", value=False, key=f"mp_tsa_dbl_{i}")

        plex_entries.append({
            "primary_name": pm_name.strip(),
            "primary_dil": pm_dil,
            "primary_dbl": pm_dbl,
            "polymer": pm_poly_sel,
            "polymer_dbl": pm_poly_dbl,
            "opal": pm_opal,
            "opal_dil": pm_opal_dil,
            "opal_dbl": pm_opal_dbl,
            "tsa_used": pm_tsa_used,
            "tsa_dil": pm_tsa_dil,
            "tsa_dbl": pm_tsa_dbl,
        })

    if st.button("Add Multi-Plex Slide"):
        if warn_780_position:
            st.error("Opal 780 must be in the last plex. Please fix or reduce plex count.")
        elif warn_duplicate_opal:
            st.error("Same Opal used multiple times (except '780' or 'others'). Please revise.")
        else:
            if mp_use_cust and not mp_cname.strip():
                st.warning("Enter custom reagent name or uncheck 'Use Custom Reagent'.")
            else:
                mp_slide = {
                    "h2o2": mp_h2o2,
                    "pb_before": mp_pb_before,
                    "pb_after": mp_pb_after,
                    "neg": mp_neg,
                    "use_dapi": mp_use_dapi,
                    "dapi_dil": mp_dapi_dil,
                    "dapi_dbl": mp_dapi_dbl,
                    "use_custom": mp_use_cust,
                    "cust_name": mp_cname.strip(),
                    "cust_dil": mp_cdil,
                    "cust_dbl": mp_cdbl,
                    "cust_dilu": mp_cdilu.strip(),
                    "vectaplex": mp_vectaplex,
                    "vectaplex_dbl": mp_vect_dbl,
                    "plex_list": plex_entries
                }
                st.session_state["mp_slides"].append(mp_slide)
                st.success("Multi-Plex Slide added.")

    # show multi-plex slides + remove
    st.write("#### Current Multi-Plex Slides")
    for idx, sld in enumerate(st.session_state["mp_slides"]):
        colA, colB = st.columns([4,1])
        with colA:
            # guard .get in case older slides don't have these
            vect   = sld.get("vectaplex", False)
            pb_b   = sld.get("pb_before", False)
            pb_a   = sld.get("pb_after", False)
            st.write(f"Slide #{idx+1}: #plex={len(sld['plex_list'])}, vectaplex={vect}, PB_before={pb_b}, PB_after={pb_a}")
        with colB:
            if st.button(f"Remove Multi-Plex Slide {idx+1}", key=f"remove_mp_{idx}"):
                st.session_state["mp_slides"].pop(idx)
                st.rerun()

    if "mp_final_rows" not in st.session_state:
        st.session_state["mp_final_rows"] = []

    def build_mp_table():
        mp_slides_local = st.session_state["mp_slides"]
        if not mp_slides_local:
            st.warning("No multi-plex slides to compute!")
            return

        usage_map = defaultdict(list)
        slide_summaries = []

        # Sequence logic:
        # if opal != 780 => opal => then Vectaplex => but actually we want Vectaplex A & B with same portion
        # if opal == 780 => TSA => Vectaplex => opal
        # each Vectaplex pot => "Vectaplex A" or "Vectaplex B"

        for s_idx, slide in enumerate(mp_slides_local, start=1):
            seq = []
            if slide["h2o2"]:
                usage_map[("H2O2","H2O2",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                seq.append("H2O2")

            for i, plex in enumerate(slide["plex_list"], start=1):
                if slide["pb_before"]:
                    usage_map[("Protein Block (PB)","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                    seq.append("PB(before)")

                if not slide["neg"]:
                    pname = plex["primary_name"] or f"(Prim P{i})"
                    usage_map[(pname,"Primary", plex["primary_dil"], plex["primary_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex["primary_dbl"])
                    )
                    seq.append(f"Primary({pname})")
                else:
                    seq.append(f"Plex {i}: Primary(skipped - neg)")

                pol_name = f"Polymer-{plex['polymer']}"
                usage_map[(pol_name,"Polymer",1.0, plex["polymer_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, plex["polymer_dbl"])
                )
                seq.append(pol_name)

                if plex["opal"]=="780":
                    # TSA => Vectaplex => opal
                    if plex["tsa_used"]:
                        usage_map[("TSA-DIG","TSA-DIG", plex["tsa_dil"], plex["tsa_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, plex["tsa_dbl"])
                        )
                        seq.append("TSA-DIG")

                    if slide["vectaplex"]:
                        # We create 2 pots: "Vectaplex A" & "Vectaplex B", each same portion
                        portion = calc_dispense_portion(dispense_vol, slide["vectaplex_dbl"])
                        usage_map[("Vectaplex A","Vectaplex",1.0,False,"")].append(portion)
                        usage_map[("Vectaplex B","Vectaplex",1.0,False,"")].append(portion)
                        seq.append("Vectaplex(A+B)")

                    op_name = f"Opal-{plex['opal']}"
                    usage_map[(op_name,"Opal", plex["opal_dil"], plex["opal_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex["opal_dbl"])
                    )
                    seq.append(op_name)
                else:
                    # opal => vectaplex
                    op_name = f"Opal-{plex['opal']}"
                    usage_map[(op_name,"Opal", plex["opal_dil"], plex["opal_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex["opal_dbl"])
                    )
                    seq.append(op_name)

                    if slide["vectaplex"]:
                        portion = calc_dispense_portion(dispense_vol, slide["vectaplex_dbl"])
                        usage_map[("Vectaplex A","Vectaplex",1.0,False,"")].append(portion)
                        usage_map[("Vectaplex B","Vectaplex",1.0,False,"")].append(portion)
                        seq.append("Vectaplex(A+B)")

                if slide["pb_after"]:
                    usage_map[("Protein Block (PB)","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                    seq.append("PB(after)")

            # after all plexes => dapi?
            if slide["use_dapi"]:
                usage_map[("DAPI","DAPI", slide["dapi_dil"], slide["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, slide["dapi_dbl"])
                )
                seq.append("DAPI")

            # custom?
            if slide["use_custom"]:
                cname = slide["cust_name"]
                cdil  = slide["cust_dil"]
                cdbl  = slide["cust_dbl"]
                cdilu = slide["cust_dilu"]
                usage_map[(cname,"Custom", cdil, cdbl, cdilu)].append(
                    calc_dispense_portion(dispense_vol, cdbl)
                )
                seq.append(f"Custom({cname})")

            slide_summaries.append({"Multi-Plex Slide": s_idx, "Sequence":" → ".join(seq)})

        st.subheader("Multi-Plex Slide Summary")
        st.table(slide_summaries)

        # unify usage
        final_rows = []
        for (name, rtype, dil, dbl, cdi), portions in usage_map.items():
            sum_portions = sum(portions)
            tot_volume = dead_vol + sum_portions
            stock_vol = tot_volume / dil
            warn_label = check_volume_warning(tot_volume)

            # << Instead of this: >>
            # if rtype=="Custom":
            #     used_diluent = cdi
            # else:
            #     used_diluent = choose_diluent(rtype)

            # << Do THIS: pass both rtype and name, plus custom if rtype==Custom >>
            used_diluent = ""
            if rtype == "Custom":
                # if it's custom, pass cdi as the 'custom' string
                used_diluent = choose_diluent(rtype, reagent_name=name, custom=cdi)
            else:
                # otherwise, just pass rtype and the name (like "Opal-780")
                used_diluent = choose_diluent(rtype, reagent_name=name)

            row_dict = {
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": used_diluent,
                "Total Volume (µL)": format_number(tot_volume),
                "Stock Volume (µL)": format_number(stock_vol),
                "Diluent Volume (µL)": format_number(tot_volume - stock_vol),
                "Warning": warn_label,
            }
            final_rows.append(row_dict)

        st.session_state["mp_final_rows"] = final_rows

    if st.button("Compute Multi-Plex Table"):
        build_mp_table()
        st.session_state.pop("mp_pot_names", None)
        st.session_state.pop("mp_pot_named", None)
        st.success("Multi-Plex table built! Scroll down.")

    final = st.session_state.get("mp_final_rows", [])
    if not final:
        return

    if "mp_pot_named" not in st.session_state:
        st.subheader("Name Your Pots")
        with st.form("pot_naming form"):
            if "mp_pot_names" not in st.session_state:
                st.session_state["mp_pot_names"] = {}
                for r in final:
                    st.session_state["mp_pot_names"][r["Reagent"]] = r["Reagent"]

            for r in final:
                key = f"pot_name__{r['Reagent']}"
                st.session_state["mp_pot_names"][r["Reagent"]] = st.text_input(
                    label=f"{r['Reagent']}",
                    value=st.session_state["mp_pot_names"][r["Reagent"]],
                    key=key
                )

            submit = st.form_submit_button("Use These Pot Names")
            if submit:
                st.session_state["mp_pot_named"] = True
                st.success("Pot names saved! Scroll down to see your custom-named table.")

        return  # wait for user to name pots
    df = pd.DataFrame(final).drop(columns=["__base_portion"], errors="ignore")
    # insert Pot Name column from user inputs
    pot_names = st.session_state["mp_pot_names"]
    df.insert(0, "Pot Name", df["Reagent"].map(pot_names))

    # grouping by Type as before
    TYPE_ORDER = ["H2O2", "PB", "Primary", "Polymer", "TSA-DIG", "Opal", "DAPI", "Vectaplex", "Custom"]
    type_rank = {t: i for i, t in enumerate(TYPE_ORDER)}
    df["__rk"] = df["Type"].map(lambda x: type_rank.get(x, 9999))
    df.sort_values(by=["__rk", "Pot Name"], inplace=True)
    df.drop(columns="__rk", inplace=True)

    # 4) Display the table with coloring
    def highlight(r):
        v = float(r["Total Volume (µL)"])
        if v > 6000: return ["background-color:#ffcccc"] * len(r)
        if v > 4000: return ["background-color:#ffffcc"] * len(r)
        return [""] * len(r)

    st.subheader("Multi-Plex Reagent Table")
    st.write(df.style.apply(highlight, axis=1).to_html(), unsafe_allow_html=True)

    # pot-limit check
    if len(df) > 29:
        st.error(f"WARNING: {len(df)} total pots exceed the 29-pot limit!")

    # 5) Export & Print buttons
    # CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv_bytes, "multi_plex_v1.1.csv", "text/csv")

    # Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="MultiPlex")
    st.download_button(
        "⬇️ Download XLSX",
        buf.getvalue(),
        "multi_plex_v1.1.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Print
    st.markdown(
        "<button onclick='window.print()' style='padding:8px;font-size:16px;'>🖨 Print Table</button>",
        unsafe_allow_html=True
    )

    st.subheader("Plex Sequence Guide")

    pot_names = st.session_state["mp_pot_names"]
    guide_rows = []

    for slide_idx, slide in enumerate(st.session_state["mp_slides"], start=1):
        seq_parts = []
        for plex_i, plex in enumerate(slide["plex_list"], start=1):
            # Primary
            pname = plex["primary_name"].strip() or f"(Prim {plex_i})"
            seq_parts.append(pot_names.get(pname, pname))

            # Polymer
            poly_name = f"Polymer-{plex['polymer']}"
            seq_parts.append(pot_names.get(poly_name, poly_name))

            # Opal
            op_name = f"Opal-{plex['opal']}"
            seq_parts.append(pot_names.get(op_name, op_name))

        guide_rows.append({
            "Slide": slide_idx,
            "Sequence": " → ".join(seq_parts)
        })

    guide_df = pd.DataFrame(guide_rows)
    st.table(guide_df)


###############################################################################
# MAIN APP
###############################################################################

def main_app():
    st.title("BondRX Opal Reagent Prep Bot, Created by Jacky@Ramachandran Lab, V1.1")

    # Global Settings
    st.header("Global Settings")
    dispense_vol = st.number_input("Dispense Volume (µL)", min_value=1, max_value=9999, value=150)
    dead_vol     = st.number_input("Dead Volume (µL)", min_value=0, max_value=9999, value=150)
    st.write("---")

    # Flow choice
    flow_choice = st.radio("Select Flow:", ["Single-Plex","Multi-Plex"])
    if flow_choice=="Single-Plex":
        single_plex_flow(dispense_vol, dead_vol)
    else:
        multi_plex_flow(dispense_vol, dead_vol)


def main():
    main_app()

if __name__=="__main__":
    main()
