import streamlit as st
import streamlit_authenticator as stauth
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

# --- 1. DATABASE CONNECTION ---
def get_connection():
    try:
        return psycopg2.connect(st.secrets["postgres_url"])
    except:
        return psycopg2.connect(
            host="localhost",
            database="inventory_system",
            user="postgres",
            password="YOUR_LOCAL_PASSWORD"
        )

# --- 2. DATA FETCHING ---
def fetch_users():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT username, name, password_hash as password, email FROM users")
                return cur.fetchall()
    except Exception as e:
        st.error(f"Database Error: {e}")
        return []

# --- 3. AUTHENTICATION SETUP ---
db_users = fetch_users()
credentials = {
    "usernames": {
        u['username']: {
            "name": u['name'],
            "password": u['password'],
            "email": u['email']
        } for u in db_users
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "inventory_manager_cookie",
    "auth_signature_key",
    cookie_expiry_days=30
)

# --- 4. SIGN UP & FORGOT PASSWORD UI (Pre-Login) ---
if not st.session_state.get("authentication_status"):
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("🆕 Create Account"):
            with st.form("registration_form"):
                new_email = st.text_input("Email")
                new_username = st.text_input("Username").lower()
                new_name = st.text_input("Full Name")
                new_pw = st.text_input("Password", type="password")
                if st.form_submit_button("Register"):
                    if new_email and new_username and new_pw:
                        try:
                            hashed_pw = stauth.Hasher.hash(new_pw)
                            with get_connection() as conn:
                                with conn.cursor() as cur:
                                    cur.execute(
                                        "INSERT INTO users (username, name, email, password_hash) VALUES (%s, %s, %s, %s)",
                                        (new_username, new_name, new_email, hashed_pw)
                                    )
                                conn.commit()
                            st.success("Registration successful! Please login.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("All fields are required.")

    with col2:
        with st.expander("🔑 Reset Password"):
            # Note: In a real app, this would send an email. 
            # Here, we verify the username/email and update the DB.
            with st.form("forgot_password_form"):
                user_to_reset = st.text_input("Username")
                email_to_verify = st.text_input("Registered Email")
                new_password = st.text_input("New Password", type="password")
                if st.form_submit_button("Reset Password"):
                    try:
                        with get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("SELECT * FROM users WHERE username=%s AND email=%s", (user_to_reset, email_to_verify))
                                if cur.fetchone():
                                    new_hash = stauth.Hasher.hash(new_password)
                                    cur.execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, user_to_reset))
                                    conn.commit()
                                    st.success("Password updated successfully!")
                                else:
                                    st.error("Username and Email do not match.")
                    except Exception as e:
                        st.error(f"Error: {e}")

# --- 5. MAIN LOGIN ---
authenticator.login(location='main')

if st.session_state["authentication_status"]:
    # --- LOGGED IN UI ---
    st.sidebar.title(f"Welcome, {st.session_state['name']}")
    authenticator.logout("Logout", "sidebar")
    
    st.title("🛡️ Warehouse Pro: Enterprise Edition")
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Operations", "📜 Audit Log"])

    with tab1:
        st.header("Live Inventory Status")
        # (Rest of your Dashboard code: search, metrics, table, download)
        # Use your previous dashboard code here...
        st.info("Select 'Refresh Data' to see current levels.")
        if st.button("🔄 Refresh Data"):
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM current_stock;")
                    df = pd.DataFrame(cur.fetchall())
                    st.dataframe(df, use_container_width=True)

    with tab2:
        st.header("Process Transactions")
        # Use your previous operations code here...
        sku = st.text_input("SKU").upper()
        qty = st.number_input("Quantity", min_value=1)
        if st.button("Confirm Sale"):
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT process_sale(%s, 'MDC', %s)", (sku, qty))
                        st.success(cur.fetchone()[0])
                    conn.commit()
            except Exception as e:
                st.error(f"Error: {e}")

    with tab3:
        st.header("Ledger History")
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM inventory_ledger ORDER BY created_at DESC LIMIT 20")
                st.table(cur.fetchall())

elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
elif st.session_state["authentication_status"] is None:
    st.warning("Please login to access the system.")