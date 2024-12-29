import streamlit as st
from collections import defaultdict


###############################################################################
# Utility for volumes
###############################################################################

def calc_dispense_portion(dispense_vol: float, double_disp: bool) -> float:
    """Return the portion for a single usage: (dispense_vol * 2 if double_disp else 1)."""
    return dispense_vol * (2 if double_disp else 1)


def check_volume_warning(volume: float) -> str:
    """Return a warning string if volume >5000 or >6000."""
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    return ""

def format_number(num: float) -> str:
    """
    Return a human-friendly string:
      - If num is an integer, show it with no decimals.
      - Otherwise, show up to 4 decimal places (or fewer if possible).
    """
    if float(num).is_integer():
        return str(int(num))
    else:
        # Attempt to show minimal decimals up to 4 places
        return f"{num:.4g}"  # or you could do something else, e.g. f"{num:.4f}"

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

    # We'll store a list of slides in session_state["slides"].
    # Each element is a dict describing the chosen items for that slide.
    if "slides" not in st.session_state:
        st.session_state["slides"] = []

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

    tsa_dig_used = False
    tsa_dig_dil = 1000.0
    tsa_dig_double = False
    if st.session_state.get("opal_choice") == "780":
        st.markdown("**Opal 780 selected. Configure TSA-DIG?**")
        tsa_dig_used = st.checkbox("Use TSA-DIG?")
        if tsa_dig_used:
            tsa_dig_dil = st.number_input("TSA-DIG Dilution Factor", min_value=1.0, value=1000.0)
            tsa_dig_double = st.checkbox("Double Dispense (TSA-DIG)?", value=False)

    # E) DAPI
    use_dapi = st.checkbox("Use DAPI?", value=True)
    dapi_dil = 100
    dapi_double = False
    if use_dapi:
        dapi_dil = st.number_input("DAPI Dilution Factor", min_value=1.0, value=1000.0)
        dapi_double = st.checkbox("Double Dispense (DAPI)?", value=True)

    # F) Custom Reagent
    use_custom = st.checkbox("Use Custom Reagent?", value=False)
    custom_name = ""
    custom_dil = 1.0
    custom_double = False
    custom_diluent = ""
    if use_custom:
        custom_name = st.text_input("Custom Reagent Name", "")
        custom_dil = st.number_input("Custom Dilution Factor", min_value=1.0, value=1000.0)
        custom_double = st.checkbox("Double Dispense (Custom)?", value=False)
        custom_diluent = st.text_input("Custom Reagent Diluent", "bondwash/blocker")

    if st.button("Add Slide"):
        # Validate primary name unless negative ctrl
        if not negative_ctrl and not primary_name.strip():
            st.warning("Please enter a primary name if not a negative control!")
        elif use_custom and not custom_name.strip():
            st.warning("Please enter a name for the custom reagent or uncheck 'Use Custom Reagent?'")
        else:
            # Save one "slide" entry
            slide_info = {
                "h2o2": h2o2,
                "pb": pb,
                "negative_ctrl": negative_ctrl,

                "primary_name": primary_name.strip(),
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

                "use_dapi": use_dapi,
                "dapi_dil": dapi_dil,
                "double_dapi": dapi_double,

                "use_custom": use_custom,
                "custom_name": custom_name.strip(),
                "custom_dil": custom_dil,
                "custom_double": custom_double,
                "custom_diluent": custom_diluent.strip(),
            }
            st.session_state["slides"].append(slide_info)
            st.success("Slide added.")

    # -------------------------------------------------------------------------
    # 3) Show Current Slides with Remove Buttons
    # -------------------------------------------------------------------------
    st.header("Current Slides")
    if st.session_state["slides"]:
        for idx, slide in enumerate(st.session_state["slides"]):
            colA, colB = st.columns([4,1])
            with colA:
                desc = f"Slide #{idx+1} "
                if slide["negative_ctrl"]:
                    desc += "[NEG CTRL] "
                desc += f"| Primary: {slide['primary_name']} | Polymer: {slide['polymer_choice']} | Opal: {slide['opal_choice']}"
                if slide["tsa_dig_used"]:
                    desc += " + TSA-DIG"
                if slide["use_dapi"]:
                    desc += " + DAPI"
                if slide["use_custom"]:
                    desc += f" + Custom({slide['custom_name']})"
                st.write(desc)
            with colB:
                if st.button(f"Remove Slide {idx+1}", key=f"remove_slide_{idx}"):
                    st.session_state["slides"].pop(idx)
                    st.experimental_rerun()
    else:
        st.write("No slides added yet.")

    st.write("---")

    # -------------------------------------------------------------------------
    # 4) Generate Final Tables (Reagent Table + Slide Summary)
    # -------------------------------------------------------------------------
    if st.button("Generate Final Tables"):
        slides = st.session_state["slides"]
        if not slides:
            st.warning("No slides to generate!")
            return

        # We unify usage in a map:
        # key = (reagent_name, reagent_type, dil_factor, double_disp, diluent)
        # value = list_of_dispense_portions
        usage_map = defaultdict(list)

        # We'll create a "slide summary" as well
        slide_summaries = []

        for i, slide in enumerate(slides, start=1):
            seq = []

            # H2O2
            if slide["h2o2"]:
                # type = "H2O2", dil=1.0, double=False, diluent=""
                usage_map[("H2O2", "H2O2", 1.0, False, "")].append(
                    calc_dispense_portion(dispense_volume, False)
                )
                seq.append("H2O2")

            # PB
            if slide["pb"]:
                usage_map[("Protein Block (PB)", "PB", 1.0, False, "")].append(
                    calc_dispense_portion(dispense_volume, False)
                )
                seq.append("PB")

            # Primary
            if not slide["negative_ctrl"]:
                # name, type="Primary", dil=slide["primary_dil"], double=slide["double_primary"], diluent=""
                p_name = slide["primary_name"] or "(Unnamed Primary)"
                usage_map[(p_name, "Primary", slide["primary_dil"], slide["double_primary"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["double_primary"])
                )
                seq.append(f"Primary({p_name})")
            else:
                seq.append("Primary(skipped - NegCtrl)")

            # Polymer
            polymer_name = f"Polymer-{slide['polymer_choice']}"
            # type="Polymer", dil=1.0, double=slide["double_polymer"], diluent=""
            usage_map[(polymer_name, "Polymer", 1.0, slide["double_polymer"], "")].append(
                calc_dispense_portion(dispense_volume, slide["double_polymer"])
            )
            seq.append(polymer_name)

            # Opal
            opal_name = f"Opal-{slide['opal_choice']}"
            usage_map[(opal_name, "Opal", slide["opal_dil"], slide["double_opal"], "")].append(
                calc_dispense_portion(dispense_volume, slide["double_opal"])
            )
            seq.append(opal_name)

            # TSA-DIG
            if slide["tsa_dig_used"]:
                usage_map[("TSA-DIG", "TSA-DIG", slide["tsa_dig_dil"], slide["tsa_dig_double"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["tsa_dig_double"])
                )
                seq.append("TSA-DIG")

            # DAPI
            if slide["use_dapi"]:
                usage_map[("DAPI", "DAPI", slide["dapi_dil"], slide["double_dapi"], "")].append(
                    calc_dispense_portion(dispense_volume, slide["double_dapi"])
                )
                seq.append("DAPI")

            # Custom Reagent
            if slide["use_custom"]:
                # unify by user-provided name, type="Custom", dil=..., double=..., diluent=...
                c_name = slide["custom_name"]
                c_dil = slide["custom_dil"]
                c_double = slide["custom_double"]
                c_diluent = slide["custom_diluent"]
                usage_map[(c_name, "Custom", c_dil, c_double, c_diluent)].append(
                    calc_dispense_portion(dispense_volume, c_double)
                )
                seq.append(f"Custom({c_name})")

            # Save the sequence
            slide_summaries.append({
                "Slide": i,
                "Sequence": " → ".join(seq)
            })

        # A) Slide Summary
        st.subheader("Slide Summary")
        st.table(slide_summaries)

        # B) Unified Reagent Table
        st.subheader("Unified Reagent Table")
        final_rows = []
        for (name, rtype, dil, dbl, diluent), portions in usage_map.items():
            sum_portions = sum(portions)
            total_vol = dead_volume + sum_portions
            stock_vol = total_vol / dil  # e.g. if dil=1 => no dilution

            row = {
                "Reagent": name,
                "Type": rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?": "Yes" if dbl else "No",
                "Diluent": diluent,
                "Total Volume (µL)": format_number(total_vol),
                "Stock Volume (µL)": format_number(stock_vol),
                "Warning": check_volume_warning(total_vol)
            }
            final_rows.append(row)

        # Pot-limit check
        pot_count = len(final_rows)
        if pot_count > 29:
            st.error(f"WARNING: You have {pot_count} total pots, exceeding the 29-pot limit!")

        # Display final table
        st.table(final_rows)


def main():
    single_plex_app()


if __name__ == "__main__":
    main()

