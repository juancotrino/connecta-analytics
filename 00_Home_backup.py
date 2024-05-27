from PIL import Image

import streamlit as st

from modules.styling import apply_default_style


# -------------- SETTINGS --------------
page_title = "Connecta Analytics Interface"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

apply_default_style(
    page_title,
    page_icon
)

st.sidebar.markdown("# Home")
st.sidebar.markdown("""
© Copyright 2024 Connecta SAS. All Rights Reserved
""")

container = st.container()

st.title(page_title)

# --- DROP DOWN VALUES FOR SELECTING THE PERIOD ---
logo = Image.open('static/images/connecta.png')

container.image(logo, width=500)

st.write(
    """
This is a site under construction. Please expand the menu with the arrow on the top left hand corner
to see the available services.
    """
)
