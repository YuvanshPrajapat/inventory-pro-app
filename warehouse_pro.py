import streamlit as st
import streamlit_authenticator as stauth
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

# --- 1. DATABASE CONNECTION ---
def get_connection():
    # In Streamlit Cloud, use st.secrets. Locally, you can replace with your string.
    try:
        return psycopg2.connect(st.secrets["postgres_url"])
    except:
        # Fallback for local testing if secrets aren't set
        return psycopg2.connect(
            host="localhost",
            database="inventory_system",
            user="postgres",
            password="YOUR_PASSWORD"
        )

# --- 2. AUTHENTICATION LOGIC ---
def fetch_users():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT username, name, password_hash as password FROM users")
                return cur.fetchall()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return []

db_users = fetch_users()
credentials = {
    "usernames": {
        u['username']: {
            "name": u['name'],
            "password": u['password']
        } for u in db_users
    }
}

# Initialize Authenticator (v0.3+ Syntax)
authenticator = stauth.Authenticate(
    credentials,
    "inventory_manager_cookie",
    "auth_signature_key",
    cookie_expiry_days=30
)

# The new version often only requires the label or uses keyword arguments
try:
    # Try the most modern syntax
    authenticator.login(location='main')
except:
    # Fallback for slightly older versions
    authenticator.login("Login", "main")

# Then access the status from the session state
authentication_status = st.session_state["authentication_status"]
name = st.session_state["name"]
username = st.session_state["username"]

if authentication_status:
    # --- AUTHENTICATED AREA ---
    st.sidebar.title(f"Welcome, {name}")
    authenticator.logout("Logout", "sidebar")
    
    st.title("🛡️ Warehouse Pro: Ledger Edition")
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Operations", "📜 Audit Log"])

    # --- TAB 1: DASHBOARD ---
    with tab1:
        st.header("Live Inventory Status")
        col_in1, col_in2 = st.columns([1, 2])
        with col_in1:
            threshold = st.number_input("Low Stock Alert Level", min_value=1, value=5)
        with col_in2:
            search_query = st.text_input("🔍 Search SKU or Product Name", "").strip().upper()

        if st.button("🔄 Refresh Data"):
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM current_stock;")
                    rows = cur.fetchall()
                    if rows:
                        df = pd.DataFrame(rows)
                        low_stock_items = [r for r in rows if r['total_qty'] <= threshold]
                        
                        # Metrics
                        st.divider()
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Unique Products", len(df['sku'].unique()))
                        m2.metric("Total Units", int(df['total_qty'].sum()))
                        m3.metric("Low Stock Alerts", len(low_stock_items))

                        # Search Filter
                        if search_query:
                            df = df[df['name'].str.upper().str.contains(search_query) | 
                                    df['sku'].str.contains(search_query)]

                        # Table with Highlighting
                        def highlight_rows(s):
                            return ['background-color: #ffcccc' if s.total_qty <= threshold else '' for _ in s]
                        
                        st.dataframe(df.style.apply(highlight_rows, axis=1), use_container_width=True, hide_index=True)
                        
                        # Export
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download CSV Report", data=csv, file_name='stock_report.csv')

    # --- TAB 2: OPERATIONS ---
    with tab2:
        st.subheader("Process Transactions")
        op_sku = st.text_input("Target SKU").upper()
        op_type = st.selectbox("Type", ["sale", "shipment", "return"])
        op_qty = st.number_input("Quantity", min_value=1)

        if st.button("Execute Transaction"):
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        if op_type == "sale":
                            cur.execute("SELECT process_sale(%s, 'MDC', %s)", (op_sku, op_qty))
                            msg = cur.fetchone()[0]
                        else:
                            qty = op_qty if op_type != "sale" else -op_qty
                            cur.execute("""
                                INSERT INTO inventory_ledger (product_id, warehouse_id, change_amount, reason)
                                VALUES ((SELECT product_id FROM products WHERE sku=%s), 
                                        (SELECT warehouse_id FROM warehouses WHERE code='MDC'), %s, %s)
                            """, (op_sku, qty, op_type))
                            msg = "Stock successfully updated!"
                    conn.commit()
                st.success(msg)
            except Exception as e:
                st.error(f"Transaction Denied: {e}")

    # --- TAB 3: AUDIT LOG ---
    with tab3:
        st.header("Transaction Ledger")
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT l.created_at, p.sku, p.name, l.change_amount, l.reason 
                    FROM inventory_ledger l 
                    JOIN products p ON l.product_id = p.product_id 
                    ORDER BY l.created_at DESC LIMIT 50
                """)
                st.table(cur.fetchall())

elif authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your credentials")