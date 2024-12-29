import streamlit as st

# ---------------------------------------------------------
# Helper: For Primary -> Which polymer do we use?
# (You can expand or change this mapping as needed.)
# ---------------------------------------------------------
SPECIES_TO_POLYMER = {
    "goat": "Polymer-Goat",
    "sheep": "Polymer-Sheep",
    "mouse": "Polymer-Mouse",
    "rat": "Polymer-Rat",
    "rabbit": "Polymer-Rabbit"
}


def main():
    st.title("Robot Multiplex Preparation Calculator")

    # ---------------------------------------------------------
    # 1) Ask Single-Plex or Multi-Plex
    # ---------------------------------------------------------
    plex_type = st.radio(
        "Select Experiment Type:",
        options=["Single-Plex", "Multi-Plex"]
    )

    # ---------------------------------------------------------
    # 2) Reagent Input Section
    # ---------------------------------------------------------
    # We'll keep all reagents in session_state so we can display or use them later
    if "reagents" not in st.session_state:
        st.session_state["reagents"] = []

    st.subheader("Step 1: Add Reagents")
    with st.form("add_reagent_form", clear_on_submit=True):
        r_name = st.text_input("Reagent Name", "")

        # Only allow: Primary, DAPI, Others
        r_type = st.selectbox(
            "Reagent Type",
            ["Primary", "DAPI", "Others"]
        )

        # If it's Primary, show species & opal options
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
            # Possibly a double dispense needed?
            double_dispense = st.checkbox("Double Dispense?")
            # Negative control usually doesn't apply to DAPI,
            # but we keep it consistent with your instructions:
            negative_ctrl_needed = st.checkbox("Negative Control needed for this reagent?")
        else:
            # For "Others", simpler
            negative_ctrl_needed = st.checkbox("Negative Control needed for this reagent?")

        submitted = st.form_submit_button("Add Reagent")

    if submitted:
        if not r_name:
            st.warning("Please enter a Reagent Name.")
        else:
            # Determine polymer from species if it's primary
            polymer = SPECIES_TO_POLYMER[species] if r_type == "Primary" else None

            reagent_info = {
                "name": r_name,
                "type": r_type,
                "species": species,
                "polymer": polymer,
                "opal": opal_choice,
                "double_dispense": double_dispense,
                "negative_ctrl": negative_ctrl_needed
            }
            st.session_state["reagents"].append(reagent_info)
            st.success(f"Added reagent: {r_name}")

    # Show reagents table if any
    if st.session_state["reagents"]:
        st.write("**Current reagents:**")
        st.table(st.session_state["reagents"])
    else:
        st.write("No reagents added yet.")

    # ---------------------------------------------------------
    # 3) Single-Plex vs Multi-Plex Additional Steps
    # ---------------------------------------------------------
    if plex_type == "Single-Plex":
        st.subheader("Step 2: Single-Plex Details")
        st.write("For a single-plex, each primary reagent typically equals one test slide.")

        # Example: We could ask total # of negative control slides
        neg_controls_count = st.number_input("Number of negative control slides?", min_value=0, value=0)

        if st.button("Compute / Show Summary (Single-Plex)"):
            # Example summary:
            primary_reagents = [r for r in st.session_state["reagents"] if r["type"] == "Primary"]
            num_test_slides = len(primary_reagents)

            st.write(f"**Number of test slides** = # of primary reagents = {num_test_slides}")
            st.write(f"**Negative control slides** = {neg_controls_count}")

            st.write("You can now proceed with any volume calculations you want here. "
                     "Below is just a quick demonstration of a results table.")

            # Example: just listing each primary => 1 slide
            results = []
            for idx, r in enumerate(primary_reagents, start=1):
                results.append({
                    "Test Slide #": idx,
                    "Primary Reagent": r["name"],
                    "Species": r["species"],
                    "Polymer": r["polymer"],
                    "Opal": r["opal"],
                    "Double Dispense?": r["double_dispense"],
                    "Apply to Negative Control?": not r["negative_ctrl"]  # if negative_ctrl == True, skip
                })

            st.table(results)

    else:
        # Multi-Plex Flow
        st.subheader("Step 2: Multi-Plex Details")
        num_plexes = st.number_input("How many plexes?", min_value=1, max_value=8, value=2)

        st.write("Assign an order of reagent usage matching the number of plexes.")
        st.write("For example, if you have 3 plexes, you can pick which primary goes in plex #1, #2, #3.")

        # We'll gather primary reagents:
        primary_reagents = [r for r in st.session_state["reagents"] if r["type"] == "Primary"]

        # We'll store the user's chosen order in session state:
        if "plex_order" not in st.session_state:
            st.session_state["plex_order"] = {}

        for i in range(1, num_plexes + 1):
            # Pick which primary goes in plex i
            selected = st.selectbox(
                f"Which primary reagent is used in plex #{i}?",
                options=["(none)"] + [p["name"] for p in primary_reagents],
                key=f"plex_order_select_{i}"  # unique key
            )
            st.session_state["plex_order"][i] = selected

        neg_controls_count = st.number_input("Number of negative control slides?", min_value=0, value=0)

        if st.button("Compute / Show Summary (Multi-Plex)"):
            st.write("**Plex Assignment Summary**")
            assignment_list = []
            for i in range(1, num_plexes + 1):
                chosen_name = st.session_state["plex_order"][i]
                # retrieve the reagent info if not "(none)"
                if chosen_name and chosen_name != "(none)":
                    r_info = next((r for r in primary_reagents if r["name"] == chosen_name), None)
                    if r_info:
                        assignment_list.append({
                            "Plex #": i,
                            "Primary Reagent": r_info["name"],
                            "Species": r_info["species"],
                            "Polymer": r_info["polymer"],
                            "Opal": r_info["opal"],
                            "Double Dispense?": r_info["double_dispense"],
                            "Apply to Negative Control?": not r_info["negative_ctrl"]
                        })
                    else:
                        assignment_list.append({
                            "Plex #": i,
                            "Primary Reagent": "(none)",
                            "Species": "",
                            "Polymer": "",
                            "Opal": "",
                            "Double Dispense?": "",
                            "Apply to Negative Control?": ""
                        })
                else:
                    # No reagent assigned
                    assignment_list.append({
                        "Plex #": i,
                        "Primary Reagent": "(none)",
                        "Species": "",
                        "Polymer": "",
                        "Opal": "",
                        "Double Dispense?": "",
                        "Apply to Negative Control?": ""
                    })

            st.table(assignment_list)

            st.write("**Negative Control Slides**:", neg_controls_count)
            st.write("You can now integrate your volume-calculation logic here. "
                     "For instance, you might sum up the usage of each reagent across the assigned plexes, "
                     "or do more advanced calculations.")


if __name__ == "__main__":
    main()

