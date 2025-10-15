import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

st.markdown("""
<style>
/* --- Remove Streamlit default header and toolbar completely --- */
[data-testid="stHeader"] {display: none !important;}
[data-testid="stToolbar"] {display: none !important;}
header {display: none !important;}

/* --- Hide sidebar (we use dropdown for mobile) --- */
[data-testid="stSidebar"] {display: none !important;}

/* --- Ensure main container is fully visible from top --- */
[data-testid="stAppViewContainer"] > .main {
    margin-top: 0 !important;
    padding-top: 2.5rem !important;  /* ensures visible space at the top */
}

/* --- Global layout adjustments --- */
.block-container {
    padding: 1rem 2rem !important;
}

/* --- Responsive adjustments for mobile --- */
@media (max-width: 768px) {
    [data-testid="stAppViewContainer"] > .main {
        padding-top: 1.8rem !important;
    }
    .block-container {
        padding: 0.6rem 1rem !important;
    }
    .stButton>button {
        width: 100% !important;
    }
    .stMarkdown, .stTextInput, .stSelectbox, .stTextArea {
        font-size: 14px !important;
    }
    .stExpander {
        margin-bottom: 0.8rem !important;
    }
    h1, h2, h3 {
        font-size: 1.1rem !important;
    }
}

/* Optional: make dataframes and charts responsive */
.stDataFrame, .stTable {
    overflow-x: auto !important;
    display: block !important;
}
</style>
""", unsafe_allow_html=True)
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")
st.markdown("""
    <style>
    /* Hide the "View source" GitHub banner */
    [data-testid="stToolbar"] {
        visibility: hidden;
        height: 0;
        position: fixed;
    }
    </style>
""", unsafe_allow_html=True)

# =========================
# 🔐 AUTHENTIFICATION
# =========================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

if "credentials" in st.secrets:
    USERS = dict(st.secrets["credentials"])

def check_password(username, password):
    return username in USERS and USERS[username] == password

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.markdown("## 🔒 Connection")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if check_password(user, pwd):
                st.session_state.authenticated = True
                st.session_state.username = user
                st.success(f"Welcome {user} 👋")
                st.rerun()
            else:
                st.error("Incorrect Password or Username")
    st.stop()
else:
    st.sidebar.markdown(f"**Connected as :** {st.session_state.username}")
    if st.sidebar.button("🔓 Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()
# ---------------------------
# DB HELPERS
# ---------------------------
@st.cache_data
def get_db_path():
    possible = [
        os.path.join(os.getcwd(), "data", "all_pharma.db"),
        "data/all_pharma.db",
        "all_pharma.db",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "all_pharma.db")
    ]
    for p in possible:
        if os.path.exists(p):
            return p
    st.error("❌ Database not found. Place 'all_pharma.db' in the `data/` folder or next to the app.")
    st.stop()

@st.cache_data
def load_data():
    db = get_db_path()
    conn = sqlite3.connect(db)
    try:
        df = pd.read_sql_query("SELECT * FROM drugs", conn)
    except Exception as e:
        conn.close()
        st.error(f"Error loading 'drugs' table: {e}")
        st.stop()
    conn.close()
    return df

def ensure_observation_column():
    db = get_db_path()
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(drugs);")
    columns = [info[1] for info in cursor.fetchall()]
    if "Observations" not in columns:
        cursor.execute("ALTER TABLE drugs ADD COLUMN Observations TEXT;")
        conn.commit()
    conn.close()

# Call once at startup
ensure_observation_column()

def extract_price(val):
    try:
        if pd.isna(val): return None
        return float(str(val).replace("DA", "").replace(",", ".").strip())
    except:
        return None

# ---------------------------
# LAYOUT: custom sidebar (left column) + main column
# Using in-page columns avoids Streamlit's built-in sidebar hiding on mobile
# ---------------------------
menu_options = ["🏠 Home", "💊 Products", "📊 Dashboard", "🧾 Observations"]

# Create two columns: left = navigation (acts as a sidebar), right = main content
left_col, main_col = st.columns([1, 4], gap="small")

with left_col:
    st.markdown("### 💊 Navigation")
    
    # Initialize session state value for menu if absent
    if "nav_selection" not in st.session_state:
        st.session_state.nav_selection = menu_options[0]

    try:
        selected_index = menu_options.index(st.session_state.nav_selection)
    except ValueError:
        selected_index = 0

    # Render navigation menu
    st.session_state.nav_selection = st.radio(
        "Menu",
        menu_options,
        index=selected_index,
        key="nav_selection_radio"
    )

    # Divider
    st.markdown("---")
    st.markdown(f"**Connected as:**  \n`{st.session_state.username}`")

    # 🚪 Logout button — now visible in your left sidebar column
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

    

