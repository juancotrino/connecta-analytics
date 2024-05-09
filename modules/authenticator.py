from datetime import datetime
from contextlib import suppress
import json
import requests
import jwt
import streamlit as st
import extra_streamlit_components as stx

class Authenticator:
    def __init__(self, config: dict) -> None:
        self.api_key = config["apiKey"]
        self.cookie_manager = stx.CookieManager()

    def cookie_is_valid(self, cookie_manager: stx.CookieManager, cookie_name: str) -> bool:
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

        token = self.cookie_manager.get(cookie_name)
        if token is None:
            return False
        with suppress(Exception):
            token = jwt.decode(token, st.secrets["COOKIE_KEY"], algorithms=["HS256"])
        if (
            token
            and not st.session_state["logout"]
            and token["exp_date"] > datetime.utcnow().timestamp()
            and {"name", "username"}.issubset(set(token))
        ):
            st.session_state["name"] = token["name"]
            st.session_state["username"] = token["username"]
            st.session_state["authentication_status"] = True
            return True
        return False

    ## -------------------------------------------------------------------------------------------------
    ## Firebase Auth API -------------------------------------------------------------------------------
    ## -------------------------------------------------------------------------------------------------

    def sign_in_with_email_and_password(self, email, password):
        request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
        request_object = requests.post(request_ref, headers=headers, data=data)
        self.raise_detailed_error(request_object)
        return request_object.json()

    def get_account_info(self, id_token):
        request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getAccountInfo?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"idToken": id_token})
        request_object = requests.post(request_ref, headers=headers, data=data)
        self.raise_detailed_error(request_object)
        return request_object.json()

    def send_email_verification(self, id_token):
        request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getOobConfirmationCode?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"requestType": "VERIFY_EMAIL", "idToken": id_token})
        request_object = requests.post(request_ref, headers=headers, data=data)
        self.raise_detailed_error(request_object)
        return request_object.json()

    def send_password_reset_email(self, email):
        request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getOobConfirmationCode?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"requestType": "PASSWORD_RESET", "email": email})
        request_object = requests.post(request_ref, headers=headers, data=data)
        self.raise_detailed_error(request_object)
        return request_object.json()

    def create_user_with_email_and_password(self, email, password):
        request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8" }
        data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
        request_object = requests.post(request_ref, headers=headers, data=data)
        self.raise_detailed_error(request_object)
        return request_object.json()

    def delete_user_account(self, id_token):
        request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/deleteAccount?key={0}".format(self.api_key)
        headers = {"content-type": "application/json; charset=UTF-8"}
        data = json.dumps({"idToken": id_token})
        request_object = requests.post(request_ref, headers=headers, data=data)
        self.raise_detailed_error(request_object)
        return request_object.json()

    def raise_detailed_error(self, request_object):
        try:
            request_object.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise requests.exceptions.HTTPError(error, request_object.text)

    ## -------------------------------------------------------------------------------------------------
    ## Authentication functions ------------------------------------------------------------------------
    ## -------------------------------------------------------------------------------------------------

    def sign_in(self, email:str, password:str) -> None:
        try:
            # Attempt to sign in with email and password
            id_token = self.sign_in_with_email_and_password(email,password)['idToken']

            # Get account information
            user_info = self.get_account_info(id_token)["users"][0]

            # If email is not verified, send verification email and do not sign in
            if not user_info["emailVerified"]:
                self.send_email_verification(id_token)
                st.session_state.auth_warning = 'Check your email to verify your account'

            # Save user info to session state and rerun
            else:
                st.session_state.user_info = user_info
                st.rerun()

        except requests.exceptions.HTTPError as error:
            error_message = json.loads(error.args[1])['error']['message']
            if error_message in {"INVALID_EMAIL", "EMAIL_NOT_FOUND", "INVALID_PASSWORD", "MISSING_PASSWORD", "INVALID_LOGIN_CREDENTIALS"}:
                st.session_state.auth_warning = 'Error: Use a valid email and password'
            else:
                print(error_message)
                st.session_state.auth_warning = 'Error: Please try again later'

        except Exception as error:
            print(error)
            st.session_state.auth_warning = 'Error: Please try again later'


    def create_account(self, email:str, password:str) -> None:
        try:
            # Create account (and save id_token)
            id_token = self.create_user_with_email_and_password(email,password)['idToken']

            # Create account and send email verification
            self.send_email_verification(id_token)
            st.session_state.auth_success = 'Check your inbox to verify your email'

        except requests.exceptions.HTTPError as error:
            error_message = json.loads(error.args[1])['error']['message']
            if error_message == "EMAIL_EXISTS":
                st.session_state.auth_warning = 'Error: Email belongs to existing account'
            elif error_message in {"INVALID_EMAIL","INVALID_PASSWORD","MISSING_PASSWORD","MISSING_EMAIL","WEAK_PASSWORD"}:
                st.session_state.auth_warning = 'Error: Use a valid email and password'
            else:
                st.session_state.auth_warning = 'Error: Please try again later'

        except Exception as error:
            print(error)
            st.session_state.auth_warning = 'Error: Please try again later'


    def reset_password(self, email:str) -> None:
        try:
            self.send_password_reset_email(email)
            st.session_state.auth_success = 'Password reset link sent to your email'

        except requests.exceptions.HTTPError as error:
            error_message = json.loads(error.args[1])['error']['message']
            if error_message in {"MISSING_EMAIL","INVALID_EMAIL","EMAIL_NOT_FOUND"}:
                st.session_state.auth_warning = 'Error: Use a valid email'
            else:
                st.session_state.auth_warning = 'Error: Please try again later'

        except Exception:
            st.session_state.auth_warning = 'Error: Please try again later'


    def sign_out(self) -> None:
        st.session_state.clear()
        st.session_state.auth_success = 'You have successfully signed out'


    def delete_account(self, password:str) -> None:
        try:
            # Confirm email and password by signing in (and save id_token)
            id_token = self.sign_in_with_email_and_password(st.session_state.user_info['email'],password)['idToken']

            # Attempt to delete account
            self.delete_user_account(id_token)
            st.session_state.clear()
            st.session_state.auth_success = 'You have successfully deleted your account'

        except requests.exceptions.HTTPError as error:
            error_message = json.loads(error.args[1])['error']['message']
            print(error_message)

        except Exception as error:
            print(error)


