import numpy as np
import pandas as pd

import streamlit as st

from app.modules.charts_generator import generate_chart, get_fonts

def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    Generate interest charts to add in your presentations.
    """)

    with st.expander('Sensory benefits'):

        st.markdown('#### Chart parameters')

        config = {
            'name': st.column_config.TextColumn('Name', required=True, width='medium'),
            'scenario': st.column_config.TextColumn('Scenario', required=True, width='large'),
            'value': st.column_config.NumberColumn('Value', required=True),
            'base': st.column_config.TextColumn('Base', required=True),
            'percentage': st.column_config.NumberColumn('Percentage', min_value=0, max_value=100, format='%d%%'),
        }

        attributes_info = st.data_editor(
            pd.DataFrame(columns=config.keys()),
            num_rows="dynamic",
            column_config=config
        ).replace({None: np.nan})

        attributes_info = attributes_info.dropna(subset=['name', 'scenario', 'value', 'base'], how='all')

        fonts = get_fonts()

        try:
            font = st.selectbox('Font', options=fonts, index=fonts.index('Ubuntu'))
        except:
            font = 'Ubuntu'

        marker_color = st.color_picker('Marker color')

        if not attributes_info.empty:
            st.markdown('#### Result')

            fig = generate_chart(attributes_info, font, marker_color)
            st.pyplot(fig)
