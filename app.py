import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import re
from datetime import date
from contextlib import contextmanager

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

# Custom CSS for enhanced UI consistency (kept largely as provided)
st.markdown("""
<style>
/* General Streamlit Overrides */
[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; }
/* Keep the default sidebar hidden to use our custom left column for navigation */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"] > .main {
    margin-top: 0 !important;
    padding-top: 2.5rem !important;
}
.block-container { padding: 1rem 2rem !important; }

@media (max-width: 768px) {
    [data-testid="stAppViewContainer"] > .main { padding-top: 1.8rem !important; }
    .block-container { padding: 0.6rem 1rem !important; }
    .stButton>button { width: 100% !important; }
    .stMarkdown, .stTextInput, .stSelectbox, .stTextArea { font-size: 14px !important; }
    .stExpander { margin-bottom: 0.8rem !important; }
    h1, h2, h3 { font-size: 1.1rem !important; }
}
.stDataFrame, .stTable {
    overflow-x: auto !important;
    display: block !important;
}

h1 {
    /* Uses Streamlit's primary theme color */
    border-bottom: 3px solid var(--primary-color, #007bff); 
    padding-bottom: 10px;
    margin-bottom: 30px;
    font-size: 2em;
}

h2 {
    margin-top: 40px;
    font-size: 1.5em;
}

/* Container styling (st.container) */
.stContainer {
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
    margin-bottom: 25px;
}

/* Force the custom radio navigation to use full column width */
[data-testid="stRadio"] label {
    display: block;
    width: 100%;
    margin-bottom: 5px;
}

</style>
""", unsafe_allow_html=True)

# =========================
# 🔐 AUTHENTICATION
# =========================

# Initialize authentication states
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Load credentials from secrets or provide a safe default
if "credentials" in st.secrets:
    USERS = dict(st.secrets["credentials"])

def check_password(username, password):
    """Checks if the provided username and password are valid."""
    return username in USERS and USERS[username] == password

# Authentication block (stops execution if not authenticated)
if not st.session_state.authenticated:
    st.markdown("<h1 style='border-bottom: none;'>💊 Pharma Dashboard Login</h1>", unsafe_allow_html=True)
    
    # Center the login form for better aesthetics
    col_spacer, col_login, col_spacer_2 = st.columns([1, 2, 1])
    
    with col_login:
        with st.form("login_form"):
            st.markdown("## 🔒 Connection")
            user = st.text_input("Username", key="login_user")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if check_password(user, pwd):
                    st.session_state.authenticated = True
                    st.session_state.username = user
                    st.success(f"Welcome {user} 👋")
                    st.rerun()
                else:
                    st.error("Incorrect Password or Username")
    st.stop()
# --- End of Authentication Block ---


# ---------------------------
# DB HELPERS & INITIALIZATION
# ---------------------------

@st.cache_data
def get_db_path():
    """Attempts to find the SQLite database file in common Streamlit path locations."""
    # List of possible paths to check
    possible = [
        os.path.join(os.getcwd(), "data", "all_pharma.db"),
        "data/all_pharma.db",
        "all_pharma.db",
        # Fallback using the script's directory (might fail in cloud environments)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "all_pharma.db")
    ]
    for p in possible:
        if os.path.exists(p):
            return p
            
    st.error("❌ Database 'all_pharma.db' not found. Please ensure it is available.")
    st.stop()

DB_PATH = get_db_path()

