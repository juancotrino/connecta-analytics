import itertools

import numpy as np
import pandas as pd

import streamlit as st

from app.modules.utils import try_download, write_temp_excel
from app.modules.field_tools import (
    check_percentage_total,
    get_expanded_variable_pollsters,
    get_expanded_surveys,
    get_business_countries,
    get_field_supervisors,
    save_field_supervisors,
)


def main():
    with st.expander("Field Quotas"):
        render_field_quotas()

    with st.expander("Supervisors Management"):
        render_supervisors()


def render_supervisors():
    st.markdown("""
    This tool manages field supervisors data.
    """)
    columns = ["country", "supervisor_name", "phone_number", "active"]
    country_map = get_business_countries()
    country_names_by_code = {code: name for name, code in country_map.items()}
    supervisors = [dict(supervisor) for supervisor in get_field_supervisors()]
    if message := st.session_state.pop("field_supervisor_message", None):
        st.success(message)
    is_admin = "connecta-admin" in st.session_state.get("roles", [])
    tab_names = ["View", "Add"]
    if is_admin:
        tab_names.extend(["Edit", "Delete"])

    tabs = st.tabs(tab_names)
    with tabs[0]:
        supervisors_df = pd.DataFrame(supervisors, columns=columns)
        if not supervisors_df.empty:
            supervisors_df["country"] = supervisors_df["country"].map(
                country_names_by_code
            ).fillna(supervisors_df["country"])
            supervisors_df["phone_number"] = (
                supervisors_df["phone_number"].fillna("").astype(str)
            )
        st.dataframe(
            supervisors_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "country": "Country",
                "supervisor_name": "Supervisor Name",
                "phone_number": "Phone Number",
                "active": "Active",
            },
        )

    with tabs[1]:
        with st.form("add_field_supervisor"):
            country = st.selectbox("Country", options=list(country_map), index=None)
            supervisor_name = st.text_input("Supervisor Name")
            phone_number = st.text_input("Phone Number (country code optional)")
            active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("Add supervisor", type="primary")

        if submitted:
            if not country or not supervisor_name.strip() or not phone_number.strip():
                st.error("Country, supervisor name, and phone number are required.")
            else:
                supervisors.append(
                    {
                        "country": country_map[country],
                        "supervisor_name": supervisor_name.strip(),
                        "phone_number": phone_number.strip(),
                        "active": active,
                    }
                )
                save_field_supervisors(supervisors)
                get_field_supervisors.clear()
                st.session_state.field_supervisor_message = (
                    "Supervisor added successfully."
                )
                st.rerun()

    if is_admin:
        supervisor_options = [
            f"{index + 1}. {country_names_by_code.get(item.get('country'), item.get('country', ''))} - "
            f"{item.get('supervisor_name', '')} - {item.get('phone_number', '')}"
            for index, item in enumerate(supervisors)
        ]

        with tabs[2]:
            if not supervisors:
                st.info("There are no supervisors to edit.")
            else:
                selected_index = st.selectbox(
                    "Supervisor",
                    options=range(len(supervisors)),
                    format_func=lambda index: supervisor_options[index],
                    key="edit_supervisor_index",
                )
                selected_supervisor = supervisors[selected_index]
                selected_country = country_names_by_code.get(
                    selected_supervisor.get("country"), selected_supervisor.get("country")
                )

                with st.form(f"edit_field_supervisor_{selected_index}"):
                    edited_country = st.selectbox(
                        "Country",
                        options=list(country_map),
                        index=(
                            list(country_map).index(selected_country)
                            if selected_country in country_map
                            else None
                        ),
                    )
                    edited_name = st.text_input(
                        "Supervisor Name",
                        value=selected_supervisor.get("supervisor_name", ""),
                    )
                    edited_phone = st.text_input(
                        "Phone Number (country code optional)",
                        value=str(selected_supervisor.get("phone_number", "")),
                    )
                    edited_active = st.checkbox(
                        "Active", value=selected_supervisor.get("active", True)
                    )
                    submitted = st.form_submit_button(
                        "Save supervisor", type="primary"
                    )

                if submitted:
                    if (
                        not edited_country
                        or not edited_name.strip()
                        or not edited_phone.strip()
                    ):
                        st.error(
                            "Country, supervisor name, and phone number are required."
                        )
                    else:
                        supervisors[selected_index] = {
                            "country": country_map[edited_country],
                            "supervisor_name": edited_name.strip(),
                            "phone_number": edited_phone.strip(),
                            "active": edited_active,
                        }
                        save_field_supervisors(supervisors)
                        get_field_supervisors.clear()
                        st.session_state.field_supervisor_message = (
                            "Supervisor updated successfully."
                        )
                        st.rerun()

        with tabs[3]:
            if not supervisors:
                st.info("There are no supervisors to delete.")
            else:
                selected_index = st.selectbox(
                    "Supervisor",
                    options=range(len(supervisors)),
                    format_func=lambda index: supervisor_options[index],
                    key="delete_supervisor_index",
                )
                with st.form(f"delete_field_supervisor_{selected_index}"):
                    st.warning("Deleting a supervisor cannot be undone.")
                    confirmed = st.checkbox("I confirm this deletion.")
                    submitted = st.form_submit_button("Delete supervisor", type="primary")

                if submitted:
                    if not confirmed:
                        st.error("Confirm the deletion before continuing.")
                    else:
                        supervisors.pop(selected_index)
                        save_field_supervisors(supervisors)
                        get_field_supervisors.clear()
                        st.session_state.field_supervisor_message = (
                            "Supervisor deleted successfully."
                        )
                        st.rerun()


def render_field_quotas():
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
