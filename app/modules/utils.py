import os
import requests

import streamlit as st

@st.cache_data(show_spinner=False)
def get_countries() -> dict[str, str]:

    url = 'https://api.worldbank.org/v2/country?format=json&per_page=300&region=LCN'

    response = requests.get(url)

    countries_info = response.json()[1]

    country_names = [country['name'] for country in countries_info if 'Latin America & Caribbean' in country['region']['value']]
    countries_iso_2_code = {country['name']: country['iso2Code'] for country in countries_info if country['name'] in country_names}

    return countries_iso_2_code

def get_authorized_pages_names(pages_roles: dict):
    files = sorted(os.listdir('app/pages'))
    files_names = [file.split('.')[0] for file in files if not file.startswith('_')]
    pages_names = [' '.join(file_name.split('_')) for file_name in files_names]

    user_roles = st.session_state.get("roles")

    if user_roles:
        pages_to_show = [page for page in pages_names if any(role in pages_roles[page.replace(' ', '_')]['roles'] for role in user_roles)]

    return pages_to_show