# Main content area
with main_col:
    menu = st.session_state.get("nav_selection", menu_options[0])

    # =========================
    # HOME
    # =========================
    if menu == "🏠 Home":
        st.title("💊 Pharma Data Platform")
        st.markdown("Welcome to the Pharmaceutical Management & Analysis Platform 📊")

    # =========================
    # 💊 PRODUCTS
    # =========================
    elif menu == "💊 Products":
        st.header("💊 List of Products")
        df = load_data()
    
        # Ensure Observations column exists in the database
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cols = pd.read_sql_query("PRAGMA table_info(drugs);", conn)
        if "Observations" not in cols["name"].values:
            conn.execute("ALTER TABLE drugs ADD COLUMN Observations TEXT;")
            conn.commit()
        conn.close()
    
        # 🔍 Search bar
        search = st.text_input("🔍 Search by name or substance")
        if search:
            search_cols = ["name", "type", "scientific_name"]
            available_cols = [c for c in search_cols if c in df.columns]
            mask = False
            for c in available_cols:
                mask |= df[c].astype(str).str.contains(search, case=False, na=False)
            df = df[mask]
    
        # 📄 Pagination
        items_per_page = 50
        total_pages = max(1, (len(df) - 1) // items_per_page + 1)
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
        subset = df.iloc[(page - 1) * items_per_page : page * items_per_page]
    
        # 💊 Product display
        for _, row in subset.iterrows():
            with st.expander(f"💊 {row['name']}"):
                st.write(f"**Scientific name:** {row.get('scientific_name', 'N/A')}")
                st.write(f"**ATC:** {row.get('atc', 'N/A')}")
                st.write(f"**Type:** {row.get('type', 'N/A')}")
                st.write(f"**Price:** {row.get('price', 'N/A')}")
    
                # 🩺 Observation section (read-only)
                obs_text = row.get("Observations", "")
                st.markdown("**🩺 Observation:**")
                if obs_text and str(obs_text).strip() != "":
                    st.info(obs_text)
                else:
                    st.write("_No observation recorded for this product._")
    
                # 📄 Description section
                if "description" in df.columns and row.get("description"):
                    st.markdown("**📄 Description:**", unsafe_allow_html=True)
                    st.markdown(row["description"], unsafe_allow_html=True)
    
                st.markdown("---")

    # =========================
    # DASHBOARD
    # =========================
    elif menu == "📊 Dashboard":
        st.header("📊 Global Analysis")
    
        df = load_data()
    
        # Ensure price is numeric where possible
        df["Prix_num"] = df["price"].apply(extract_price)
    
        # Remove empty/NaN text fields
        df = df.fillna("")
    
        # --- Pie charts safely ---
        for col in ["atc", "bcs", "oeb", "bioequivalence"]:
            if col in df.columns:
                valid = df[df[col].astype(str).str.strip() != ""]
                if not valid.empty:
                    fig = px.pie(valid, names=col, title=f"By {col.upper()}")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"No valid data for {col.upper()}")
    
        # --- Type pie chart ---
        if "type" in df.columns:
            valid_type = df[df["type"].astype(str).str.strip() != ""]
            if not valid_type.empty:
                fig_class = px.pie(valid_type, names="type", title="Therapeutical Classes")
                st.plotly_chart(fig_class, use_container_width=True)
            else:
                st.info("No valid data for therapeutical classes.")
    
        # --- Price visualizations ---
        if df["Prix_num"].notna().any():
            # Top 10 most expensive
            top10 = df.nlargest(10, "Prix_num")
            if not top10.empty:
                fig = px.bar(top10, x="name", y="Prix_num", title="Top 10 Most Expensive Medicines")
                st.plotly_chart(fig, use_container_width=True)
    
            # Histogram
            fig = px.histogram(df[df["Prix_num"].notna()], x="Prix_num", nbins=20, title="Price Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No valid numeric price data to display.")

    # =========================
    # OBSERVATIONS
    # =========================
    elif menu == "🧾 Observations":
        st.header("🩺 Commercial & Medical Observations")

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                type TEXT,
                comment TEXT,
                date TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.commit()

        df_products = pd.read_sql_query("SELECT DISTINCT name FROM drugs ORDER BY name", conn)
        products = df_products["name"].tolist()
        conn.close()

        with st.form("new_obs", clear_on_submit=True):
            product = st.selectbox("Product", ["Type manually..."] + products)
            obs_type = st.selectbox("Type", ["Commercial", "Medical", "Other"])
            if product == "Type manually...":
                product = st.text_input("Manual Product Name")
            comment = st.text_area("💬 Observation")
            submit = st.form_submit_button("💾 Save")
            if submit:
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "INSERT INTO observations (product_name, type, comment) VALUES (?, ?, ?)",
                    (product, obs_type, comment)
                )
            
                # 🔁 NEW: Also update the 'drugs' table Observations column
                conn.execute(
                    "UPDATE drugs SET Observations = ? WHERE name = ?",
                    (comment, product)
                )

                conn.commit()
                conn.close()
                st.success("✅ Observation saved and linked to product.")
                st.experimental_rerun()
        
                st.markdown("---")
                conn = sqlite3.connect(db_path)
                df_obs = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
                conn.close()

                if df_obs.empty:
                        st.info("No observations yet.")
                else:
                        # pagination for observations
                        page_size = 10
                        total_pages = max(1, (len(df_obs) - 1) // page_size + 1)
                        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
                        start = (page - 1) * page_size
                        end = start + page_size
                        page_df = df_obs.iloc[start:end]
            
                        for _, row in page_df.iterrows():
                            with st.expander(f"{row['product_name']} ({row['type']}) - {row['date']}"):
                                st.write(row["comment"])
        
    





























