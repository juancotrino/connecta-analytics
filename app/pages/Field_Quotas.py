import itertools

import numpy as np
import pandas as pd

import streamlit as st

from app.modules.utils import try_download, write_temp_excel
from app.modules.field_quotas import (
    check_percentage_total,
    get_expanded_variable_pollsters,
    get_expanded_surveys,
)


def main():
    st.markdown("""
    This tool helps to generate Field Quotas given different variables and values.
    """)

    st.markdown("""
    ## Field Quotas
    """)

    with st.container(border=True):
        st.markdown("""
        ### Variables definition
        """)

        number_of_variables = st.number_input(
            "Number of Variables",
            min_value=0,
            key="number_of_variables",
        )

        if number_of_variables == 0:
            return

        cols = st.columns(number_of_variables)

        variable_dict = {}
        for i in range(number_of_variables):
            with cols[i]:
                variable_name = st.text_input(f"Name for variable {i + 1}")
                st.markdown("Variable values:")
                variable_values = st.data_editor(
                    pd.DataFrame(columns=["Values"]),
                    num_rows="dynamic",
                    hide_index=True,
                    key=f"variable_values_{i}",
                    use_container_width=True,
                ).replace({None: np.nan})
                variable_dict[variable_name] = variable_values

        selected_variables = list(variable_dict.keys())

        nested_variables = pd.DataFrame(
            columns=[f"Level {i}" for i in range(2)] + ["Nested"]
        )

        with st.expander("Nested variables"):
            # Generate all combinations of two elements
            combinations = [
                (a, b, False) for a, b in itertools.combinations(selected_variables, 2)
            ]

            nested_variables = st.data_editor(
                pd.DataFrame(
                    combinations, columns=[f"Level {i}" for i in range(2)] + ["Nested"]
                ),
                num_rows="fixed",
            ).replace({None: np.nan})

            nested_variables = nested_variables[
                nested_variables["Nested"] == True  # noqa: E712
            ].reset_index(drop=True)

    with st.container(border=True):
        st.markdown("""
        ### Pollsters distribution
        """)
        total_pollsters = st.number_input(
            "Number of Pollsters",
            min_value=0,
            key="total_pollsters",
        )
        variable_pollsters = None
        expanded_variable_pollsters = None
        with st.expander("Divide Pollsters by Variable"):
            # Generate all combinations of two elements
            variable_pollsters = st.selectbox(
                "Variable",
                selected_variables,
                index=None,
                placeholder="Choose a variable",
            )

            if variable_pollsters:
                config = {
                    "Values": st.column_config.TextColumn("Values", disabled=True)
                }
                variable_pollsters_df = st.data_editor(
                    pd.DataFrame(
                        variable_dict[variable_pollsters],
                        columns=["Values", "Number of Pollsters"],
                    ),
                    num_rows="fixed",
                    column_config=config,
                    hide_index=True,
                ).replace({None: np.nan})

                if (
                    variable_pollsters_df["Number of Pollsters"].sum()
                    != total_pollsters
                ) and not any(variable_pollsters_df["Number of Pollsters"].isnull()):
                    st.error(
                        "Total number of pollsters do not match with sum of "
                        f"pollsters in variable '{variable_pollsters}' options."
                    )

                elif not any(variable_pollsters_df["Number of Pollsters"].isnull()):
                    expanded_variable_pollsters = get_expanded_variable_pollsters(
                        variable_pollsters_df
                    )

    with st.form(key="field_quotas"):
        st.markdown("""
        ### Survey Percentages
        """)

        total_surveys = st.number_input(
            "Number of Surveys",
            min_value=0,
            key="number_of_surveys",
        )

        config = {
            "percentage": st.column_config.NumberColumn(
                "Percentage",
                min_value=0,
                max_value=100,
                format="%.0f%%",  # Format with suffix of percentage
                required=True,
            )
        }

        selected_variables_data = {
            variable: variable_dict[variable]["Values"]
            for variable in selected_variables
        }

        outer_variables = [
            variable
            for variable in selected_variables
            if variable not in nested_variables["Level 1"].tolist()
        ]

        if all(variable for variable in outer_variables) and not all(
            data.empty for _, data in selected_variables_data.items()
        ):
            st.write("### Percentages for independent variables")
            cols = st.columns(len(outer_variables))

            variable_percentages_dict = {}
            for i, outer_variable in enumerate(outer_variables):
                if selected_variables_data[outer_variable].empty:
                    continue
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

        variable_nested_percentages_dict = {}
        if not nested_variables.empty:
            st.write("### Percentages for nested variables")
            cols = st.columns(len(nested_variables))

            for i, nested_variable in nested_variables.iterrows():
                with cols[i]:
                    higher_variable = nested_variable["Level 0"]
                    lower_variable = nested_variable["Level 1"]
                    nested_variable_str = f"{higher_variable} - {lower_variable}"

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
            try:
                check_percentage_total(
                    variable_percentages_dict, variable_type="independent"
                )
                check_percentage_total(
                    variable_nested_percentages_dict, variable_type="nested"
                )

                expanded_surveys = write_temp_excel(
                    get_expanded_surveys(
                        total_surveys,
                        total_pollsters,
                        variable_pollsters,
                        expanded_variable_pollsters,
                        variable_percentages_dict,
                        variable_nested_percentages_dict,
                        selected_variables_data,
                        selected_variables,
                    )
                )
            except Exception as e:
                st.error(e)

    try:
        try_download(
            "Download Quotas",
            expanded_surveys,
            "field_quotas",
            "xlsx",
        )
    except Exception:
        pass
