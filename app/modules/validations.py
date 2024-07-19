import numpy as np
import pandas as pd
import pyreadstat

import streamlit as st

def validate_segmentation_spss_db(jobs: pd.DataFrame, temp_file_name: str) -> bool:

    validations = []

    survey_data: pd.DataFrame = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )[0]

    db_variables = survey_data.columns

    for _, scenario in jobs.iterrows():
        if scenario['condition'] and (
            # (scenario['variables'] == '' or scenario['variables'] is None) or
            not any([variable in scenario['condition'] for variable in db_variables])
        ):
            st.warning(f"Variables in condition are not present either in the SPSS database or in the `Variables` column. Scenario: {scenario['scenario_name']}")
            validations.append(False)

        if scenario['correlation_variables'] and (
            not any([variable in scenario['correlation_variables'] for variable in db_variables])
        ):
            st.warning(f"Variables in Correaltion Variables are not present in the SPSS database. Scenario: {scenario['scenario_name']}")
            validations.append(False)

    return all(validations) if validations else True

def validate_segmentation_spss_jobs(jobs: pd.DataFrame) -> bool:

    validations = []

    if any(jobs['scenario_name'].duplicated()):
        st.warning('Duplicated Scenario Names')
        validations.append(False)

    for _, scenario in jobs.iterrows():
        if (
            (scenario['condition'] != '' and scenario['condition'] is not None) and
            scenario['variables'] and
            not (
                any([variable in scenario['condition'] for variable in scenario['variables'].split(',')]) or
                any([variable in scenario['condition'] for variable in scenario['variables'].split('\n')])
            )
        ):
            st.warning(f"Variables in condition don't match required variables. Scenario: {scenario['scenario_name']}")
            validations.append(False)

        if scenario['variables'] and scenario['cross_variable'] and scenario['cross_variable'] not in scenario['variables']:
            st.warning(f"Cross variable must be present in required variables. Scenario: {scenario['scenario_name']}")
            validations.append(False)

    return all(np.invert(validations)) if validations else True
