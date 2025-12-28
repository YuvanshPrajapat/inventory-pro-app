import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

# --- DATABASE CONNECTION ---
def get_connection():
    # This pulls the database URL from the cloud settings, NOT hardcoded
    return psycopg2.connect(st.secrets["postgres_url"])

st.set_page_config(page_title="Warehouse Pro", layout="wide")
st.title("🛡️ Warehouse Pro: Ledger Edition")

# Create Tabs for different tasks
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Add Product/Stock", "📜 Audit Log"])

# --- TAB 1: LIVE DASHBOARD ---
with tab1:
    st.header("Live Inventory Status")
    
    # 1. User Inputs for Filtering
    col_input1, col_input2 = st.columns([1, 2])
    with col_input1:
        threshold = st.number_input("Low Stock Threshold Alert", min_value=1, value=5)
    with col_input2:
        search_query = st.text_input("🔍 Search by Product Name or SKU", "").strip().upper()
    
    # 2. Trigger Data Fetch
    if st.button("🔄 Refresh & Sync Data"):
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # We pull from the SQL View we created earlier
                cur.execute("SELECT * FROM current_stock;")
                rows = cur.fetchall()
                
                if rows:
                    import pandas as pd
                    df = pd.DataFrame(rows)
                    
                    # 3. Calculate Global Metrics
                    low_stock_items = [r for r in rows if r['total_qty'] <= threshold]
                    
                    # 4. Display Quick Stats Row
                    st.divider()
                    m_col1, m_col2, m_col3 = st.columns(3)
                    with m_col1:
                        st.metric("Total Unique Products", len(df['sku'].unique()))
                    with m_col2:
                        st.metric("Total Units in Stock", int(df['total_qty'].sum()))
                    with m_col3:
                        st.metric("Low Stock Items", len(low_stock_items), delta=-len(low_stock_items), delta_color="inverse")
                    
                    # 5. Apply Search Filter (if user typed something)
                    if search_query:
                        df = df[df['name'].str.upper().str.contains(search_query) | 
                                df['sku'].str.contains(search_query)]
                    
                    # 6. Low Stock Alert Message
                    if low_stock_items:
                        st.error(f"⚠️ Critical: {len(low_stock_items)} items are below the threshold level!")

                    # 7. Define Conditional Formatting (Red for Low Stock)
                    def highlight_low_stock(s):
                        return ['background-color: #ffcccc' if s.total_qty <= threshold else '' for _ in s]
                    
                    # 8. Display the Styled Table
                    st.subheader("Inventory Detail Table")
                    st.dataframe(
                        df.style.apply(highlight_low_stock, axis=1), 
                        use_container_width=True,
                        hide_index=True
                    )

                    # 9. Export Option
                    st.divider()
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download This View as CSV",
                        data=csv_data,
                        file_name='inventory_report.csv',
                        mime='text/csv'
                    )
                else:
                    st.warning("The inventory ledger is currently empty. Please add stock in the 'Operations' tab.")

# --- TAB 2: OPERATIONS (Add/Sell) ---
with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Add New Product")
        new_sku = st.text_input("New SKU (e.g. PHN-001)")
        new_name = st.text_input("Product Name")
        new_color = st.color_picker("Product Color Tag", "#00f")
        
        if st.button("✨ Register Product"):
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Inserting into our JSONB column
                        cur.execute(
                            "INSERT INTO products (sku, name, attributes) VALUES (%s, %s, %s)",
                            (new_sku.upper(), new_name, f'{{"color": "{new_color}"}}')
                        )
                    conn.commit()
                st.success(f"Product {new_sku} registered!")
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        st.subheader("Stock In / Stock Out")
        op_sku = st.text_input("Enter SKU to update")
        op_type = st.selectbox("Transaction Type", ["shipment", "sale", "return"])
        op_qty = st.number_input("Quantity", min_value=1)
        
        if st.button("Confirm Transaction"):
            try:
                # If it's a sale, we make the number negative for the ledger
                final_qty = -op_qty if op_type == "sale" else op_qty
                
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Using our safe SQL function
                        if op_type == "sale":
                            cur.execute("SELECT process_sale(%s, 'MDC', %s)", (op_sku.upper(), op_qty))
                            res = cur.fetchone()[0]
                        else:
                            # Standard shipment/return logic
                            cur.execute("""
                                INSERT INTO inventory_ledger (product_id, warehouse_id, change_amount, reason)
                                VALUES (
                                    (SELECT product_id FROM products WHERE sku = %s),
                                    (SELECT warehouse_id FROM warehouses WHERE code = 'MDC'),
                                    %s, %s
                                )""", (op_sku.upper(), final_qty, op_type))
                            res = "Stock updated successfully!"
                    conn.commit()
                st.success(res)
            except Exception as e:
                st.error(f"Action Failed: {e}")

# --- TAB 3: AUDIT LOG ---
with tab3:
    st.header("Full Transaction History")
    st.info("This is an immutable ledger. Entries cannot be deleted.")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT l.created_at, p.sku, p.name, l.change_amount, l.reason 
                FROM inventory_ledger l 
                JOIN products p ON l.product_id = p.product_id 
                ORDER BY l.created_at DESC
            """)
            st.table(cur.fetchall())