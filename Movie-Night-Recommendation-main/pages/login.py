import streamlit as st
import hashlib
from database.db import SessionLocal
from database.models import User


# -------------------- HASH FUNCTIONS --------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    return hashlib.sha256(password.encode()).hexdigest() == hashed


# -------------------- LOGIN PAGE --------------------
def login_page():
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    left_spacer, center_col, right_spacer = st.columns([1.1, 1.4, 1.1])

    with center_col:
        st.title("Movie Night Recommender")
        tab1, tab2 = st.tabs(["Login", "Register"])

        # ---------------- LOGIN ----------------
        with tab1:
            st.header("Login")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login"):
                db = SessionLocal()
                user = db.query(User).filter(User.email == email).first()
                db.close()

                if user and verify_password(password, user.password_hash):
                    st.session_state.user = user
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

        # ---------------- REGISTER ----------------
        with tab2:
            st.header("Register")
            name = st.text_input("Name", key="reg_name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_password")

            if st.button("Register"):
                db = SessionLocal()
                existing = db.query(User).filter(User.email == email).first()

                if existing:
                    db.close()
                    st.error("Email already exists")
                else:
                    hashed = hash_password(password)
                    new_user = User(name=name, email=email, password_hash=hashed)
                    db.add(new_user)
                    db.commit()
                    db.close()
                    st.success("Registered! Please login.")

        # ---------------- LOGOUT ----------------
        if 'user' in st.session_state:
            st.write(f"Welcome, {st.session_state.user.name}!")
            if st.button("Logout"):
                del st.session_state.user
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
