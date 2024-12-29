import streamlit as st
from collections import defaultdict


###############################################################################
# Utility for volumes
###############################################################################

def calc_total_volume(dispense_vol, dead_vol, double_disp):
    """
    Simple formula:
      total_volume = dead_vol + (dispense_vol * (2 if double_disp else 1))
    """
    factor = 2 if double_disp else 1
    return dead_vol + (dispense_vol * factor)


def check_warn(volume):
    """
    Return warning if volume > 5000 or > 6000
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    return ""


###############################################################################
# Main single-plex app
###############################################################################

def single_plex_app():
    st.title("Single-Plex Example with Dynamic TSA-DIG Prompt & Slide Summary")

    # -------------------------------------------------------------------------
    # 1) Global Settings
    # -------------------------------------------------------------------------
    st.header("Global Settings")
    dispense_volume = st.number_input(
        "Dispense Volume (µL)",
        min_value=1, max_value=9999,
        value=150,
        help="Base volume for each reagent usage."
    )
    dead_volume = st.number_input(
        "Dead Volume (µL)",
        min_value=0, max_value=2000,
        value=150,
        help="One-time overhead for each reagent container."
    )
    # For simplicity, we assume each item (H2O2, PB, Primary, Polymer, Opal, DAPI)
    # is loaded in its own “pot.” If you unify them in your real lab, adapt accordingly.

    # This example code also includes DAPI automatically for each slide (common in single-plex).
    # If you want the user to add or skip DAPI, you can add a checkbox.
    st.write("---")

    # We store each test slide as a dict in st.session_state["primary_entries"].
    # Each dict has the fields describing the user’s choices for that slide:
    # {
    #   "primary_name": str,
    #   "polymer_choice": str,
    #   "opal_choice": str,
    #   "tsa_dig_used": bool,
    #   "tsa_dig_dil": float,
    #   "tsa_dig_double": bool,
    #   "double_primary": bool,
    #   "double_polymer": bool,
    #   "double_opal": bool,
    #   "h2o2": bool,
    #   "pb": bool,
    #   "negative_ctrl": bool,
    #   "primary_dil": float,
    #   "opal_dil": float
    # }
    if "primary_entries" not in st.session_state:
        st.session_state["primary_entries"] = []

    # -------------------------------------------------------------------------
    # 2) UI to configure "Add Primary Set"
    #    We'll do it with normal widgets (not st.form) for dynamic TSA-DIG.
    # -------------------------------------------------------------------------
    st.header("Add Primary (One Slide Each)")
    # A) Basic checkboxes
    h2o2 = st.checkbox("Use H2O2?", value=True)
    pb = st.checkbox("Use Protein Block (PB)?", value=True)
    negative_ctrl = st.checkbox("Negative Control? (Skip primary volume)")

    # B) Primary
    primary_name = st.text_input("Primary Name", "")
    primary_dil = st.number_input("Primary Dilution Factor", min_value=1.0, value=1000.0)
    double_primary = st.checkbox("Double Dispense (Primary)?", value=False)

    # C) Polymer
    polymer_options = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
    polymer_choice = st.selectbox("Polymer Type", polymer_options)
    double_polymer = st.checkbox("Double Dispense (Polymer)?", value=False)

    # D) Opal choice
    opal_options = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
    opal_choice = st.selectbox("Opal Choice", opal_options, key="opal_choice")
    opal_dil = st.number_input("Opal Dilution Factor", min_value=1.0, value=1000.0)
    double_opal = st.checkbox("Double Dispense (Opal)?", value=False)

    # E) TSA-DIG => dynamic: only appear if opal_choice == "780"
    tsa_dig_used = False
    tsa_dig_dil = 1000.0
    tsa_dig_double = False
    if st.session_state.get("opal_choice") == "780":
        st.markdown("**Opal 780 selected. Configure TSA-DIG?**")
        tsa_dig_used = st.checkbox("Use TSA-DIG?")
        if tsa_dig_used:
            tsa_dig_dil = st.number_input("TSA-DIG Dilution Factor", min_value=1.0, value=1000.0)
            tsa_dig_double = st.checkbox("Double Dispense (TSA-DIG)?", value=False)

    if st.button("Add Primary Set"):
        # Validate primary name if not negative control:
        if not negative_ctrl and not primary_name.strip():
            st.warning("Please enter a primary name if not a negative control!")
        else:
            new_slide = {
                "h2o2": h2o2,
                "pb": pb,
                "negative_ctrl": negative_ctrl,
                "primary_name": primary_name.strip() if not negative_ctrl else "(skipped by neg. ctrl)",
                "primary_dil": primary_dil,
                "double_primary": double_primary,
                "polymer_choice": polymer_choice,
                "double_polymer": double_polymer,
                "opal_choice": opal_choice,
                "opal_dil": opal_dil,
                "double_opal": double_opal,
                "tsa_dig_used": tsa_dig_used,
                "tsa_dig_dil": tsa_dig_dil,
                "tsa_dig_double": tsa_dig_double,
            }
            st.session_state["primary_entries"].append(new_slide)
            st.success("Added one test slide.")

    # -------------------------------------------------------------------------
    # 3) Show Current Slides with Remove Buttons
    # -------------------------------------------------------------------------
    st.header("Current Slides")
    if st.session_state["primary_entries"]:
        for idx, slide_info in enumerate(st.session_state["primary_entries"]):
            colA, colB = st.columns([4, 1])
            with colA:
                st.write(
                    f"**Slide #{idx + 1}** | Primary: {slide_info['primary_name']} | "
                    f"Polymer: {slide_info['polymer_choice']} | "
                    f"Opal: {slide_info['opal_choice']}"
                    + (" + TSA-DIG" if slide_info["tsa_dig_used"] else "")
                    + (" (Neg Ctrl)" if slide_info["negative_ctrl"] else "")
                )
            with colB:
                if st.button(f"Remove Slide {idx + 1}", key=f"remove_slide_{idx}"):
                    st.session_state["primary_entries"].pop(idx)
                    st.experimental_rerun()
    else:
        st.write("No slides added yet.")

    st.write("---")

    # -------------------------------------------------------------------------
    # 4) Generate Final Tables (Reagent Table + Slide Summary)
    # -------------------------------------------------------------------------
    if st.button("Generate Final Tables"):
        if not st.session_state["primary_entries"]:
            st.warning("No slides to generate!")
            return

        # We'll produce TWO tables:
        # A) "Reagent Table": volumes for each item: H2O2, PB, Primary, Polymer, Opal, DAPI, TSA-DIG
        # B) "Slide Summary": the sequence for each slide (skipping primary if negative ctrl)

        reagent_rows = []  # each row => dict( Reagent, Type, TotalVol, StockVol, Warning )
        slide_sequences = []  # each item => dict( Slide #, SequenceList )

        # Let's define simple usage rules for volume calculation:
        #   total_volume = dead_vol + (dispense_vol * (2 if double? else 1))
        #   stock_volume = total_volume / dilation_factor (except H2O2, PB, polymer might be no dilution => 1.0)
        #
        # If negative_ctrl => skip the "primary" item entirely (set volume=0 for that).
        # We'll always add an item for each selection if the user checked the box, or if it's required (like DAPI).
        # If user didn't check the box (H2O2 or PB) => skip that item.

        # We'll gather items for each slide:
        #   H2O2 => if slide_info["h2o2"] == True
        #   PB   => if slide_info["pb"] == True
        #   Primary => if not slide_info["negative_ctrl"]
        #   Polymer => always included
        #   Opal => always included
        #   TSA-DIG => if slide_info["tsa_dig_used"]
        #   DAPI => always included (common for single-plex)
        #
        # In a real lab, you might unify repeated usage if multiple slides use the same reagent.
        # But user wants each slide's items (for clarity).
        # We'll create a row per item per slide.
        # Then we also build the "sequence" for the slide summary.

        for idx, slide in enumerate(st.session_state["primary_entries"], start=1):
            seq_list = []

            # 1) H2O2
            if slide["h2o2"]:
                vol = calc_total_volume(dispense_volume, dead_volume, double_disp=False)
                # let's say no "double" for H2O2? Or you could do a separate checkbox.
                reagent_rows.append({
                    "Slide": idx,
                    "Reagent": "H2O2",
                    "Type": "H2O2",
                    "Total Volume (µL)": round(vol, 2),
                    "Stock Volume (µL)": round(vol, 2),  # no dilution
                    "Warning": check_warn(vol)
                })
                seq_list.append("H2O2")

            # 2) PB
            if slide["pb"]:
                vol = calc_total_volume(dispense_volume, dead_volume, double_disp=False)
                reagent_rows.append({
                    "Slide": idx,
                    "Reagent": "Protein Block (PB)",
                    "Type": "PB",
                    "Total Volume (µL)": round(vol, 2),
                    "Stock Volume (µL)": round(vol, 2),
                    "Warning": check_warn(vol)
                })
                seq_list.append("PB")

            # 3) Primary
            if not slide["negative_ctrl"]:
                # normal primary usage
                vol = calc_total_volume(dispense_volume, dead_volume, slide["double_primary"])
                stock_vol = vol / slide["primary_dil"]
                reagent_rows.append({
                    "Slide": idx,
                    "Reagent": slide["primary_name"],
                    "Type": "Primary",
                    "Total Volume (µL)": round(vol, 2),
                    "Stock Volume (µL)": round(stock_vol, 2),
                    "Warning": check_warn(vol)
                })
                seq_list.append(f"Primary({slide['primary_name']})")
            else:
                # negative ctrl => skip primary
                seq_list.append("Primary(skipped - Neg Ctrl)")

            # 4) Polymer
            # For simplicity, let's assume polymer has no separate dilution => use 1.0
            vol = calc_total_volume(dispense_volume, dead_volume, slide["double_polymer"])
            reagent_rows.append({
                "Slide": idx,
                "Reagent": f"Polymer-{slide['polymer_choice']}",
                "Type": "Polymer",
                "Total Volume (µL)": round(vol, 2),
                "Stock Volume (µL)": round(vol, 2),
                "Warning": check_warn(vol)
            })
            seq_list.append(f"Polymer({slide['polymer_choice']})")

            # 5) Opal
            vol_opal = calc_total_volume(dispense_volume, dead_volume, slide["double_opal"])
            stock_vol_opal = vol_opal / slide["opal_dil"]
            reagent_rows.append({
                "Slide": idx,
                "Reagent": f"Opal-{slide['opal_choice']}",
                "Type": "Opal",
                "Total Volume (µL)": round(vol_opal, 2),
                "Stock Volume (µL)": round(stock_vol_opal, 2),
                "Warning": check_warn(vol_opal)
            })
            seq_list.append(f"Opal({slide['opal_choice']})")

            # 6) TSA-DIG
            if slide["tsa_dig_used"]:
                vol_tsa = calc_total_volume(dispense_volume, dead_volume, slide["tsa_dig_double"])
                stock_vol_tsa = vol_tsa / slide["tsa_dig_dil"]
                reagent_rows.append({
                    "Slide": idx,
                    "Reagent": "TSA-DIG",
                    "Type": "TSA-DIG",
                    "Total Volume (µL)": round(vol_tsa, 2),
                    "Stock Volume (µL)": round(stock_vol_tsa, 2),
                    "Warning": check_warn(vol_tsa)
                })
                seq_list.append("TSA-DIG")

            # 7) DAPI (always for single-plex)
            vol_dapi = calc_total_volume(dispense_volume, dead_volume, double_disp=False)
            # If DAPI can be diluted, you can add a separate input.
            # For now, let's assume no separate dilution => 1.0
            reagent_rows.append({
                "Slide": idx,
                "Reagent": "DAPI",
                "Type": "DAPI",
                "Total Volume (µL)": round(vol_dapi, 2),
                "Stock Volume (µL)": round(vol_dapi, 2),
                "Warning": check_warn(vol_dapi)
            })
            seq_list.append("DAPI")

            # Save the full sequence for Slide #n
            slide_sequences.append({
                "Slide": idx,
                "Sequence": " → ".join(seq_list)
            })

        # ---------------------------------------------------------------------
        # A) Reagent Table
        # ---------------------------------------------------------------------
        st.subheader("Reagent Table (Per Slide)")
        # Check how many total rows => pot limit
        if len(reagent_rows) > 29:
            st.error(f"WARNING: {len(reagent_rows)} total items, exceeds the 29-pot limit.")
        st.table(reagent_rows)

        # ---------------------------------------------------------------------
        # B) Slide Summary Table
        # ---------------------------------------------------------------------
        st.subheader("Slide Summary")
        st.table(slide_sequences)


def main():
    single_plex_app()


if __name__ == "__main__":
    main()

