import streamlit as st

def get_diluent(reagent_type):
    """
    Return the appropriate diluent based on reagent type.
    Adjust as needed for your lab’s usage.
    """
    rt = reagent_type.lower()
    if rt == "primary":
        return "bondwash/blocker"
    elif rt == "opal":
        return "amplifier"
    elif rt == "polymer":
        return ""
    elif rt == "dapi":
        return "bondwash/blocker"
    elif rt == "tsa-dig":
        return "amplifier"  # or whatever you prefer
    else:
        # "others"
        return "bondwash/blocker"

def calc_total_volume(dispense_vol, dead_vol, double_dispense):
    """
    total_volume = dead_vol + (dispense_vol * (2 if double_dispense else 1))
    """
    multiplier = 2 if double_dispense else 1
    return dead_vol + (dispense_vol * multiplier)

def single_plex_app():
    st.title("Single-Plex Workflow")

    # ---------------------------------------------------------
    # Global machine settings
    # ---------------------------------------------------------
    st.subheader("Global Settings")
    dispense_volume = st.number_input(
        "Dispense Volume (µL)",
        min_value=1, max_value=10000,
        value=150,
        help="Default 150 µL (Bond machine setup)."
    )
    dead_volume = st.number_input(
        "Dead Volume (µL)",
        min_value=0, max_value=2000,
        value=150,
        help="Extra volume to account for dead space, etc."
    )
    st.write("---")

    # We store final reagent rows in session_state
    if "sp_reagents" not in st.session_state:
        # Each row = dict(
        #   Reagent,
        #   Type,
        #   DilutionFactor,
        #   DoubleDispense,
        #   Diluent,
        #   TotalVolume,
        #   StockVolume,
        # )
        st.session_state["sp_reagents"] = []

    # A helper to create and add a row to session_state
    def add_reagent_row(name, rtype, dilution_factor, double_disp, disp_vol, dead_vol):
        """
        Create a row dictionary and append to sp_reagents.
        total_volume = calc_total_volume(...)
        stock_volume = total_volume / (dilution_factor or 1.0)
        """
        total_vol = calc_total_volume(disp_vol, dead_vol, double_disp)
        # Avoid divide-by-zero if user puts 0 for dilution
        df = dilution_factor if dilution_factor else 1.0
        stock_vol = total_vol / df

        row = {
            "Reagent": name,
            "Type": rtype,
            "Dilution Factor": dilution_factor if dilution_factor else "-",
            "Double?": "Yes" if double_disp else "No",
            "Diluent": get_diluent(rtype),
            "Total Volume (µL)": round(total_vol, 2),
            "Stock Volume (µL)": round(stock_vol, 4),
        }
        st.session_state["sp_reagents"].append(row)

    # ---------------------------------------------------------
    # Form to add a reagent
    # ---------------------------------------------------------
    st.subheader("Add a Reagent")
    with st.form("add_reagent_form", clear_on_submit=True):
        # Let user pick the type from set: Primary, Opal, DAPI, Others
        reagent_type = st.selectbox(
            "Reagent Type",
            ["Primary", "Opal", "DAPI", "Others"]
        )

        reagent_name = st.text_input("Reagent Name (e.g. 'PDGFRB', 'Opal 540', etc.)")

        # Common inputs
        dilution_factor = st.number_input(
            "Dilution Factor",
            min_value=1.0, value=1000.0,
            help="Used to compute stock volume = total_volume / dilution_factor."
        )
        double_dispense = st.checkbox("Double Dispense?")

        polymer_name = None
        add_tsa_dig = False
        tsa_dig_dilution = 1000.0
        tsa_dig_double = False

        # If primary, ask user for polymer name
        if reagent_type == "Primary":
            polymer_name = st.text_input(
                "Polymer Name for this primary",
                "Polymer-Rabbit"  # example default
            )

        # If opal, let user see if it's 780 -> show TSA-DIG prompt
        if reagent_type == "Opal":
            # If user specifically typed "Opal 780" in the reagent_name,
            # or you could parse the string. If you prefer a selectbox for opal,
            # do that instead. Example:
            # opal_options = ["Opal 480","Opal 520","Opal 540","Opal 570",
            #                 "Opal 620","Opal 650","Opal 690","Opal 780","others"]
            # selected_opal = st.selectbox("Pick Opal", opal_options)
            # ...
            # But for now, we check if user typed "780" in the name:
            if "780" in reagent_name:
                st.markdown("**Opal 780 detected**. Add TSA-DIG?")
                add_tsa_dig = st.checkbox("Add TSA-DIG for this Opal 780?")
                if add_tsa_dig:
                    tsa_dig_dilution = st.number_input(
                        "TSA-DIG Dilution Factor",
                        min_value=1.0, value=1000.0
                    )
                    tsa_dig_double = st.checkbox("Double Dispense TSA-DIG?")

        submitted = st.form_submit_button("Add to Table")

    # ---------------------------------------------------------
    # Handle "Add Reagent" submission
    # ---------------------------------------------------------
    if submitted:
        if not reagent_name:
            st.warning("Please provide a reagent name.")
        else:
            # 1) If "Primary", add two rows: (Primary) + (Polymer)
            if reagent_type == "Primary":
                # row for the primary
                add_reagent_row(
                    name=reagent_name,
                    rtype="Primary",
                    dilution_factor=dilution_factor,
                    double_disp=double_dispense,
                    disp_vol=dispense_volume,
                    dead_vol=dead_volume
                )
                # row for the polymer
                # (We might not have a "dilution factor" or "double" for polymer, so use default.)
                # You can adapt if polymer also sometimes needs dilution, etc.
                if polymer_name:
                    add_reagent_row(
                        name=polymer_name,
                        rtype="Polymer",
                        dilution_factor=1.0,  # no dilution
                        double_disp=False,
                        disp_vol=dispense_volume,
                        dead_vol=dead_volume
                    )
                st.success(f"Added Primary + Polymer for {reagent_name}.")

            # 2) If "Opal"
            elif reagent_type == "Opal":
                add_reagent_row(
                    name=reagent_name,
                    rtype="Opal",
                    dilution_factor=dilution_factor,
                    double_disp=double_dispense,
                    disp_vol=dispense_volume,
                    dead_vol=dead_volume
                )
                # If user wants TSA-DIG (only if "780" is in name, per your logic)
                if add_tsa_dig:
                    add_reagent_row(
                        name="TSA-DIG",
                        rtype="TSA-DIG",
                        dilution_factor=tsa_dig_dilution,
                        double_disp=tsa_dig_double,
                        disp_vol=dispense_volume,
                        dead_vol=dead_volume
                    )
                st.success(f"Added Opal reagent: {reagent_name}")

            # 3) If "DAPI"
            elif reagent_type == "DAPI":
                add_reagent_row(
                    name=reagent_name,
                    rtype="DAPI",
                    dilution_factor=dilution_factor,
                    double_disp=double_dispense,
                    disp_vol=dispense_volume,
                    dead_vol=dead_volume
                )
                st.success(f"Added DAPI reagent: {reagent_name}")

            # 4) If "Others"
            else:
                add_reagent_row(
                    name=reagent_name,
                    rtype="Others",
                    dilution_factor=dilution_factor,
                    double_disp=double_dispense,
                    disp_vol=dispense_volume,
                    dead_vol=dead_volume
                )
                st.success(f"Added Other reagent: {reagent_name}")

    st.write("---")

    # ---------------------------------------------------------
    # Display the Reagent Table
    # ---------------------------------------------------------
    st.subheader("Reagent Table")
    if st.session_state["sp_reagents"]:
        # Warn if total reagents > 29
        total_pots = len(st.session_state["sp_reagents"])
        if total_pots > 29:
            st.error(f"WARNING: You have {total_pots} reagents, exceeding the 29-pot limit!")

        # Build a display with warnings for volumes
        display_rows = []
        for row in st.session_state["sp_reagents"]:
            vol = row["Total Volume (µL)"]
            warn_msg = ""
            if vol > 6000:
                warn_msg = "EXCEEDS 6000 µL limit!"
            elif vol > 5000:
                warn_msg = "Consider splitting!"

            display_rows.append({
                "Reagent": row["Reagent"],
                "Type": row["Type"],
                "Dilution": row["Dilution Factor"],
                "Double?": row["Double?"],
                "Diluent": row["Diluent"],
                "Total Volume (µL)": vol,
                "Stock Volume (µL)": row["Stock Volume (µL)"],
                "Warning": warn_msg
            })

        st.table(display_rows)

        # Optional: Button to clear everything
        if st.button("Clear All"):
            st.session_state["sp_reagents"].clear()
            st.experimental_rerun()
    else:
        st.write("No reagents added yet.")

def main():
    single_plex_app()

if __name__ == "__main__":
    main()

