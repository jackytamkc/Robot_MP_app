import streamlit as st

###############################################################################
# Utility functions
###############################################################################

def calc_total_volume(dispense_vol, dead_vol, num_usages, double_flags):
    """
    For a given reagent that is used multiple times (e.g., polymer used for N primaries),
    we unify usage:
      total_volume = dead_vol + sum_of_each_usage_dispense
    where each usage_dispense = dispense_vol * (2 if usage is double else 1).

    - dispense_vol: base volume for one usage
    - dead_vol: we apply it once
    - num_usages: how many times this reagent is used
    - double_flags: list of booleans indicating if double-dispense was checked for each usage
    """
    total_dispense_sum = 0
    for dbl in double_flags:
        total_dispense_sum += (dispense_vol * (2 if dbl else 1))

    total_volume = dead_vol + total_dispense_sum
    return total_volume

def calc_single_volume(dispense_vol, dead_vol, double_dispense):
    """
    For single usage (e.g. each primary, each opal usage, each TSA usage),
    total_volume = dead_vol + (dispense_vol * (2 if double_dispense else 1)).
    """
    factor = 2 if double_dispense else 1
    return dead_vol + (dispense_vol * factor)

def check_warnings(volume):
    """
    Returns a string if volume > 5000 or > 6000.
    """
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    elif volume > 5000:
        return "Consider splitting!"
    else:
        return ""

###############################################################################
# Main single-plex code
###############################################################################

