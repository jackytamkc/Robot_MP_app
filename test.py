import streamlit as st


def compute_volume_needed(num_test_slides, num_neg_controls, reagent_info):
    """Compute volume needed (in µL) for a single reagent."""
    # For demonstration, I'm still using the same logic,
    # but you can refine it.
    if reagent_info["type"].lower() == "primary":
        # Negative controls don't get primary
        total_slides = num_test_slides
    else:
        total_slides = num_test_slides + num_neg_controls

    base_volume = total_slides * reagent_info["dilution"]

    # Double dispensing if "Opal" or "DAPI"
    if reagent_info["type"].lower() in ["opal", "dapi"]:
        base_volume *= 2

    total_volume = base_volume + reagent_info["dead_volume"]
    return total_volume


def main():
    st.title("Robot Multiplex Preparation Calculator")

    # Initialize session state to hold reagent data
    if "reagents" not in st.session_state:
        st.session_state["reagents"] = []

    st.subheader("Step 1: Add/Manage Reagents")

    # A form for adding reagent details
    with st.form("add_reagent_form", clear_on_submit=True):
        # Each input corresponds to a column in your table
        reagent_name = st.text_input("Reagent Name", "")
        reagent_type = st.selectbox(
            "Reagent Type",
            ["Primary", "Opal", "DAPI", "Amplifier", "Secondary", "Polymer", "Others"]
        )
        initial_stock = st.number_input("Initial Stock (µL)", min_value=0, value=300)
        dilution = st.number_input("Dilution Factor", min_value=0.0, value=1.0, step=0.1)
        dead_volume = st.number_input("Dead Volume (µL)", min_value=0, value=150)

        submit_button = st.form_submit_button("Add Reagent")

    # If user clicked the "Add Reagent" button
    if submit_button:
        # Append a dict of reagent info to session_state
        st.session_state["reagents"].append(
            {
                "name": reagent_name,
                "type": reagent_type,
                "initial_stock": initial_stock,
                "dilution": dilution,
                "dead_volume": dead_volume
            }
        )
        st.success(f"Added reagent: {reagent_name}")

    # Display the table of all added reagents
    if st.session_state["reagents"]:
        st.table(st.session_state["reagents"])
    else:
        st.write("No reagents added yet.")

    # Next, get the main experimental parameters
    st.subheader("Step 2: Experimental Setup")
    num_plex = st.number_input("Number of Plex?", min_value=1, max_value=8, value=1)
    num_test_slides = st.number_input("Number of Test Slides?", min_value=0, value=8)
    num_neg_controls = st.number_input("Number of Negative Controls?", min_value=0, value=0)

    # Button to compute volumes for all reagents
    if st.button("Compute Required Volumes"):
        if not st.session_state["reagents"]:
            st.warning("Please add at least one reagent before computing!")
        else:
            results = []
            for reagent in st.session_state["reagents"]:
                needed_volume = compute_volume_needed(num_test_slides, num_neg_controls, reagent)
                results.append(
                    {
                        "Reagent": reagent["name"],
                        "Type": reagent["type"],
                        "Volume Needed (µL)": round(needed_volume, 2),
                        "Initial Stock (µL)": reagent["initial_stock"]
                    }
                )

            st.subheader("Calculated Volumes")
            st.table(results)


if __name__ == "__main__":
    main()
