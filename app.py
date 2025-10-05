import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# === Authentification (mettez ça tout en haut de app.py) ===
import streamlit as st
import hashlib

# Récupérer le dict d'utilisateurs hachés (ou fallback vers dict en dur si pas configuré)
USERS_HASHED = {}
if "credentials" in st.secrets:
    USERS_HASHED = dict(st.secrets["credentials"])
else:
    # fallback (pour dev local seulement) — remplace par des SHA256 réels
    USERS_HASHED = {
        "admin": hashlib.sha256("monMDPsecret".encode()).hexdigest(),
        "user1": hashlib.sha256("motdepasse1".encode()).hexdigest()
    }

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

def check_password(username, password):
    """Compare sha256(password) avec la valeur hachée enregistrée."""
    if username not in USERS_HASHED:
        return False
    hashed_input = hashlib.sha256(password.encode()).hexdigest()
    return hashed_input == USERS_HASHED.get(username)

# Si pas encore authentifié -> afficher le formulaire
if not st.session_state.authenticated:
    with st.form("login_form", clear_on_submit=False):
        st.markdown("## 🔒 Connexion")
        user = st.text_input("Nom d'utilisateur")
        pwd = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")
        if submitted:
            if check_password(user, pwd):
                st.session_state.authenticated = True
                st.session_state.username = user
                st.success(f"Bienvenue {user} !")
                # rafraîchir la page pour que le reste de l'app s'affiche sans le formulaire
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect")
    # stopper l'exécution pour être sûr que le reste n'apparaisse pas
    st.stop()
else:
    # authentifié -> afficher qui est connecté et bouton logout dans la barre latérale
    st.sidebar.markdown(f"**Connecté en tant que :** {st.session_state.username}")
    if st.sidebar.button("🔓 Se déconnecter"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.experimental_rerun()
# === fin bloc authentification ===
# =========================
# Connexion DB + utilitaires
# =========================
DB_PATH = "data/all_pharma.db"  # base contenant PillPilot + Rosheta

def get_connection():
    return sqlite3.connect(DB_PATH)

def load_data():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM drugs", conn)
        # Créer les colonnes d'observations si elles n'existent pas
        if "observation_medicale" not in df.columns:
            df["observation_medicale"] = None
        if "observation_commerciale" not in df.columns:
            df["observation_commerciale"] = None
        if "id" not in df.columns:
            df.reset_index(inplace=True)
            df.rename(columns={"index": "id"}, inplace=True)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la table : {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def extraire_prix(texte):
    import re
    match = re.search(r"(\d+[\.,]?\d*)", str(texte))
    return float(match.group(1).replace(",", ".")) if match else None

def ajouter_observation(med_id, medical, commercial):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE drugs
        SET observation_medicale = ?, observation_commerciale = ?, date_modif = ?
        WHERE id = ?
    """, (medical, commercial, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), med_id))
    conn.commit()
    conn.close()

# =========================
# Interface Streamlit
# =========================
menu = st.sidebar.radio("📌 Navigation", [
    "🏠 Accueil",
    "💊 Médicaments",
    "✍️ Observations",
    "📊 Dashboard"
])

# =========================
# 🏠 ACCUEIL
# =========================
if menu == "🏠 Accueil":
    st.title("💊 Pharma Pipeline")
    st.write("Bienvenue dans l’outil d’évaluation des produits pharmaceutiques.")
    st.write("Utilise le menu latéral pour naviguer.")

# =========================
# 💊 LISTE MÉDICAMENTS
# =========================
elif menu == "💊 Médicaments":
    st.header("💊 Liste des médicaments")
    df = load_data()
    df["Prix_num"] = df["price"].apply(extraire_prix)
    st.dataframe(df)

# =========================
# ✍️ OBSERVATIONS
# =========================
elif menu == "✍️ Observations":
    st.header("✍️ Ajouter des observations")
    df = load_data()

    med_choice = st.selectbox("Sélectionner un médicament :", df["name"].fillna("").tolist())
    med_id = df[df["name"] == med_choice]["id"].values[0]

    obs_med = st.text_area("Observation médicale :")
    obs_com = st.text_area("Observation commerciale :")

    if st.button("💾 Enregistrer"):
        ajouter_observation(med_id, obs_med, obs_com)
        st.success("✅ Observations enregistrées avec succès !")

# =========================
# 📊 DASHBOARD
# =========================
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard - Analyse globale")
    df = load_data()
    df["Prix_num"] = df["price"].apply(extraire_prix)

    # Pie charts pour ATC, BCS, OEB, Bioéquivalence
    for col in ["atc", "bcs", "oeb", "bioequivalence"]:
        if col in df.columns:
            fig = px.pie(df, names=col, title=f"Répartition par {col.upper()}")
            st.plotly_chart(fig, use_container_width=True)

    # Pie chart pour les classes thérapeutiques
    if "type" in df.columns:
        fig_class = px.pie(df, names="type", title="Répartition des classes thérapeutiques")
        st.plotly_chart(fig_class, use_container_width=True)

    # Top 10 prix
    if df["Prix_num"].notna().any():
        top10 = df.nlargest(10, "Prix_num")
        fig = px.bar(top10, x="name", y="Prix_num", title="Top 10 Médicaments les plus chers")
        st.plotly_chart(fig, use_container_width=True)

        fig = px.histogram(df, x="Prix_num", nbins=20, title="Distribution des Prix")
        st.plotly_chart(fig, use_container_width=True)






