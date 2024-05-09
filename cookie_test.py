from PIL import Image

import streamlit as st
import extra_streamlit_components as stx

from modules.styling import apply_default_style

import datetime

page_title = "Analytics Interface"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

apply_default_style(
    page_title,
    page_icon,
)

st.write("# Cookie Manager")

# @st.cache_resource(experimental_allow_widgets=True)
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

def main():
    st.subheader("All Cookies:")
    cookies = cookie_manager.get_all()
    st.write(cookies)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Get Cookie:")
        cookie = st.text_input("Cookie", key="0")
        clicked = st.button("Get")
        if clicked:
            value = cookie_manager.get(cookie=cookie)
            st.write(value)

    with c2:
        st.subheader("Set Cookie:")
        cookie = st.text_input("Cookie", key="1")
        val = st.text_input("Value")
        if st.button("Add"):
            cookie_manager.set(cookie, val) # Expires in a day by default

    with c3:
        st.subheader("Delete Cookie:")
        cookie = st.text_input("Cookie", key="2")
        if st.button("Delete"):
            cookie_manager.delete(cookie)

# Run the Streamlit app
if __name__ == "__main__":
    main()
