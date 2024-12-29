import streamlit as st
from collections import defaultdict
import pandas as pd
import math

###############################################################################
# SHARED UTILITY FUNCTIONS
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    """
    Return the portion used by one usage:
    portion = disp_vol * 2 if double_disp else disp_vol
    """
    return disp_vol * (2 if double_disp else 1)

def check_volume_warning(volume: float) -> str:
    """
    If volume > 6000 => 'EXCEEDS 6000 µL limit!'
    If volume > 5000 => 'Consider splitting!'
    Else => ''
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    else:
        return ""

def format_number(num: float) -> str:
    """
    If num is effectively an integer, show no decimals.
    Otherwise show up to 4 significant digits.
    """
    if float(num).is_integer():
        return str(int(num))
    else:
        return f"{num:.4g}"

def choose_diluent(rtype: str, custom: str = "") -> str:
    """
    Return the default diluent based on reagent type:
      - 'H2O2', 'PB', 'Polymer', 'Vectaplex' => ''
      - 'Opal' => 'amplifier'
      - 'Primary', 'TSA-DIG', 'DAPI' => 'bondwash/blocker'
      - 'Custom' => use 'custom'
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
    If row's total volume > max_allowed, split into multiple sub-pots.
    Each sub-pot re-incurs dead_vol.
    We rely on 'base_dispense_portion' in row_dict to know how much portion was
    before adding dead volume.

    Returns a list of new sub-rows if splitting is needed; otherwise returns [row_dict].
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
        # fallback
        portion = total_vol - dead_vol
        if portion < 0:
            portion = 0

    # each sub-pot can have at most (max_allowed - dead_vol) portion
    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        # can't fix
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
# SINGLE-PLEX FLOW
###############################################################################

