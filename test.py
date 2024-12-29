import streamlit as st

# Example: Minimal data extracted from your sheet
REAGENTS = {
    "PDGFRB": {
        "initial_stock": 300,  # e.g. the volume you have in the 'Open 1' row
        "dilution": 1.5,
        "dead_volume": 150,  # from your note that dead volume is 150uL
        "type": "Primary"
    },
    "COL1": {
        "initial_stock": 300,
        "dilution": 0.75,
        "dead_volume": 150,
        "type": "Primary"
    },
    "IGG1": {
        "initial_stock": 300,
        "dilution": 0.75,
        "dead_volume": 150,
        "type": "Primary"
    },
    # ...
    "Opal 480": {
        "initial_stock": 450,
        "dilution": 0.45,
        "dead_volume": 150,
        "type": "Opal"
    },
    # ...
    "TSA-DIG": {
        "initial_stock": 450,
        "dilution": 4.5,
        "dead_volume": 150,
        "type": "Amplifier"
    },
    "DAPI": {
        "initial_stock": 450,
        "dilution": 9,
        "dead_volume": 150,
        "type": "DAPI"
    },
    # ...
}


def compute_volume_needed(num_test_slides, num_neg_controls, reagent_info):
    """
    Returns the volume needed (in µL) for a single reagent 
    based on the number of test slides and negative controls.
    """
    # If reagent is a "Primary", do NOT apply it to negative controls
    if reagent_info["type"] == "Primary":
        total_slides = num_test_slides  # ignore negative controls for primaries
    else:
        total_slides = num_test_slides + num_neg_controls

    # Suppose we just multiply (slides * dilution) + dead volume
    # This is just an example: adapt it to your real calculations.
    base_volume = total_slides * reagent_info["dilution"]

    # Check if we need a double dispensing (Opal or DAPI)
    # If so, multiply by 2
    if reagent_info["type"] in ["Opal", "DAPI"]:
        base_volume *= 2

    # Add dead volume
    total_volume = base_volume + reagent_info["dead_volume"]

    return total_volume


def main():
    st.title("Robot Multiplex Preparation Calculator")
    st.write("Enter the parameters below to compute reagent volumes:")

    # 2) Get user inputs
    num_plex = st.number_input("Number of Plex?", min_value=1, max_value=8, value=1)
    num_test_slides = st.number_input("Number of Test Slides?", min_value=0, value=8)
    num_neg_controls = st.number_input("Number of Negative Controls?", min_value=0, value=0)

    # 3) Button to compute
    if st.button("Compute Volumes"):
        results = []

        for reagent_name, reagent_info in REAGENTS.items():
            needed_volume = compute_volume_needed(num_test_slides, num_neg_controls, reagent_info)
            results.append(
                {
                    "Reagent": reagent_name,
                    "Type": reagent_info["type"],
                    "Volume Needed (µL)": round(needed_volume, 2),
                }
            )

        # 4) Show results
        st.subheader("Calculated Volumes")
        st.table(results)


if __name__ == "__main__":
    main()