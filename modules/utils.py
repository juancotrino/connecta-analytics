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