def single_plex_flow(dispense_vol, dead_vol):
    st.write("### Single-Plex Flow")

    # Slide storage
    if "sp_slides" not in st.session_state:
        st.session_state["sp_slides"] = []

    # 1) Add Single-Plex Slide
    st.subheader("Add Single-Plex Slide")
    sp_h2o2 = st.checkbox("Use H2O2? (Single-Plex)", value=True)
    sp_pb   = st.checkbox("Use Protein Block? (Single-Plex)", value=True)
    sp_neg  = st.checkbox("Negative Control? (skip primary)", value=False)

    # Primary
    sp_prim_name = st.text_input("Primary Name (Single-Plex)", "")
    sp_prim_dil  = st.number_input("Primary Dil (Single-Plex)", min_value=1.0, value=1000.0)
    sp_prim_dbl  = st.checkbox("Double Dispense (Primary)?", value=False)

    # Polymer
    poly_opts = ["Rabbit","Sheep","Goat","Mouse","Rat","Others"]
    sp_poly = st.selectbox("Polymer (Single-Plex)", poly_opts)
    sp_poly_dbl = st.checkbox("Double Dispense (Polymer)?", value=False)

    # Opal
    opal_opts = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
    sp_opal   = st.selectbox("Opal (Single-Plex)", opal_opts)
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
            sp_tsa_dbl = st.checkbox("Double Dispense (TSA)? (Single-Plex)", value=False)

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
    sp_cdil  = 1.0
    sp_cdbl  = False
    sp_cdilu = ""
    if sp_use_cust:
        sp_cname = st.text_input("Custom Name (Single-Plex)", "")
        sp_cdil  = st.number_input("Custom Dil (Single-Plex)", min_value=1.0, value=1000.0)
        sp_cdbl  = st.checkbox("Double Dispense (Custom)?", value=False)
        sp_cdilu = st.text_input("Custom Diluent (Single-Plex)", "bondwash/blocker")

    # Button to add
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

    # 2) Show current Single-Plex slides + remove button
    st.write("#### Current Single-Plex Slides")
    for idx, sld in enumerate(st.session_state["sp_slides"]):
        col1, col2 = st.columns([4,1])
        with col1:
            st.write(f"Slide #{idx+1}: primary={sld['prim_name']}, opal={sld['opal']}, negctrl={sld['neg']}")
        with col2:
            if st.button(f"Remove Single-Plex Slide {idx+1}", key=f"remove_sp_{idx}"):
                st.session_state["sp_slides"].pop(idx)
                st.rerun()  # or st.stop() if your version is older

    # 3) Compute table
    if "sp_final_rows" not in st.session_state:
        st.session_state["sp_final_rows"] = []

    def build_sp_table():
        from collections import defaultdict
        usage_map = defaultdict(list)
        slide_summ = []
        sp_local = st.session_state["sp_slides"]
        if not sp_local:
            st.warning("No single-plex slides to compute!")
            return

        # Build usage
        for i, sld in enumerate(sp_local, start=1):
            seq = []
            if sld["h2o2"]:
                usage_map[("H2O2","H2O2",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                seq.append("H2O2")
            if sld["pb"]:
                usage_map[("Protein Block (PB)","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                seq.append("PB")
            if not sld["neg"]:
                pname = sld["prim_name"] or "(Unnamed Primary)"
                usage_map[(pname,"Primary", sld["prim_dil"], sld["prim_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sld["prim_dbl"])
                )
                seq.append(f"Primary({pname})")
            else:
                seq.append("Primary(skipped - Neg)")
            # polymer
            pol_name = f"Polymer-{sld['poly']}"
            usage_map[(pol_name, "Polymer", 1.0, sld["poly_dbl"], "")].append(
                calc_dispense_portion(dispense_vol, sld["poly_dbl"])
            )
            seq.append(pol_name)

            # opal
            op_name = f"Opal-{sld['opal']}"
            usage_map[(op_name, "Opal", sld["opal_dil"], sld["opal_dbl"], "")].append(
                calc_dispense_portion(dispense_vol, sld["opal_dbl"])
            )
            seq.append(op_name)

            # tsa
            if sld["tsa_used"]:
                usage_map[("TSA-DIG","TSA-DIG", sld["tsa_dil"], sld["tsa_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sld["tsa_dbl"])
                )
                seq.append("TSA-DIG")

            # dapi
            if sld["use_dapi"]:
                usage_map[("DAPI","DAPI", sld["dapi_dil"], sld["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, sld["dapi_dbl"])
                )
                seq.append("DAPI")

            # custom
            if sld["use_custom"]:
                cname = sld["cust_name"]
                cdil  = sld["cust_dil"]
                cdbl  = sld["cust_dbl"]
                cdilu = sld["cust_dilu"]
                usage_map[(cname,"Custom", cdil, cdbl, cdilu)].append(
                    calc_dispense_portion(dispense_vol, cdbl)
                )
                seq.append(f"Custom({cname})")

            slide_summ.append({"Slide": i, "Sequence": " → ".join(seq)})

        # Show summary
        st.subheader("Single-Plex Slide Summary")
        st.table(slide_summ)

        # unify
        final_rows = []
        for (name, rtype, dil, dbl, cdilu), portions in usage_map.items():
            sums = sum(portions)
            totv = dead_vol + sums
            stck = totv / dil
            w = check_volume_warning(totv)
            if rtype=="Custom":
                dilu = cdilu
            else:
                dilu = choose_diluent(rtype)

            final_rows.append({
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": dilu,
                "Total Volume (µL)": format_number(totv),
                "Stock Volume (µL)": format_number(stck),
                "Warning": w,
                "base_dispense_portion": sums,
            })
        st.session_state["sp_final_rows"] = final_rows

    if st.button("Compute Single-Plex Table"):
        build_sp_table()
        st.success("Single-Plex table built! Scroll down.")

    # 4) Show final + splitting only if needed
    if st.session_state["sp_final_rows"]:
        sp_final = st.session_state["sp_final_rows"]

        # Are there any row > 5000?
        any_over_5000 = any(
            r["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"]
            for r in sp_final
        )
        if not any_over_5000:
            # Just show final table, no splitting
            st.subheader("Single-Plex Final Table (No Splitting Needed)")
            df = pd.DataFrame(sp_final)
            st.dataframe(df, use_container_width=True)
        else:
            # Show final table and a split button
            st.subheader("Single-Plex Table (Potential Splitting Needed)")
            df = pd.DataFrame(sp_final)
            st.dataframe(df, use_container_width=True)

            if st.button("Split Single-Plex Rows >5000?"):
                new_list = []
                for row_ in sp_final:
                    if row_["Warning"] in ["Consider splitting!", "EXCEEDS 6000 µL limit!"]:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_vol)
                        new_list.extend(splitted)
                    else:
                        new_list.append(row_)
                st.session_state["sp_final_rows"] = new_list
                st.success("Splitting done! See final splitted table below.")
                st.stop()

###############################################################################
# MULTI-PLEX FLOW
###############################################################################

def multi_plex_flow(dispense_vol, dead_vol):
    st.write("### Multi-Plex Flow (New Sequence Logic)")

    # store multi-plex slides
    if "mp_slides" not in st.session_state:
        st.session_state["mp_slides"] = []

    # 1) Add multi-plex slide
    st.subheader("Add Multi-Plex Slide")

    mp_h2o2 = st.checkbox("Use H2O2? (Multi-Plex)", value=True)
    # PB toggles
    mp_pb_before = st.checkbox("Use PB before each primary?", value=True)
    mp_pb_after  = st.checkbox("Use PB after each opal?", value=False)

    mp_neg = st.checkbox("Negative Control? (skip primary for each plex?)", value=False)

    # DAPI
    mp_use_dapi = st.checkbox("Use DAPI? (Multi-Plex)", value=False)
    mp_dapi_dil = 1000.0
    mp_dapi_dbl = False
    if mp_use_dapi:
        mp_dapi_dil = st.number_input("DAPI Dil (Multi-Plex)", min_value=1.0, value=1000.0)
        mp_dapi_dbl = st.checkbox("Double Dispense (DAPI)? (Multi-Plex)?", value=False)

    # custom
    mp_use_cust = st.checkbox("Use Custom? (Multi-Plex)", value=False)
    mp_cname = ""
    mp_cdil  = 1.0
    mp_cdbl  = False
    mp_cdilu = ""
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

    # how many plex
    mp_nplex = st.number_input("Number of plex in this Multi-Plex slide?", min_value=1, max_value=8, value=2)

    plex_entries = []
    warn_780_position = False

    # For each plex
    for i in range(mp_nplex):
        st.write(f"**Plex #{i+1}**")
        pm_name = st.text_input(f"Primary Name (Plex {i+1})", key=f"mp_prim_name_{i}")
        pm_dil  = st.number_input(f"Primary Dil (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_prim_dil_{i}")
        pm_dbl  = st.checkbox(f"Double Dispense(Primary)? (Plex {i+1})", value=False, key=f"mp_prim_dbl_{i}")

        # polymer
        pm_poly_opts = ["Rabbit","Sheep","Goat","Mouse","Rat","Others"]
        pm_poly_sel  = st.selectbox(f"Polymer (Plex {i+1})", pm_poly_opts, key=f"mp_poly_sel_{i}")
        pm_poly_dbl  = st.checkbox(f"Double Dispense(Polymer)? (Plex {i+1})", value=False, key=f"mp_poly_dbl_{i}")

        # opal
        opal_opts = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
        pm_opal = st.selectbox(f"Opal (Plex {i+1})", opal_opts, key=f"mp_opal_{i}")
        pm_opal_dil = st.number_input(f"Opal Dil (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_opal_dil_{i}")
        pm_opal_dbl = st.checkbox(f"Double Dispense(Opal)? (Plex {i+1})", value=False, key=f"mp_opal_dbl_{i}")

        if pm_opal == "780" and i < (mp_nplex -1):
            warn_780_position = True

        # TSA for 780
        pm_tsa_used = False
        pm_tsa_dil  = 1000.0
        pm_tsa_dbl  = False
        if pm_opal == "780":
            st.write(f"(Plex {i+1}) => TSA-DIG?")
            pm_tsa_used = st.checkbox(f"Use TSA-DIG? (Plex {i+1})", key=f"mp_tsa_used_{i}")
            if pm_tsa_used:
                pm_tsa_dil = st.number_input(f"TSA-DIG Dil (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_tsa_dil_{i}")
                pm_tsa_dbl = st.checkbox(f"Double Dispense(TSA)? (Plex {i+1})", value=False, key=f"mp_tsa_dbl_{i}")

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
            st.error("Opal 780 must be in the last plex. Please fix your plex order or reduce plex count.")
        else:
            # check custom
            if mp_use_cust and not mp_cname.strip():
                st.warning("Enter custom reagent name or uncheck 'Use Custom'.")
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

    # Show existing multi-plex slides + remove button
    st.write("#### Current Multi-Plex Slides")
    for idx, sld in enumerate(st.session_state["mp_slides"]):
        col1, col2 = st.columns([4,1])
        with col1:
            st.write(f"Slide #{idx+1}: #plex={len(sld['plex_list'])}, vectaplex={sld['vectaplex']}, PB_before={sld['pb_before']} PB_after={sld['pb_after']}")
        with col2:
            if st.button(f"Remove Multi-Plex Slide {idx+1}", key=f"remove_mp_{idx}"):
                st.session_state["mp_slides"].pop(idx)
                st.rerun()

    if "mp_final_rows" not in st.session_state:
        st.session_state["mp_final_rows"] = []

    def build_mp_table():
        if not st.session_state["mp_slides"]:
            st.warning("No multi-plex slides to compute!")
            return

        usage_map = defaultdict(list)
        slide_summaries = []

        # Sequence rules (your new constraints):
        # - If opal != 780 => opal, then vectaplex (if vectaplex used).
        # - If opal == 780 => TSA -> vectaplex -> opal.
        # - PB can be used before each primary if pb_before, after each opal if pb_after.
        # - Negative control => skip primary
        # - The code below implements that logic in a single pass.

        for s_idx, slide in enumerate(st.session_state["mp_slides"], start=1):
            seq = []
            # H2O2
            if slide["h2o2"]:
                usage_map[("H2O2","H2O2",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                seq.append("H2O2")

            # For each plex in order
            plexes = slide["plex_list"]
            for plex_i, plex_info in enumerate(plexes, start=1):
                # PB before?
                if slide["pb_before"]:
                    usage_map[("Protein Block (PB)","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                    seq.append("PB(before)")

                # negative ctrl => skip primary
                if not slide["neg"]:
                    pname = plex_info["primary_name"] or f"(UnnamedPrim{plex_i})"
                    usage_map[(pname,"Primary", plex_info["primary_dil"], plex_info["primary_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex_info["primary_dbl"])
                    )
                    seq.append(f"Primary({pname})")
                else:
                    seq.append(f"Plex {plex_i}: Primary(skipped - neg)")

                # polymer
                polymer_name = f"Polymer-{plex_info['polymer']}"
                usage_map[(polymer_name, "Polymer", 1.0, plex_info["polymer_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, plex_info["polymer_dbl"])
                )
                seq.append(polymer_name)

                # If opal=780 => we do: TSA -> vectaplex? -> opal
                if plex_info["opal"] == "780":
                    if plex_info["tsa_used"]:
                        usage_map[("TSA-DIG","TSA-DIG", plex_info["tsa_dil"], plex_info["tsa_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, plex_info["tsa_dbl"])
                        )
                        seq.append("TSA-DIG")

                    if slide["vectaplex"]:
                        # vectaplex after TSA but before opal
                        usage_map[("Vectaplex", "Vectaplex", 1.0, slide["vectaplex_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, slide["vectaplex_dbl"])
                        )
                        seq.append("Vectaplex")

                    # now opal
                    op_name = f"Opal-{plex_info['opal']}"
                    usage_map[(op_name,"Opal", plex_info["opal_dil"], plex_info["opal_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex_info["opal_dbl"])
                    )
                    seq.append(op_name)

                else:
                    # if opal != 780 => opal => then vectaplex
                    op_name = f"Opal-{plex_info['opal']}"
                    usage_map[(op_name,"Opal", plex_info["opal_dil"], plex_info["opal_dbl"], "")].append(
                        calc_dispense_portion(dispense_vol, plex_info["opal_dbl"])
                    )
                    seq.append(op_name)

                    if slide["vectaplex"]:
                        usage_map[("Vectaplex","Vectaplex",1.0, slide["vectaplex_dbl"], "")].append(
                            calc_dispense_portion(dispense_vol, slide["vectaplex_dbl"])
                        )
                        seq.append("Vectaplex")

                # PB after?
                if slide["pb_after"]:
                    usage_map[("Protein Block (PB)","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False))
                    seq.append("PB(after)")

            # after all plexes => DAPI if used
            if slide["use_dapi"]:
                usage_map[("DAPI","DAPI", slide["dapi_dil"], slide["dapi_dbl"], "")].append(
                    calc_dispense_portion(dispense_vol, slide["dapi_dbl"])
                )
                seq.append("DAPI")

            # custom
            if slide["use_custom"]:
                cname = slide["cust_name"]
                cdil  = slide["cust_dil"]
                cdbl  = slide["cust_dbl"]
                cdilu = slide["cust_dilu"]
                usage_map[(cname,"Custom", cdil, cdbl, cdilu)].append(
                    calc_dispense_portion(dispense_vol, cdbl)
                )
                seq.append(f"Custom({cname})")

            # done one slide
            slide_summaries.append({"Multi-Plex Slide": s_idx, "Sequence": " → ".join(seq)})

        st.subheader("Multi-Plex Slide Summary")
        st.table(slide_summaries)

        # unify usage
        final_rows = []
        for (name, rtype, dil, dbl, cdilu), portions in usage_map.items():
            sums = sum(portions)
            totv = dead_vol + sums
            stck = totv / dil
            w = check_volume_warning(totv)
            if rtype == "Custom":
                dd = cdilu
            else:
                dd = choose_diluent(rtype)

            final_rows.append({
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": dd,
                "Total Volume (µL)": format_number(totv),
                "Stock Volume (µL)": format_number(stck),
                "Warning": w,
                "base_dispense_portion": sums,
            })
        st.session_state["mp_final_rows"] = final_rows

    if st.button("Compute Multi-Plex Table"):
        build_mp_table()
        st.success("Multi-Plex table built! Scroll down.")

    # 2) Show final + splitting only if needed
    if st.session_state["mp_final_rows"]:
        mp_final = st.session_state["mp_final_rows"]
        any_over_5000 = any(r["Warning"] in ["Consider splitting!","EXCEEDS 6000 µL limit!"] for r in mp_final)
        if not any_over_5000:
            st.subheader("Multi-Plex Final Table (No Splitting Needed)")
            df = pd.DataFrame(mp_final)
            st.dataframe(df, use_container_width=True)
        else:
            st.subheader("Multi-Plex Table (Potential Splitting Needed)")
            df = pd.DataFrame(mp_final)
            st.dataframe(df, use_container_width=True)

            if st.button("Split Multi-Plex Rows >5000?"):
                new_list = []
                for row_ in mp_final:
                    if row_["Warning"] in ["Consider splitting!","EXCEEDS 6000 µL limit!"]:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_vol)
                        new_list.extend(splitted)
                    else:
                        new_list.append(row_)
                st.session_state["mp_final_rows"] = new_list
                st.success("Splitting done for Multi-Plex. Scroll further.")
                st.stop()

###############################################################################
# MAIN MENU
###############################################################################

def main_app():
    st.title("Combined Single-Plex / Multi-Plex with Updated Vectaplex & Sequence Logic")

    # GLOBAL SETTINGS
    st.header("Global Settings")
    disp_vol = st.number_input("Dispense Volume (µL)", min_value=1, max_value=9999, value=150)
    dead_vol = st.number_input("Dead Volume (µL)", min_value=0, max_value=9999, value=150)
    st.write("---")

    # SINGLE vs MULTI
    choice = st.radio("Choose Flow:", ["Single-Plex","Multi-Plex"])

    if choice=="Single-Plex":
        single_plex_flow(disp_vol, dead_vol)
    else:
        multi_plex_flow(disp_vol, dead_vol)

def main():
    main_app()

if __name__=="__main__":
    main()
