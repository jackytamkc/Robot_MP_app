import streamlit as st
from collections import defaultdict
import pandas as pd
import math

###############################################################################
# Shared Utility Functions
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    """Return dispense portion = disp_vol * 2 if double_disp else 1."""
    return disp_vol * (2 if double_disp else 1)

def check_volume_warning(volume: float) -> str:
    """Return 'EXCEEDS 6000 µL limit!' if >6000, 'Consider splitting!' if >5000, else ''. """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    return ""

def format_number(num: float) -> str:
    """No decimals if integer, else up to 4 sig digits."""
    if float(num).is_integer():
        return str(int(num))
    else:
        return f"{num:.4g}"

def choose_diluent(rtype: str, custom: str = "") -> str:
    """
    By default:
      - 'H2O2', 'PB', 'Polymer', 'Vectaplex' => ''
      - 'Opal' => 'amplifier'
      - 'Primary', 'TSA-DIG', 'DAPI' => 'bondwash/blocker'
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

def split_row(row_dict, max_allowed=5000, dead_vol=150):
    """
    If row's total volume > max_allowed, split into multiple sub-pots, each re-incurring dead volume.
    row_dict must have 'base_dispense_portion' to reconstruct how many sub-pots we need.
    """
    total_str = row_dict["Total Volume (µL)"]
    try:
        total_vol = float(total_str)
    except:
        total_vol = 0.0

    if total_vol <= max_allowed:
        return [row_dict]

    portion = row_dict.get("base_dispense_portion", None)
    if portion is None:
        portion = total_vol - dead_vol
        if portion < 0:
            portion = 0

    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        return [row_dict]  # can't fix

    needed = math.ceil(portion / max_portion)
    new_rows = []
    leftover = portion

    dil_str = row_dict["Dilution Factor"]
    try:
        dil_factor = float(dil_str)
    except:
        dil_factor = 1.0

    for i in range(needed):
        pot_portion = min(leftover, max_portion)
        leftover -= pot_portion
        pot_vol = dead_vol + pot_portion
        stock_vol = pot_vol / dil_factor

        sub_row = row_dict.copy()
        sub_row["Reagent"] += f" (Split {i+1}/{needed})"
        sub_row["Total Volume (µL)"] = format_number(pot_vol)
        sub_row["Stock Volume (µL)"] = format_number(stock_vol)
        sub_row["base_dispense_portion"] = pot_portion
        sub_row["Warning"] = check_volume_warning(pot_vol)
        new_rows.append(sub_row)

    return new_rows

###############################################################################
# Single-Plex Flow (unchanged)
###############################################################################

def single_plex_flow(dispense_volume, dead_volume):
    st.write("### Single-Plex Flow")

    if "sp_slides" not in st.session_state:
        st.session_state["sp_slides"] = []

    # --- UI to add a single-plex slide ---
    st.subheader("Add Single-Plex Slide")

    sp_h2o2  = st.checkbox("Use H2O2? (Single-Plex)", value=True)
    sp_pb    = st.checkbox("Use Protein Block? (Single-Plex)", value=True)
    sp_neg   = st.checkbox("Negative Control? (skip primary)", value=False)

    # Primary
    sp_prim_name = st.text_input("Primary Name (Single-Plex)", "")
    sp_prim_dil  = st.number_input("Primary Dil (Single-Plex)", min_value=1.0, value=1000.0)
    sp_prim_dbl  = st.checkbox("Double Dispense (Primary)?", value=False)

    # Polymer
    poly_opts = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
    sp_poly = st.selectbox("Polymer (Single-Plex)", poly_opts)
    sp_poly_dbl = st.checkbox("Double Dispense (Polymer)?", value=False)

    # Opal
    opal_opts = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
    sp_opal_choice = st.selectbox("Opal (Single-Plex)", opal_opts)
    sp_opal_dil    = st.number_input("Opal Dil (Single-Plex)", min_value=1.0, value=1000.0)
    sp_opal_dbl    = st.checkbox("Double Dispense (Opal)?", value=False)

    # TSA if opal=780
    sp_tsa_used = False
    sp_tsa_dil  = 1000.0
    sp_tsa_dbl  = False
    if sp_opal_choice == "780":
        st.markdown("Opal 780 => consider TSA-DIG?")
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
    sp_use_custom = st.checkbox("Use Custom Reagent? (Single-Plex)", value=False)
    sp_cname = ""
    sp_cdil  = 1.0
    sp_cdbl  = False
    sp_cdilu = ""
    if sp_use_custom:
        sp_cname = st.text_input("Custom Reagent Name (Single-Plex)", "")
        sp_cdil  = st.number_input("Custom Reagent Dil (Single-Plex)", min_value=1.0, value=1000.0)
        sp_cdbl  = st.checkbox("Double Dispense (Custom)? (Single-Plex)", value=False)
        sp_cdilu = st.text_input("Custom Reagent Diluent (Single-Plex)", "bondwash/blocker")

    if st.button("Add Single-Plex Slide"):
        if not sp_neg and not sp_prim_name.strip():
            st.warning("Provide a primary name or check 'Negative Control'")
        elif sp_use_custom and not sp_cname.strip():
            st.warning("Enter custom reagent name or uncheck 'use custom'")
        else:
            slide_dict = {
                "h2o2": sp_h2o2,
                "pb": sp_pb,
                "negative_ctrl": sp_neg,
                "primary_name": sp_prim_name.strip(),
                "primary_dil": sp_prim_dil,
                "double_primary": sp_prim_dbl,
                "polymer": sp_poly,
                "double_polymer": sp_poly_dbl,
                "opal": sp_opal_choice,
                "opal_dil": sp_opal_dil,
                "double_opal": sp_opal_dbl,
                "tsa_used": sp_tsa_used,
                "tsa_dil": sp_tsa_dil,
                "tsa_double": sp_tsa_dbl,
                "use_dapi": sp_use_dapi,
                "dapi_dil": sp_dapi_dil,
                "double_dapi": sp_dapi_dbl,
                "use_custom": sp_use_custom,
                "custom_name": sp_cname.strip(),
                "custom_dil": sp_cdil,
                "custom_double": sp_cdbl,
                "custom_diluent": sp_cdilu.strip(),
            }
            st.session_state["sp_slides"].append(slide_dict)
            st.success("Single-Plex Slide added.")

    # Show existing slides
    st.write("#### Current Single-Plex Slides:")
    if "sp_slides" in st.session_state and st.session_state["sp_slides"]:
        for i, sld in enumerate(st.session_state["sp_slides"]):
            st.write(f"Slide {i+1}: primary={sld['primary_name']}, opal={sld['opal']}, polymer={sld['polymer']}, neg={sld['negative_ctrl']}")
    else:
        st.write("No single-plex slides yet.")

    # Compute single-plex table (like before)
    if "sp_final_rows" not in st.session_state:
        st.session_state["sp_final_rows"] = []

    def build_single_plex_final():
        from collections import defaultdict
        sp_map = defaultdict(list)
        slide_summary = []

        for i, sld in enumerate(st.session_state["sp_slides"], start=1):
            seq = []
            if sld["h2o2"]:
                sp_map[("H2O2", "H2O2", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("H2O2")
            if sld["pb"]:
                sp_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("PB")
            if not sld["negative_ctrl"]:
                # primary
                pname = sld["primary_name"] or "(Unnamed Primary)"
                sp_map[(pname, "Primary", sld["primary_dil"], sld["double_primary"], "")].append(
                    calc_dispense_portion(dispense_volume, sld["double_primary"])
                )
                seq.append(f"Primary({pname})")
            else:
                seq.append("Primary(skipped - Neg Ctrl)")

            # polymer
            pol_name = f"Polymer-{sld['polymer']}"
            sp_map[(pol_name, "Polymer", 1.0, sld["double_polymer"], "")].append(
                calc_dispense_portion(dispense_volume, sld["double_polymer"])
            )
            seq.append(pol_name)

            # opal
            op_name = f"Opal-{sld['opal']}"
            sp_map[(op_name, "Opal", sld["opal_dil"], sld["double_opal"], "")].append(
                calc_dispense_portion(dispense_volume, sld["double_opal"])
            )
            seq.append(op_name)

            # tsa
            if sld["tsa_used"]:
                sp_map[("TSA-DIG", "TSA-DIG", sld["tsa_dil"], sld["tsa_double"], "")].append(
                    calc_dispense_portion(dispense_volume, sld["tsa_double"])
                )
                seq.append("TSA-DIG")

            # dapi
            if sld["use_dapi"]:
                sp_map[("DAPI", "DAPI", sld["dapi_dil"], sld["double_dapi"], "")].append(
                    calc_dispense_portion(dispense_volume, sld["double_dapi"])
                )
                seq.append("DAPI")

            # custom
            if sld["use_custom"]:
                c_name = sld["custom_name"]
                c_dil  = sld["custom_dil"]
                c_dbl  = sld["custom_double"]
                c_dilu = sld["custom_diluent"]
                sp_map[(c_name, "Custom", c_dil, c_dbl, c_dilu)].append(
                    calc_dispense_portion(dispense_volume, c_dbl)
                )
                seq.append(f"Custom({c_name})")

            slide_summary.append({"Slide": i, "Sequence": " → ".join(seq)})

        st.subheader("Single-Plex Slide Summary")
        st.table(slide_summary)

        # unify
        rows = []
        for (name, rtype, dil, dbl, cdilu), parts in sp_map.items():
            summation = sum(parts)
            totvol = dead_volume + summation
            stock = totvol / dil
            warn = check_volume_warning(totvol)
            # pick final diluent
            if rtype == "Custom":
                final_diluent = cdilu
            else:
                final_diluent = choose_diluent(rtype)
            rows.append({
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": final_diluent,
                "Total Volume (µL)": format_number(totvol),
                "Stock Volume (µL)": format_number(stock),
                "Warning": warn,
                "base_dispense_portion": summation,
            })
        st.session_state["sp_final_rows"] = rows

    if st.button("Compute Single-Plex Table"):
        build_single_plex_final()
        st.success("Single-Plex table built! See below.")

    if st.session_state.get("sp_final_rows"):
        sp_fr = st.session_state["sp_final_rows"]
        st.subheader("Single-Plex Table (Before Splitting)")
        df = pd.DataFrame(sp_fr)

        def highlight_sp(row):
            try:
                vv = float(row["Total Volume (µL)"])
            except:
                vv = 0
            if vv > 6000:
                return ["background-color: #ffcccc"]*len(row)
            elif vv > 5000:
                return ["background-color: #ffffcc"]*len(row)
            else:
                return [""]*len(row)
        sty = df.style.apply(highlight_sp, axis=1)
        st.dataframe(sty, use_container_width=True)

        # splitting
        overidx = df.index[df["Warning"].isin(["Consider splitting!", "EXCEEDS 6000 µL limit!"])].tolist()
        if overidx:
            st.write("Some single-plex rows exceed 5000. Split them?")
            if st.button("Split Single-Plex Rows >5000"):
                newrows = []
                for i, row_ in enumerate(sp_fr):
                    if i in overidx:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_volume)
                        newrows.extend(splitted)
                    else:
                        newrows.append(row_)
                st.session_state["sp_final_rows"] = newrows
                st.success("Splitting done! Scroll down.")
                st.stop()

        # After split
        sp_fr_up = st.session_state["sp_final_rows"]
        df2 = pd.DataFrame(sp_fr_up)
        st.subheader("Single-Plex Table (After Splitting)")
        def highlight_sp2(row):
            try:
                vv = float(row["Total Volume (µL)"])
            except:
                vv = 0
            if vv > 6000:
                return ["background-color: #ffcccc"]*len(row)
            elif vv > 5000:
                return ["background-color: #ffffcc"]*len(row)
            else:
                return [""]*len(row)
        sty2 = df2.style.apply(highlight_sp2, axis=1)
        st.dataframe(sty2, use_container_width=True)
        if len(sp_fr_up) > 29:
            st.error(f"WARNING: You have {len(sp_fr_up)} total pots, exceeds 29 limit!")

###############################################################################
# Multi-Plex Flow with new constraints
###############################################################################

def multi_plex_flow(dispense_volume, dead_volume):
    st.write("### Multi-Plex Flow (New Sequence Logic)")

    # Store multi-plex slides
    if "mp_slides" not in st.session_state:
        st.session_state["mp_slides"] = []

    # 1) Add a multi-plex slide
    st.subheader("Add Multi-Plex Slide")

    mp_h2o2 = st.checkbox("Use H2O2? (Multi-Plex)", value=True)
    # We'll track PB in two ways: PB before primary, PB after opal
    # user can choose if they want PB at both times or none
    mp_pb_before = st.checkbox("Use PB before each primary?", value=True)
    mp_pb_after  = st.checkbox("Use PB after each opal?", value=False)

    mp_neg = st.checkbox("Negative Control? (skip primary for each plex?)", value=False)

    # DAPI
    mp_use_dapi = st.checkbox("Use DAPI? (Multi-Plex)", value=False)
    mp_dapi_dil = 1000.0
    mp_dapi_dbl = False
    if mp_use_dapi:
        mp_dapi_dil = st.number_input("DAPI Dil (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_dapi_dbl = st.checkbox("Double Dispense (DAPI)?", value=False)

    # custom
    mp_use_custom = st.checkbox("Use Custom Reagent? (Multi-Plex)", value=False)
    mp_cname = ""
    mp_cdil  = 1.0
    mp_cdb   = False
    mp_cddi  = ""
    if mp_use_custom:
        mp_cname = st.text_input("Custom Reagent Name (Multi-Plex)", "")
        mp_cdil  = st.number_input("Custom Reagent Dil Factor (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_cdb   = st.checkbox("Double Dispense (Custom)? (Multi-Plex)?", value=False)
        mp_cddi  = st.text_input("Custom Reagent Diluent (Multi-Plex)", "bondwash/blocker")

    # Vectaplex usage
    mp_vectaplex_used = st.checkbox("Use Vectaplex? (Multi-Plex)", value=False)
    mp_vectaplex_double = False
    if mp_vectaplex_used:
        mp_vectaplex_double = st.checkbox("Double Dispense (Vectaplex)?", value=False)

    # how many plex
    mp_nplex = st.number_input("Number of plex in this Multi-Plex slide?", min_value=1, max_value=8, value=2)

    # For each plex, user picks primary set
    # *BUT* we must also ensure that if user picks 780 in any plex that is not the last plex, we warn
    plex_list = []
    warn_780_position = False

    for i in range(mp_nplex):
        st.write(f"**Plex #{i+1}**")
        pm_name = st.text_input(f"Primary Name (Plex {i+1})", "")
        pm_dil  = st.number_input(f"Primary Dil (Plex {i+1})", min_value=1.0, value=1000.0)
        pm_dbl  = st.checkbox(f"Double Dispense (Primary) (Plex {i+1})?", value=False, key=f"mp_p{i}_dblprim")

        # polymer
        pm_poly_opts = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
        pm_poly_sel  = st.selectbox(f"Polymer (Plex {i+1})", pm_poly_opts)
        pm_poly_dbl  = st.checkbox(f"Double Dispense (Polymer)? (Plex {i+1})", value=False, key=f"mp_p{i}_dblpoly")

        # opal
        pm_opal_opts = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
        pm_opal_sel  = st.selectbox(f"Opal (Plex {i+1})", pm_opal_opts)
        pm_opal_dil  = st.number_input(f"Opal Dil Factor (Plex {i+1})", min_value=1.0, value=1000.0)
        pm_opal_dbl  = st.checkbox(f"Double Dispense (Opal)? (Plex {i+1})", value=False, key=f"mp_p{i}_dblopal")

        # if opal=780 but plex != last => set warn_780_position = True
        if pm_opal_sel == "780" and i < (mp_nplex - 1):
            warn_780_position = True

        # TSA
        pm_tsa_used = False
        pm_tsa_dil  = 1000.0
        pm_tsa_dbl  = False
        if pm_opal_sel == "780":
            st.write(f"(Plex {i+1}) -> Opal 780 => TSA-DIG possible:")
            pm_tsa_used = st.checkbox(f"Use TSA-DIG? (Plex {i+1})", value=False)
            if pm_tsa_used:
                pm_tsa_dil = st.number_input(f"TSA-DIG Dil (Plex {i+1})", min_value=1.0, value=1000.0)
                pm_tsa_dbl = st.checkbox(f"Double Dispense (TSA)? (Plex {i+1})", value=False)

        plex_list.append({
            "pname": pm_name.strip(),
            "pdil": pm_dil,
            "pdbl": pm_dbl,
            "polymer": pm_poly_sel,
            "polymer_dbl": pm_poly_dbl,
            "opal": pm_opal_sel,
            "opal_dil": pm_opal_dil,
            "opal_dbl": pm_opal_dbl,
            "tsa_used": pm_tsa_used,
            "tsa_dil": pm_tsa_dil,
            "tsa_dbl": pm_tsa_dbl,
        })

    if st.button("Add Multi-Plex Slide"):
        # If user tries to put 780 not in last plex => warn and skip
        if warn_780_position:
            st.error("Opal 780 must be in the last plex. Please fix the plex order or reduce the plex count.")
        else:
            # If user has custom but no name => warn
            if mp_use_custom and not mp_cname.strip():
                st.warning("Enter a custom reagent name or uncheck 'Use Custom Reagent'.")
            else:
                slide_info = {
                    "h2o2": mp_h2o2,
                    "pb_before": mp_pb_before,
                    "pb_after": mp_pb_after,
                    "negctrl": mp_neg,
                    "use_dapi": mp_use_dapi,
                    "dapi_dil": mp_dapi_dil,
                    "dapi_dbl": mp_dapi_dbl,
                    "use_custom": mp_use_custom,
                    "custom_name": mp_cname.strip(),
                    "custom_dil": mp_cdil,
                    "custom_double": mp_cdb,
                    "custom_diluent": mp_cddi.strip(),
                    "vectaplex_used": mp_vectaplex_used,
                    "vectaplex_double": mp_vectaplex_double,
                    "plex_list": plex_list
                }
                st.session_state["mp_slides"].append(slide_info)
                st.success("Multi-Plex Slide added.")

    # show current multi-plex slides
    st.write("#### Current Multi-Plex Slides")
    if "mp_slides" in st.session_state and st.session_state["mp_slides"]:
        for idx, sl in enumerate(st.session_state["mp_slides"]):
            st.write(f"Slide #{idx+1}: #plex={len(sl['plex_list'])}, vectaplex={sl['vectaplex_used']}, PB_before={sl['pb_before']}, PB_after={sl['pb_after']}")
    else:
        st.write("No multi-plex slides yet.")

    if "mp_final_rows" not in st.session_state:
        st.session_state["mp_final_rows"] = []

    def build_multi_plex_table():
        # We define the final sequence for each slide:
        #  H2O2
        #  FOR plex in order:
        #    if PB_before => PB -> primary -> polymer -> (TSA? => if vectaplex => vectaplex => opal) else => opal
        #    if PB_after => PB afterwards
        #  after last plex => if DAPI => DAPI
        #  if custom => custom
        #  Done
        usage_map = defaultdict(list)
        slide_summaries = []

        if not st.session_state["mp_slides"]:
            st.warning("No multi-plex slides to compute!")
            return

        for s_index, slide in enumerate(st.session_state["mp_slides"], start=1):
            seq = []

            # H2O2
            if slide["h2o2"]:
                usage_map[("H2O2", "H2O2", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("H2O2")

            # For each plex in order
            for p_i, plex_info in enumerate(slide["plex_list"], start=1):
                # If PB before => add PB
                if slide["pb_before"]:
                    usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                    seq.append("PB(before)")

                # if negctrl => skip primary
                if not slide["negctrl"]:
                    # add primary
                    pname = plex_info["pname"] or f"Primary(Plex{p_i})"
                    usage_map[(pname, "Primary", plex_info["pdil"], plex_info["pdbl"], "")].append(
                        calc_dispense_portion(dispense_volume, plex_info["pdbl"])
                    )
                    seq.append(f"Primary({pname})")
                else:
                    seq.append(f"Plex {p_i}: Primary skipped(negctrl)")

                # polymer
                poly_name = f"Polymer-{plex_info['polymer']}"
                usage_map[(poly_name, "Polymer", 1.0, plex_info["polymer_dbl"], "")].append(
                    calc_dispense_portion(dispense_volume, plex_info["polymer_dbl"])
                )
                seq.append(poly_name)

                # TSA? => if plex uses TSA, add it
                if plex_info["tsa_used"]:
                    usage_map[("TSA-DIG", "TSA-DIG", plex_info["tsa_dil"], plex_info["tsa_dbl"], "")].append(
                        calc_dispense_portion(dispense_volume, plex_info["tsa_dbl"])
                    )
                    seq.append("TSA-DIG")

                # If vectaplex is used => add it before opal, possibly double
                if slide["vectaplex_used"]:
                    usage_map[("Vectaplex", "Vectaplex", 1.0, slide["vectaplex_double"], "")].append(
                        calc_dispense_portion(dispense_volume, slide["vectaplex_double"])
                    )
                    seq.append("Vectaplex")

                # Now the opal
                op_name = f"Opal-{plex_info['opal']}"
                usage_map[(op_name, "Opal", plex_info["opal_dil"], plex_info["opal_dbl"], "")].append(
                    calc_dispense_portion(dispense_volume, plex_info["opal_dbl"])
                )
                seq.append(op_name)

                # If PB after => add PB
                if slide["pb_after"]:
                    usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                    seq.append("PB(after)")

            # after all plexes: if DAPI => add
            if slide["use_dapi"]:
                usage_map[("DAPI", "DAPI", slide["dapi_dil"], slide["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["dapi_dbl"])
                )
                seq.append("DAPI")

            # custom
            if slide["use_custom"]:
                c_name = slide["custom_name"]
                c_dil  = slide["custom_dil"]
                c_db   = slide["custom_double"]
                c_dilu = slide["custom_diluent"]
                usage_map[(c_name, "Custom", c_dil, c_db, c_dilu)].append(
                    calc_dispense_portion(dispense_volume, c_db)
                )
                seq.append(f"Custom({c_name})")

            slide_summaries.append({"Multi-Plex Slide": s_index, "Sequence": " → ".join(seq)})

        # show summary
        st.subheader("Multi-Plex Slide Summary")
        st.table(slide_summaries)

        # unify usage
        final_rows = []
        for (name, rtype, dil, dbl, cdilu), portions in usage_map.items():
            sum_portions = sum(portions)
            total_vol = dead_volume + sum_portions
            stock_vol = total_vol / dil
            rowwarn   = check_volume_warning(total_vol)

            if rtype == "Custom":
                final_diluent = cdilu
            else:
                final_diluent = choose_diluent(rtype)

            row = {
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": final_diluent,
                "Total Volume (µL)": format_number(total_vol),
                "Stock Volume (µL)": format_number(stock_vol),
                "Warning": rowwarn,
                "base_dispense_portion": sum_portions,
            }
            final_rows.append(row)

        st.session_state["mp_final_rows"] = final_rows

    if st.button("Compute Multi-Plex Table"):
        build_multi_plex_table()
        st.success("Multi-Plex Table built! Scroll down to see results.")

    # show & handle splitting
    if "mp_final_rows" in st.session_state and st.session_state["mp_final_rows"]:
        mp_fr = st.session_state["mp_final_rows"]
        st.subheader("Multi-Plex Table (Before Splitting)")
        df = pd.DataFrame(mp_fr)

        def highlight_mplex(row):
            try:
                vol = float(row["Total Volume (µL)"])
            except:
                vol = 0
            if vol > 6000:
                return ["background-color: #ffcccc"] * len(row)
            elif vol > 5000:
                return ["background-color: #ffffcc"] * len(row)
            else:
                return [""] * len(row)
        sty = df.style.apply(highlight_mplex, axis=1)
        st.dataframe(sty, use_container_width=True)

        # splitting
        overidx = df.index[df["Warning"].isin(["Consider splitting!", "EXCEEDS 6000 µL limit!"])].tolist()
        if overidx:
            st.write("Some multi-plex rows exceed 5000. Split them?")
            if st.button("Split Multi-Plex Rows >5000"):
                newlist = []
                for i, row_ in enumerate(mp_fr):
                    if i in overidx:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_volume)
                        newlist.extend(splitted)
                    else:
                        newlist.append(row_)
                st.session_state["mp_final_rows"] = newlist
                st.success("Splitting done for multi-plex. Scroll down.")
                st.stop()

        # after splitting
        mp_fr2 = st.session_state["mp_final_rows"]
        st.subheader("Multi-Plex Table (After Splitting)")
        df2 = pd.DataFrame(mp_fr2)
        def highlight_mplex2(row):
            try:
                vol = float(row["Total Volume (µL)"])
            except:
                vol = 0
            if vol > 6000:
                return ["background-color: #ffcccc"] * len(row)
            elif vol > 5000:
                return ["background-color: #ffffcc"] * len(row)
            else:
                return [""] * len(row)
        sty2 = df2.style.apply(highlight_mplex2, axis=1)
        st.dataframe(sty2, use_container_width=True)
        if len(mp_fr2) > 29:
            st.error(f"WARNING: {len(mp_fr2)} pots total, exceeding 29 limit!")


###############################################################################
# Main App
###############################################################################

def main_app():
    st.title("Combined Single-Plex / Multi-Plex With New Sequence Logic")

    st.header("Global Settings")
    disp_vol = st.number_input("Dispense Volume (µL)", min_value=1, max_value=9999, value=150)
    dead_vol = st.number_input("Dead Volume (µL)", min_value=0, max_value=9999, value=150)
    st.write("---")

    choice = st.radio("Choose mode:", ["Single-Plex", "Multi-Plex"])

    if choice == "Single-Plex":
        single_plex_flow(disp_vol, dead_vol)
    else:
        multi_plex_flow(disp_vol, dead_vol)


def main():
    main_app()

if __name__ == "__main__":
    main()
