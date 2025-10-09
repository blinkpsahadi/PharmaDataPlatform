import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# =========================
# 🌍 CONFIGURATION GLOBALE
# =========================
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

# --- Global responsive CSS ---
st.markdown("""
    <style>
    /* Hide Streamlit toolbar */
    [data-testid="stToolbar"] {visibility: hidden; height: 0; position: fixed;}

    /* Improve readability on mobile */
    @media (max-width: 768px) {
        h1, h2, h3, h4, h5, h6 {font-size: 1.1rem !important;}
        .stButton>button {width: 100% !important;}
        .stTextInput>div>div>input,
        .stTextArea>div>textarea,
        .stSelectbox>div>div>select {
            font-size: 14px !important;
        }
        .block-container {
            padding: 1rem 0.6rem !important;
        }
        .stExpander {
            border-radius: 12px;
            margin-bottom: 10px !important;
        }
        .stNumberInput>div>div>input {
            width: 100% !important;
        }
    }

    /* Scrollable tables and better wrapping */
    .stDataFrame, .stTable {
        overflow-x: auto !important;
        display: block;
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

# =========================
# 📦 FONCTIONS
# =========================

@st.cache_data
def get_db_path():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    possible_paths = [
        os.path.join(base_dir, "data", "all_pharma.db"),
        os.path.join(os.getcwd(), "data", "all_pharma.db"),
        "data/all_pharma.db",
        "all_pharma.db",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path

    st.error("❌ Database not found. Place 'all_pharma.db' in `data/` folder.")
    st.stop()

@st.cache_data
def load_data():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM drugs", conn)
    except Exception as e:
        st.error(f"Error while loading table 'drugs' : {e}")
        st.stop()
    finally:
        conn.close()
    return df

def extraire_prix(val):
    try:
        if pd.isna(val):
            return None
        val = str(val).replace("DA", "").replace(",", ".").strip()
        return float(val)
    except:
        return None

# =========================
# 🧭 BARRE LATÉRALE
# =========================
menu = st.sidebar.radio(
    "Navigation",
    ["🏠 Home", "💊 Products", "📊 Dashboard", "🧾 Observations"]
)

# =========================
# 🏠 HOME
# =========================
if menu == "🏠 Home":
    st.title("💊 Pharma Data Platform")
    st.markdown("""
        Welcome to the Pharmaceutical Management & Analysis Platform 📊  
        This app adapts automatically to your screen — PC, tablet, or smartphone.  
    """)

# =========================
# 💊 PRODUCTS
# =========================
elif menu == "💊 Products":
    st.header("💊 List of Products")

    df = load_data()

    # Search
    search = st.text_input("🔍 Search by name or substance")

    if search:
        df = df[df["name"].str.contains(search, case=False, na=False) |
                df["type"].str.contains(search, case=False, na=False)]

    # Pagination (dynamic per device)
    items_per_page = 50 if st.runtime.scriptrunner.script_run_context.is_running_with_streamlit else 100
    total_pages = (len(df) // items_per_page) + 1
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    start, end = (page - 1) * items_per_page, page * items_per_page
    subset = df.iloc[start:end]

    # Mobile-friendly expander
    for _, row in subset.iterrows():
        with st.expander(f"💊 {row['name']}"):
            st.markdown(f"**ATC:** {row.get('atc', 'N/A')}")
            st.markdown(f"**Type:** {row.get('type', 'N/A')}")
            st.markdown(f"**Price:** {row.get('price', 'N/A')}")
            if 'description' in df.columns and row.get("description"):
                st.markdown("**Description:**", unsafe_allow_html=True)
                st.markdown(row["description"], unsafe_allow_html=True)
            st.markdown("---")

# =========================
# 📊 DASHBOARD
# =========================
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard - Global Analysis")
    df = load_data()
    df["Prix_num"] = df["price"].apply(extraire_prix)

    for col in ["atc", "bcs", "oeb", "bioequivalence"]:
        if col in df.columns:
            fig = px.pie(df, names=col, title=f"By {col.upper()}")
            st.plotly_chart(fig, use_container_width=True)

    if "type" in df.columns:
        fig_class = px.pie(df, names="type", title="Therapeutical Classes")
        st.plotly_chart(fig_class, use_container_width=True)

    if df["Prix_num"].notna().any():
        top10 = df.nlargest(10, "Prix_num")
        fig = px.bar(top10, x="name", y="Prix_num", title="Top 10 Most Expensive Medicines")
        st.plotly_chart(fig, use_container_width=True)

        fig = px.histogram(df, x="Prix_num", nbins=20, title="Price Distribution")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# 🧾 OBSERVATIONS
# =========================
elif menu == "🧾 Observations":
    DB_PATH = os.path.join("data", "all_pharma.db")

    def init_db():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                type TEXT,
                comment TEXT,
                date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_all_products():
        conn = sqlite3.connect(DB_PATH)
        try:
            df = pd.read_sql_query("SELECT DISTINCT name FROM drugs ORDER BY name ASC", conn)
            conn.close()
            return df["name"].tolist()
        except Exception:
            conn.close()
            return []

    def load_observations():
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
        conn.close()
        return df

    def add_observation(product, obs_type, comment):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO observations (product_name, type, comment) VALUES (?, ?, ?)",
            (product, obs_type, comment)
        )
        conn.commit()
        conn.close()

    def update_observation(obs_id, new_comment):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE observations SET comment = ? WHERE id = ?", (new_comment, obs_id))
        conn.commit()
        conn.close()

    def delete_observation(obs_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM observations WHERE id = ?", (obs_id,))
        conn.commit()
        conn.close()

    # --- UI ---
    st.header("🩺 Commercial & Medical Observations")
    init_db()
    products = get_all_products()

    st.subheader("➕ Add a New Observation")

    with st.form("new_obs_form", clear_on_submit=True):
        col1, col2 = st.columns([2, 1]) if st.session_state.get("is_desktop", True) else st.columns(1)
        with col1:
            selected_product = st.selectbox(
                "Choose or Type a product",
                options=["Type manually..."] + products,
                index=0
            )
        with col2:
            obs_type = st.selectbox("Type", ["Commercial", "Medical", "Other"])

        if selected_product == "Type manually...":
            product_name = st.text_input("Product name")
        else:
            product_name = selected_product

        comment = st.text_area("💬 Observation details")

        submitted = st.form_submit_button("💾 Save")
        if submitted:
            if product_name.strip() == "" or comment.strip() == "":
                st.warning("⚠️ Please fill all required fields.")
            else:
                add_observation(product_name.strip(), obs_type, comment.strip())
                st.success(f"✅ Observation added for **{product_name}**.")
                st.rerun()

    st.markdown("---")
    st.subheader("📜 History of Observations")

    df_obs = load_observations()
    if df_obs.empty:
        st.info("No observations recorded yet.")
    else:
        page_size = 10
        total_pages = (len(df_obs) - 1) // page_size + 1
        page = st.number_input("Page", min_value=1, max_value=total_pages, step=1)

        start = (page - 1) * page_size
        end = start + page_size
        page_df = df_obs.iloc[start:end]

        for _, row in page_df.iterrows():
            with st.expander(f"🧾 {row['product_name']} ({row['type']}) - {row['date']}"):
                st.write(row['comment'])
                new_comment = st.text_area("✏️ Edit comment", row['comment'], key=f"edit_{row['id']}")
                colA, colB = st.columns(2) if st.session_state.get("is_desktop", True) else st.columns(1)
                with colA:
                    if st.button("💾 Update", key=f"update_{row['id']}"):
                        update_observation(row['id'], new_comment)
                        st.success("Observation updated ✅")
                        st.rerun()
                with colB:
                    if st.button("🗑️ Delete", key=f"delete_{row['id']}"):
                        delete_observation(row['id'])
                        st.warning("Observation deleted ❌")
                        st.rerun()

