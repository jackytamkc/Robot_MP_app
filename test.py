import streamlit as st
from collections import defaultdict
import pandas as pd
import math


###############################################################################
# SHARED UTILITIES
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    """Portion = dispense_vol * 2 if double_disp else just dispense_vol."""
    return disp_vol * (2 if double_disp else 1)


def check_volume_warning(volume: float) -> str:
    """
    If volume >6000 => 'EXCEEDS 6000 µL limit!'
    elif volume >5000 => 'Consider splitting!'
    else => ''
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    return ""


def format_number(num: float) -> str:
    """
    Show no decimals if integer, else up to 4 sig digits.
    """
    if float(num).is_integer():
        return str(int(num))
    else:
        return f"{num:.4g}"


def choose_diluent(rtype: str, custom: str = "") -> str:
    """
    Decide default diluent:
      - 'H2O2','PB','Polymer','Vectaplex' => ''
      - 'Opal' => 'amplifier'
      - 'Primary','TSA-DIG','DAPI' => 'bondwash/blocker'
      - 'Custom' => custom
    """
    if rtype in ["H2O2", "PB", "Polymer", "Vectaplex"]:
        return ""
    elif rtype == "Opal":
        return "amplifier"
    elif rtype in ["Primary", "TSA-DIG", "DAPI"]:
        return "bondwash/blocker"
    elif rtype == "Custom":
        return custom
    else:
        return ""


def split_row(row_dict: dict, max_allowed=5000, dead_vol=150) -> list:
    """
    If row's total volume > max_allowed, we split it into sub-pots. 
    Each sub-pot re-incurs the dead_vol. 
    We rely on 'base_dispense_portion' to see how much was before adding dead_vol.
    """
    total_str = row_dict["Total Volume (µL)"]
    try:
        total_vol = float(total_str)
    except:
        total_vol = 0.0

    if total_vol <= max_allowed:
        return [row_dict]

    portion = row_dict.get("base_dispense_portion", total_vol - dead_vol)
    if portion < 0:
        portion = 0

    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        # can't fix if dead_vol >= max_allowed
        return [row_dict]

    needed = math.ceil(portion / max_portion)
    new_rows = []
    leftover = portion

    # parse dilution
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
        sub_row["Reagent"] += f" (Split {i + 1}/{needed})"
        sub_row["Total Volume (µL)"] = format_number(pot_total)
        sub_row["Stock Volume (µL)"] = format_number(stock_vol)
        sub_row["base_dispense_portion"] = sub_portion
        sub_row["Warning"] = check_volume_warning(pot_total)
        new_rows.append(sub_row)

    return new_rows


###############################################################################
# SINGLE-PLEX FLOW
###############################################################################

def single_plex_flow(dispense_vol, dead_vol):
    st.write("### Single-Plex Flow")

    if "sp_slides" not in st.session_state:
        st.session_state["sp_slides"] = []

    # 1) Add Single-Plex Slide
    st.subheader("Add Single-Plex Slide")

    sp_h2o2 = st.checkbox("Use H2O2? (Single-Plex)", value=True)
    sp_pb = st.checkbox("Use Protein Block? (Single-Plex)", value=True)
    sp_neg = st.checkbox("Negative Control? (skip primary)", value=False)

    # Primary
    sp_prim_name = st.text_input("Primary Name (Single-Plex)", "")
    sp_prim_dil = st.number_input("Primary Dil (Single-Plex)", min_value=1.0, value=1000.0)
    sp_prim_dbl = st.checkbox("Double Dispense (Primary)?", value=False)

    # Polymer
    poly_opts = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
    sp_poly = st.selectbox("Polymer (Single-Plex)", poly_opts)
    sp_poly_dbl = st.checkbox("Double Dispense (Polymer)?", value=False)

    # Opal
    opal_opts = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
    sp_opal = st.selectbox("Opal (Single-Plex)", opal_opts)
    sp_opal_dil = st.number_input("Opal Dil (Single-Plex)", min_value=1.0, value=1000.0)
    sp_opal_dbl = st.checkbox("Double Dispense (Opal)?", value=False)

    # TSA if opal=780
    sp_tsa_used = False
    sp_tsa_dil = 1000.0
    sp_tsa_dbl = False
    if sp_opal == "780":
        st.markdown("Opal 780 => TSA-DIG?")
        sp_tsa_used = st.checkbox("Use TSA-DIG? (Single-Plex)")
        if sp_tsa_used:
            sp_tsa_dil = st.number_input("TSA-DIG Dil (Single-Plex)", min_value=1.0, value=1000.0)
            sp_tsa_dbl = st.checkbox("Double Dispense (TSA)?", value=False)

    # DAPI
    sp_use_dapi = st.checkbox("Use DAPI? (Single-Plex)", value=False)
    sp_dapi_dil = 1000.0
    sp_dapi_dbl = False
    if sp_use_dapi:
        sp_dapi_dil = st.number_input("DAPI Dil (Single-Plex)", min_value=1.0, value=1000.0)
        sp_dapi_dbl = st.checkbox("Double Dispense (DAPI)?", value=False)

    # custom
    sp_use_cust = st.checkbox("Use Custom Reagent? (Single-Plex)", value=False)
    sp_cname = ""
    sp_cdil = 1.0
    sp_cdbl = False
    sp_cdilu = ""
    if sp_use_cust:
        sp_cname = st.text_input("Custom Name (Single-Plex)", "")
        sp_cdil = st.number_input("Custom Dil (Single-Plex)", min_value=1.0, value=1000.0)
        sp_cdbl = st.checkbox("Double Dispense (Custom)?", value=False)
        sp_cdilu = st.text_input("Custom Diluent (Single-Plex)", "bondwash/blocker")

    if st.button("Add Single-Plex Slide"):
        if not sp_neg and not sp_prim_name.strip():
            st.warning("Provide a primary name or check negative control.")
        elif sp_use_cust and not sp_cname.strip():
            st.warning("Provide custom reagent name or uncheck 'Use Custom'.")
        else:
            sdict = {
                "h2o2": sp_h2o2,
                "pb": sp_pb,
                "neg": sp_neg,
                "prim_name": sp_prim_name.strip(),
                "prim_dil": sp_prim_dil,
                "prim_dbl": sp_prim_dbl,
                "poly": sp_poly,
                "poly_dbl": sp_poly_dbl,
                "opal": sp_opal,
                "opal_dil": sp_opal_dil,
                "opal_dbl": sp_opal_dbl,
                "tsa_used": sp_tsa_used,
                "tsa_dil": sp_tsa_dil,
                "tsa_dbl": sp_tsa_dbl,
                "use_dapi": sp_use_dapi,
                "dapi_dil": sp_dapi_dil,
                "dapi_dbl": sp_dapi_dbl,
                "use_custom": sp_use_cust,
                "cust_name": sp_cname.strip(),
                "cust_dil": sp_cdil,
                "cust_dbl": sp_cdbl,
                "cust_dilu": sp_cdilu.strip(),
            }
            st.session_state["sp_slides"].append(sdict)
            st.success("Single-Plex Slide added.")

    # Remove button
    st.write("#### Current Single-Plex Slides")
    for idx, sld in enumerate(st.session_state["sp_slides"]):
        colA, colB = st.columns([4, 1])
        with colA:
            st.write(f"Slide #{idx + 1}: primary={sld['prim_name']}, opal={sld['opal']}, neg={sld['neg']}")
        with colB:
            if st.button(f"Remove Single-Plex Slide {idx + 1}", key=f"remove_sp_{idx}"):
                st.session_state["sp_slides"].pop(idx)
                st.rerun()

    if "sp_final_rows" not in st.session_state:
        st.session_state["sp_final_rows"] = []

    def build_sp_table():
        slides_local = st.session_state["sp_slides"]
        if not slides_local:
            st.warning("No single-plex slides to compute!")
            return

        from collections import defaultdict
        usage_map = defaultdict(list)
        slide_summ = []

        # Gather usage
        for i, sld in enumerate(slides_local, start=1):
            seq = []
            if sld["h2o2"]:
                usage_map[("H2O2", "H2O2", 1.0, False, "")].append(calc_dispense_portion(dispense_vol, False))
                seq.append("H2O2")
            if sld["pb"]:
                usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(
                    calc_dispense_portion(dispense_vol, False))
                seq.append("PB")
            if not sld["neg"]:
                pname = sld["prim_name"] or "(Unnamed Primary)"
                usage_map[(pname, "Primary", sld["prim_dil"], sld["prim_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sld["prim_dbl"])
                )
                seq.append(f"Primary({pname})")
            else:
                seq.append("Primary(skipped - Neg)")

            pol_name = f"Polymer-{sld['poly']}"
            usage_map[(pol_name, "Polymer", 1.0, sld["poly_dbl"], "")].append(
                calc_dispense_portion(dispense_vol, sld["poly_dbl"])
            )
            seq.append(pol_name)

            op_name = f"Opal-{sld['opal']}"
            usage_map[(op_name, "Opal", sld["opal_dil"], sld["opal_dbl"], "")].append(
                calc_dispense_portion(dispense_vol, sld["opal_dbl"])
            )
            seq.append(op_name)

            if sld["tsa_used"]:
                usage_map[("TSA-DIG", "TSA-DIG", sld["tsa_dil"], sld["tsa_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sld["tsa_dbl"])
                )
                seq.append("TSA-DIG")

            if sld["use_dapi"]:
                usage_map[("DAPI", "DAPI", sld["dapi_dil"], sld["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sld["dapi_dbl"])
                )
                seq.append("DAPI")

            if sld["use_custom"]:
                cname = sld["cust_name"]
                cdil = sld["cust_dil"]
                cdbl = sld["cust_dbl"]
                cdilu = sld["cust_dilu"]
                usage_map[(cname, "Custom", cdil, cdbl, cdilu)].append(
                    calc_dispense_portion(dispense_vol, cdbl)
                )
                seq.append(f"Custom({cname})")

            slide_summ.append({"Slide": i, "Sequence": " → ".join(seq)})

        st.subheader("Single-Plex Slide Summary")
        st.table(slide_summ)

        # unify usage
        final_rows = []
        for (name, rtype, dil, dbl, cdilu), portions in usage_map.items():
            sum_portions = sum(portions)
            tot_vol = dead_vol + sum_portions
            stock_vol = tot_vol / dil
            wrn = check_volume_warning(tot_vol)

            if rtype == "Custom":
                dilu = cdilu
            else:
                dilu = choose_diluent(rtype)

            final_rows.append({
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": dilu,
                "Total Volume (µL)": format_number(tot_vol),
                "Stock Volume (µL)": format_number(stock_vol),
                "Warning": wrn,
                "base_dispense_portion": sum_portions,
            })

        st.session_state["sp_final_rows"] = final_rows

    if st.button("Compute Single-Plex Table"):
        build_sp_table()
        st.success("Single-Plex table built! Scroll down.")

    sp_final = st.session_state.get("sp_final_rows", [])
    if sp_final:
        # Check if any row >5000
        any_over_5000 = any(r["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"] for r in sp_final)
        if not any_over_5000:
            st.subheader("Single-Plex Final Table (No Splitting Needed)")
            df = pd.DataFrame(sp_final)

            # We'll style it for color highlighting
            def sp_highlight(row):
                vol_str = row["Total Volume (µL)"]
                vol = float(vol_str) if vol_str else 0
                if vol > 6000:
                    return ["background-color: #ffcccc"] * len(row)
                elif vol > 5000:
                    return ["background-color: #ffffcc"] * len(row)
                else:
                    return [""] * len(row)

            styled_df = df.style.apply(sp_highlight, axis=1)
            # use to_html so we see the colors
            st.write(styled_df.to_html(), unsafe_allow_html=True)

        else:
            st.subheader("Single-Plex Table (Potential Splitting Needed)")
            df = pd.DataFrame(sp_final)

            def sp_highlight(row):
                vol_str = row["Total Volume (µL)"]
                vol = float(vol_str) if vol_str else 0
                if vol > 6000:
                    return ["background-color: #ffcccc"] * len(row)
                elif vol > 5000:
                    return ["background-color: #ffffcc"] * len(row)
                else:
                    return [""] * len(row)

            styled_df = df.style.apply(sp_highlight, axis=1)
            st.write(styled_df.to_html(), unsafe_allow_html=True)

            if st.button("Split Single-Plex Rows >5000?"):
                new_list = []
                for row_ in sp_final:
                    if row_["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"]:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_vol)
                        new_list.extend(splitted)
                    else:
                        new_list.append(row_)
                st.session_state["sp_final_rows"] = new_list
                st.success("Splitting done for Single-Plex. See updated table below.")
                # Show splitted table now
                df2 = pd.DataFrame(st.session_state["sp_final_rows"])

                def sp_highlight2(row):
                    vol_str = row["Total Volume (µL)"]
                    vol = float(vol_str) if vol_str else 0
                    if vol > 6000:
                        return ["background-color: #ffcccc"] * len(row)
                    elif vol > 5000:
                        return ["background-color: #ffffcc"] * len(row)
                    else:
                        return [""] * len(row)

                styled_df2 = df2.style.apply(sp_highlight2, axis=1)
                st.write(styled_df2.to_html(), unsafe_allow_html=True)


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
    mp_pb_after = st.checkbox("Use PB after each opal?", value=False)
    mp_neg = st.checkbox("Negative Control? (skip primary each plex)", value=False)

    # DAPI
    mp_use_dapi = st.checkbox("Use DAPI? (Multi-Plex)", value=False)
    mp_dapi_dil = 1000.0
    mp_dapi_dbl = False
    if mp_use_dapi:
        mp_dapi_dil = st.number_input("DAPI Dil (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_dapi_dbl = st.checkbox("Double Dispense (DAPI)? (Multi-Plex)")

    # custom
    mp_use_cust = st.checkbox("Use Custom Reagent? (Multi-Plex)", value=False)
    mp_cname = ""
    mp_cdil = 1.0
    mp_cdbl = False
    mp_cdilu = ""
    if mp_use_cust:
        mp_cname = st.text_input("Custom Name (Multi-Plex)", "")
        mp_cdil = st.number_input("Custom Dil (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_cdbl = st.checkbox("Double Dispense (Custom)? (Multi-Plex)", value=False)
        mp_cdilu = st.text_input("Custom Diluent (Multi-Plex)", "bondwash/blocker")

    # Vectaplex
    mp_vectaplex = st.checkbox("Use Vectaplex? (Multi-Plex)", value=False)
    mp_vect_dbl = False
    if mp_vectaplex:
        mp_vect_dbl = st.checkbox("Double Dispense (Vectaplex)?", value=False)

    # how many plex
    mp_nplex = st.number_input("Number of plex in this Multi-Plex slide?", min_value=1, max_value=8, value=2)

    plex_entries = []
    used_opals = set()
    warn_780_position = False
    warn_duplicate_opal = False

    st.write("#### Configure Each Plex (Horizontal)")

    for i in range(mp_nplex):
        st.markdown(f"**Plex #{i + 1}**")
        # We'll use columns to reduce vertical space
        col1, col2, col3 = st.columns([2, 1, 1])  # for primary
        with col1:
            pm_name = st.text_input(f"Primary (Plex {i + 1})", key=f"mp_prim_{i}")
        with col2:
            pm_dil = st.number_input(f"Prim Dil (Plex {i + 1})", min_value=1.0, value=1000.0, key=f"mp_prim_dil_{i}")
        with col3:
            pm_dbl = st.checkbox(f"Double(Primary)?", value=False, key=f"mp_prim_dbl_{i}")

        col4, col5 = st.columns([2, 1])  # for polymer
        with col4:
            pm_poly_opts = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
            pm_poly_sel = st.selectbox(f"Polymer (Plex {i + 1})", pm_poly_opts, key=f"mp_poly_{i}")
        with col5:
            pm_poly_dbl = st.checkbox("Double(Polymer)?", value=False, key=f"mp_poly_dbl_{i}")

        # for opal
        col6, col7, col8 = st.columns([2, 1, 1])
        with col6:
            opal_opts = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
            pm_opal = st.selectbox(f"Opal (Plex {i + 1})", opal_opts, key=f"mp_opal_{i}")
        with col7:
            pm_opal_dil = st.number_input(f"Opal Dil (Plex {i + 1})", min_value=1.0, value=1000.0,
                                          key=f"mp_opal_dil_{i}")
        with col8:
            pm_opal_dbl = st.checkbox("Double(Opal)?", value=False, key=f"mp_opal_dbl_{i}")

        # ensure unique opal (unless "others" or "780" if you want to allow duplicates for them)
        # Adjust logic as you prefer
        if pm_opal not in ["others", "780"]:
            if pm_opal in used_opals:
                warn_duplicate_opal = True
            used_opals.add(pm_opal)

        if pm_opal == "780" and i < (mp_nplex - 1):
            warn_780_position = True

        # TSA if 780
        pm_tsa_used = False
        pm_tsa_dil = 1000.0
        pm_tsa_dbl = False
        if pm_opal == "780":
            st.markdown(f"Opal 780 => TSA-DIG for Plex {i + 1}?")
            pm_tsa_used = st.checkbox(f"Use TSA-DIG? (Plex {i + 1})", key=f"mp_tsa_used_{i}")
            if pm_tsa_used:
                pm_tsa_dil = st.number_input(f"TSA-DIG Dil (Plex {i + 1})", min_value=1.0, value=1000.0,
                                             key=f"mp_tsa_dil_{i}")
                pm_tsa_dbl = st.checkbox(f"Double(TSA)? (Plex {i + 1})", value=False, key=f"mp_tsa_dbl_{i}")

        # gather into a dict
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
            st.error("Opal 780 must be in the last plex. Please revise your plex order or reduce plex count.")
        elif warn_duplicate_opal:
            st.error("Same Opal used more than once (excluding '780' or 'others'). Please pick unique opals.")
        else:
            # if user has custom but no name => block
            if mp_use_cust and not mp_cname.strip():
                st.warning("Enter a custom reagent name or uncheck 'Use Custom Reagent'.")
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

    # 2) Show slides + remove
    st.write("#### Current Multi-Plex Slides")
    for idx, sld in enumerate(st.session_state["mp_slides"]):
        colA, colB = st.columns([4, 1])
        with colA:
            # Make sure to use .get(...) if older slides might not have these keys
            vect = sld.get("vectaplex", False)
            pb_b = sld.get("pb_before", False)
            pb_a = sld.get("pb_after", False)
            st.write(
                f"Slide #{idx + 1}: #plex={len(sld['plex_list'])}, vectaplex={vect}, PB_before={pb_b}, PB_after={pb_a}")
        with colB:
            if st.button(f"Remove Multi-Plex Slide {idx + 1}", key=f"remove_mp_{idx}"):
                st.session_state["mp_slides"].pop(idx)
                st.rerun()

    # 3) Build Final Table
    if "mp_final_rows" not in st.session_state:
        st.session_state["mp_final_rows"] = []

    def build_mp_table():
        if not st.session_state["mp_slides"]:
            st.warning("No multi-plex slides to compute!")
            return

        usage_map = defaultdict(list)
        slide_summaries = []

        # Sequence rules:
        # - If opal != 780 => opal then vectaplex
        # - If opal == 780 => TSA => vectaplex => opal
        # - PB before primary if pb_before
        # - PB after opal if pb_after
        # - Negative => skip primary
        # - etc

        for s_index, slide in enumerate(st.session_state["mp_slides"], start=1):
            seq = []
            if slide["h2o2"]:
                usage_map[("H2O2", "H2O2", 1.0, False, "")].append(calc_dispense_portion(dispense_vol, False))
                seq.append("H2O2")

            for i, plex_info in enumerate(slide["plex_list"], start=1):
                if slide["pb_before"]:
                    usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(
                        calc_dispense_portion(dispense_vol, False))
                    seq.append("PB(before)")

                if not slide["neg"]:
                    pname = plex_info["primary_name"] or f"(Prim P{i})"
                    usage_map[(pname, "Primary", plex_info["primary_dil"], plex_info["primary_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex_info["primary_dbl"])
                    )
                    seq.append(f"Primary({pname})")
                else:
                    seq.append(f"Plex {i}: Primary(skipped - neg)")

                poly_name = f"Polymer-{plex_info['polymer']}"
                usage_map[(poly_name, "Polymer", 1.0, plex_info["polymer_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, plex_info["polymer_dbl"])
                )
                seq.append(poly_name)

                if plex_info["opal"] == "780":
                    # TSA => vectaplex => opal
                    if plex_info["tsa_used"]:
                        usage_map[("TSA-DIG", "TSA-DIG", plex_info["tsa_dil"], plex_info["tsa_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, plex_info["tsa_dbl"])
                        )
                        seq.append("TSA-DIG")

                    if slide["vectaplex"]:
                        usage_map[("Vectaplex", "Vectaplex", 1.0, slide["vectaplex_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, slide["vectaplex_dbl"])
                        )
                        seq.append("Vectaplex")

                    op_name = f"Opal-{plex_info['opal']}"
                    usage_map[(op_name, "Opal", plex_info["opal_dil"], plex_info["opal_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex_info["opal_dbl"])
                    )
                    seq.append(op_name)

                else:
                    # opal => vectaplex
                    op_name = f"Opal-{plex_info['opal']}"
                    usage_map[(op_name, "Opal", plex_info["opal_dil"], plex_info["opal_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex_info["opal_dbl"])
                    )
                    seq.append(op_name)

                    if slide["vectaplex"]:
                        usage_map[("Vectaplex", "Vectaplex", 1.0, slide["vectaplex_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, slide["vectaplex_dbl"])
                        )
                        seq.append("Vectaplex")

                if slide["pb_after"]:
                    usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(
                        calc_dispense_portion(dispense_vol, False))
                    seq.append("PB(after)")

            # after all plex => dapi
            if slide["use_dapi"]:
                usage_map[("DAPI", "DAPI", slide["dapi_dil"], slide["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, slide["dapi_dbl"])
                )
                seq.append("DAPI")

            # custom
            if slide["use_custom"]:
                cname = slide["cust_name"]
                cdil = slide["cust_dil"]
                cdbl = slide["cust_dbl"]
                cdilu = slide["cust_dilu"]
                usage_map[(cname, "Custom", cdil, cdbl, cdilu)].append(
                    calc_dispense_portion(dispense_vol, cdbl)
                )
                seq.append(f"Custom({cname})")

            slide_summaries.append({"Multi-Plex Slide": s_index, "Sequence": " → ".join(seq)})

        st.subheader("Multi-Plex Slide Summary")
        st.table(slide_summaries)

        # unify
        final_rows = []
        for (name, rtype, dil, dbl, cdi), portions in usage_map.items():
            sums = sum(portions)
            totv = dead_vol + sums
            stockv = totv / dil
            warn = check_volume_warning(totv)
            if rtype == "Custom":
                dd = cdi
            else:
                dd = choose_diluent(rtype)

            final_rows.append({
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": dd,
                "Total Volume (µL)": format_number(totv),
                "Stock Volume (µL)": format_number(stockv),
                "Warning": warn,
                "base_dispense_portion": sums,
            })
        st.session_state["mp_final_rows"] = final_rows

    if st.button("Compute Multi-Plex Table"):
        build_mp_table()
        st.success("Multi-Plex table built! Scroll down.")

    mp_final = st.session_state.get("mp_final_rows", [])
    if mp_final:
        # check if any row > 5000
        any_over_5000 = any(r["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"] for r in mp_final)
        if not any_over_5000:
            st.subheader("Multi-Plex Final Table (No Splitting Needed)")
            df = pd.DataFrame(mp_final)

            def mp_highlight(row):
                vol_str = row["Total Volume (µL)"]
                vol = float(vol_str) if vol_str else 0
                if vol > 6000:
                    return ["background-color: #ffcccc"] * len(row)
                elif vol > 5000:
                    return ["background-color: #ffffcc"] * len(row)
                else:
                    return [""] * len(row)

            styled_df = df.style.apply(mp_highlight, axis=1)
            st.write(styled_df.to_html(), unsafe_allow_html=True)

        else:
            st.subheader("Multi-Plex Table (Potential Splitting Needed)")
            df = pd.DataFrame(mp_final)

            def mp_highlight(row):
                vol_str = row["Total Volume (µL)"]
                vol = float(vol_str) if vol_str else 0
                if vol > 6000:
                    return ["background-color: #ffcccc"] * len(row)
                elif vol > 5000:
                    return ["background-color: #ffffcc"] * len(row)
                else:
                    return [""] * len(row)

            styled_df = df.style.apply(mp_highlight, axis=1)
            st.write(styled_df.to_html(), unsafe_allow_html=True)

            if st.button("Split Multi-Plex Rows >5000?"):
                new_list = []
                for row_ in mp_final:
                    if row_["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"]:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_vol)
                        new_list.extend(splitted)
                    else:
                        new_list.append(row_)
                st.session_state["mp_final_rows"] = new_list
                st.success("Splitting done for Multi-Plex. Updated table below.")

                # show splitted table now
                df2 = pd.DataFrame(st.session_state["mp_final_rows"])

                def mp_highlight2(row):
                    vol_str = row["Total Volume (µL)"]
                    vol = float(vol_str) if vol_str else 0
                    if vol > 6000:
                        return ["background-color: #ffcccc"] * len(row)
                    elif vol > 5000:
                        return ["background-color: #ffffcc"] * len(row)
                    else:
                        return [""] * len(row)

                styled_df2 = df2.style.apply(mp_highlight2, axis=1)
                st.write(styled_df2.to_html(), unsafe_allow_html=True)


###############################################################################
# MAIN APP
###############################################################################

def main_app():
    st.title("Combined Single-Plex / Multi-Plex with Horizontal Input, No Repeated Opal, and Splitting")

    # 1) Global Settings
    st.header("Global Settings")
    disp_vol = st.number_input("Dispense Volume (µL)", min_value=1, max_value=9999, value=150)
    dead_vol = st.number_input("Dead Volume (µL)", min_value=0, max_value=9999, value=150)
    st.write("---")

    # 2) Single-Plex or Multi-Plex
    choice = st.radio("Select Flow:", ["Single-Plex", "Multi-Plex"])

    if choice == "Single-Plex":
        single_plex_flow(disp_vol, dead_vol)
    else:
        multi_plex_flow(disp_vol, dead_vol)


def main():
    main_app()


if __name__ == "__main__":
    main()
