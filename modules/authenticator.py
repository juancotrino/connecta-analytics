import os
import math
import time
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from functools import partial

import extra_streamlit_components as stx
import jwt
import requests
import streamlit as st
from email_validator import EmailNotValidError, validate_email
from firebase_admin import auth, firestore


POST_REQUEST_URL_BASE = "https://identitytoolkit.googleapis.com/v1/accounts:"


class Authenticator:
    def __init__(
        self,
        firebase_api_key: str,
        cookie_key: str,
        cookie_expiry_days: int = 30,
        cookie_name: str = "login_cookie",
        preauthorized: str = "connecta.com.co"
    ) -> None:
        self.firebase_api_key = firebase_api_key
        self.cookie_key = cookie_key
        self.post_request_url_base = POST_REQUEST_URL_BASE
        self.post_request = partial(
            requests.post,
            headers={"content-type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        self.success_message = partial(st.success, icon="✅")
        self.error_message = partial(st.error, icon="🚨")
        self.cookie_manager = stx.CookieManager()
        self.cookie_expiry_days = cookie_expiry_days
        self.cookie_name = cookie_name
        self.preauthorized = preauthorized

    def parse_error_message(
        self,
        response: requests.Response
    ) -> str:
        """
        Parses an error message from a requests.Response object and makes it look better.

        Parameters:
            response (requests.Response): The response object to parse.

        Returns:
            str: Prettified error message.

        Raises:
            KeyError: If the 'error' key is not present in the response JSON.
        """
        return (
            response.json()["error"]["message"]
            .casefold()
            .replace("_", " ")
            .replace("email", "e-mail")
        )

    def authenticate_user(
        self,
        email: str,
        password: str,
        require_email_verification: bool = True
    ) -> dict[str, str | bool | int] | None:
        """
        Authenticates a user with the given email and password using the Firebase Authentication
        REST API.

        Parameters:
            email (str): The email address of the user to authenticate.
            password (str): The password of the user to authenticate.
            require_email_verification (bool): Specify whether a user has to be e-mail verified to
            be authenticated

        Returns:
            dict or None: A dictionary containing the authenticated user's ID token, refresh token,
            and other information, if authentication was successful. Otherwise, None.

        Raises:
            requests.exceptions.RequestException: If there was an error while authenticating the user.
        """

        url = f"{self.post_request_url_base}signInWithPassword?key={self.firebase_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
            "emailVerified": require_email_verification,
        }
        response = self.post_request(url, json=payload)
        if response.status_code != 200:
            self.error_message(f"Authentication failed: {self.parse_error_message(response)}")
            return None
        response = response.json()
        if require_email_verification and "idToken" not in response:
            self.error_message("Invalid e-mail or password.")
            return None

        return response

    def get_user_roles(
        self,
        user_uid: str
    ) -> tuple[str]:
        db = firestore.client()
        document = db.collection("users").document(user_uid).get()

        if document.exists:
            user_info = document.to_dict()
            roles = tuple(user_info['roles'])
        else:
            roles = ('basic', )

        return roles

    @property
    def forgot_password_form(self) -> None:
        """Creates a Streamlit widget to reset a user's password. Authentication uses
        the Firebase Authentication REST API.

        Parameters:
            preauthorized (Union[str, Sequence[str], None]): An optional domain or a list of
            domains which are authorized to register.
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
            return self.success_message(f"Password reset link has been sent to {email}")
        return self.error_message(f"Error sending password reset email: {self.parse_error_message(response)}")

    @property
    def register_user_form(self) -> None:
        """Creates a Streamlit widget for user registration.

        Password strength is validated using entropy bits (the power of the password alphabet).
        Upon registration, a validation link is sent to the user's email address.

        Parameters:
            preauthorized (Union[str, Sequence[str], None]): An optional domain or a list of
            domains which are authorized to register.
        """

        with st.form(key="register_form"):
            email =  st.text_input("E-mail")
            name = st.text_input("Name")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            roles = st.multiselect("Roles", options=self.active_roles, default='connecta-viewer')
            register_button = st.form_submit_button(label="Submit")

        if not register_button:
            return None
        # Below are some checks to ensure proper and secure registration
        if password != confirm_password:
            return self.error_message("Passwords do not match")
        if not name:
            return self.error_message("Please enter your name")
        if "@" not in email and isinstance(self.preauthorized, str):
            email = f"{email}@{self.preauthorized}"
        if self.preauthorized and not email.endswith(self.preauthorized):
            return self.error_message("Domain not allowed")
        try:
            validate_email(email, check_deliverability=True)
        except EmailNotValidError as e:
            return self.error_message(e)

        # Need a password that has minimum 66 entropy bits (the power of its alphabet)
        # I multiply this number by 1.5 to display password strength with st.progress
        # For an explanation, read this -
        # https://en.wikipedia.org/wiki/Password_strength#Entropy_as_a_measure_of_password_strength
        alphabet_chars = len(set(password))
        strength = int(len(password) * math.log2(alphabet_chars) * 1.5)
        if strength < 100:
            st.progress(strength)
            return st.warning(
                "Password is too weak. Please choose a stronger password.", icon="⚠️"
            )
        user = auth.create_user(
            email=email, password=password, display_name=name, email_verified=False
        )

        self.assign_user_role(user.uid, roles)

        # Having registered the user, send them a verification e-mail
        token = self.authenticate_user(
            email,
            password,
            require_email_verification=False
        )["idToken"]
        url = f"{POST_REQUEST_URL_BASE}sendOobCode?key={self.firebase_api_key}"
        payload = {"requestType": "VERIFY_EMAIL", "idToken": token}
        response = self.post_request(url, json=payload)
        if response.status_code != 200:
            return self.error_message(f"Error sending verification email: {self.parse_error_message(response)}")
        self.success_message(
            "Your account has been created successfully. To complete the registration process, "
            "please verify your email address by clicking on the link we have sent to your inbox."
        )
        return st.balloons()

    def assign_user_role(self, uid: str, roles: list[str]):
        db = firestore.client()
        db.collection("users").document(uid).set({'roles': roles})

    @property
    def active_roles(self) -> tuple[str]:
        db = firestore.client()
        document = db.collection("settings").document("roles").get()

        if document.exists:
            roles_info = document.to_dict()
            roles = tuple(roles_info['active'])
            return roles
        else:
            st.warning('There are no active roles registered.')

    @property
    def update_password_form(self) -> None:
        """Creates a Streamlit widget to update a user's password."""
        col1, _, _ = st.columns(3)
        # Get the email and password from the user
        new_password = col1.text_input("New password", key="new_password")
        confirm_new_password = col1.text_input("Confirm new password", key="confirm_new_password")
        # Attempt to log the user in
        if not st.button("Update password"):
            return None
        if new_password != confirm_new_password:
            return self.error_message("The passwords do not match.")
        user = auth.get_user_by_email(st.session_state["username"])
        auth.update_user(user.uid, password=new_password)
        return self.success_message("Successfully updated user password.")

    @property
    def update_display_name_form(self) -> None:
        """Creates a Streamlit widget to update a user's display name.

        Parameters
        ----------
        - cookie_manager : stx.CookieManager
            A JWT cookie manager instance for Streamlit
        - cookie_name : str
            The name of the reauthentication cookie.
        - cookie_expiry_days: (optional) str
            An integer representing the number of days until the cookie expires
        """
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
        return self.success_message("Successfully updated user display name.")


    def token_encode(
        self,
        exp_date: datetime
    ) -> str:
        """Encodes a JSON Web Token (JWT) containing user session data for passwordless
        reauthentication.

        Parameters
        ----------
        exp_date : datetime
            The expiration date of the JWT.

        Returns
        -------
        str
            The encoded JWT cookie string for reauthentication.

        Notes
        -----
        The JWT contains the user's name, username, and the expiration date of the JWT in
        timestamp format. The `os.getenv("COOKIE_KEY")` value is used to sign the JWT with
        the HS256 algorithm.
        """
        return jwt.encode(
            {
                "name": st.session_state["name"],
                "username": st.session_state["username"],
                "roles": st.session_state["roles"],
                "exp_date": exp_date.timestamp(),
            },
            self.cookie_key,
            algorithm="HS256",
        )

    @property
    def cookie_is_valid(self) -> bool:
        """Check if the reauthentication cookie is valid and, if it is, update the session state.

        Parameters
        ----------
        - cookie_manager : stx.CookieManager
            A JWT cookie manager instance for Streamlit
        - cookie_name : str
            The name of the reauthentication cookie.
        - cookie_expiry_days: (optional) str
            An integer representing the number of days until the cookie expires

        Returns
        -------
        bool
            True if the cookie is valid and the session state is updated successfully; False otherwise.

        Notes
        -----
        This function checks if the specified reauthentication cookie is present in the cookies stored by
        the cookie manager, and if it is valid. If the cookie is valid, this function updates the session
        state of the Streamlit app and authenticates the user.
        """
        time.sleep(0.3)
        token = self.cookie_manager.get(self.cookie_name)

        # In case of a first run, pre-populate missing session state arguments
        for key in {"name", "authentication_status", "username", "roles"}.difference(
            set(st.session_state)
        ):
            st.session_state[key] = None

        if token is None:
            return False

        with suppress(Exception):
            token = jwt.decode(token, self.cookie_key, algorithms=["HS256"])

        if (
            token
            and token["exp_date"] > datetime.now(timezone.utc).timestamp()
            and {"name", "username"}.issubset(set(token))
        ):
            st.session_state["name"] = token["name"]
            st.session_state["username"] = token["username"]
            st.session_state["roles"] = token["roles"]
            st.session_state["authentication_status"] = True
            return True
        return False


    def login_user(
        self,
        email: str,
        password: str
    ):
        # Authenticate the user with Firebase REST API
        login_response = self.authenticate_user(email, password)
        if not login_response:
            return None

        try:
            decoded_token = auth.verify_id_token(login_response["idToken"])
            user = auth.get_user(decoded_token["uid"])
            if not user.email_verified:
                return self.error_message("Please verify your e-mail address.")
            return user
        except Exception as e:
            print(f'Error: {e}')

    @property
    def login_form(self) -> None:
        """Creates a login widget using Firebase REST API and a cookie manager.

        Parameters
        ----------
        - cookie_manager : stx.CookieManager
            A JWT cookie manager instance for Streamlit
        - cookie_name : str
            The name of the reauthentication cookie.
        - cookie_expiry_days: (optional) str
            An integer representing the number of days until the cookie expires

        Notes
        -----

        If the user has already been authenticated, this function does nothing. Otherwise, it displays
        a login form which prompts the user to enter their email and password. If the login credentials
        are valid and the user's email address has been verified, the user is authenticated and a
        reauthentication cookie is created with the specified expiration date.
        """

        if st.session_state["authentication_status"]:
            return None
        with st.form("Login"):
            email = st.text_input("E-mail")
            if "@" not in email and isinstance(self.preauthorized, str):
                email = f"{email}@{self.preauthorized}"
            st.session_state["username"] = email
            password = st.text_input("Password", type="password")

            if st.form_submit_button('Login', type="primary"):
                user = self.login_user(email, password)
                if user:
                    st.session_state["name"] = user.display_name
                    st.session_state["username"] = user.email
                    st.session_state["roles"] = self.get_user_roles(user.uid)
                    st.session_state["authentication_status"] = True
                    exp_date = datetime.now(timezone.utc) + timedelta(days=self.cookie_expiry_days)

                    self.cookie_manager.set(
                        self.cookie_name,
                        self.token_encode(exp_date),
                        expires_at=exp_date
                    )

                    time.sleep(0.12)

    @property
    def login_panel(self) -> None:
        """Creates a side panel for logged-in users, preventing the login menu from
        appearing.

        Parameters
        ----------
        - cookie_manager : stx.CookieManager
            A JWT cookie manager instance for Streamlit
        - cookie_name : str
            The name of the reauthentication cookie.
        - cookie_expiry_days: (optional) str
            An integer representing the number of days until the cookie expires

        Notes
        -----
        If the user is logged in, this function displays two tabs for resetting the user's password
        and updating their display name.

        If the user clicks the "Logout" button, the reauthentication cookie and user-related information
        from the session state is deleted, and the user is logged out.
        """

        try:
            greeting_name = st.session_state['username'].split('@')[0] if st.session_state['name'] is None else st.session_state['name']
            st.write(f"Welcome, *{greeting_name}*!")
        except:
            pass

        if st.button("Logout", type="primary"):
            self.cookie_manager.delete(self.cookie_name)
            st.session_state["name"] = None
            st.session_state["username"] = None
            st.session_state["roles"] = None
            st.session_state["authentication_status"] = None
            return None

        with st.expander("Account configurarion"):

            user_tab1, user_tab2 = st.tabs(["Reset password", "Update user details"])
            with user_tab1:
                self.update_password_form
            with user_tab2:
                self.update_display_name_form

        return None

    @property
    def not_logged_in(self) -> bool:
        """Creates a tab panel for unauthenticated, preventing the user control sidebar and
        the rest of the script from appearing until the user logs in.

        Parameters
        ----------
        - cookie_manager : stx.CookieManager
            A JWT cookie manager instance for Streamlit
        - cookie_name : str
            The name of the reauthentication cookie.
        - cookie_expiry_days: (optional) str
            An integer representing the number of days until the cookie expires

        Returns
        -------
        Authentication status boolean.

        Notes
        -----
        If the user is already authenticated, the login panel function is called to create a side
        panel for logged-in users. If the function call does not update the authentication status
        because the username/password does not exist in the Firebase database, the rest of the script
        does not get executed until the user logs in.
        """
        early_return = True
        # In case of a first run, pre-populate missing session state arguments
        for key in {"name", "authentication_status", "username", "roles"}.difference(
            set(st.session_state)
        ):
            st.session_state[key] = None

        # Check authentication status
        auth_status = st.session_state["authentication_status"]

        # If the user is already authenticated or the authentication status is None, return False directly
        if auth_status is True:
            return not early_return

        _, col2, _ = st.columns(3)

        login_tabs = col2.empty()
        with login_tabs:
            login_tab1, login_tab2 = st.tabs(
                [
                    "Login",
                    "Forgot password"
                ]
            )
            with login_tab1:
                self.login_form
            with login_tab2:
                self.forgot_password_form

        auth_status = st.session_state["authentication_status"]
        if auth_status is False:
            self.error_message("Username/password is incorrect")
            return early_return
        if auth_status is None:
            return early_return
        login_tabs.empty()
        # A workaround for a bug in Streamlit -
        # https://playground.streamlit.app/?q=empty-doesnt-work
        # TLDR: element.empty() doesn't actually seem to work with a multi-element container
        # unless you add a sleep after it.
        time.sleep(0.01)

        return not early_return

    def hide_unauthorized_pages(self, pages_roles: dict):
        user_roles = st.session_state.get("roles")

        if user_roles:

            pages_to_hide = [page for page, authorized_page_roles in pages_roles.items() if not any(role in authorized_page_roles['roles'] for role in user_roles)]

            css_pages_to_hide = '\n\t'.join(
                [
                    (
                        '.st-emotion-cache-j7qwjs.eczjsme12 a[data-testid="stSidebarNavLink"][href*="{page_name}"] > span.st-emotion-cache-1m6wrpk.eczjsme10 '
                        .format(page_name=page_name)
                    ) + '{display: none;}' for page_name in pages_to_hide
                ]
            )

            st.markdown(f"""
                <style>
                    {css_pages_to_hide}
                </style>
                """,
                unsafe_allow_html=True,
            )

    def __str__(self) -> str:
        return f'cookie is valid: {self.cookie_is_valid}, not logged in {self.not_logged_in}'

@st.cache_resource(experimental_allow_widgets=True)
def get_authenticator():
    return Authenticator(
        os.getenv('FIREBASE_API_KEY'),
        os.getenv('COOKIE_KEY')
    )

@st.cache_data(show_spinner=False)
def get_page_roles() -> dict[str, dict[str, list]]:
    db = firestore.client()
    documents = db.collection("pages").stream()
    return {document.id: document.to_dict() for document in documents}
