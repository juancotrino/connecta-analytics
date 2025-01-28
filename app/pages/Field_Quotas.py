import itertools

import numpy as np
import pandas as pd

import streamlit as st

from app.modules.utils import try_download, write_temp_excel
from app.modules.field_quotas import get_field_quotas_data, get_expanded_surveys


field_quotas = get_field_quotas_data()


def combine_percentages(
    row, variable_percentages_dict: dict, variable_nested_percentages_dict: dict
):
    final_percentage = 1
    for variable in row:
        final_percentage *= variable_percentages_dict[variable]


def main():
    st.markdown("""
    This tool helps to generate Field Quotas given different variables and values.
    """)

    st.markdown("""
    ## Field Quotas
    """)

    st.markdown("""
    ### Filters
    """)

    selected_variables = st.multiselect(
        "Select variables:",
        field_quotas["variables"],
        key="variables",
    )

    # Generate all combinations of two elements
    combinations = [
        (a, b, False) for a, b in itertools.combinations(selected_variables, 2)
    ]

    nested_variables_df = st.data_editor(
        pd.DataFrame(
            combinations, columns=[f"Level {i}" for i in range(2)] + ["Nested"]
        ),
        num_rows="fixed",
    ).replace({None: np.nan})

    st.markdown("""
    ### Percentages
    """)

    with st.form(key="field_quotas"):
        total_surveys = st.number_input(
            "Number of Surveys",
            min_value=0,
            key="number_of_surveys",
        )

        total_pollsters = st.number_input(
            "Number of Pollsters",
            min_value=0,
            key="total_pollsters",
        )

        config = {
            "percentage": st.column_config.NumberColumn(
                "Percentage",
                min_value=0,
                max_value=100,
                format="%.0f%%",  # Format with suffix of percentage
                required=True,
                width="medium",
            )
        }

        nested_variables = nested_variables_df[
            nested_variables_df["Nested"] == True  # noqa: E712
        ].reset_index(drop=True)

        selected_variables_data = {
            variable: field_quotas["variables"][variable]
            for variable in selected_variables
        }

        outer_variables = [
            variable
            for variable in selected_variables
            if variable not in nested_variables["Level 1"].tolist()
        ]

        if outer_variables:
            st.write("### Percentages for independent variables")
            cols = st.columns(len(outer_variables))

            variable_percentages_dict = {}
            for i, outer_variable in enumerate(outer_variables):
                with cols[i]:
                    st.write(f"#### {outer_variable}")
                    df_percentage = pd.DataFrame(
                        {
                            outer_variable: selected_variables_data[outer_variable],
                            "percentage": None,
                        }
                    )

                    variable_config = {
                        outer_variable: st.column_config.TextColumn(
                            outer_variable, disabled=True
                        )
                    }

                    variable_percentage_df = st.data_editor(
                        df_percentage,
                        num_rows="fixed",
                        column_config=config | variable_config,
                        key=f"percentage_table_{outer_variable}",
                        hide_index=True,
                    ).replace({None: np.nan})

                    variable_percentages_dict[outer_variable] = variable_percentage_df

        if not nested_variables.empty:
            st.write("### Percentages for nested variables")
            cols = st.columns(len(nested_variables))

            variable_nested_percentages_dict = {}
            for i, nested_variable in nested_variables.iterrows():
                with cols[i]:
                    higher_variable = nested_variable["Level 0"]
                    lower_variable = nested_variable["Level 1"]
                    nested_variable_str = f"{higher_variable}-{lower_variable}"

                    st.write(f"#### {nested_variable_str}")

                    nested_variable_data = {
                        k: v
                        for k, v in selected_variables_data.items()
                        if k in (higher_variable, lower_variable)
                    }

                    combinations = [
                        combination
                        for combination in list(
                            itertools.product(*nested_variable_data.values())
                        )
                    ]

                    df_nested_percentage = pd.DataFrame(
                        {
                            higher_variable: [v[0] for v in combinations],
                            lower_variable: [v[1] for v in combinations],
                            "percentage": None,
                        }
                    )

                    variable_config = {
                        higher_variable: st.column_config.TextColumn(
                            higher_variable, disabled=True
                        ),
                        lower_variable: st.column_config.TextColumn(
                            lower_variable, disabled=True
                        ),
                    }

                    variable_nested_percentage_df = st.data_editor(
                        df_nested_percentage,
                        num_rows="fixed",
                        column_config=config | variable_config,
                        key=f"percentage_nested_table_{nested_variable}",
                        hide_index=True,
                    ).replace({None: np.nan})

                    variable_nested_percentages_dict[nested_variable_str] = (
                        variable_nested_percentage_df
                    )

        submitted = st.form_submit_button("Generate survey list")

        if submitted:
            expanded_surveys = write_temp_excel(
                get_expanded_surveys(
                    total_surveys,
                    total_pollsters,
                    variable_percentages_dict,
                    variable_nested_percentages_dict,
                    selected_variables_data,
                    selected_variables,
                )
            )

    try:
        try_download(
            "Download surveys list",
            expanded_surveys,
            "survey_list",
            "xlsx",
        )
    except Exception:
        pass
