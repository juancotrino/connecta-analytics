import numpy as np
import pandas as pd

import streamlit as st

def validate_segmentation_spss_jobs(jobs: pd.DataFrame) -> bool:

    validations = []

    if any(jobs['scenario_name'].duplicated()):
        st.warning('Duplicated Scenario Names')
        validations.append(False)

    for _, scenario in jobs.iterrows():

        # if scenario['condition'] != '':
        #     if scenario['condition'] is not None and not any([variable in scenario['condition'] for variable in scenario['variables'].split(',')]):
        #         st.warning(f"Variables in condition don't match required variables. Scenario: {scenario['scenario_name']}")
        #         validations.append(False)

        # if scenario['calculate_chi2'] and scenario['cross_variable'] is None:
        #     st.warning(f"Cross variable is missing. Scenario: {scenario['scenario_name']}")
        #     validations.append(False)

        if scenario['variables'] and scenario['cross_variable'] and scenario['cross_variable'] not in scenario['variables']:
            st.warning(f"Cross variable must be present in required variables. Scenario: {scenario['scenario_name']}")
            validations.append(False)

    return all(np.invert(validations)) if validations else True
