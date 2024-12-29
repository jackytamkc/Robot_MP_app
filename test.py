import streamlit as st
from collections import defaultdict


###############################################################################
# Utility & Calculation
###############################################################################

def calc_total_volume(disp_vol_list, dead_vol):
    """
    Summation approach:
      total_volume = dead_vol + sum(disp_vol_list)
    where disp_vol_list are the 'per-usage' volumes
    (each usage might be 150µL or 300µL if double_disp, etc.).
    """
    return dead_vol + sum(disp_vol_list)


def check_warnings(volume):
    """
    Return a string if volume > 5000 or > 6000
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    return ""


###############################################################################
# The main Single-Plex app
###############################################################################

def single_plex_app():
    st.title("Single-Plex with Unification & Deletable Items")

    # -------------------------------------------------------------------------
    # 1) Global machine settings
    # -------------------------------------------------------------------------
    st.header("Global Settings")
    dispense_volume = st.number_input(
        "Dispense Volume (µL)",
        min_value=1, max_value=10000,
        value=150,
        help="Base volume used for each usage."
    )
    dead_volume = st.number_input(
        "Dead Volume (µL)",
        min_value=0, max_value=2000,
        value=150,
        help="One-time overhead for each distinct reagent group."
    )
    st.write("---")

    # We'll store "usage_list" in session_state. Each entry describes ONE usage
    # (e.g., one primary usage, one polymer usage, one DAPI usage, etc.).
    # Later, we unify by (name, type, dilution).
    if "usage_list" not in st.session_state:
        st.session_state["usage_list"] = []

    # Helper to add an item to usage_list
    def add_usage_item(name, rtype, dil_factor, double_flag):
        item = {
            "reagent_name": name,
            "reagent_type": rtype,
            "dilution_factor": dil_factor,
            "double_disp": double_flag,
        }
        st.session_state["usage_list"].append(item)

    # -------------------------------------------------------------------------
    # 2) FORMS to add items
    # -------------------------------------------------------------------------
    st.header("Add Items")

    # ------------------------- A) PRIMARY form -------------------------
    st.subheader("Add Primary (includes Polymer & Opal)")

    # We'll do a dynamic approach: if user picks Opal 780, show TSA-DIG fields
    # We'll do this via a form so changes reflect after submission.
    with st.form("add_primary_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            primary_name = st.text_input("Primary Name", "")
            primary_dil = st.number_input("Primary Dilution Factor", min_value=1.0, value=1000.0)
            primary_double = st.checkbox("Double Dispense (Primary)?", value=False)

        with col2:
            # Polymer Choice
            polymer_options = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
            polymer_choice = st.selectbox("Polymer Type", polymer_options)
            polymer_double = st.checkbox("Double Dispense (Polymer)?", value=False)

        # Now pick Opal
        opal_options = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
        opal_choice = st.selectbox("Opal Choice", opal_options)
        opal_dil = st.number_input("Opal Dilution Factor", min_value=1.0, value=1000.0)
        opal_double = st.checkbox("Double Dispense (Opal)?", value=False)

        # If user picks opal=780, immediately show TSA-DIG fields
        tsa_used = False
        tsa_dil = 1000.0
        tsa_double = False
        if opal_choice == "780":
            tsa_used = st.checkbox("Add TSA-DIG?")
            if tsa_used:
                tsa_dil = st.number_input("TSA-DIG Dilution Factor", min_value=1.0, value=1000.0)
                tsa_double = st.checkbox("Double Dispense (TSA-DIG)?", value=False)

        submitted_primary = st.form_submit_button("Add Primary Set")

    if submitted_primary:
        if not primary_name:
            st.warning("Please enter a primary name!")
        else:
            # Add the primary itself
            add_usage_item(primary_name, "Primary", primary_dil, primary_double)
            # Add the polymer usage
            polymer_name = f"Polymer-{polymer_choice}"
            add_usage_item(polymer_name, "Polymer", 1.0, polymer_double)
            # Add the opal usage
            opal_name = f"Opal-{opal_choice}"
            add_usage_item(opal_name, "Opal", opal_dil, opal_double)
            # Possibly add TSA-DIG
            if tsa_used:
                add_usage_item("TSA-DIG", "TSA-DIG", tsa_dil, tsa_double)

            st.success(f"Added primary set for: {primary_name}")

    # ------------------------- B) DAPI form -------------------------
    st.subheader("Add DAPI")

    with st.form("add_dapi_form", clear_on_submit=True):
        dapi_name = st.text_input("DAPI Name", "Spectral DAPI")
        dapi_dil = st.number_input("DAPI Dilution Factor", min_value=1.0, value=1000.0)
        dapi_double = st.checkbox("Double Dispense (DAPI)?", value=False)
        submitted_dapi = st.form_submit_button("Add DAPI")

    if submitted_dapi:
        if not dapi_name:
            st.warning("Please enter a DAPI name!")
        else:
            add_usage_item(dapi_name, "DAPI", dapi_dil, dapi_double)
            st.success(f"Added DAPI: {dapi_name}")

    # ------------------------- C) OTHERS form -------------------------
    st.subheader("Add Other Reagent")

    with st.form("add_others_form", clear_on_submit=True):
        other_name = st.text_input("Reagent Name", "")
        other_dil = st.number_input("Dilution Factor (Others)", min_value=1.0, value=1000.0)
        other_double = st.checkbox("Double Dispense (Others)?", value=False)
        submitted_other = st.form_submit_button("Add Others")

    if submitted_other:
        if not other_name:
            st.warning("Please enter a reagent name!")
        else:
            add_usage_item(other_name, "Others", other_dil, other_double)
            st.success(f"Added Others reagent: {other_name}")

    st.write("---")

    # -------------------------------------------------------------------------
    # 3) Show the usage list with Remove buttons
    # -------------------------------------------------------------------------
    st.header("Current Usage List")
    usage_list = st.session_state["usage_list"]
    if usage_list:
        # Display each usage as a row with a "Remove" button
        for idx, usage in enumerate(usage_list):
            colA, colB = st.columns([4, 1])
            with colA:
                st.write(
                    f"**Name**: {usage['reagent_name']} | "
                    f"**Type**: {usage['reagent_type']} | "
                    f"**Dil**: {usage['dilution_factor']} | "
                    f"**Double?**: {usage['double_disp']}"
                )
            with colB:
                if st.button(f"Remove {idx}", key=f"remove_{idx}"):
                    st.session_state["usage_list"].pop(idx)
                    st.experimental_rerun()
    else:
        st.write("No items in the list yet.")

    st.write("---")

    # -------------------------------------------------------------------------
    # 4) Generate Final Table (Unify by (name, type, dilution))
    # -------------------------------------------------------------------------
    if st.button("Generate Final Table"):
        if not usage_list:
            st.warning("No usage items to calculate!")
        else:
            # We'll unify items by (reagent_name, reagent_type, dilution_factor).
            # We gather all usage to sum up the 'dispense portion'.
            # Then we add 1 dead volume to that sum to get total volume.

            # Step A: Build a map of (name, type, dil) -> list_of_dispense_multipliers
            # where each usage => (dispenseVolume * (2 if double else 1))
            group_map = defaultdict(list)  # key = (name, type, dil), value = list of 'portion volumes'

            for usage in usage_list:
                key = (usage["reagent_name"], usage["reagent_type"], usage["dilution_factor"])
                # one usage portion = baseDisp * (2 if double else 1)
                portion = dispense_volume * (2 if usage["double_disp"] else 1)
                group_map[key].append(portion)

            # Step B: For each group, sum the portion list, add dead volume,
            # compute stock volume = totalVol / dil.
            final_rows = []
            for (name, rtype, dil), portions in group_map.items():
                sum_portions = sum(portions)
                total_vol = calc_total_volume(disp_vol_list=portions, dead_vol=dead_volume)
                stock_vol = total_vol / dil  # Assuming user keeps consistent dil.

                row = {
                    "Reagent": name,
                    "Type": rtype,
                    "Dilution Factor": dil,
                    "Total Volume (µL)": round(total_vol, 2),
                    "Stock Volume (µL)": round(stock_vol, 2),
                    "Warning": check_warnings(total_vol)
                }
                final_rows.append(row)

            # Step C: Check pot limit (simply the number of final rows)
            pot_count = len(final_rows)
            if pot_count > 29:
                st.error(f"WARNING: You have {pot_count} total reagents, exceeding 29-pot limit!")

            # Display final table
            st.write("### Final Reagent Table")
            st.table(final_rows)


###############################################################################
# Main entry point
###############################################################################
def main():
    single_plex_app()


if __name__ == "__main__":
    main()

