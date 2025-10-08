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
# 🔧 FONCTIONS UTILES
# =========================
@st.cache_data
def load_data():
    # Déterminer le chemin du fichier SQLite (dossier "data")
    db_path = os.path.join(os.path.dirname(__file__), "data", "all_pharma.db")

    # Vérifier que la base existe
    if not os.path.exists(db_path):
        st.error(f"⚠️ Base de données introuvable : {db_path}")
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(db_path)
        # Vérifier si la table 'drugs' existe
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
        if "drugs" not in tables["name"].values:
            st.error("⚠️ La table 'drugs' est absente de la base.")
            st.dataframe(tables)  # Montre les tables disponibles pour débogage
            conn.close()
            return pd.DataFrame()

        # Charger la table drugs
        df = pd.read_sql("SELECT * FROM drugs;", conn)
        conn.close()

        if df.empty:
            st.warning("La table 'drugs' est vide.")
        else:
            st.success(f"✅ Base chargée ({len(df)} enregistrements)")

        return df

    except Exception as e:
        st.error(f"❌ Erreur lors du chargement de la base : {e}")
        return pd.DataFrame()

def extraire_prix(val):
    try:
        if isinstance(val, str):
            val = val.replace("DA", "").replace(",", ".").strip()
        return float(val)
    except:
        return None

def init_observation_table():
    conn = sqlite3.connect("all_pharma.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name TEXT,
            type TEXT,
            commentaire TEXT,
            auteur TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_observations():
    conn = sqlite3.connect("all_pharma.db")
    df_obs = pd.read_sql_query("SELECT * FROM observations", conn)
    conn.close()
    return df_obs

def add_observation(drug_name, type_obs, commentaire, auteur):
    conn = sqlite3.connect("all_pharma.db")
    conn.execute("INSERT INTO observations (drug_name, type, commentaire, auteur) VALUES (?, ?, ?, ?)",
                 (drug_name, type_obs, commentaire, auteur))
    conn.commit()
    conn.close()

def update_observation(obs_id, commentaire):
    conn = sqlite3.connect("all_pharma.db")
    conn.execute("UPDATE observations SET commentaire = ? WHERE id = ?", (commentaire, obs_id))
    conn.commit()
    conn.close()

def delete_observation(obs_id):
    conn = sqlite3.connect("all_pharma.db")
    conn.execute("DELETE FROM observations WHERE id = ?", (obs_id,))
    conn.commit()
    conn.close()

# Initialisation si nécessaire
init_observation_table()

# =========================
# 🧭 NAVIGATION
# =========================
st.sidebar.title("📚 Navigation")
menu = st.sidebar.radio(
    "Aller à :", 
    ["💊 Médicaments", "📊 Dashboard", "🗒️ Observations"]
)

# =========================
# 💊 MÉDICAMENTS
# =========================
if menu == "💊 Médicaments":
    st.header("💊 Liste des Médicaments")
    df = load_data()

    search_term = st.text_input("🔍 Rechercher un médicament :")
    if search_term:
        df = df[df["name"].str.contains(search_term, case=False, na=False)]

    items_per_page = 100
    total_pages = max(1, (len(df) - 1) // items_per_page + 1)
    page = st.number_input("Page :", min_value=1, max_value=total_pages, step=1)

    start = (page - 1) * items_per_page
    end = start + items_per_page
    df_page = df.iloc[start:end]

    st.write(f"Affichage des médicaments {start+1} à {min(end, len(df))} sur {len(df)}")

    for _, row in df_page.iterrows():
        with st.container():
            st.markdown(f"### 🧪 {row['name']}")
            if pd.notna(row.get("price")):
                st.markdown(f"💰 **Prix :** {row['price']}")
            if pd.notna(row.get("type")):
                st.markdown(f"🏷️ **Classe thérapeutique :** {row['type']}")
            if pd.notna(row.get("atc")):
                st.markdown(f"🧬 **ATC :** {row['atc']}")
            if pd.notna(row.get("bcs")):
                st.markdown(f"📘 **BCS :** {row['bcs']}")
            if pd.notna(row.get("bioequivalence")):
                st.markdown(f"⚗️ **Bioéquivalence :** {row['bioequivalence']}")
            if pd.notna(row.get("oeb")):
                st.markdown(f"🧫 **OEB :** {row['oeb']}")
            if pd.notna(row.get("description")):
                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown(f"{row['description']}", unsafe_allow_html=True)
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
# 🗒️ OBSERVATIONS
# =========================
elif menu == "🗒️ Observations":
    st.header("🗒️ Observations Médicales & Commerciales")

    df_obs = get_observations()
    df_drugs = load_data()

    with st.expander("➕ Ajouter une nouvelle observation"):
        col1, col2 = st.columns(2)
        with col1:
            drug = st.selectbox("Médicament :", sorted(df_drugs["name"].unique()))
        with col2:
            type_obs = st.selectbox("Type :", ["Commerciale", "Médicale"])

        commentaire = st.text_area("Observation :", "")
        if st.button("💾 Enregistrer l’observation"):
            add_observation(drug, type_obs, commentaire, st.session_state.username)
            st.success("Observation enregistrée ✅")
            st.rerun()

    st.markdown("### 📋 Liste des observations existantes")

    if not df_obs.empty:
        for _, row in df_obs.iterrows():
            with st.expander(f"💊 {row['drug_name']} — {row['type']} par {row['auteur']}"):
                new_comment = st.text_area("Modifier le commentaire :", row["commentaire"], key=f"edit_{row['id']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Sauvegarder", key=f"save_{row['id']}"):
                        update_observation(row["id"], new_comment)
                        st.success("Observation mise à jour ✅")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Supprimer", key=f"del_{row['id']}"):
                        delete_observation(row["id"])
                        st.warning("Observation supprimée 🗑️")
                        st.rerun()
    else:
        st.info("Aucune observation enregistrée pour le moment.")

