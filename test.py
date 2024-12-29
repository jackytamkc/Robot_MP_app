import streamlit as st

# A simple dictionary for species -> polymer inference
SPECIES_TO_POLYMER = {
    "goat": "Polymer-Goat",
    "sheep": "Polymer-Sheep",
    "mouse": "Polymer-Mouse",
    "rat": "Polymer-Rat",
    "rabbit": "Polymer-Rabbit"
}


def main():
    st.title("Robot Multiplex Preparation Calculator")

    # --------------------------------------------------------------------
    # Session states initialization
    # --------------------------------------------------------------------
    if "reagents" not in st.session_state:
        st.session_state["reagents"] = []
    if "show_reagents" not in st.session_state:
        st.session_state["show_reagents"] = False
    if "plex_type" not in st.session_state:
        st.session_state["plex_type"] = None
    if "results" not in st.session_state:
        st.session_state["results"] = None
    if "plex_order" not in st.session_state:
        st.session_state["plex_order"] = {}

    # A helper to clear results whenever something major changes
    def clear_results():
        st.session_state["results"] = None

    # --------------------------------------------------------------------
    # 1) Choose Single-Plex or Multi-Plex
    #    If user changes the selection, clear old results.
    # --------------------------------------------------------------------
    new_plex_type = st.radio(
        "Select Experiment Type:",
        options=["Single-Plex", "Multi-Plex"],
        index=0 if st.session_state["plex_type"] == "Single-Plex" else 1
    )
    if new_plex_type != st.session_state["plex_type"]:
        st.session_state["plex_type"] = new_plex_type
        clear_results()  # Clear old results if the user switched types

    plex_type = st.session_state["plex_type"]

    # --------------------------------------------------------------------
    # 2) Add Reagents (Reagent Type limited to Primary, DAPI, Others)
    # --------------------------------------------------------------------
    st.subheader("Step 1: Add Reagents")

    with st.form("add_reagent_form", clear_on_submit=True):
        r_name = st.text_input("Reagent Name", "")

        r_type = st.selectbox(
            "Reagent Type (only Primary, DAPI, Others)",
            ["Primary", "DAPI", "Others"]
        )

        # For primary, ask species & opal
        species = None
        opal_choice = None
        double_dispense = False
        negative_ctrl_needed = False

        if r_type == "Primary":
            species = st.selectbox(
                "Species (to determine polymer)",
                ["goat", "sheep", "mouse", "rat", "rabbit"]
            )
            opal_choice = st.selectbox(
                "Opal to link with",
                ["480", "520", "540", "570", "620", "650", "690", "780", "others"]
            )
            double_dispense = st.checkbox("Double Dispense?")
            negative_ctrl_needed = st.checkbox("Negative Control needed for this reagent?")
        elif r_type == "DAPI":
            double_dispense = st.checkbox("Double Dispense?")
            negative_ctrl_needed = st.checkbox("Negative Control needed for this reagent?")
        else:
            # For Others, just negative control (if relevant)
            negative_ctrl_needed = st.checkbox("Negative Control needed for this reagent?")

        submitted = st.form_submit_button("Add Reagent")

    # When user clicks "Add Reagent"
    if submitted:
        if not r_name:
            st.warning("Please enter a Reagent Name.")
        else:
            polymer = SPECIES_TO_POLYMER[species] if (r_type == "Primary" and species) else None
            new_reagent = {
                "name": r_name,
                "type": r_type,
                "species": species,
                "polymer": polymer,
                "opal": opal_choice,
                "double_dispense": double_dispense,
                "negative_ctrl": negative_ctrl_needed
            }
            st.session_state["reagents"].append(new_reagent)
            st.success(f"Added reagent: {r_name}")
            clear_results()  # Clear results if new reagent added

    # Button to show/hide "Current Reagents"
    if st.button("Show/Hide Current Reagents"):
        st.session_state["show_reagents"] = not st.session_state["show_reagents"]

    # If user wants to see the current reagents
    if st.session_state["show_reagents"]:
        if st.session_state["reagents"]:
            st.write("**Current Reagents:**")
            # We'll build a small table with a 'Remove' button for each row
            for i, r in enumerate(st.session_state["reagents"]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{r['name']}** | Type: {r['type']} | Species: {r['species']} | "
                             f"Opal: {r['opal']} | Double?: {r['double_dispense']} | "
                             f"NegCtrl?: {r['negative_ctrl']}")
                with col2:
                    if st.button(f"Remove {r['name']}", key=f"remove_{i}"):
                        st.session_state["reagents"].pop(i)
                        st.experimental_rerun()
        else:
            st.write("No reagents added.")

    # --------------------------------------------------------------------
    # 3) Single-Plex or Multi-Plex Flow
    # --------------------------------------------------------------------
    if plex_type == "Single-Plex":
        single_plex_flow()

    else:
        multi_plex_flow()


