import time
import itertools
from PIL import Image
import streamlit as st

# from streamlit_option_menu import option_menu

from modules.authenticator import get_authenticator, get_page_roles
from modules.styling import apply_default_style, apply_403_style, footer
from modules.noel_dashboard import (
    get_data,
    to_excel_bytes,
    calculate_statistics_regular_scale,
    calculate_statistics_jr_scale
)
from settings import AUTHORIZED_PAGES_ROLES

# -------------- SETTINGS --------------
page_title = "Noel Dashboard"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

page_name = ''.join(i for i in __file__.split('/')[-1] if not i.isdigit())[1:].split('.')[0]
authorized_roles = AUTHORIZED_PAGES_ROLES[page_name]

apply_default_style(
    page_title,
    page_icon,
    initial_sidebar_state='expanded'
)

authenticator = get_authenticator()
# --------------------------------------

if not authenticator.cookie_is_valid and authenticator.not_logged_in:
    st.switch_page("00_Home.py")

roles = st.session_state.get("roles")
auth_status = st.session_state.get("authentication_status")

pages_roles = get_page_roles()
_ = authenticator.hide_unauthorized_pages(pages_roles)
authorized_page_roles = pages_roles[page_name]['roles']

if not roles or not any(role in authorized_page_roles for role in roles) or auth_status is not True:
    apply_403_style()
    _, col2, _ = st.columns(3)
    time_left = col2.progress(100)
    footer()

    for seconds in reversed(range(0, 101, 25)):
        time_left.progress(seconds, f'Redirecing to Home page in {seconds // 25 + 1}...')
        time.sleep(1)

    st.switch_page("00_Home.py")

else:

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

    # scale_type = option_menu(
    #     menu_title=None,
    #     options=[
    #         "Regular Scales",
    #         "JR Scales"
    #     ],
    #     icons=[
    #         "align-end",
    #         "align-middle"
    #     ], # https://icons.getbootstrap.com/
    #     orientation="horizontal",
    #     styles={
    #         "nav-link-selected": {"background-color": "#F78E1E"},
    #     }
    # )

    scale_type = st.radio(
        'Scale types:',
        options=[
            "Regular Scales",
            "JR Scales"
        ],
        horizontal=True
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

footer()
