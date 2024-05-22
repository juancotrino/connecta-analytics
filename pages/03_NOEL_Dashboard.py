import itertools
from PIL import Image
import streamlit as st

from streamlit_option_menu import option_menu

from modules.styling import apply_default_style, apply_404_style
from modules.noel_dashboard import (
    get_data,
    to_excel_bytes,
    calculate_statistics_regular_scale,
    calculate_statistics_jr_scale
)

# -------------- SETTINGS --------------
page_title = "Noel Dashboard"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

# --------------------------------------

role = st.session_state.get("role")
auth_status = st.session_state.get("authentication_status")

if role not in ('connecta-ds',) or auth_status is not True:
    apply_404_style()

else:

    apply_default_style(
        page_title,
        page_icon,
        initial_sidebar_state='expanded'
    )

    st.sidebar.markdown("# Noel Dashboard")
    st.sidebar.markdown("""
    This is a dashboard where TP, B2B, JR and other metrics can be
    seen in a compact and easy to filter and understandlable way.
    """)

    st.title(page_title)
    st.header('Filters')

    data = get_data()

    col11, col12 = st.columns(2)
    col21, col22, col23, col24 = st.columns(4)
    col31, col32, col33, col34 = st.columns(4)

    filters_template = {
        'Categoría': ('Category', col11),
        'Sub - Categoría': ('Sub Category', col12),
        'Cliente': ('Client', col21),
        'Nombre del estudio': ('Study Name', col22),
        'Marca': ('Brand', col23),
        'sample': ('Sample', col24),
        'Edad': ('Age', col31),
        'Género': ('Gender', col32),
        'Estrato/Nivel socieconómico': ('SES', col33),
        'País': ('Country', col34),
    }

    filters = {filter_name: [] for filter_name in filters_template.keys()}

    for filter_name, attributes in filters_template.items():
        name, field = attributes
        if name == 'Age':
            disabled = len(data['Edad'].dropna().unique()) == 0
            selection = field.slider(
                name,
                value=(
                    int(min(data['Edad'].dropna().unique())) if not disabled else 0,
                    int(max(data['Edad'].dropna().unique())) if not disabled else 0
                ),
                disabled=disabled
            )
            data = data[(data['Edad'] >= selection[0]) & (data['Edad'] <= selection[1])]
        else:
            selection = field.multiselect(name, sorted(data[filter_name].unique()))
            if selection:
                data = data[data[filter_name].isin(selection)]

        filters[filter_name] = selection

    total_filters = [str(_filter) for _filter in list(itertools.chain.from_iterable(filters.values()))]

    scale_type = option_menu(
        menu_title=None,
        options=[
            "Regular Scales",
            "JR Scales"
        ],
        icons=[
            "align-end",
            "align-middle"
        ], # https://icons.getbootstrap.com/
        orientation="horizontal",
        styles={
            "nav-link-selected": {"background-color": "#F78E1E"},
        }
    )

    if scale_type == 'Regular Scales':
        table = calculate_statistics_regular_scale(data)
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
            mime='application/xlsx'
        )

    elif scale_type == 'JR Scales':
        table = calculate_statistics_jr_scale(data)
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
            mime='application/xlsx'
        )
