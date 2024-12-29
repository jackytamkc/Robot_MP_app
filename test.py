import streamlit as st
from collections import defaultdict
import pandas as pd
import math

###############################################################################
# 1) Shared Utility Functions
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    """
    Return the portion for a single usage:
      portion = disp_vol * (2 if double_disp else 1)
    """
    return disp_vol * (2 if double_disp else 1)

def check_volume_warning(volume: float) -> str:
    """
    Return a warning label:
      - If volume > 6000 => "EXCEEDS 6000 µL limit!"
      - If volume > 5000 => "Consider splitting!"
      - Else => ""
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    return ""

def format_number(num: float) -> str:
    """
    Convert a float to a human-friendly string:
      - If it's effectively an integer, show no decimals
      - Otherwise, show up to 4 significant digits
    """
    if float(num).is_integer():
        return str(int(num))
    else:
        return f"{num:.4g}"

def choose_diluent(rtype: str, custom: str = "") -> str:
    """
    Decide the diluent string based on reagent type:
      - "H2O2", "PB", "Polymer", "Vectaplex" => ""
      - "Opal" => "amplifier"
      - "Primary", "TSA-DIG", "DAPI" => "bondwash/blocker"
      - "Custom" => user-provided custom string
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
    Attempt to split a row if total volume > max_allowed.
    Each sub-pot re-incurs the dead volume.

    row_dict has:
      "Reagent", "Type", "Dilution Factor", "Double Disp?", "Diluent",
      "Total Volume (µL)", "Stock Volume (µL)", "Warning",
      "base_dispense_portion" => sum of usage portions (before adding dead_vol).

    Returns a list of sub-rows if splitting needed; otherwise [row_dict].
    """
    total_vol_str = row_dict["Total Volume (µL)"]
    try:
        total_vol = float(total_vol_str)
    except:
        total_vol = 0.0

    if total_vol <= max_allowed:
        return [row_dict]

    # We need base_dispense_portion
    portion = row_dict.get("base_dispense_portion", None)
    if portion is None:
        portion = total_vol - dead_vol
        if portion < 0:
            portion = 0

    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        # can't fix if dead_vol >= max_allowed
        return [row_dict]

    needed_pots = math.ceil(portion / max_portion)
    new_rows = []
    leftover = portion

    try:
        dil_factor = float(row_dict["Dilution Factor"])
    except:
        dil_factor = 1.0

    for i in range(needed_pots):
        pot_portion = min(leftover, max_portion)
        leftover -= pot_portion
        pot_total = dead_vol + pot_portion
        stock_vol = pot_total / dil_factor

        sub_row = row_dict.copy()
        sub_row["Reagent"] += f" (Split {i+1}/{needed_pots})"
        sub_row["Total Volume (µL)"] = format_number(pot_total)
        sub_row["Stock Volume (µL)"] = format_number(stock_vol)
        sub_row["base_dispense_portion"] = pot_portion
        sub_row["Warning"] = check_volume_warning(pot_total)
        new_rows.append(sub_row)

    return new_rows

###############################################################################
# 2) Single-Plex Flow
###############################################################################

def single_plex_flow(dispense_volume, dead_volume):
    """
    Collect and store single-plex slides in st.session_state["sp_slides"],
    then unify usage + produce final table when user clicks 'Compute Single-Plex Table'.
    """
    st.write("### Single-Plex Flow")

    if "sp_slides" not in st.session_state:
        st.session_state["sp_slides"] = []

    # ---------- Add Single-Plex Slide UI ----------
    st.subheader("Add Single-Plex Slide")

    sp_h2o2 = st.checkbox("Use H2O2? (Single-Plex)", value=True, key="sp_h2o2")
    sp_pb   = st.checkbox("Use Protein Block? (Single-Plex)", value=True, key="sp_pb")
    sp_negctrl = st.checkbox("Negative Control? (skip primary)", key="sp_negctrl")

    # Primary
    sp_primary_name = st.text_input("Primary Name (Single-Plex)", "", key="sp_primary_name")
    sp_primary_dil  = st.number_input("Primary Dilution (Single-Plex)", min_value=1.0, value=1000.0, key="sp_primary_dil")
    sp_double_primary = st.checkbox("Double Dispense (Primary)?", value=False, key="sp_double_primary")

    # Polymer
    polymer_choices = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
    sp_polymer_choice = st.selectbox("Polymer Type (Single-Plex)", polymer_choices, key="sp_polymer_choice")
    sp_double_polymer = st.checkbox("Double Dispense (Polymer)?", value=False, key="sp_double_polymer")

    # Opal
    opal_choices = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
    sp_opal_choice = st.selectbox("Opal Choice (Single-Plex)", opal_choices, key="sp_opal_choice")
    sp_opal_dil    = st.number_input("Opal Dil. Factor (Single-Plex)", min_value=1.0, value=1000.0, key="sp_opal_dil")
    sp_double_opal = st.checkbox("Double Dispense (Opal)?", value=False, key="sp_double_opal")

    # TSA if opal=780
    sp_tsa_used = False
    sp_tsa_dil = 1000.0
    sp_tsa_double = False
    if st.session_state.get("sp_opal_choice") == "780":
        st.markdown("Opal 780 → optional TSA-DIG for single-plex?")
        sp_tsa_used = st.checkbox("Use TSA-DIG? (Single-Plex)", key="sp_tsa_used")
        if sp_tsa_used:
            sp_tsa_dil = st.number_input("TSA-DIG Dilution (Single-Plex)", min_value=1.0, value=1000.0, key="sp_tsa_dil")
            sp_tsa_double = st.checkbox("Double Dispense (TSA-DIG)?", value=False, key="sp_tsa_double")

    # DAPI
    sp_use_dapi = st.checkbox("Use DAPI? (Single-Plex)", value=False, key="sp_use_dapi")
    sp_dapi_dil = 1000.0
    sp_double_dapi = False
    if sp_use_dapi:
        sp_dapi_dil = st.number_input("DAPI Dilution (Single-Plex)", min_value=1.0, value=1000.0, key="sp_dapi_dil")
        sp_double_dapi = st.checkbox("Double Dispense (DAPI)?", value=False, key="sp_dapi_double")

    # Custom
    sp_use_custom = st.checkbox("Use Custom Reagent? (Single-Plex)", value=False, key="sp_use_custom")
    sp_custom_name = ""
    sp_custom_dil = 1.0
    sp_custom_double = False
    sp_custom_diluent = ""
    if sp_use_custom:
        sp_custom_name = st.text_input("Custom Reagent Name (Single-Plex)", "", key="sp_custom_name")
        sp_custom_dil  = st.number_input("Custom Reagent Dil. Factor (Single-Plex)", min_value=1.0, value=1000.0, key="sp_custom_dil")
        sp_custom_double = st.checkbox("Double Dispense (Custom)?", value=False, key="sp_custom_double")
        sp_custom_diluent = st.text_input("Custom Reagent Diluent (Single-Plex)", "bondwash/blocker", key="sp_custom_diluent")

    if st.button("Add Single-Plex Slide"):
        if not sp_negctrl and not sp_primary_name.strip():
            st.warning("Please enter a primary name if not negative control!")
        elif sp_use_custom and not sp_custom_name.strip():
            st.warning("Please enter a custom reagent name or uncheck the custom reagent box.")
        else:
            one_slide = {
                "h2o2": sp_h2o2,
                "pb": sp_pb,
                "negative_ctrl": sp_negctrl,

                "primary_name": sp_primary_name.strip(),
                "primary_dil": sp_primary_dil,
                "double_primary": sp_double_primary,

                "polymer_choice": sp_polymer_choice,
                "double_polymer": sp_double_polymer,

                "opal_choice": sp_opal_choice,
                "opal_dil": sp_opal_dil,
                "double_opal": sp_double_opal,

                "tsa_used": sp_tsa_used,
                "tsa_dil": sp_tsa_dil,
                "tsa_double": sp_tsa_double,

                "use_dapi": sp_use_dapi,
                "dapi_dil": sp_dapi_dil,
                "double_dapi": sp_double_dapi,

                "use_custom": sp_use_custom,
                "custom_name": sp_custom_name.strip(),
                "custom_dil": sp_custom_dil,
                "custom_double": sp_custom_double,
                "custom_diluent": sp_custom_diluent.strip(),
            }
            st.session_state["sp_slides"].append(one_slide)
            st.success("Single-Plex Slide added.")

    # Show current single-plex slides
    st.write("#### Current Single-Plex Slides")
    sp_slides = st.session_state["sp_slides"]
    if sp_slides:
        for idx, s in enumerate(sp_slides):
            st.write(f"Slide #{idx+1}: Primary={s['primary_name']}, polymer={s['polymer_choice']}, opal={s['opal_choice']} (negctrl?={s['negative_ctrl']})")
    else:
        st.write("No single-plex slides added yet.")

    # ---------- Compute Single-Plex Table ----------
    if "sp_final_rows" not in st.session_state:
        st.session_state["sp_final_rows"] = []

    def build_single_plex_table():
        if not st.session_state["sp_slides"]:
            st.warning("No single-plex slides to compute!")
            return

        usage_map = defaultdict(list)
        slide_summaries = []

        slides_local = st.session_state["sp_slides"]
        for i, slide in enumerate(slides_local, start=1):
            seq = []
            if slide["h2o2"]:
                usage_map[("H2O2", "H2O2", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("H2O2")
            if slide["pb"]:
                usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("PB")
            if not slide["negative_ctrl"]:
                # primary
                pname = slide["primary_name"] or "(Unnamed Primary)"
                usage_map[(pname, "Primary", slide["primary_dil"], slide["double_primary"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["double_primary"])
                )
                seq.append(f"Primary({pname})")
            else:
                seq.append("Primary(skipped - NegCtrl)")
            # polymer
            poly_name = f"Polymer-{slide['polymer_choice']}"
            usage_map[(poly_name, "Polymer", 1.0, slide["double_polymer"], "")].append(
                calc_dispense_portion(dispense_volume, slide["double_polymer"])
            )
            seq.append(poly_name)

            # opal
            opal_name = f"Opal-{slide['opal_choice']}"
            usage_map[(opal_name, "Opal", slide["opal_dil"], slide["double_opal"], "")].append(
                calc_dispense_portion(dispense_volume, slide["double_opal"])
            )
            seq.append(opal_name)

            # TSA
            if slide["tsa_used"]:
                usage_map[("TSA-DIG", "TSA-DIG", slide["tsa_dil"], slide["tsa_double"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["tsa_double"])
                )
                seq.append("TSA-DIG")

            # DAPI
            if slide["use_dapi"]:
                usage_map[("DAPI", "DAPI", slide["dapi_dil"], slide["double_dapi"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["double_dapi"])
                )
                seq.append("DAPI")

            # custom
            if slide["use_custom"]:
                c_name = slide["custom_name"]
                c_dil = slide["custom_dil"]
                c_double = slide["custom_double"]
                c_diluent = slide["custom_diluent"]
                usage_map[(c_name, "Custom", c_dil, c_double, c_diluent)].append(
                    calc_dispense_portion(dispense_volume, c_double)
                )
                seq.append(f"Custom({c_name})")

            slide_summaries.append({"Slide": i, "Sequence": " → ".join(seq)})

        # Show slide summary
        st.subheader("Single-Plex: Slide Summary")
        st.table(slide_summaries)

        # unify
        final_rows = []
        for (name, rtype, dil, dbl, diluent_cust), portions in usage_map.items():
            sum_portions = sum(portions)
            total_vol = dead_volume + sum_portions
            stock_vol = total_vol / dil
            row_warn = check_volume_warning(total_vol)

            # pick final diluent
            if rtype == "Custom":
                final_diluent = diluent_cust
            else:
                final_diluent = choose_diluent(rtype)

            row_dict = {
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": final_diluent,
                "Total Volume (µL)": format_number(total_vol),
                "Stock Volume (µL)": format_number(stock_vol),
                "Warning": row_warn,
                "base_dispense_portion": sum_portions,
            }
            final_rows.append(row_dict)

        st.session_state["sp_final_rows"] = final_rows

    if st.button("Compute Single-Plex Table"):
        build_single_plex_table()
        st.success("Single-Plex table computed! See below.")

    # ---------- Show Single-Plex table + Splitting ----------
    if "sp_final_rows" in st.session_state and st.session_state["sp_final_rows"]:
        sp_final = st.session_state["sp_final_rows"]
        st.subheader("Single-Plex Reagent Table (Before Splitting)")

        df = pd.DataFrame(sp_final)

        def highlight_rows(row):
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

        styled_df = df.style.apply(highlight_rows, axis=1)
        st.dataframe(styled_df, use_container_width=True)

        # Over 5000 => consider splitting
        over_idx = df.index[df["Warning"].isin(["Consider splitting!", "EXCEEDS 6000 µL limit!"])].tolist()
        if over_idx:
            st.write("Rows exceed 5000 µL. Split them?")
            if st.button("Split Single-Plex Rows > 5000 µL"):
                new_list = []
                for i, row_ in enumerate(sp_final):
                    if i in over_idx:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_volume)
                        new_list.extend(splitted)
                    else:
                        new_list.append(row_)
                st.session_state["sp_final_rows"] = new_list
                st.success("Splitting done. See updated table below.")
                st.rerun()  # or remove if you have streamlit >=1.10 and want st.experimental_rerun()

        # Show updated
        sp_final_updated = st.session_state["sp_final_rows"]
        df2 = pd.DataFrame(sp_final_updated)

        def highlight_rows2(row):
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
        styled_df2 = df2.style.apply(highlight_rows2, axis=1)
        st.subheader("Single-Plex Reagent Table (After Splitting)")
        st.dataframe(styled_df2, use_container_width=True)

        # pot limit
        pot_count = len(sp_final_updated)
        if pot_count > 29:
            st.error(f"WARNING: You have {pot_count} total pots, exceeding the 29-pot limit!")


###############################################################################
# 3) Multi-Plex Flow
###############################################################################

def multi_plex_flow(dispense_volume, dead_volume):
    """
    A multi-plex approach:
      - st.session_state["mp_slides"] for storing multi-plex slides
      - Each slide can have H2O2, PB, negative ctrl, DAPI, custom reagent
      - "vectaplex_used" => add 'Vectaplex A' and 'Vectaplex B' with no dilution
      - For each plex in that slide, user defines a primary set
      - Then unify usage & show final table (plus splitting) upon "Compute"
    """
    st.write("### Multi-Plex Flow")

    if "mp_slides" not in st.session_state:
        st.session_state["mp_slides"] = []

    # 1) Add a multi-plex slide
    st.subheader("Add Multi-Plex Slide")

    mp_h2o2 = st.checkbox("Use H2O2? (Multi-Plex)", value=True, key="mp_h2o2")
    mp_pb   = st.checkbox("Use Protein Block? (Multi-Plex)", value=True, key="mp_pb")
    mp_negctrl = st.checkbox("Negative Control? (skip primary) (Multi-Plex)", key="mp_negctrl")

    # DAPI
    mp_use_dapi = st.checkbox("Use DAPI? (Multi-Plex)", value=False, key="mp_use_dapi")
    mp_dapi_dil = 1000.0
    mp_dapi_double = False
    if mp_use_dapi:
        mp_dapi_dil = st.number_input("DAPI Dil. Factor (Multi-Plex)", min_value=1.0, value=1000.0, key="mp_dapi_dil")
        mp_dapi_double = st.checkbox("Double Dispense (DAPI)? (Multi-Plex)", key="mp_dapi_double")

    # Custom
    mp_use_custom = st.checkbox("Use Custom Reagent? (Multi-Plex)", value=False, key="mp_use_custom")
    mp_custom_name = ""
    mp_custom_dil  = 1.0
    mp_custom_double = False
    mp_custom_diluent = ""
    if mp_use_custom:
        mp_custom_name = st.text_input("Custom Reagent Name (Multi-Plex)", "", key="mp_custom_name")
        mp_custom_dil  = st.number_input("Custom Reagent Dil. Factor (Multi-Plex)", min_value=1.0, value=1000.0, key="mp_custom_dil")
        mp_custom_double = st.checkbox("Double Dispense (Custom)? (Multi-Plex)", value=False, key="mp_custom_double")
        mp_custom_diluent = st.text_input("Custom Reagent Diluent (Multi-Plex)", "bondwash/blocker", key="mp_custom_diluent")

    # Vectaplex
    mp_vectaplex = st.checkbox("Use Vectaplex? (Multi-Plex)", value=False, key="mp_vectaplex")

    # How many plex?
    mp_num_plex = st.number_input("Number of plex in this slide?", min_value=1, max_value=8, value=2, key="mp_num_plex")
    plex_entries = []

    # For each plex
    for i in range(mp_num_plex):
        st.write(f"**Plex #{i+1}**")
        # primary
        pm_name = st.text_input(f"Plex {i+1} - Primary Name", key=f"mp_primary_{i}")
        pm_dil  = st.number_input(f"Plex {i+1} - Primary Dil. Factor", min_value=1.0, value=1000.0, key=f"mp_primary_dil_{i}")
        pm_dbl  = st.checkbox(f"Plex {i+1} - Double Dispense Primary?", key=f"mp_primary_double_{i}")

        # polymer
        pm_poly_choices = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
        pm_poly_sel = st.selectbox(f"Plex {i+1} - Polymer Type", pm_poly_choices, key=f"mp_poly_sel_{i}")
        pm_poly_dbl = st.checkbox(f"Plex {i+1} - Double Dispense Polymer?", key=f"mp_polymer_double_{i}")

        # opal
        pm_opal_choices = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
        pm_opal_sel = st.selectbox(f"Plex {i+1} - Opal Choice", pm_opal_choices, key=f"mp_opal_sel_{i}")
        pm_opal_dil = st.number_input(f"Plex {i+1} - Opal Dil. Factor", min_value=1.0, value=1000.0, key=f"mp_opal_dil_{i}")
        pm_opal_dbl = st.checkbox(f"Plex {i+1} - Double Dispense Opal?", key=f"mp_opal_double_{i}")

        # TSA if opal=780
        pm_tsa_used = False
        pm_tsa_dil  = 1000.0
        pm_tsa_dbl  = False
        if st.session_state.get(f"mp_opal_sel_{i}") == "780":
            st.markdown(f"Plex {i+1} - Opal 780 => TSA-DIG?")
            pm_tsa_used = st.checkbox(f"Use TSA-DIG? (Plex {i+1})", key=f"mp_tsa_used_{i}")
            if pm_tsa_used:
                pm_tsa_dil = st.number_input(f"TSA-DIG Dil. Factor (Plex {i+1})", min_value=1.0, value=1000.0, key=f"mp_tsa_dil_{i}")
                pm_tsa_dbl = st.checkbox(f"Double Dispense TSA-DIG? (Plex {i+1})", key=f"mp_tsa_dbl_{i}")

        plex_entries.append({
            "primary_name": pm_name.strip(),
            "primary_dil": pm_dil,
            "double_primary": pm_dbl,

            "polymer_choice": pm_poly_sel,
            "double_polymer": pm_poly_dbl,

            "opal_choice": pm_opal_sel,
            "opal_dil": pm_opal_dil,
            "double_opal": pm_opal_dbl,

            "tsa_used": pm_tsa_used,
            "tsa_dil": pm_tsa_dil,
            "tsa_double": pm_tsa_dbl
        })

    # Add Slide
    if st.button("Add Multi-Plex Slide"):
        if mp_use_custom and not mp_custom_name.strip():
            st.warning("Enter a custom reagent name or uncheck 'Use Custom Reagent'.")
        else:
            one_slide = {
                "h2o2": mp_h2o2,
                "pb": mp_pb,
                "negctrl": mp_negctrl,
                "use_dapi": mp_use_dapi,
                "dapi_dil": mp_dapi_dil,
                "double_dapi": mp_dapi_double,
                "use_custom": mp_use_custom,
                "custom_name": mp_custom_name.strip(),
                "custom_dil": mp_custom_dil,
                "custom_double": mp_custom_double,
                "custom_diluent": mp_custom_diluent.strip(),
                "vectaplex_used": mp_vectaplex,
                "plexes": plex_entries
            }
            st.session_state["mp_slides"].append(one_slide)
            st.success("Multi-Plex Slide added.")

    # Show current multi-plex slides
    st.write("#### Current Multi-Plex Slides")
    if st.session_state["mp_slides"]:
        for idx, s in enumerate(st.session_state["mp_slides"]):
            st.write(f"Slide #{idx+1}: #plex={len(s['plexes'])}, vectaplex?={s['vectaplex_used']}, dapi?={s['use_dapi']}")
    else:
        st.write("No multi-plex slides added.")

    # ---------- Compute Multi-Plex Table ----------
    if "mp_final_rows" not in st.session_state:
        st.session_state["mp_final_rows"] = []

    def build_multi_plex_table():
        mp_slides_local = st.session_state["mp_slides"]
        if not mp_slides_local:
            st.warning("No multi-plex slides to compute!")
            return

        usage_map = defaultdict(list)
        slide_summaries = []

        # We'll assume the sequence: H2O2 -> PB -> for each plex in order => if vectaplex => vectaplex reagents => if dapi => DAPI => if custom => custom
        # negative ctrl => skip primary for each plex
        # We'll keep it simpler: each multi-plex "slide" is an entire set of plexes. We'll produce 1 summary line per multi-plex slide
        for i, slide in enumerate(mp_slides_local, start=1):
            seq = []

            if slide["h2o2"]:
                usage_map[("H2O2", "H2O2", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("H2O2")

            if slide["pb"]:
                usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("PB")

            for plex_index, plex_info in enumerate(slide["plexes"], start=1):
                if not slide["negctrl"]:
                    # Primary
                    p_name = plex_info["primary_name"] or f"(Unnamed Plex {plex_index} Primary)"
                    usage_map[(p_name, "Primary", plex_info["primary_dil"], plex_info["double_primary"], "")].append(
                        calc_dispense_portion(dispense_volume, plex_info["double_primary"])
                    )
                    seq.append(f"Primary({p_name})")
                else:
                    seq.append(f"Plex {plex_index}: Primary skipped (Neg Ctrl)")

                # polymer
                poly_name = f"Polymer-{plex_info['polymer_choice']}"
                usage_map[(poly_name, "Polymer", 1.0, plex_info["double_polymer"], "")].append(
                    calc_dispense_portion(dispense_volume, plex_info["double_polymer"])
                )
                seq.append(poly_name)

                # opal
                opal_name = f"Opal-{plex_info['opal_choice']}"
                usage_map[(opal_name, "Opal", plex_info["opal_dil"], plex_info["double_opal"], "")].append(
                    calc_dispense_portion(dispense_volume, plex_info["double_opal"])
                )
                seq.append(opal_name)

                # TSA if used
                if plex_info["tsa_used"]:
                    usage_map[("TSA-DIG", "TSA-DIG", plex_info["tsa_dil"], plex_info["tsa_double"], "")].append(
                        calc_dispense_portion(dispense_volume, plex_info["tsa_double"])
                    )
                    seq.append("TSA-DIG")

            # if vectaplex => add "Vectaplex A" & "Vectaplex B"
            if slide["vectaplex_used"]:
                usage_map[("Vectaplex A", "Vectaplex", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                usage_map[("Vectaplex B", "Vectaplex", 1.0, False, "")].append(calc_dispense_portion(dispense_volume, False))
                seq.append("Vectaplex(A+B)")

            # DAPI
            if slide["use_dapi"]:
                usage_map[("DAPI", "DAPI", slide["dapi_dil"], slide["double_dapi"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["double_dapi"])
                )
                seq.append("DAPI")

            # custom
            if slide["use_custom"]:
                c_name = slide["custom_name"]
                c_dil  = slide["custom_dil"]
                c_dbl  = slide["custom_double"]
                c_diluent = slide["custom_diluent"]
                usage_map[(c_name, "Custom", c_dil, c_dbl, c_diluent)].append(
                    calc_dispense_portion(dispense_volume, c_dbl)
                )
                seq.append(f"Custom({c_name})")

            slide_summaries.append({"Multi-Plex Slide": i, "Sequence": " → ".join(seq)})

        # show summary
        st.subheader("Multi-Plex: Slide Summary")
        st.table(slide_summaries)

        # unify
        mp_rows = []
        for (name, rtype, dil, dbl, cust_diluent), portions in usage_map.items():
            sum_portions = sum(portions)
            total_vol = dead_volume + sum_portions
            stock_vol = total_vol / dil
            row_warn = check_volume_warning(total_vol)

            if rtype == "Custom":
                final_diluent = cust_diluent
            else:
                final_diluent = choose_diluent(rtype)

            row_dict = {
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": final_diluent,
                "Total Volume (µL)": format_number(total_vol),
                "Stock Volume (µL)": format_number(stock_vol),
                "Warning": row_warn,
                "base_dispense_portion": sum_portions,
            }
            mp_rows.append(row_dict)

        st.session_state["mp_final_rows"] = mp_rows

    if st.button("Compute Multi-Plex Table"):
        build_multi_plex_table()
        st.success("Multi-Plex table computed! See below.")

    # show & split
    if "mp_final_rows" in st.session_state and st.session_state["mp_final_rows"]:
        mp_final = st.session_state["mp_final_rows"]
        st.subheader("Multi-Plex Reagent Table (Before Splitting)")
        df = pd.DataFrame(mp_final)

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

        styled_df = df.style.apply(highlight_mplex, axis=1)
        st.dataframe(styled_df, use_container_width=True)

        # splitting
        over_idx = df.index[df["Warning"].isin(["Consider splitting!", "EXCEEDS 6000 µL limit!"])].tolist()
        if over_idx:
            st.write("Some rows exceed 5000 µL. Split them?")
            if st.button("Split Multi-Plex Rows > 5000 µL"):
                new_list = []
                for i, row_ in enumerate(mp_final):
                    if i in over_idx:
                        splitted = split_row(row_, max_allowed=5000, dead_vol=dead_volume)
                        new_list.extend(splitted)
                    else:
                        new_list.append(row_)
                st.session_state["mp_final_rows"] = new_list
                st.success("Splitting done. See updated table below.")
                st.rerun()  # or remove if you can use st.experimental_rerun()

        # after splitting
        mp_final_updated = st.session_state["mp_final_rows"]
        df2 = pd.DataFrame(mp_final_updated)

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

        styled_df2 = df2.style.apply(highlight_mplex2, axis=1)
        st.subheader("Multi-Plex Reagent Table (After Splitting)")
        st.dataframe(styled_df2, use_container_width=True)

        pot_count = len(mp_final_updated)
        if pot_count > 29:
            st.error(f"WARNING: You have {pot_count} total pots, exceeding the 29-pot limit!")


###############################################################################
# 4) MAIN MENU
###############################################################################

def main_app():
    st.title("Combined Single-Plex / Multi-Plex App with Splitting & Highlights")

    # Global settings
    st.header("Global Settings")
    dispense_volume = st.number_input("Dispense Volume (µL)", min_value=1, max_value=9999, value=150)
    dead_volume = st.number_input("Dead Volume (µL)", min_value=0, max_value=9999, value=150)
    st.write("---")

    # Choose Single-Plex or Multi-Plex
    choice = st.radio("Which approach do you want to use?", ["Single-Plex", "Multi-Plex"])

    if choice == "Single-Plex":
        single_plex_flow(dispense_volume, dead_volume)
    else:
        multi_plex_flow(dispense_volume, dead_volume)


###############################################################################
# 5) Entry Point
###############################################################################
def main():
    main_app()

if __name__ == "__main__":
    main()