def single_plex_app():
    st.title("Single-Plex Workflow (with Polymer Unification)")

    # -------------------------------------------------------------------------
    # Global machine settings
    # -------------------------------------------------------------------------
    st.subheader("Global Settings")
    dispense_volume = st.number_input(
        "Dispense Volume (µL)",
        min_value=1, max_value=10000,
        value=150,
        help="Base volume used for each reagent usage."
    )
    dead_volume = st.number_input(
        "Dead Volume (µL)",
        min_value=0, max_value=2000,
        value=150,
        help="Applied once for each distinct reagent or polymer type."
    )
    st.write("---")

    # Keep track of each "primary usage" in session state
    # Each entry is a dict with keys:
    #   primary_name, primary_dil, primary_double
    #   polymer_type, polymer_double
    #   opal_choice, opal_dil, opal_double
    #   tsa_used, tsa_dil, tsa_double
    if "primary_entries" not in st.session_state:
        st.session_state["primary_entries"] = []

    # -------------------------------------------------------------------------
    # Form to add a new primary usage
    # -------------------------------------------------------------------------
    st.subheader("Add a Primary Usage")

    with st.form("add_primary_form", clear_on_submit=True):
        primary_name = st.text_input("Primary Name (e.g. 'PDGFRB')", "")
        primary_dil = st.number_input("Primary Dilution Factor", min_value=1.0, value=1000.0)
        primary_double = st.checkbox("Double Dispense for Primary?")

        # Polymer selection
        polymer_options = ["Rabbit", "Sheep", "Goat", "Mouse", "Rat", "Others"]
        polymer_choice = st.selectbox("Polymer Type", polymer_options)
        polymer_double = st.checkbox("Double Dispense for Polymer?")

        # Opal selection
        opal_options = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
        opal_choice = st.selectbox("Opal Choice", opal_options)
        opal_dil = st.number_input("Opal Dilution Factor", min_value=1.0, value=1000.0)
        opal_double = st.checkbox("Double Dispense for Opal?")

        # If opal == 780, user can optionally add TSA-DIG
        tsa_used = False
        tsa_dil = 1000.0
        tsa_double = False
        if opal_choice == "780":
            st.write("Opal 780 selected. Do you want to add TSA-DIG?")
            tsa_used = st.checkbox("Add TSA-DIG?")
            if tsa_used:
                tsa_dil = st.number_input("TSA-DIG Dilution Factor", min_value=1.0, value=1000.0)
                tsa_double = st.checkbox("Double Dispense for TSA-DIG?")

        submitted = st.form_submit_button("Add to List")

    if submitted:
        if not primary_name:
            st.warning("Please provide a primary name.")
        else:
            new_entry = {
                "primary_name": primary_name,
                "primary_dil": primary_dil,
                "primary_double": primary_double,
                "polymer_type": polymer_choice,
                "polymer_double": polymer_double,
                "opal_choice": opal_choice,
                "opal_dil": opal_dil,
                "opal_double": opal_double,
                "tsa_used": tsa_used,
                "tsa_dil": tsa_dil,
                "tsa_double": tsa_double,
            }
            st.session_state["primary_entries"].append(new_entry)
            st.success(f"Added primary usage: {primary_name}")

    # -------------------------------------------------------------------------
    # Show Current Entries
    # -------------------------------------------------------------------------
    if st.session_state["primary_entries"]:
        st.write("### Current Primary Usages")
        for i, usage in enumerate(st.session_state["primary_entries"]):
            st.markdown(
                f"**Primary #{i+1}**: {usage['primary_name']} | Polymer: {usage['polymer_type']} | "
                f"Opal: {usage['opal_choice']}{' + TSA-DIG' if usage['tsa_used'] else ''}"
            )
        st.write("---")

    # -------------------------------------------------------------------------
    # Button to Generate Final Table
    # -------------------------------------------------------------------------
    if st.button("Generate Final Table"):
        if not st.session_state["primary_entries"]:
            st.warning("No primary usages found!")
        else:
            # Build final output rows in separate lists, then combine:
            final_rows = []

            # 1) Primaries: one row per usage
            for usage in st.session_state["primary_entries"]:
                # total volume for primary (single usage)
                prim_vol = calc_single_volume(dispense_volume, dead_volume, usage["primary_double"])
                stock_vol = prim_vol / usage["primary_dil"]
                row = {
                    "Reagent": usage["primary_name"],
                    "Type": "Primary",
                    "Double?": "Yes" if usage["primary_double"] else "No",
                    "Dilution Factor": usage["primary_dil"],
                    "Total Volume (µL)": round(prim_vol, 2),
                    "Stock Volume (µL)": round(stock_vol, 2),
                    "Warning": check_warnings(prim_vol),
                }
                final_rows.append(row)

            # 2) Polymers: unify usage by polymer type
            #    We group all usage that used the same polymer, summing their dispense volumes
            #    but applying only one dead volume in total.
            from collections import defaultdict
            polymer_usage_map = defaultdict(list)
            # key = polymer_type (string), value = list of booleans for double-dispense

            for usage in st.session_state["primary_entries"]:
                ptype = usage["polymer_type"]
                polymer_usage_map[ptype].append(usage["polymer_double"])

            # Now build one row per polymer type
            for ptype, double_list in polymer_usage_map.items():
                # total polymer volume = dead_vol + sum( dispense_vol*(2 if double else 1 ) ) across all usage
                polymer_volume = calc_total_volume(
                    dispense_vol=dispense_volume,
                    dead_vol=dead_volume,
                    num_usages=len(double_list),
                    double_flags=double_list
                )
                # polymer is not diluted => stock volume = total volume
                row = {
                    "Reagent": f"Polymer-{ptype}",
                    "Type": "Polymer",
                    "Double?": f"{sum(double_list)}/{len(double_list)} used double"
                               if len(double_list) > 1 else ("Yes" if double_list[0] else "No"),
                    "Dilution Factor": 1.0,
                    "Total Volume (µL)": round(polymer_volume, 2),
                    "Stock Volume (µL)": round(polymer_volume, 2),  # no dilution
                    "Warning": check_warnings(polymer_volume),
                }
                final_rows.append(row)

            # 3) Opals: one row per usage (we do NOT unify opals here)
            for usage in st.session_state["primary_entries"]:
                opal_vol = calc_single_volume(
                    dispense_vol=dispense_volume,
                    dead_vol=dead_volume,
                    double_dispense=usage["opal_double"]
                )
                stock_vol = opal_vol / usage["opal_dil"]
                row = {
                    "Reagent": f"Opal {usage['opal_choice']}",
                    "Type": "Opal",
                    "Double?": "Yes" if usage["opal_double"] else "No",
                    "Dilution Factor": usage["opal_dil"],
                    "Total Volume (µL)": round(opal_vol, 2),
                    "Stock Volume (µL)": round(stock_vol, 2),
                    "Warning": check_warnings(opal_vol),
                }
                final_rows.append(row)

                # 4) TSA-DIG if used
                if usage["tsa_used"]:
                    tsa_vol = calc_single_volume(
                        dispense_vol=dispense_volume,
                        dead_vol=dead_volume,
                        double_dispense=usage["tsa_double"]
                    )
                    stock_vol_tsa = tsa_vol / usage["tsa_dil"]
                    row2 = {
                        "Reagent": "TSA-DIG",
                        "Type": "TSA-DIG",
                        "Double?": "Yes" if usage["tsa_double"] else "No",
                        "Dilution Factor": usage["tsa_dil"],
                        "Total Volume (µL)": round(tsa_vol, 2),
                        "Stock Volume (µL)": round(stock_vol_tsa, 2),
                        "Warning": check_warnings(tsa_vol),
                    }
                    final_rows.append(row2)

            # -----------------------------------------------------------------
            # Build a table, check pot limit
            # -----------------------------------------------------------------
            # The total pot count = number of rows in final_rows
            pot_count = len(final_rows)
            if pot_count > 29:
                st.error(f"WARNING: You have {pot_count} reagents (pots), exceeding the 29-pot limit!")

            st.write("### Final Reagent Table")
            st.table(final_rows)

            # Optionally store final_rows somewhere or allow CSV download, etc.


def main():
    single_plex_app()

if __name__ == "__main__":
    main()
