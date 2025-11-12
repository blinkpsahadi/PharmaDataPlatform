import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import re

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

st.markdown("""
<style>
[data-testid="stHeader"], [data-testid="stToolbar"], header {display: none !important;}
[data-testid="stSidebar"] {display: none !important;}
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
</style>
""", unsafe_allow_html=True)

# =========================
# 🔐 AUTHENTICATION
# =========================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

if "credentials" in st.secrets:
    USERS = dict(st.secrets["credentials"])
else:
    USERS = {"admin": "password"} # Default local user for testing

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

ensure_observation_column()

# ---------------------------
# APP NAVIGATION
# ---------------------------
menu_options = ["🏠 Home", "💊 Products", "📊 Dashboard", "🧾 Observations"]
left_col, main_col = st.columns([1, 4], gap="small")

with left_col:
    st.markdown("### 💊 Navigation")
    if "nav_selection" not in st.session_state:
        st.session_state.nav_selection = menu_options[0]
    selected_index = menu_options.index(st.session_state.nav_selection)
    st.session_state.nav_selection = st.radio(
        "Menu", menu_options, index=selected_index, key="nav_selection_radio"
    )
    st.markdown("---")
    st.markdown(f"**Connected as:** `{st.session_state.username}`")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

with main_col:
    menu = st.session_state.get("nav_selection", menu_options[0])

    # HOME
    if menu == "🏠 Home":
        st.title("💊 Pharma Data Platform")
        st.markdown("Welcome to the Pharmaceutical Management & Analysis Platform 📊")

    # PRODUCTS
    elif menu == "💊 Products":
        st.header("💊 List of Products")
        df = load_data()

        search = st.text_input("🔍 Search by name or substance")
        if search:
            search_cols = ["name", "type", "scientific_name"]
            available_cols = [c for c in search_cols if c in df.columns]
            mask = False
            for c in available_cols:
                mask |= df[c].astype(str).str.contains(search, case=False, na=False)
            df = df[mask]

        items_per_page = 50
        total_pages = max(1, (len(df) - 1) // items_per_page + 1)
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
        subset = df.iloc[(page - 1) * items_per_page : page * items_per_page]

        for _, row in subset.iterrows():
            with st.expander(f"💊 {row['name']}"):
                # Tentative de récupération de Code_ATC, car le nom de colonne peut varier
                atc_code = row.get('Code ATC', row.get('Code_ATC', 'N/A'))
                
                st.write(f"**Scientific name:** {row.get('scientific_name', 'N/A')}")
                st.write(f"**Code ATC:** {atc_code}")
                st.write(f"**Type:** {row.get('type', 'N/A')}")
                st.write(f"**Price:** {row.get('price', 'N/A')}")
                obs_text = row.get("Observations", "")
                st.markdown("**🩺 Observation:**")
                if obs_text and str(obs_text).strip() != "":
                    st.info(obs_text)
                else:
                    st.write("_No observation recorded for this product._")

    # DASHBOARD
    elif menu == "📊 Dashboard":
        st.header("📊 Global Analysis")
        df = load_data()
        
        # Helper pour extraire le prix numérique
        def safe_extract(val):
            try:
                # Extrait le premier nombre flottant (supporte les virgules comme séparateur décimal)
                match = re.search(r"[\d]+[.,]?[\d]*", str(val))
                return float(match.group().replace(",", ".")) if match else None
            except Exception:
                return None
                
        df["Prix_num"] = df["price"].apply(safe_extract)
        df = df.fillna("")

        # --- 1. Distributions Catégorielles (Bar Charts & Pie Charts) ---
        st.subheader("Distribution des Produits par Classification")
        
        categorical_cols = ["Code ATC", "bcs", "oeb", "bioequivalence"]
        cols = st.columns(2)
        col_index = 0
        
        for col in categorical_cols:
            # Tente d'utiliser Code_ATC si Code ATC n'existe pas
            col_key = col if col in df.columns else (col.replace(" ", "_") if col == "Code ATC" and "Code_ATC" in df.columns else None)
            
            if col_key and col_key in df.columns:
                valid = df[df[col_key].astype(str).str.strip() != ""]
                
                if not valid.empty:
                    # Utilisation du Bar Chart pour une meilleure comparaison
                    count_df = valid.groupby(col_key).size().reset_index(name='Count')
                    
                    # Limite aux 10 premières catégories pour les graphiques à barres trop longs
                    if len(count_df) > 10:
                        count_df = count_df.nlargest(10, 'Count')
                        title = f"Top 10 : {col.upper()}"
                    else:
                        title = f"Distribution par {col.upper()}"
                    
                    fig = px.bar(
                        count_df, 
                        x=col_key, 
                        y='Count', 
                        title=title,
                        color=col_key,
                        template='plotly_white'
                    )
                    
                    with cols[col_index % 2]:
                        st.plotly_chart(fig, use_container_width=True)
                    col_index += 1

        # Classes Thérapeutiques (Pie Chart) 
        if "type" in df.columns:
            valid_type = df[df["type"].astype(str).str.strip() != ""]
            if not valid_type.empty:
                fig_class = px.pie(
                    valid_type, 
                    names="type", 
                    title="Distribution des Classes Thérapeutiques",
                    template='plotly_white'
                )
                st.plotly_chart(fig_class, use_container_width=True)

        # --- 2. Analyse des Prix (Relation Numérique/Catégorielle) ---
        valid_prices = df[pd.to_numeric(df["Prix_num"], errors="coerce").notna()].copy()
        valid_prices["Prix_num"] = valid_prices["Prix_num"].astype(float)

        if not valid_prices.empty:
            st.markdown("---")
            st.subheader("Analyse des Prix")

            # 2.1. Top 10 Existing Bar Chart
            top10 = valid_prices.nlargest(10, "Prix_num")
            fig_top10 = px.bar(top10, x="name", y="Prix_num", 
                                 title="Top 10 des Médicaments les Plus Chers",
                                 template='plotly_white')
            st.plotly_chart(fig_top10, use_container_width=True)

            # 2.2. Price Distribution Histogram
            fig_hist = px.histogram(valid_prices, x="Prix_num", nbins=20, 
                                     title="Distribution des Prix",
                                     template='plotly_white')
            st.plotly_chart(fig_hist, use_container_width=True)
            
            # 2.3. Box Plot de Prix par Classe Thérapeutique
            if "type" in valid_prices.columns:
                valid_type_prices = valid_prices[valid_prices["type"].astype(str).str.strip() != ""]
                
                # Optionnel : Afficher seulement les 15 premières classes si le nombre est trop grand
                top_types = valid_type_prices['type'].value_counts().nlargest(15).index.tolist()
                filtered_prices = valid_type_prices[valid_type_prices['type'].isin(top_types)]
                
                if not filtered_prices.empty:
                    fig_box = px.box(
                        filtered_prices, 
                        x="type", 
                        y="Prix_num", 
                        title="Distribution des Prix par Classe Thérapeutique (Top 15)",
                        color="type",
                        template='plotly_white'
                    )
                    fig_box.update_layout(xaxis_title="Classe Thérapeutique", yaxis_title="Prix (Numérique)", showlegend=False)
                    st.plotly_chart(fig_box, use_container_width=True)
        else:
            st.info("No valid numeric price data to display.")


    # OBSERVATIONS
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
                conn.execute(
                    "UPDATE drugs SET Observations = ? WHERE name = ?",
                    (comment, product)
                )
                conn.commit()
                conn.close()
                st.success("✅ Observation saved and linked to product.")
                load_data.clear()
                st.rerun()

        st.markdown("---")
        conn = sqlite3.connect(db_path)
        df_obs = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
        conn.close()

        if df_obs.empty:
            st.info("No observations yet.")
        else:
            page_size = 10
            total_pages = max(1, (len(df_obs) - 1) // page_size + 1)
            page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
            start = (page - 1) * page_size
            end = start + page_size
            page_df = df_obs.iloc[start:end]

            for _, row in page_df.iterrows():
                with st.expander(f"{row['product_name']} ({row['type']}) - {row['date']}"):
                    st.write(row["comment"])
