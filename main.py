import importlib
import logging
from typing import Optional, List
from dotenv import load_dotenv

from PIL import Image
import streamlit as st
import firebase_admin

from app.modules.styling import apply_default_style, footer
from app.modules.authenticator import (
    Authenticator,
    get_authenticator,
    get_page_roles,
)
from app.modules.utils import get_authorized_pages_names

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
PAGE_TITLE = "Analytics Interface"
PAGE_ICON = Image.open("static/images/connecta-logo.png")


class AppConfig:
    """Configuration class for the application."""

    def __init__(self):
        self.page_title = PAGE_TITLE
        self.page_icon = PAGE_ICON
        self.logo_path = "static/images/connecta.png"

    def initialize_firebase(self) -> None:
        """Initialize Firebase if not already initialized."""
        if not firebase_admin._apps:
            app_options = {"projectId": "connecta-app-1"}
            try:
                firebase_admin.initialize_app(options=app_options)
            except Exception as e:
                message = f"Error initializing firebase app: {str(e)}"
                logger.error(message)
                raise


class App:
    """Main application class."""

    def __init__(self):
        self.config = AppConfig()
        self.authenticator: Optional[Authenticator] = None
        self.pages_roles: Optional[dict] = None
        self.pages_names: Optional[List[str]] = None

    def setup(self) -> None:
        """Initialize application components."""
        apply_default_style(
            self.config.page_title, self.config.page_icon, page_type="login"
        )
        self.config.initialize_firebase()
        self.authenticator = get_authenticator()
        self.pages_roles = get_page_roles()
        self.pages_names = get_authorized_pages_names(self.pages_roles)

    def render_header(self) -> None:
        """Render application header."""
        st.title(self.config.page_title)
        logo = Image.open(self.config.logo_path)
        st.image(logo, width=500)

    def render_admin_panel(self) -> None:
        """Render admin panel if user has admin privileges."""
        if (
            not st.session_state.get("roles")
            or "connecta-admin" not in st.session_state["roles"]
        ):
            return

        with st.expander("Administrator options"):
            tab1, tab2 = st.tabs(["New User", "Cache"])
            with tab1:
                try:
                    _ = self.authenticator.register_user_form
                except Exception as e:
                    st.error(str(e))
            with tab2:
                if st.button("Clear cache", type="primary"):
                    st.cache_data.clear()

    def render_pages(self) -> None:
        """Render available pages based on user roles."""
        if not self.pages_names:
            return

        st.sidebar.markdown("# Available components")
        tabs = st.tabs(self.pages_names)

        for page_name, tab in zip(self.pages_names, tabs):
            with tab:
                try:
                    module = importlib.import_module(
                        f"app.pages.{page_name.replace(' ', '_')}"
                    )
                    module.main()
                except Exception as e:
                    logger.error(f"Error loading page {page_name}: {str(e)}")
                    st.error(f"Error loading page: {str(e)}")

    def hide_unauthorized_pages(self) -> None:
        """Hide pages that user doesn't have access to."""
        if self.authenticator and self.pages_roles:
            self.authenticator.hide_unauthorized_pages(self.pages_roles)

    def run(self) -> None:
        """Main application entry point."""
        try:
            self.setup()
            self.render_header()

            if not self.authenticator:
                raise ValueError("Authenticator not initialized")

            # Add a loading state while checking authentication
            with st.spinner("Checking authentication..."):
                # Check authentication status. If None (initial state) or False (failed login),
                # attempt to validate cookie.
                current_auth_status = st.session_state.get("authentication_status")

                if (
                    current_auth_status is None
                ):  # First run or after logout, try cookie validation
                    if self.authenticator.cookie_is_valid:
                        # If cookie is valid, it means auth status changed from None to True.
                        # Rerun to ensure all components react to the updated session state.
                        st.rerun()
                    # If cookie is not valid, current_auth_status remains None, proceed to login form.
                elif current_auth_status is False:
                    # Authentication failed previously, user sees login form.
                    pass  # No specific action needed, will fall into the 'else' block below

            # Now, based on the (potentially updated) authentication status, render the UI.
            if st.session_state.get("authentication_status"):
                # User is authenticated
                _ = self.authenticator.login_panel  # Displays logout and account config
                self.hide_unauthorized_pages()
                self.render_admin_panel()
                self.render_pages()
                footer()
            else:
                # User is not authenticated, display login forms
                st.markdown(
                    """
                    <style>
                        [data-testid="collapsedControl"] {
                            display: none
                        }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                _, col2, _ = st.columns(3)
                with col2:
                    login_tab1, login_tab2 = st.tabs(["Login", "Forgot password"])
                    with login_tab1:
                        _ = self.authenticator.login_form
                    with login_tab2:
                        _ = self.authenticator.forgot_password_form
                footer()  # Render footer for login page

        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            st.error(f"An error occurred: {str(e)}")
            # Re-raise the exception to show Streamlit's error overlay if desired
            raise


def main():
    """Application entry point."""
    app = App()
    app.run()


main()
