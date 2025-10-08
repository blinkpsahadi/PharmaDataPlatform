import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

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
    """Trouve dynamiquement le chemin vers la base SQLite, même dans Streamlit Cloud."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()  # fallback si __file__ non défini

    possible_paths = [
        os.path.join(base_dir, "data", "all_pharma.db"),
        os.path.join(os.getcwd(), "data", "all_pharma.db"),
        "data/all_pharma.db",
        "all_pharma.db",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    st.error("❌ Database not found. Place 'all_pharma.db' in the folder `data/`.")
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

if menu == "🚪 Logout":
    st.session_state.authenticated = False
    st.rerun()

# =========================
# 🏠 ACCUEIL
# =========================
if menu == "🏠 Home":
    st.title("💊 Pharma Data Platform")
    st.markdown("Welcome to the Pharmaceutical Managment & Analysis Pharma Data Platform 📊")

# =========================
# 💊 PRODUITS
# =========================
elif menu == "💊 Products":
    st.header("💊 List of products")

    df = load_data()

    # Recherche
    search = st.text_input("🔍 Research by name, or substance.")

    if search:
        df = df[df["name"].str.contains(search, case=False, na=False) |
                df["type"].str.contains(search, case=False, na=False)]

    # Pagination
    items_per_page = 100
    total_pages = (len(df) // items_per_page) + 1
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    start, end = (page - 1) * items_per_page, page * items_per_page
    subset = df.iloc[start:end]

    # Affichage des produits
    for _, row in subset.iterrows():
        with st.expander(f"💊 {row['name']}"):
            st.markdown(f"**ATC :** {row.get('atc', 'N/A')}")
            st.markdown(f"**Type :** {row.get('type', 'N/A')}")
            st.markdown(f"**Price :** {row.get('price', 'N/A')}")
            if 'description' in df.columns and row.get("description"):
                st.markdown("**Description :**", unsafe_allow_html=True)
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
import streamlit as st
import sqlite3
import pandas as pd

# =========================
# 🔍 FONCTIONS UTILITAIRES
# =========================
def init_db():
    """Créer la table des observations si elle n'existe pas."""
    conn = sqlite3.connect("data/all_pharma.db")
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

def load_observations():
    """Charger toutes les observations enregistrées."""
    conn = sqlite3.connect("data/all_pharma.db")
    df = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
    conn.close()
    return df

def get_all_products():
    """Charger les noms des produits depuis la table drugs."""
    conn = sqlite3.connect("data/all_pharma.db")
    try:
        df = pd.read_sql_query("SELECT DISTINCT name FROM drugs ORDER BY name ASC", conn)
        conn.close()
        return df["name"].tolist()
    except Exception:
        conn.close()
        return []

def add_observation(product, obs_type, comment):
    """Insérer une nouvelle observation."""
    conn = sqlite3.connect("data/all_pharma.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO observations (product_name, type, comment) VALUES (?, ?, ?)",
        (product, obs_type, comment)
    )
    conn.commit()
    conn.close()

def delete_observation(obs_id):
    """Supprimer une observation."""
    conn = sqlite3.connect("data/all_pharma.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM observations WHERE id = ?", (obs_id,))
    conn.commit()
    conn.close()


# =========================
# 💬 SECTION STREAMLIT
# =========================
def render_observations_section():
    st.header("🩺 Commercial & Medical Observations")

    init_db()  # s'assurer que la table existe

    # Liste déroulante des produits
    products = get_all_products()
    st.subheader("Add a new observation")

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_product = st.selectbox(
            "Choose or Type a product",
            options=["Type..."] + products,
            index=0
        )
    with col2:
        obs_type = st.selectbox("Type of observation", ["Commercial", "Medical", "Other"])

    if selected_product == "Type...":
        product_name = st.text_input("Nom du produit")
    else:
        product_name = selected_product

    comment = st.text_area("💬 observation's details")

    if st.button("💾 Save observation"):
        if product_name.strip() == "" or comment.strip() == "":
            st.warning("Please add the product's name and a comment.")
        else:
            add_observation(product_name.strip(), obs_type, comment.strip())
            st.success(f"Observation added for **{product_name}**.")
            st.rerun()

    st.markdown("---")
    st.subheader("📜 History of Observations")

    df_obs = load_observations()
    if df_obs.empty:
        st.info("No observation saved for the moment.")
    else:
        st.dataframe(df_obs, use_container_width=True)

        # Option de suppression
        obs_to_delete = st.selectbox(
            "🗑️ Delete observation",
            options=[""] + [f"{r['id']} - {r['product_name']} ({r['type']})" for _, r in df_obs.iterrows()]
        )
        if obs_to_delete:
            obs_id = int(obs_to_delete.split(" - ")[0])
            if st.button("Confirm suppression"):
                delete_observation(obs_id)
                st.success("Observation Deleted Successfully.")
                st.rerun()

    elif menu == "🧾 Observations":
        st.header("🧾 Medical and Commercial Observations")
    
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categorie TEXT,
                produit TEXT,
                observation TEXT
            )
        """)
    
        with st.form("observation_form"):
            categorie = st.selectbox("Category", ["Commercial", "Medical"])
            produit = st.text_input("Concerned Product")
            observation = st.text_area("Observation")
            submit = st.form_submit_button("💾 Save")
    
            if submit and produit and observation:
                conn.execute(
                    "INSERT INTO observations (categorie, produit, observation) VALUES (?, ?, ?)",
                    (categorie, produit, observation)
                )
                conn.commit()
                st.success("Observation Saved ✅")

    # Liste des observations
    df_obs = pd.read_sql_query("SELECT * FROM observations", conn)
    conn.close()

        if not df_obs.empty:
            st.subheader("📋 List of observations")
            for _, row in df_obs.iterrows():
                with st.expander(f"{row['categorie']} - {row['produit']}"):
                    st.write(row['observation'])







