import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# =========================
# 🔐 AUTHENTIFICATION
# =========================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

if "credentials" in st.secrets:
    USERS = dict(st.secrets["credentials"])
else:
    USERS = {"admin": "monMDPsecret", "user1": "autreMDP"}

def check_password(username, password):
    return username in USERS and USERS[username] == password

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.markdown("## 🔒 Connexion")
        user = st.text_input("Nom d'utilisateur")
        pwd = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")
        if submitted:
            if check_password(user, pwd):
                st.session_state.authenticated = True
                st.session_state.username = user
                st.success(f"Bienvenue {user} 👋")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
    st.stop()
else:
    st.sidebar.markdown(f"**Connecté en tant que :** {st.session_state.username}")
    if st.sidebar.button("🔓 Se déconnecter"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

# =========================
# 📦 FONCTIONS
# =========================

@st.cache_data
def get_db_path():
    """Retourne le chemin absolu vers la base de données, même en déploiement."""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "data", "all_pharma.db"),
        os.path.join("data", "all_pharma.db"),
        "all_pharma.db"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    st.error("❌ Base de données introuvable. Assurez-vous que 'data/all_pharma.db' existe.")
    st.stop()

@st.cache_data
def load_data():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM drugs", conn)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la table 'drugs' : {e}")
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
    ["🏠 Accueil", "💊 Produits", "📊 Dashboard", "🧾 Observations", "🚪 Déconnexion"]
)

if menu == "🚪 Déconnexion":
    st.session_state.authenticated = False
    st.rerun()

# =========================
# 🏠 ACCUEIL
# =========================
if menu == "🏠 Accueil":
    st.title("💊 Pharma Data Platform")
    st.markdown("Bienvenue sur la plateforme d’analyse et de gestion pharmaceutique 📊")

# =========================
# 💊 PRODUITS
# =========================
elif menu == "💊 Produits":
    st.header("💊 Liste des produits (base Rosheta + PillPilot)")

    df = load_data()

    # Recherche
    search = st.text_input("🔍 Rechercher un produit par nom, substance ou classe thérapeutique")

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
            st.markdown(f"**Prix :** {row.get('price', 'N/A')}")
            if 'description' in df.columns and row.get("description"):
                st.markdown("**Description :**", unsafe_allow_html=True)
                st.markdown(row["description"], unsafe_allow_html=True)
            st.markdown("---")

# =========================
# 📊 DASHBOARD
# =========================
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard - Analyse globale")
    df = load_data()
    df["Prix_num"] = df["price"].apply(extraire_prix)

    for col in ["atc", "bcs", "oeb", "bioequivalence"]:
        if col in df.columns:
            fig = px.pie(df, names=col, title=f"Répartition par {col.upper()}")
            st.plotly_chart(fig, use_container_width=True)

    if "type" in df.columns:
        fig_class = px.pie(df, names="type", title="Répartition des classes thérapeutiques")
        st.plotly_chart(fig_class, use_container_width=True)

    if df["Prix_num"].notna().any():
        top10 = df.nlargest(10, "Prix_num")
        fig = px.bar(top10, x="name", y="Prix_num", title="Top 10 Médicaments les plus chers")
        st.plotly_chart(fig, use_container_width=True)

        fig = px.histogram(df, x="Prix_num", nbins=20, title="Distribution des Prix")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# 🧾 OBSERVATIONS
# =========================
elif menu == "🧾 Observations":
    st.header("🧾 Observations Commerciales & Médicales")

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
        categorie = st.selectbox("Catégorie", ["Commerciale", "Médicale"])
        produit = st.text_input("Produit concerné")
        observation = st.text_area("Observation")
        submit = st.form_submit_button("💾 Enregistrer")

        if submit and produit and observation:
            conn.execute(
                "INSERT INTO observations (categorie, produit, observation) VALUES (?, ?, ?)",
                (categorie, produit, observation)
            )
            conn.commit()
            st.success("Observation enregistrée ✅")

    # Liste des observations
    df_obs = pd.read_sql_query("SELECT * FROM observations", conn)
    conn.close()

    if not df_obs.empty:
        st.subheader("📋 Liste des observations")
        for _, row in df_obs.iterrows():
            with st.expander(f"{row['categorie']} - {row['produit']}"):
                st.write(row['observation'])
