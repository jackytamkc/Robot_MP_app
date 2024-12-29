import streamlit as st

def single_plex_app():
    """
    Single-Plex workflow:
      1) Ask user for global Dispense Volume and Dead Volume.
      2) Each time the user adds a Primary, automatically add 3 (or 4) rows:
         - Primary
         - Polymer
         - Opal
         - TSA-DIG (only if Opal 780 is chosen)
      3) Compute total volume for each row.
      4) Highlight/warn if total volume > 5000 µL (suggest splitting).
      5) Enforce a 6000 µL max (or optionally block usage).
      6) Warn if total reagents exceed 29 pots.
    """
    st.header("Single-Plex Workflow")

    # -----------------------------
    # Step 1: Global Setup
    # -----------------------------
    st.subheader("Global Settings")
    dispense_volume = st.number_input(
        "Dispense Volume (µL) per slide or reaction",
        min_value=1, max_value=10000,
        value=150,
        help="Default is 150 µL based on Bond machine setup."
    )

    dead_volume = st.number_input(
        "Dead Volume (µL)",
        min_value=0, max_value=1000,
        value=150,
        help="Extra volume to account for dead space, tips, etc."
    )

    st.write("---")

    # -----------------------------
    # Keep a list of all reagents (rows) we generate
    # -----------------------------
    if "sp_reagents" not in st.session_state:
        # Each item will be a dict:
        # {
        #   "Reagent": str,
        #   "Type": str,  # "Primary", "Polymer", "Opal", or "TSA-DIG"
        #   "Dilution": (float or None),
        #   "DoubleDispense": bool,
        #   "TotalVolume": float,
        # }
        st.session_state["sp_reagents"] = []

    # A helper function to calculate volumes
    def calculate_volume(reagent_type, dilution_factor, double_dispense, dispense_vol, dead_vol):
        """
        Returns the total volume needed for one reagent row.
        Basic rules for single-plex example:
          - Primary/Opal: totalVolume = deadVol + (dispenseVol / dilutionFactor)
              *2 if double-dispense is True
          - Polymer: totalVolume = deadVol + dispenseVol (no dilution)
          - TSA-DIG: same as 'Others'? (Here we treat it as an 'Opal-like' approach or no dilution?
            We'll do the simpler approach: totalVolume = deadVol + dispenseVol.)
        Adjust these rules to match your real protocol.
        """
        # Decide logic:
        if reagent_type == "Primary" or reagent_type == "Opal":
            base = dispense_vol / dilution_factor if dilution_factor else 0
            if double_dispense:
                base *= 2
            total = dead_vol + base
        elif reagent_type == "Polymer":
            total = dead_vol + dispense_vol
        elif reagent_type == "TSA-DIG":
            # For example, treat it similarly to polymer (no dilution):
            total = dead_vol + dispense_vol
        else:
            # fallback
            total = dead_vol + dispense_vol
        return total

    # -----------------------------
    # Step 2: Add a Primary Reagent
    # -----------------------------
    st.subheader("Add a Primary Reagent")
    with st.form("add_primary_form", clear_on_submit=True):
        primary_name = st.text_input("Primary Name")
        # For single-plex, we ask for a "dilution factor" for both the Primary and the Opal.
        primary_dilution = st.number_input(
            "Primary Dilution Factor",
            min_value=1.0, value=1000.0,
            help="E.g., 1000 => 150 / 1000 = 0.15µL if dispense is 150µL."
        )
        double_dispense_primary = st.checkbox("Double Dispense for Primary?")

        # OPAL choice
        opal_options = ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
        selected_opal = st.selectbox("Opal Choice", opal_options)
        opal_dilution = st.number_input(
            "Opal Dilution Factor",
            min_value=1.0, value=1000.0,
            help="E.g., 1000 => 150 / 1000 = 0.15µL if dispense is 150µL."
        )
        double_dispense_opal = st.checkbox("Double Dispense for Opal?")

        submitted = st.form_submit_button("Add to List")

    if submitted:
        if not primary_name:
            st.warning("Please enter a primary name.")
        else:
            # 1) Add the Primary row
            primary_volume = calculate_volume(
                reagent_type="Primary",
                dilution_factor=primary_dilution,
                double_dispense=double_dispense_primary,
                dispense_vol=dispense_volume,
                dead_vol=dead_volume
            )
            st.session_state["sp_reagents"].append({
                "Reagent": primary_name,
                "Type": "Primary",
                "Dilution": primary_dilution,
                "DoubleDispense": double_dispense_primary,
                "TotalVolume": round(primary_volume, 2),
            })

            # 2) Add the Polymer row
            polymer_volume = calculate_volume(
                reagent_type="Polymer",
                dilution_factor=None,
                double_dispense=False,  # Typically no double dispense
                dispense_vol=dispense_volume,
                dead_vol=dead_volume
            )
            polymer_name = f"Polymer for {primary_name}"
            st.session_state["sp_reagents"].append({
                "Reagent": polymer_name,
                "Type": "Polymer",
                "Dilution": None,
                "DoubleDispense": False,
                "TotalVolume": round(polymer_volume, 2),
            })

            # 3) Add the Opal row
            opal_name = f"Opal {selected_opal} for {primary_name}"
            opal_volume = calculate_volume(
                reagent_type="Opal",
                dilution_factor=opal_dilution,
                double_dispense=double_dispense_opal,
                dispense_vol=dispense_volume,
                dead_vol=dead_volume
            )
            st.session_state["sp_reagents"].append({
                "Reagent": opal_name,
                "Type": "Opal",
                "Dilution": opal_dilution,
                "DoubleDispense": double_dispense_opal,
                "TotalVolume": round(opal_volume, 2),
            })

            # 4) If opal == 780, add TSA-DIG
            if selected_opal == "780":
                tsa_name = f"TSA-DIG for {primary_name}"
                tsa_volume = calculate_volume(
                    reagent_type="TSA-DIG",
                    dilution_factor=None,
                    double_dispense=False,
                    dispense_vol=dispense_volume,
                    dead_vol=dead_volume
                )
                st.session_state["sp_reagents"].append({
                    "Reagent": tsa_name,
                    "Type": "TSA-DIG",
                    "Dilution": None,
                    "DoubleDispense": False,
                    "TotalVolume": round(tsa_volume, 2),
                })

            st.success(f"Added Primary set: {primary_name}")

    st.write("---")

    # -----------------------------
    # Step 3: Show the result table
    # -----------------------------
    st.subheader("Reagent Table")

    if st.session_state["sp_reagents"]:
        # Check how many total reagents we have
        total_rows = len(st.session_state["sp_reagents"])

        # If total_rows > 29 => warn user we exceed machine capacity
        if total_rows > 29:
            st.error(
                f"**WARNING:** You have {total_rows} reagents (rows), "
                "which exceeds the 29-pot limit of this machine!"
            )

        # Build a display table
        display_rows = []
        for i, r in enumerate(st.session_state["sp_reagents"]):
            row = {
                "Reagent": r["Reagent"],
                "Type": r["Type"],
                "Dilution Factor": r["Dilution"] if r["Dilution"] else "-",
                "Double?": "Yes" if r["DoubleDispense"] else "No",
                "Total Volume (µL)": r["TotalVolume"],
                "Stock Volume": f"{r['TotalVolume']} µL",  # Example to show same # or something else
            }

            # If totalVolume > 5000 => highlight or print a note
            if r["TotalVolume"] > 5000:
                row["Warning"] = "Consider splitting!"
            else:
                row["Warning"] = ""

            # If totalVolume > 6000 => you might decide to block or note:
            # (You could do row["Warning"] = "EXCEEDS 6000 µL, not possible" or so.)
            if r["TotalVolume"] > 6000:
                row["Warning"] = "EXCEEDS 6000 µL limit!"

            display_rows.append(row)

        st.table(display_rows)

        # Optional: Add a button to clear all reagents
        if st.button("Clear All Reagents"):
            st.session_state["sp_reagents"].clear()
            st.experimental_rerun()
    else:
        st.write("No reagents added yet.")


def main():
    st.title("Single-Plex Example App")

    single_plex_app()


if __name__ == "__main__":
    main()
