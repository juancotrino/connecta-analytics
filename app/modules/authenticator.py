import os
import math
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Optional, Dict, List, Union, Tuple

import extra_streamlit_components as stx
import jwt
import requests
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from email_validator import EmailNotValidError, validate_email
from firebase_admin import auth, firestore
from app.modules.business_definition import get_business_data

POST_REQUEST_URL_BASE = "https://identitytoolkit.googleapis.com/v1/accounts:"


class Authenticator:
    def __init__(
        self,
        firebase_api_key: str,
        cookie_key: str,
        cookie_manager: stx.CookieManager,
        cookie_expiry_days: int = 30,
        cookie_name: str = "login_cookie",
        preauthorized: str = "connecta.com.co",
    ) -> None:
        self.firebase_api_key = firebase_api_key
        self.cookie_key = cookie_key
        self.post_request_url_base = POST_REQUEST_URL_BASE
        self.post_request = partial(
            requests.post,
            headers={"content-type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        self.cookie_manager = cookie_manager
        self.cookie_expiry_days = cookie_expiry_days
        self.cookie_name = cookie_name
        self.preauthorized = preauthorized
        self._initialize_session_state()

    def _initialize_session_state(self) -> None:
        """Initialize all required session state variables."""
        default_states = {
            "login_error_message": None,
            "success_message": None,
            "name": None,
            "username": None,
            "roles": None,
            "company": None,
            "authentication_status": None,
            "is_logging_out": False,
        }

        for key, default_value in default_states.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

    def _parse_error_message(self, response: requests.Response) -> str:
        """Parse and format error messages from Firebase responses."""
        try:
            return (
                response.json()["error"]["message"]
                .casefold()
                .replace("_", " ")
                .replace("email", "e-mail")
            )
        except (KeyError, ValueError):
            return "An unknown error occurred"

    def _validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """Validate password strength using entropy calculation."""
        alphabet_chars = len(set(password))
        strength = int(len(password) * math.log2(alphabet_chars) * 1.5)

        if strength < 100:
            return False, "Password is too weak. Please choose a stronger password."
        return True, ""

    def _handle_auth_response(self, response: requests.Response) -> Optional[Dict]:
        """Handle authentication response and set appropriate session state messages."""
        if response.status_code != 200:
            st.session_state["login_error_message"] = (
                f"Authentication failed: {self._parse_error_message(response)}"
            )
            return None
        return response.json()

    @property
    def forgot_password_form(self) -> None:
        """Creates a Streamlit widget to reset a user's password. Authentication uses
        the Firebase Authentication REST API.
        """
        with st.form("Forgot password"):
            email = st.text_input("E-mail", key="forgot_password")
            if not st.form_submit_button("Reset password"):
                return None
        if "@" not in email and isinstance(self.preauthorized, str):
            email = f"{email}@{self.preauthorized}"

        url = f"{self.post_request_url_base}sendOobCode?key={self.firebase_api_key}"
        payload = {"requestType": "PASSWORD_RESET", "email": email}
        response = self.post_request(url, json=payload)
        if response.status_code == 200:
            st.session_state["success_message"] = (
                f"Password reset link has been sent to {email}"
            )
            st.session_state["login_error_message"] = None
            return None
        st.session_state["login_error_message"] = (
            f"Error sending password reset email: {self._parse_error_message(response)}"
        )
        st.session_state["success_message"] = None
        return None

    def authenticate_user(
        self, email: str, password: str, require_email_verification: bool = True
    ) -> Optional[Dict[str, Union[str, bool, int]]]:
        """Authenticate user with Firebase Authentication REST API."""
        url = f"{self.post_request_url_base}signInWithPassword?key={self.firebase_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
            "emailVerified": require_email_verification,
        }

        response = self.post_request(url, json=payload)
        auth_data = self._handle_auth_response(response)

        if not auth_data or (require_email_verification and "idToken" not in auth_data):
            st.session_state["login_error_message"] = "Invalid e-mail or password."
            return None

        return auth_data

    def login_user(self, email: str, password: str) -> Optional[auth.UserRecord]:
        """Handle user login process with proper error handling."""
        login_response = self.authenticate_user(email, password)
        if not login_response:
            st.session_state["authentication_status"] = False
            return None

        try:
            decoded_token = auth.verify_id_token(
                login_response["idToken"], clock_skew_seconds=10
            )
            user = auth.get_user(decoded_token["uid"])

            if not user.email_verified:
                st.session_state["authentication_status"] = False
                st.session_state["login_error_message"] = (
                    "Please verify your e-mail address."
                )
                return None

            self._update_session_state_after_login(user)
            return user

        except Exception as e:
            st.session_state["authentication_status"] = False
            st.session_state["login_error_message"] = (
                f"An error occurred during login: {str(e)}"
            )
            return None

    def _update_session_state_after_login(self, user: auth.UserRecord) -> None:
        """Update session state after successful login."""
        st.session_state.update(
            {
                "name": user.display_name,
                "username": user.email,
                "roles": get_user_roles(user.uid),
                "company": get_user_company(user.uid),
                "authentication_status": True,
                "login_error_message": None,
                "success_message": None,
            }
        )

    def logout(self) -> None:
        """Handle user logout process."""
        st.session_state["is_logging_out"] = True

        # Clear session state
        for key in [
            "name",
            "username",
            "roles",
            "company",
            "authentication_status",
            "login_error_message",
            "success_message",
        ]:
            st.session_state[key] = None

        st.cache_data.clear()

        # Delete cookie
        try:
            self.cookie_manager.delete(self.cookie_name)
            exp_date = datetime.now(timezone.utc) - timedelta(days=1)
            self.cookie_manager.set(
                self.cookie_name,
                "",
                expires_at=exp_date,
            )
        except Exception as e:
            print(f"Error during cookie deletion: {e}")

    def token_encode(self, exp_date: datetime) -> str:
        """Encode JWT token for session management."""
        return jwt.encode(
            {
                "name": st.session_state["name"],
                "username": st.session_state["username"],
                "roles": st.session_state["roles"],
                "company": st.session_state["company"],
                "exp_date": exp_date.timestamp(),
            },
            self.cookie_key,
            algorithm="HS256",
        )

    @property
    def cookie_is_valid(self) -> bool:
        """Validate session cookie and update session state accordingly."""
        token = self.cookie_manager.get(self.cookie_name)

        if token is None:
            st.session_state["authentication_status"] = None
            return False

        try:
            decoded_token = jwt.decode(token, self.cookie_key, algorithms=["HS256"])

            if (
                isinstance(decoded_token, dict)
                and decoded_token["exp_date"] > datetime.now(timezone.utc).timestamp()
                and {"name", "username"}.issubset(set(decoded_token))
            ):
                st.session_state.update(
                    {
                        "name": decoded_token["name"],
                        "username": decoded_token["username"],
                        "roles": decoded_token.get("roles"),
                        "company": decoded_token.get("company"),
                        "authentication_status": True,
                        "login_error_message": None,
                        "success_message": None,
                    }
                )
                return True

        except Exception as e:
            print(f"Error decoding token: {e}")

        st.session_state["authentication_status"] = None
        return False

    @property
    def login_form(self) -> None:
        """Render login form with improved error handling and UX."""
        if st.session_state["authentication_status"]:
            return None

        with st.form("Login"):
            message_placeholder = st.empty()

            email = st.text_input("E-mail")
            if "@" not in email and isinstance(self.preauthorized, str):
                email = f"{email}@{self.preauthorized}"
            st.session_state["username"] = email

            password = st.text_input("Password", type="password")

            if st.form_submit_button("Login", type="primary"):
                st.session_state["login_error_message"] = None
                st.session_state["success_message"] = None

                user = self.login_user(email, password)
                if user:
                    exp_date = datetime.now(timezone.utc) + timedelta(
                        days=self.cookie_expiry_days
                    )
                    self.cookie_manager.set(
                        self.cookie_name,
                        self.token_encode(exp_date),
                        expires_at=exp_date,
                    )
                    st.rerun()

            self._display_messages(message_placeholder)

    def _display_messages(self, placeholder: DeltaGenerator) -> None:
        """Display error or success messages in the UI."""
        if st.session_state.get("login_error_message"):
            placeholder.error(st.session_state["login_error_message"], icon="🚨")
        elif st.session_state.get("success_message"):
            placeholder.success(st.session_state["success_message"], icon="✅")
        else:
            placeholder.empty()

    @property
    def login_panel(self) -> None:
        """Render login panel with user information and logout option."""
        try:
            greeting_name = (
                st.session_state["username"].split("@")[0]
                if st.session_state["name"] is None
                else st.session_state["name"]
            )
            st.write(f"Welcome, *{greeting_name}*!")
        except Exception:
            pass

        if st.button("Logout", type="primary"):
            self.logout()
            st.rerun()

        with st.expander("Account configuration"):
            user_tab1, user_tab2 = st.tabs(["Reset password", "Update user details"])
            with user_tab1:
                self.update_password_form
            with user_tab2:
                self.update_display_name_form

    @property
    def not_logged_in(self) -> bool:
        """Handle unauthenticated user state."""
        if st.session_state.get("is_logging_out"):
            st.session_state["is_logging_out"] = False
            st.session_state["authentication_status"] = None
            st.session_state["login_error_message"] = None
            st.session_state["success_message"] = None
            return True

        if st.session_state["authentication_status"] is True:
            return False

        # If authentication status is None, it means the user is not authenticated.
        # Return True to indicate that the user is not logged in.
        if st.session_state["authentication_status"] is None:
            return True

        return False

    def hide_unauthorized_pages(self, pages_roles: Dict) -> None:
        """Hide pages based on user roles."""
        user_roles = st.session_state.get("roles")
        if not user_roles:
            return

        pages_to_hide = [
            page
            for page, authorized_page_roles in pages_roles.items()
            if not any(role in authorized_page_roles["roles"] for role in user_roles)
        ]

        css_pages_to_hide = "\n\t".join(
            [
                f'.st-emotion-cache-j7qwjs.eczjsme12 a[data-testid="stSidebarNavLink"][href*="{page_name}"] > span.st-emotion-cache-1m6wrpk.eczjsme10 {{display: none;}}'
                for page_name in pages_to_hide
            ]
        )

        st.markdown(
            f"""
            <style>
                {css_pages_to_hide}
            </style>
            """,
            unsafe_allow_html=True,
        )

    @property
    def register_user_form(self) -> None:
        """Creates a Streamlit widget for user registration.

        Password strength is validated using entropy bits (the power of the password alphabet).
        Upon registration, a validation link is sent to the user's email address.
        """
        user_type = st.radio("User type", options=["Internal", "External"], index=None)

        if not user_type:
            return

        with st.form(key="register_form"):
            email = st.text_input("E-mail")
            name = st.text_input("Name")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")

            if user_type == "External":
                business_data = get_business_data()
                active_companies = business_data["clients"]
                company = st.selectbox("Company", options=active_companies, index=None)
                if email:
                    self.preauthorized = email.split("@")[1]
            elif user_type == "Internal":
                user_type = "Connecta"
                company = "Connecta"
            else:
                company = None

            active_roles = [
                role for role in self.active_roles if role.startswith(user_type.lower())
            ]

            roles = st.multiselect(
                "Roles",
                options=active_roles,
                default="connecta-viewer" if user_type == "Connecta" else None,
            )

            register_button = st.form_submit_button(label="Submit")

        if not register_button:
            return None
        # Below are some checks to ensure proper and secure registration

        if password != confirm_password:
            st.session_state["login_error_message"] = "Passwords do not match"
            st.session_state["success_message"] = None
            return None

        if not name:
            st.session_state["login_error_message"] = "Please enter your name"
            st.session_state["success_message"] = None
            return None
        if "@" not in email and isinstance(self.preauthorized, str):
            email = f"{email}@{self.preauthorized}"

        if self.preauthorized and not email.endswith(self.preauthorized):
            st.session_state["login_error_message"] = "Domain not allowed"
            st.session_state["success_message"] = None
            return None

        if not roles:
            st.session_state["login_error_message"] = "Please select at least one role"
            st.session_state["success_message"] = None
            return None
        try:
            validate_email(email, check_deliverability=True)
        except EmailNotValidError as e:
            st.session_state["login_error_message"] = str(e)
            st.session_state["success_message"] = None
            return None

        # Need a password that has minimum 66 entropy bits (the power of its alphabet)
        # I multiply this number by 1.5 to display password strength with st.progress
        # For an explanation, read this -
        # https://en.wikipedia.org/wiki/Password_strength#Entropy_as_a_measure_of_password_strength
        alphabet_chars = len(set(password))
        strength = int(len(password) * math.log2(alphabet_chars) * 1.5)
        if strength < 100:
            st.progress(strength)
            st.session_state["login_error_message"] = (
                "Password is too weak. Please choose a stronger password."
            )
            st.session_state["success_message"] = None
            return None

        if (
            "login_error_message" in st.session_state
            and st.session_state["login_error_message"]
        ):
            st.error(st.session_state["login_error_message"])
            return None

        user = auth.create_user(
            email=email,
            password=password,
            display_name=name,
            email_verified=False,
            disabled=False,
        )

        self.assign_user_metadata(user.uid, roles, company)

        # Having registered the user, send them a verification e-mail
        token = self.authenticate_user(
            email, password, require_email_verification=False
        )["idToken"]
        url = f"{POST_REQUEST_URL_BASE}sendOobCode?key={self.firebase_api_key}"
        payload = {"requestType": "VERIFY_EMAIL", "idToken": token}
        response = self.post_request(url, json=payload)
        if response.status_code != 200:
            st.session_state["login_error_message"] = (
                f"Error sending verification email: {self._parse_error_message(response)}"
            )
            st.session_state["success_message"] = None
            return None
        st.session_state["success_message"] = (
            "Your account has been created successfully. To complete the registration process, "
            "please verify your email address by clicking on the link we have sent to your inbox."
        )
        st.session_state["login_error_message"] = None
        return st.balloons()

    def assign_user_metadata(self, uid: str, roles: list[str], company: str):
        db = firestore.client()
        db.collection("users").document(uid).set({"roles": roles, "company": company})

    @property
    def active_roles(self) -> tuple[str]:
        db = firestore.client()
        document = db.collection("settings").document("roles").get()

        if document.exists:
            roles_info = document.to_dict()
            roles = tuple(roles_info["active"])
            return roles
        else:
            st.warning("There are no active roles registered.")

    @property
    def update_password_form(self) -> None:
        """Creates a Streamlit widget to update a user's password."""
        col1, _, _ = st.columns(3)
        # Get the email and password from the user
        new_password = col1.text_input("New password", key="new_password")
        confirm_new_password = col1.text_input(
            "Confirm new password", key="confirm_new_password"
        )
        # Attempt to log the user in
        if not st.button("Update password"):
            return None
        if new_password != confirm_new_password:
            st.session_state["login_error_message"] = "The passwords do not match."
            st.session_state["success_message"] = None
            return None
        user = auth.get_user_by_email(st.session_state["username"])
        auth.update_user(user.uid, password=new_password)
        st.session_state["success_message"] = "Successfully updated user password."
        st.session_state["login_error_message"] = None
        return None

    @property
    def update_display_name_form(self) -> None:
        """Creates a Streamlit widget to update a user's display name."""
        col1, _, _ = st.columns(3)

        # Get the email and password from the user
        new_name = col1.text_input("New name", key="new name")
        # Attempt to log the user in
        if not st.button("Update name"):
            return None
        user = auth.get_user_by_email(st.session_state["username"])
        auth.update_user(user.uid, display_name=new_name)
        st.session_state["name"] = new_name
        # Update the cookie as well
        exp_date = datetime.now(timezone.utc) + timedelta(days=self.cookie_expiry_days)
        self.cookie_manager.set(
            self.cookie_name,
            self.token_encode(exp_date),
            expires_at=exp_date,
        )
        st.session_state["success_message"] = "Successfully updated user display name."
        st.session_state["login_error_message"] = None
        return None


@st.cache_resource(experimental_allow_widgets=True)
def get_authenticator():
    """Get or create an instance of AuthenticatorV2."""
    cookie_manager = stx.CookieManager()
    return Authenticator(
        os.getenv("FIREBASE_API_KEY"), os.getenv("COOKIE_KEY"), cookie_manager
    )


@st.cache_data(show_spinner=False, ttl=600)
def get_page_roles() -> Dict[str, Dict[str, List]]:
    """Get page roles from Firestore."""
    db = firestore.client()
    documents = db.collection("pages").stream()
    return {document.id: document.to_dict() for document in documents}


@st.cache_data(show_spinner=False, ttl=600)
def get_user_roles(user_uid: str) -> Tuple[str, ...]:
    """Get user roles from Firestore."""
    db = firestore.client()
    document = db.collection("users").document(user_uid).get()

    if document.exists:
        user_info = document.to_dict()
        return tuple(user_info["roles"])
    return ("connecta-viewer",)


@st.cache_data(show_spinner=False)
def get_user_company(user_uid: str) -> Optional[str]:
    """Get user company from Firestore."""
    db = firestore.client()
    document = db.collection("users").document(user_uid).get()

    if document.exists:
        user_info = document.to_dict()
        return user_info.get("company")
    return None