@contextmanager
def get_db_connection(db_path):
    """Context manager for handling SQLite connection and ensuring proper closure/error handling."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        yield None
    finally:
        if conn:
            conn.close()

@st.cache_data(show_spinner="Loading and cleaning data...")
def load_data():
    """Loads and cleans data from the 'drugs' table into a DataFrame."""
    df = pd.DataFrame()
    try:
        with get_db_connection(DB_PATH) as conn:
            if conn:
                df = pd.read_sql_query("SELECT * FROM drugs", conn)
    except Exception as e:
        st.error(f"Fatal error loading 'drugs' table: {e}")
        # Use return instead of st.stop() if we want the app to continue potentially showing an empty dashboard
        return pd.DataFrame() 
    
    # Data Cleaning and Preparation for Dashboard
    if 'price' in df.columns:
        # 1. Standardize string representations (remove non-numeric, replace comma decimal with dot)
        df['price_numeric'] = df['price'].astype(str).str.replace(r'[^\d,.]', '', regex=True)
        df['price_numeric'] = df['price_numeric'].str.replace(',', '.', regex=False)
        
        # 2. Convert to numeric, coercing errors to NaN
        df['price_numeric'] = pd.to_numeric(df['price_numeric'], errors='coerce')
        
    else:
        # Ensure the column exists even if original 'price' is missing
        df['price_numeric'] = pd.NA

    # Clean up classification columns to ensure they are strings for grouping/charts
    for col in ['therapeutic_class', 'type', 'source', 'Code_ATC']:
        if col in df.columns:
             # Fill NaN/None with 'Unknown' for chart readiness
            df[col] = df[col].astype(str).fillna('Unknown')

    return df

def ensure_tables_and_columns():
    """Verifies and creates the 'Observations' column in 'drugs' and the 'observations' table."""
    try:
        with get_db_connection(DB_PATH) as conn:
            if conn:
                cursor = conn.cursor()
                
                # 1. Check/Add 'Observations' column in 'drugs'
                cursor.execute("PRAGMA table_info(drugs);")
                columns = [info[1] for info in cursor.fetchall()]
                if "Observations" not in columns:
                    cursor.execute("ALTER TABLE drugs ADD COLUMN Observations TEXT;")
                    # Note: Using st.toast for non-critical feedback instead of st.success
                    st.toast("Database structure updated: 'Observations' column added.") 
                
                # 2. Check/Create 'observations' table for history
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT NOT NULL,
                        type TEXT,
                        comment TEXT,
                        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                
    except Exception as e:
        # This is a critical error
        st.error(f"Database initialization error: {e}")
        st.stop()

# Execute DB initialization upon app start
ensure_tables_and_columns()


# ---------------------------
# APP NAVIGATION & LAYOUT
# ---------------------------
menu_options = ["🏠 Home", "💊 Products", "📊 Dashboard", "🧾 Observations"]
# Use columns for custom sidebar/main content layout
left_col, main_col = st.columns([1.2, 4], gap="large") # Increased left column width slightly

# Custom Navigation in the Left Column
with left_col:
    st.markdown("### 💊 Navigation")
    if "nav_selection" not in st.session_state:
        st.session_state.nav_selection = menu_options[0]
        
    selected_index = menu_options.index(st.session_state.nav_selection)
    
    st.session_state.nav_selection = st.radio(
        "Menu", 
        menu_options, 
        index=selected_index, 
        key="nav_selection_radio",
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown(f"**Connected as:** `{st.session_state.username}`")
    
    def logout():
        """Handles logout process."""
        # Clear specific session state variables
        st.session_state.authenticated = False
        st.session_state.username = ""
        # Clear cached data/functions (important for reloading fresh state)
        load_data.clear()
        st.cache_data.clear()
        st.rerun()
        
    if st.button("🚪 Logout", use_container_width=True):
        logout()


# ---------------------------
# MAIN CONTENT RENDERER
# ---------------------------
with main_col:
    menu = st.session_state.get("nav_selection", menu_options[0])
    
    # HOME Page
    if menu == "🏠 Home":
        st.title("💊 Pharma Data Platform")
        st.info(f"Welcome back, **{st.session_state.username}**! This platform provides pharmaceutical product management and analytical tools.")
        
        st.markdown("## Platform Overview")
        st.markdown("""
        * **Products:** Browse the detailed list of molecules, search across different fields, and view the latest recorded observation.
        * **Dashboard:** Visualize global data insights, including distribution by therapeutic class, form type, source, and average pricing.
        * **Observations:** Add new commercial or medical observations and review the complete history of recorded comments.
        """)
        

    # PRODUCTS Page
    elif menu == "💊 Products":
        st.header("💊 Product Catalog")
        df = load_data()
        
        if df.empty:
            st.error("Cannot display products. Data loading failed.")
            st.stop()
            
        # --- Search Input ---
        search = st.text_input("🔍 Search by Name, Scientific Name, or ATC Code", key="product_search_input")
        
        filtered_df = df.copy()
        if search:
            search_cols = ["name", "scientific_name", "Code_ATC", "type"] 
            
            mask = False
            for c in search_cols:
                if c in filtered_df.columns:
                    # Use str.contains on the column converted to string, handling NaNs
                    mask |= filtered_df[c].astype(str).str.contains(search, case=False, na=False)
            
            if isinstance(mask, pd.Series):
                filtered_df = filtered_df[mask]
            else:
                # Should not happen if df is not empty, but safety check
                st.warning("No searchable columns found or mask creation failed.")
                filtered_df = pd.DataFrame()

        items_per_page = 10 
        total_rows = len(filtered_df)
        total_pages = max(1, (total_rows - 1) // items_per_page + 1)
        
        # Initialize pagination state
        if 'product_page' not in st.session_state:
            st.session_state.product_page = 1
        
        if total_rows == 0:
            st.info("No products found matching your criteria.")
        else:
            # Adjust current page if filtering reduces total pages
            if st.session_state.product_page > total_pages:
                st.session_state.product_page = total_pages
                
            # --- Pagination Controls ---
            col_nav_1, col_nav_2, col_nav_3 = st.columns([1, 1, 3])
            
            with col_nav_1:
                if st.button("⬅️ Previous", disabled=(st.session_state.product_page == 1), use_container_width=True):
                    st.session_state.product_page = max(1, st.session_state.product_page - 1)
                    st.rerun()
            with col_nav_2:
                if st.button("Next ➡️", disabled=(st.session_state.product_page == total_pages), use_container_width=True):
                    st.session_state.product_page = min(total_pages, st.session_state.product_page + 1)
                    st.rerun()
            with col_nav_3:
                st.markdown(f"**Page {st.session_state.product_page} of {total_pages}** ({total_rows} items found)")
                
            # Slice the DataFrame for the current page
            start_index = (st.session_state.product_page - 1) * items_per_page
            end_index = start_index + items_per_page
            subset = filtered_df.iloc[start_index:end_index]
    
            st.markdown("---")
            
            # --- Product Display Loop ---
            for _, row in subset.iterrows():
                # Use scientific name if available, otherwise commercial name in the expander title
                scientific_name = row.get('scientific_name', 'N/A')
                commercial_name = row.get('name', 'N/A')
                title_display = f"💊 **{commercial_name}** ({scientific_name})" if scientific_name not in ['N/A', 'Unknown'] else f"💊 **{commercial_name}**"
                
                with st.expander(title_display):
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**ATC Code:** `{row.get('Code_ATC', 'N/A')}`") 
                        st.write(f"**Therapeutic Class:** {row.get('therapeutic_class', 'N/A')}")
                        st.write(f"**Source/Manufacturer:** {row.get('source', 'N/A')}")
                        
                    with col2:
                        st.write(f"**Galenic Form (Type):** {row.get('type', 'N/A')}")
                        st.write(f"**Dosage:** {row.get('dosage', 'N/A')}")
                        # Display original price and cleaned numeric price (if available)
                        price_display = row.get('price', 'N/A')
                        if pd.notna(row.get('price_numeric')):
                             price_display += f" (~{row['price_numeric']:.2f} numerical)"
                        st.write(f"**Price:** {price_display}")
                    
                    st.markdown("---")
                    # 5. Latest Observation from the 'drugs' table
                    obs_text = row.get("Observations", "")
                    st.markdown("**🩺 Latest Observation:**")
                    if obs_text and str(obs_text).strip() != "" and str(obs_text).lower() != 'nan':
                        st.markdown(f'<div style="background-color: var(--secondary-background-color); padding: 10px; border-radius: 8px;">{obs_text}</div>', unsafe_allow_html=True)
                    else:
                        st.write("_No recent observation recorded in the main catalog._")
                        
    # DASHBOARD
    elif menu == "📊 Dashboard":
        st.header("📊 Global Analysis")
        df = load_data()
        
        # --- Data Preparation: Cleaning and Creating 'price_numeric' ---
        if 'price' in df.columns:
            df['price_numeric'] = df['price'].astype(str).str.replace(',', '.', regex=False)
            df['price_numeric'] = pd.to_numeric(df['price_numeric'], errors='coerce')
        else:
            df['price_numeric'] = pd.NA
            st.warning("Column 'price' not found. Price analysis is skipped.")
    
        required_cols = ['therapeutic_class', 'type', 'source', 'price_numeric']
        for col in required_cols:
            if col == 'price_numeric':
                continue
            if col not in df.columns:
                df[col] = pd.NA
                st.warning(f"Column '{col}' not found. Dashboard calculations might be incomplete.")
    
        if df.empty:
            st.error("Data required for the Dashboard is missing or empty.")
            st.stop()
    
    
        # =====================
        # CALCULATIONS
        # =====================
        @st.cache_data
        def calculate_dashboard_data(df_products):
    
            # Ensure 'name' is string
            df_products['name'] = df_products['name'].astype(str)
    
            # --- Molecule grouping per category ---
            mol_by_class = df_products.groupby('therapeutic_class')['name'].apply(list)
            mol_by_type = df_products.groupby('type')['name'].apply(list)
            mol_by_source = df_products.groupby('source')['name'].apply(list)
    
            # ------------------------------
            # 1. Therapeutic Class
            # ------------------------------
            df_class_therapy = df_products.groupby('therapeutic_class', dropna=True)['name'].count().reset_index()
            df_class_therapy.columns = ['Therapeutic Class', 'Number of Molecules']
            df_class_therapy['molecules'] = df_class_therapy['Therapeutic Class'].map(mol_by_class)
            df_class_therapy['molecules_str'] = df_class_therapy['molecules'].apply(
                lambda lst: "<br>".join([f"• {x}" for x in lst]) if isinstance(lst, list) else ""
            )
    
            # ------------------------------
            # 2. Type (Galenic Form)
            # ------------------------------
            df_type = df_products.groupby('type', dropna=True)['name'].count().reset_index()
            df_type.columns = ['Form Type (Galenic)', 'Number of Molecules']
            df_type = df_type.sort_values(by='Number of Molecules', ascending=False)
            df_type['molecules'] = df_type['Form Type (Galenic)'].map(mol_by_type)
            df_type['molecules_str'] = df_type['molecules'].apply(
                lambda lst: "<br>".join([f"• {x}" for x in lst]) if isinstance(lst, list) else ""
            )
    
            # ------------------------------
            # 3. Source (Manufacturer)
            # ------------------------------
            df_source = df_products.groupby('source', dropna=True)['name'].count().reset_index()
            df_source.columns = ['Source (Manufacturer/Data)', 'Number of Molecules']
            df_source = df_source.sort_values(by='Number of Molecules', ascending=False)
            df_source['molecules'] = df_source['Source (Manufacturer/Data)'].map(mol_by_source)
            df_source['molecules_str'] = df_source['molecules'].apply(
                lambda lst: "<br>".join([f"• {x}" for x in lst]) if isinstance(lst, list) else ""
            )
    
            # ------------------------------
            # 4. Average price by class
            # ------------------------------
            df_price_class = df_products[df_products['price_numeric'].notna()].groupby('therapeutic_class').agg(
                Average_Price=('price_numeric', 'mean'),
                Total_Molecules=('name', 'count')
            ).reset_index()
            df_price_class.columns = ['Therapeutic Class', 'Average_Price', 'Total_Molecules']
            df_price_class['molecules'] = df_price_class['Therapeutic Class'].map(mol_by_class)
            df_price_class['molecules_str'] = df_price_class['molecules'].apply(
                lambda lst: "<br>".join([f"• {x}" for x in lst]) if isinstance(lst, list) else ""
            )
    
            return df_class_therapy, df_type, df_source, df_price_class
    
    
        # =====================
        # PLOTTING FUNCTIONS
        # =====================
        PLOTLY_TEMPLATE = "streamlit"
    
        def create_pie_chart(df, names_col, values_col, title):
            if df.empty:
                return None
            fig = px.pie(
                df,
                names=names_col,
                values=values_col,
                title=title,
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template=PLOTLY_TEMPLATE,
                hover_data={'molecules_str': True}
            )
            fig.update_traces(
                hovertemplate="<b>%{label}</b><br><br><b>Molecules:</b><br>%{customdata[0]}",
                textinfo='percent+label',
                marker=dict(line=dict(color='#FFFFFF', width=1))
            )
            fig.update_layout(
                showlegend=True,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
            )
            return fig
    
    
        def create_bar_chart(df, x_col, y_col, color_col, title, y_title="Number of Molecules"):
            if df.empty:
                return None
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=color_col,
                title=title,
                text_auto=True,
                color_discrete_sequence=px.colors.qualitative.Vivid,
                template=PLOTLY_TEMPLATE,
                hover_data={'molecules_str': True}
            )
            fig.update_traces(
                hovertemplate="<b>%{x}</b><br>%{y} molecules<br><br><b>Molecules:</b><br>%{customdata[0]}"
            )
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title=y_title,
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
            )
            fig.update_xaxes(tickangle=45, tickfont=dict(size=10))
            return fig
    
    
        def create_price_bar_chart(df, x_col, y_col, title):
            if df.empty:
                return None
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=x_col,
                title=title,
                text_auto='.2s',
                color_discrete_sequence=px.colors.qualitative.Safe,
                template=PLOTLY_TEMPLATE,
                hover_data={'molecules_str': True}
            )
            fig.update_traces(
                hovertemplate="<b>%{x}</b><br>Average price: %{y:.2f}<br><br><b>Molecules:</b><br>%{customdata[0]}"
            )
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title="Average Price",
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
            )
            fig.update_xaxes(tickangle=45, tickfont=dict(size=10))
            return fig
    
    
        # =====================
        # LOAD DATA
        # =====================
        df_class_therapy, df_type, df_source, df_price_class = calculate_dashboard_data(df)
    
        st.markdown("<h1>General Pharmaceutical Data Synthesis</h1>", unsafe_allow_html=True)
        st.write(f"Analysis of **{len(df)}** molecules as of **{date.today().strftime('%m/%d/%Y')}**.")
    
    
        # 1 — Therapeutic class pie chart
        st.markdown("<h2>1. Therapeutic Class Distribution</h2>", unsafe_allow_html=True)
        fig_class_therapy = create_pie_chart(df_class_therapy, 'Therapeutic Class', 'Number of Molecules', "Distribution by Therapeutic Class")
        st.plotly_chart(fig_class_therapy, use_container_width=True)
    
    
        st.markdown("---")
    
    
        # 2 — Type/Galenic form
        st.markdown("<h2>2. Top 10 Form Type (Galenic) Distributions</h2>", unsafe_allow_html=True)
        fig_type = create_bar_chart(df_type.head(10), 'Form Type (Galenic)', 'Number of Molecules', 'Form Type (Galenic)', "Top 10 Distributions by Form Type")
        st.plotly_chart(fig_type, use_container_width=True)
    
    
        st.markdown("---")
    
    
        # 3 — Source/Manufacturer
        st.markdown("<h2>3. Top 10 Source (Manufacturer/Data) Distributions</h2>", unsafe_allow_html=True)
        fig_source = create_bar_chart(df_source.head(10), 'Source (Manufacturer/Data)', 'Number of Molecules', 'Source (Manufacturer/Data)', "Top 10 Distributions by Source")
        st.plotly_chart(fig_source, use_container_width=True)
    
    
        st.markdown("---")
    
    
        # 4 — Price by therapeutic class
        st.markdown("<h2>4. Average Price by Therapeutic Class</h2>", unsafe_allow_html=True)
        fig_price = create_price_bar_chart(
            df_price_class.sort_values(by='Average_Price', ascending=False),
            'Therapeutic Class', 'Average_Price', "Average Price by Therapeutic Class"
        )
        st.plotly_chart(fig_price, use_container_width=True)
    

    # OBSERVATIONS Page
    elif menu == "🧾 Observations":
        st.header("🩺 Commercial & Medical Observations")
        
        products = []
        try:
            with get_db_connection(DB_PATH) as conn:
                if conn:
                    # Load existing product names for the selectbox
                    df_products = pd.read_sql_query("SELECT DISTINCT name FROM drugs ORDER BY name", conn)
                    products = df_products["name"].tolist()
        except Exception as e:
            st.error(f"Error accessing database for Products list: {e}. Cannot display form.")

        
        with st.form("new_obs", clear_on_submit=True):
            st.subheader("Add New Observation")
            
            # Use columns for layout
            col_prod, col_type = st.columns([3, 1])
            
            with col_prod:
                # Selection of product or manual entry
                product_options = ["--- Select or Type Manually ---"] + products
                product_selected = st.selectbox("Product", product_options, index=0)
            
            with col_type:
                obs_type = st.selectbox("Type", ["Commercial", "Medical", "Other"])
                
            final_product_name = ""
            if product_selected == product_options[0]:
                final_product_name = st.text_input("Manual Product Name", placeholder="Enter the product name...")
            else:
                final_product_name = product_selected
                
            comment = st.text_area("💬 Observation details (Max 500 characters)", max_chars=500)
            
            submit = st.form_submit_button("💾 Save Observation", use_container_width=True)
            
            if submit:
                if final_product_name and comment:
                    try:
                        with get_db_connection(DB_PATH) as conn:
                            if conn:
                                # 1. Insert into the historical observations table
                                conn.execute(
                                    "INSERT INTO observations (product_name, type, comment) VALUES (?, ?, ?)",
                                    (final_product_name, obs_type, comment)
                                )
                                
                                # 2. Update the 'Observations' column in the 'drugs' table with the latest comment
                                conn.execute(
                                    "UPDATE drugs SET Observations = ? WHERE name = ?",
                                    (comment, final_product_name)
                                )
                                conn.commit()
                                st.success(f"✅ Observation saved for {final_product_name}.")
                                # Clear cache to ensure 'Products' page shows the update immediately
                                load_data.clear() 
                                # Rerun to clear the form and refresh the history section below
                                st.rerun() 
                                
                    except Exception as e:
                        st.error(f"Error saving observation: {e}")
                else:
                    st.warning("Please select or enter a product name and fill in the observation details.")

        st.markdown("---")
        st.subheader("Recent Observations History")
        
        df_obs = pd.DataFrame()
        try:
            with get_db_connection(DB_PATH) as conn:
                if conn:
                    # Load all observations ordered by date descending
                    df_obs = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
        except Exception:
            st.error("Could not load observations history.")

        if df_obs.empty:
            st.info("No observations recorded yet.")
        else:
            page_size = 10
            total_rows = len(df_obs)
            total_pages = max(1, (total_rows - 1) // page_size + 1)
            
            if 'obs_page' not in st.session_state:
                st.session_state.obs_page = 1
            
            # --- History Pagination Controls ---
            col_nav_A, col_nav_B, col_nav_C = st.columns([1, 1, 3])

            if st.session_state.obs_page > total_pages:
                st.session_state.obs_page = total_pages
                
            with col_nav_A:
                if st.button("⏪ Prev", key="obs_prev", disabled=(st.session_state.obs_page == 1), use_container_width=True):
                    st.session_state.obs_page = max(1, st.session_state.obs_page - 1)
                    st.rerun()
            with col_nav_B:
                if st.button("Next ⏩", key="obs_next", disabled=(st.session_state.obs_page == total_pages), use_container_width=True):
                    st.session_state.obs_page = min(total_pages, st.session_state.obs_page + 1)
                    st.rerun()
            with col_nav_C:
                st.markdown(f"**Page {st.session_state.obs_page} of {total_pages}** ({total_rows} total observations)")

            start = (st.session_state.obs_page - 1) * page_size
            end = start + page_size
            page_df = df_obs.iloc[start:end]

            # --- Observation History Display ---
            for _, row in page_df.iterrows():
                # Format the timestamp for cleaner display
                date_display = row['date'][:19].replace('-', '/').replace('T', ' - ') # Handles both SQL and potential ISO formats
                
                # Title uses type and date
                with st.expander(f"**{row['product_name']}** ({row['type']}) - *{date_display}*"):
                    st.write(row["comment"])