firebase_credentials = {
    'apiKey': "AIzaSyBWZK134ehI9cuRj3SSSyi-JQJihKHgdvg",
    'authDomain': "streamlit-test-a4b4b.firebaseapp.com",
    'projectId': "streamlit-test-a4b4b",
    'storageBucket': "streamlit-test-a4b4b.appspot.com",
    'messagingSenderId': "442438202784",
    'appId': "1:442438202784:web:0ada18316dc7e7542960c5",
    'measurementId': "G-G04XCHFESB",
    "databaseURL": ""
}

authenticator = Authenticator(firebase_credentials)

def authentication():

    _, col2, _ = st.columns([1, 2, 1])
    col2.header('Login')
    # Authentication form layout
    # do_you_have_an_account = col2.selectbox(label='Do you have an account?',options=('Yes','No','I forgot my password'))
    auth_form = col2.form(key='Authentication form', clear_on_submit=False)
    email = auth_form.text_input(label='Email')
    password = auth_form.text_input(label='Password', type='password')
    auth_notification = col2.empty()

    # Sign In
    if auth_form.form_submit_button(label='Sign In',use_container_width=True,type='primary'):
        with auth_notification, st.spinner('Signing in'):
            authenticator.sign_in(email, password)

        return st.session_state.user_info

    # Authentication success and warning messages
    if 'auth_success' in st.session_state:
        auth_notification.success(st.session_state.auth_success)
        del st.session_state.auth_success
    elif 'auth_warning' in st.session_state:
        auth_notification.warning(st.session_state.auth_warning)
        del st.session_state.auth_warning
