import time
import itertools
from PIL import Image
import streamlit as st

import numpy as np

# from streamlit_option_menu import option_menu

from app.modules.noel_dashboard import (
    get_data_unique,
    build_query,
    get_filtered_data,
    to_excel_bytes,
    calculate_statistics_regular_scale,
    calculate_statistics_jr_scale
)

MINIMUM_MNUMBER_OF_FILTERS = 3

def main():
    # -------------- SETTINGS --------------
    page_title = "## Noel Dashboard"

    # st.sidebar.markdown("## Noel Dashboard")
    # st.sidebar.markdown("""
    # This is a dashboard where TP, B2B, JR and other metrics can be
    # seen in a compact and easy to filter and understandlable way.
    # """)

    # st.markdown(page_title)
    st.markdown("""
    This is a dashboard where TP, B2B, JR and other metrics can be
    seen in a compact, easy to filter and understandable way.
    """)
    st.header('Filters')

    data = get_data_unique()

    for column in data:
        if column != 'age':
            data[column] = data[column].replace({np.nan: ''})

    # with st.form("dashboard_filters"):

    col11, col12 = st.columns(2)
    col21, col22, col23, col24 = st.columns(4)
    col31, col32, col33, col34 = st.columns(4)

    filters_template = {
        'category': ('Category', col11),
        'sub_category': ('Sub Category', col12),
        'client': ('Client', col21),
        'study_name': ('Study Name', col22),
        'brand': ('Brand', col23),
        'sample': ('Sample', col24),
        'age': ('Age', col31),
        'gender': ('Gender', col32),
        'ses': ('SES', col33),
        'country': ('Country', col34),
    }

    filters = {filter_name: [] for filter_name in filters_template.keys()}

    for filter_name, attributes in filters_template.items():
        name, field = attributes
        if name == 'Age':
            if data['age'].isna().all():
                continue
            disabled = len(data['age'].dropna().unique()) == 0
            selection = field.slider(
                name,
                value=(
                    int(min(data['age'].dropna().unique())) if not disabled else 0,
                    int(max(data['age'].dropna().unique())) if not disabled else 0
                ),
                disabled=disabled
            )
            data = data[(data['age'] >= selection[0]) & (data['age'] <= selection[1])]
        else:
            selection = field.multiselect(name, sorted(data[filter_name].unique()))
            if selection:
                data = data[data[filter_name].isin(selection)]

        filters[filter_name] = selection

        # for filter_name, attributes in filters_template.items():
        #     name, field = attributes

        #     if name == 'Age':
        #         selection = field.slider(name, value=(0, 100))
        #     else:
        #         selection = field.multiselect(name, sorted(data[filter_name].unique()))

        #     filters[filter_name] = selection

    number_of_filters_selected = len([variable for variable, options in filters.items() if options])
    generate_analysis = st.button("Generate analysis")
        # generate_analysis = st.form_submit_button("Generate analysis")

    try:
        if generate_analysis:
            if number_of_filters_selected <= MINIMUM_MNUMBER_OF_FILTERS:
                st.error('You should select more than 3 filters.')
            else:
                with st.spinner("Fetching data from BigQuery..."):
                    query = build_query(filters)
                    filtered_data = get_filtered_data(query)
                    st.session_state['filtered_data'] = filtered_data

        if 'filtered_data' not in st.session_state:
            st.session_state['filtered_data'] = None

        if st.session_state['filtered_data'] is not None:
            filtered_data = st.session_state['filtered_data']

            total_filters = [str(_filter) for _filter in list(itertools.chain.from_iterable(filters.values()))]

            scale_type = st.radio(
                'Scale types:',
                options=[
                    "Regular Scales",
                    "JR Scales"
                ],
                horizontal=True
            )

            if scale_type == 'Regular Scales':
                table = calculate_statistics_regular_scale(filtered_data)
                st.dataframe(
                    table,
                    use_container_width=True,
                    column_config={
                        'variable': 'Variable',
                        'base': 'Base',
                        'mean': 'Mean',
                        'std': 'Standard Deviation',
                    }
                )

                st.download_button(
                    label="Download Data",
                    data=to_excel_bytes(table),
                    file_name=f'regular_{"_".join(total_filters)}.xlsx',
                    mime='application/xlsx',
                    type='primary'
                )

            elif scale_type == 'JR Scales':
                table = calculate_statistics_jr_scale(filtered_data)
                st.dataframe(
                    table,
                    use_container_width=True,
                    column_config={
                        'variable': 'Variable',
                        'base': 'Base',
                        'mean': 'Mean',
                        'std': 'Standard Deviation',
                    }
                )
                st.download_button(
                    label="Download Data",
                    data=to_excel_bytes(table),
                    file_name=f'jr_{"_".join(total_filters)}.xlsx',
                    mime='application/xlsx',
                    type='primary'
                )

    except Exception as e:
        st.error(e)
