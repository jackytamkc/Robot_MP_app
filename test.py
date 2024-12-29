import streamlit as st


def compute_volume_needed(num_test_slides, num_neg_controls, reagent_info):
    """
    Returns the volume needed (in µL) for a single reagent
    based on the number of test slides and negative controls.
    """
    # EXAMPLE LOGIC — Adapt to your real protocol!
    if reagent_info["type"].lower() == "primary":
        # Negative controls do NOT get primary
        total_slides = num_test_slides
    else:
        total_slides = num_test_slides + num_neg_controls

    base_volume = total_slides * reagent_info["dilution"]

    # Example rule: Double dispensing if type is "opal" or "dapi"
    if reagent_info["type"].lower() in ["opal", "dapi"]:
        base_volume *= 2

    total_volume = base_volume + reagent_info["dead_volume"]
    return total_volume


def main():
    st.title("Robot Multiplex Preparation Calculator")

    # ---------------------------------------------------------
    # 1) Collect Reagents from User
    # ---------------------------------------------------------
    if "reagents" not in st.session_state:
        st.session_state["reagents"] = []

    st.subheader("Step 1: Add or Manage Reagents")

    with st.form("add_reagent_form", clear_on_submit=True):
        reagent_name = st.text_input("Reagent Name", "")
        reagent_type = st.selectbox(
            "Reagent Type",
            ["Primary", "Opal", "DAPI", "Amplifier", "Secondary", "Polymer", "Others"]
        )
        initial_stock = st.number_input("Initial Stock (µL)", min_value=0, value=300)
        dilution = st.number_input("Dilution Factor", min_value=0.0, value=1.0, step=0.1)
        dead_volume = st.number_input("Dead Volume (µL)", min_value=0, value=150)
        submitted = st.form_submit_button("Add Reagent")

    if submitted:
        new_reagent = {
            "name": reagent_name,
            "type": reagent_type,
            "initial_stock": initial_stock,
            "dilution": dilution,
            "dead_volume": dead_volume
        }
        st.session_state["reagents"].append(new_reagent)
        st.success(f"Added reagent: {reagent_name}")

    if st.session_state["reagents"]:
        st.table(st.session_state["reagents"])
    else:
        st.write("No reagents added yet.")

    # ---------------------------------------------------------
    # 2) Ask user for Number of Plexes and Slides
    # ---------------------------------------------------------
    st.subheader("Step 2: Experimental Setup")
    num_plex = st.number_input("Number of Plex?", min_value=1, max_value=8, value=1)
    num_test_slides = st.number_input("Number of Test Slides?", min_value=0, value=8)
    num_neg_controls = st.number_input("Number of Negative Controls?", min_value=0, value=0)

    # ---------------------------------------------------------
    # 3) Assign Which Primary Antibodies Belong to Each Plex
    # ---------------------------------------------------------
    # We'll filter the list of "Primary" reagents from the session state:
    primary_names = [
        r["name"]
        for r in st.session_state["reagents"]
        if r["type"].lower() == "primary"
    ]

    # We'll store user selections for each plex in st.session_state["plex_assignments"].
    if "plex_assignments" not in st.session_state:
        st.session_state["plex_assignments"] = {}  # { plex_number: [list_of_selected_primaries], ... }

    st.subheader("Step 3: Assign Primaries to Each Plex")
    for i in range(num_plex):
        plex_id = i + 1
        # We create a unique key for each plex's multiselect
        chosen_primaries = st.multiselect(
            f"Select primary antibodies for Plex #{plex_id}",
            options=primary_names,
            default=st.session_state["plex_assignments"].get(plex_id, []),
            key=f"plex_{plex_id}_selector"
        )
        st.session_state["plex_assignments"][plex_id] = chosen_primaries

    # ---------------------------------------------------------
    # 4) Compute volumes
    # ---------------------------------------------------------
    if st.button("Compute Required Volumes"):
        # We’ll produce a table that shows each plex, each reagent, and how much volume is needed.
        if not st.session_state["reagents"]:
            st.warning("Please add at least one reagent before computing!")
            return

        results = []

        # For each plex, we combine the selected primaries with any other reagent
        # that is not a primary (e.g., Opal, DAPI, etc.) if that's how your protocol works.
        # You might do it differently if your setup changes from plex to plex.

        # 1) Collect "non-primary" reagents (e.g., Opal, DAPI, Amplifier, etc.)
        non_primary_reagents = [
            r for r in st.session_state["reagents"]
            if r["type"].lower() != "primary"
        ]

        for plex_id in range(1, num_plex + 1):
            # 2) Retrieve the primary names that user assigned to this plex
            plex_primary_names = st.session_state["plex_assignments"].get(plex_id, [])

            # 3) Build the reagent list for this plex:
            #    - All the primaries user specifically selected for this plex
            #    - Possibly all non-primaries if you apply them in each plex
            #      (If you do NOT apply some of them, you can filter further.)
            plex_reagent_list = []

            # Add the primaries
            for primary_name in plex_primary_names:
                # find the reagent info in st.session_state["reagents"]
                r_info = next((r for r in st.session_state["reagents"] if r["name"] == primary_name), None)
                if r_info is not None:
                    plex_reagent_list.append(r_info)

            # Add the non-primary reagents if your protocol requires them for every plex
            plex_reagent_list.extend(non_primary_reagents)

            # Calculate volumes for the plex
            for reagent in plex_reagent_list:
                needed_volume = compute_volume_needed(num_test_slides, num_neg_controls, reagent)
                results.append({
                    "Plex": plex_id,
                    "Reagent": reagent["name"],
                    "Type": reagent["type"],
                    "Volume Needed (µL)": round(needed_volume, 2),
                    "Initial Stock (µL)": reagent["initial_stock"]
                })

        st.subheader("Calculated Volumes by Plex")
        st.table(results)


if __name__ == "__main__":
    main()