def single_plex_flow():
    """
    Step 2 for Single-Plex:
      - The # of test slides = # of primary reagents.
      - The # of negative control slides is derived from how many reagents
        have negative_ctrl=True (this is just an EXAMPLE).
      - Show a small calculation example.
    """
    st.subheader("Single-Plex: Calculation Example")

    # We re-collect the primary reagents:
    primaries = [r for r in st.session_state["reagents"] if r["type"] == "Primary"]

    # Example logic:
    # - # test slides = # of primary reagents
    # - # negative control slides = # of reagents that have negative_ctrl=True
    #   (One possible interpretation; adapt to your real lab logic)
    num_test_slides = len(primaries)
    num_neg_ctrl_slides = sum(r["negative_ctrl"] for r in st.session_state["reagents"])

    # We'll show this summary; user can click a "Compute" button to do a short example of volume calculations
    st.write(f"**Number of Test Slides**: {num_test_slides} (one per primary)")
    st.write(f"**Number of Negative Control Slides**: {num_neg_ctrl_slides} (derived)")

    if st.button("Compute Volumes (Single-Plex Example)"):
        # We'll do a trivial example calculation:
        # volume for each reagent = total_slides * 50 µL (test slides + neg ctrl slides)
        # If double_dispense is True, multiply by 2
        # We'll store the results in st.session_state["results"]
        total_slides = num_test_slides + num_neg_ctrl_slides
        result_rows = []
        for r in st.session_state["reagents"]:
            # Example base volume = total_slides * 50 µL
            volume = total_slides * 50.0
            if r["double_dispense"]:
                volume *= 2

            result_rows.append({
                "Reagent": r["name"],
                "Type": r["type"],
                "Double?": r["double_dispense"],
                "NegCtrl?": r["negative_ctrl"],
                "Volume (µL)": volume
            })

        st.session_state["results"] = result_rows

    # If we have results, display them
    if st.session_state["results"]:
        st.write("**Volume Calculation Results**")
        st.table(st.session_state["results"])


def multi_plex_flow():
    """
    Step 2 for Multi-Plex:
      - Ask how many plexes
      - Let user assign which primary goes to each plex in order
      - Perform a small example calculation for each plex
    """
    st.subheader("Multi-Plex: Calculation Example")

    # If the user changes the # of plexes, we clear the result
    def on_plex_change():
        st.session_state["results"] = None

    num_plexes = st.number_input(
        "How many plexes?",
        min_value=1, max_value=8, value=2,
        on_change=on_plex_change
    )

    # Build a list of primary reagents
    primary_reagents = [r for r in st.session_state["reagents"] if r["type"] == "Primary"]
    primary_names = [r["name"] for r in primary_reagents]

    # For each plex, pick a primary (or none).
    # Store in st.session_state["plex_order"] = { plex_index: reagent_name, ... }
    for i in range(1, num_plexes + 1):
        key_str = f"plex_order_select_{i}"
        if key_str not in st.session_state["plex_order"]:
            st.session_state["plex_order"][key_str] = "(none)"

        selected = st.selectbox(
            f"Which primary reagent is used in plex #{i}?",
            options=["(none)"] + primary_names,
            index=0 if st.session_state["plex_order"][key_str] not in primary_names else
            (primary_names.index(st.session_state["plex_order"][key_str]) + 1),
            key=key_str
        )

    if st.button("Compute Volumes (Multi-Plex Example)"):
        # Example logic:
        # - # test slides = # of plexes with assigned primary
        # - # negative ctrl slides = count how many assigned primaries require negative ctrl
        # - For each plex that has an assigned primary, compute some volume
        #   volume = (test_slides + neg_ctrl_slides) * 40 µL
        #   if double_dispense, multiply by 2
        #   (Again, purely for demonstration.)
        assigned_plexes = [key for key, val in st.session_state["plex_order"].items() if val != "(none)"]
        # number of test slides = number of assigned primaries (just an example)
        num_test_slides = len(assigned_plexes)

        # negative controls => how many assigned primaries have negative_ctrl=True
        # (One possible logic.)
        assigned_primaries = []
        for key_str in assigned_plexes:
            r_name = st.session_state["plex_order"][key_str]
            # find the reagent
            found = next((r for r in primary_reagents if r["name"] == r_name), None)
            if found:
                assigned_primaries.append(found)
        num_neg_ctrl_slides = sum(r["negative_ctrl"] for r in assigned_primaries)
        total_slides = num_test_slides + num_neg_ctrl_slides

        result_rows = []
        for i in range(1, num_plexes + 1):
            key_str = f"plex_order_select_{i}"
            chosen_name = st.session_state["plex_order"][key_str]
            if chosen_name != "(none)":
                # find the reagent
                r_info = next((r for r in primary_reagents if r["name"] == chosen_name), None)
                if r_info:
                    volume = total_slides * 40.0
                    if r_info["double_dispense"]:
                        volume *= 2
                    result_rows.append({
                        "Plex": i,
                        "Primary": r_info["name"],
                        "Double?": r_info["double_dispense"],
                        "NegCtrl?": r_info["negative_ctrl"],
                        "Volume (µL)": volume
                    })
            else:
                result_rows.append({
                    "Plex": i,
                    "Primary": "(none)",
                    "Double?": "",
                    "NegCtrl?": "",
                    "Volume (µL)": 0
                })

        st.session_state["results"] = result_rows

    # If we have multi-plex results, show them
    if st.session_state["results"]:
        st.write("**Multi-Plex Calculation Results**")
        st.table(st.session_state["results"])


if __name__ == "__main__":
    main()
