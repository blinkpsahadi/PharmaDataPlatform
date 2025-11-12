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
                
        import streamlit as st
        import pandas as pd
        import plotly.express as px
        from datetime import date
        
        # Configuration de la page Streamlit pour imiter le style général
        st.set_page_config(layout="wide", page_title="Rapport Immunosuppresseurs")
        
        # --- Fonctions de simulation de données (à remplacer par vos données réelles) ---
        
        def load_data():
            """Charge ou simule les données de l'analyse."""
            
            # Remplacement temporaire des données du fichier CSV/Excel par un DataFrame simulé
            # Vos données réelles devront être chargées ici.
            
            # 1. Données de nomenclature (Présent vs Hors nomenclature)
            data_nomenclature = {
                'Statut': ['Présent', 'Hors nomenclature'],
                'Nombre de Molécules': [56, 27],
                'Liste DCI': [
                    "Imatinib, Dasatinib, Nilotinib, Bosutinib, Ponatinib, Gefitinib, Erlotinib, Afatinib, Osimertinib, Neratinib, Ibrutinib, Acalabrutinib, Zanubrutinib, Sunitinib, Sorafenib, Pazopanib, Regorafenib, Cabozantinib, Lenvatinib, Gilteritinib, Axitinib, Vaclosporin, Tacrolimus, Tofacitinib, Sirolimus, Everolimus, Léflunomide, Azathioprine, Diméthyle fumarate",
                    "Pimecrolimus, Asciminib, Dacomitinib, Crizotinib, Ceritinib, Alectinib, Brigatinib, Lorlatinib, Tucatinib, Acalabrutinib, Zanubrutinib, Vandetanib, Midostaurine, Larotrectinib, Entrectinib, Capmatinib, Tepotinib, Selpercatinib, Pralsetinib, Mycophenolic acid, Sirolimus, Tériflunomide, Pirfenidone, Diméthyle fumarate"
                ]
            }
            df_nomenclature = pd.DataFrame(data_nomenclature)
            
            # 2. Données de classification groupée (Type de Classification)
            data_classification = {
                'Classification Groupée': ['Protein kinase inhibitors', 'Alkylating agents', 'Autres'],
                'Nombre de Molécules': [51, 31, 1] # 1 pour 'nan'
            }
            df_classification = pd.DataFrame(data_classification)
            
            # 3. Données d'indication
            data_indication = {
                'Indication': ['Oncologie', 'Immunosupresseur', 'Cytostatiques', 'Immunosupresseurs'],
                'Nombre de Molécules': [63, 8, 7, 5]
            }
            df_indication = pd.DataFrame(data_indication)
            
            return df_nomenclature, df_classification, df_indication
        
        # --- Fonctions de création de graphiques Plotly ---
        
        def create_pie_chart(df, title):
            """Crée un diagramme circulaire (Pie Chart) Plotly Express."""
            fig = px.pie(
                df,
                names='Statut',
                values='Nombre de Molécules',
                title=f'<span style="font-size:1.1em; color:#34495e;">{title}</span>',
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            
            # Amélioration du layout pour le style dashboard
            fig.update_layout(
                showlegend=True,
                margin=dict(l=20, r=20, t=50, b=20),
                font=dict(family="Arial, sans-serif"),
                plot_bgcolor='#f9f9f9',
                paper_bgcolor='#f9f9f9'
            )
            fig.update_traces(
                textinfo='percent+label', 
                marker=dict(line=dict(color='#FFFFFF', width=1))
            )
            return fig
        
        def create_bar_chart(df, x_col, y_col, color_col, title, y_title="Nombre de Molécules"):
            """Crée un diagramme à barres Plotly Express."""
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=color_col,
                title=f'<span style="font-size:1.1em; color:#34495e;">{title}</span>',
                text_auto=True, # Afficher les valeurs sur les barres
                color_discrete_sequence=px.colors.qualitative.Vivid
            )
            
            # Amélioration du layout
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title=y_title,
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                font=dict(family="Arial, sans-serif"),
                plot_bgcolor='#f9f9f9',
                paper_bgcolor='#f9f9f9'
            )
            fig.update_traces(
                textfont_color='black'
            )
            
            return fig
        
        # --- Styles CSS personnalisés pour imiter le HTML ---
        
        st.markdown("""
        <style>
            /* Style général du conteneur (similaire à .container) */
            .stApp {
                background-color: #f4f7f6;
            }
            
            /* Titre principal (similaire à h1) */
            h1 {
                color: #007bff;
                border-bottom: 3px solid #007bff;
                padding-bottom: 10px;
                margin-bottom: 30px;
                font-size: 2em;
            }
        
            /* Sous-titres (similaire à h2) */
            h2 {
                color: #34495e;
                margin-top: 40px;
                font-size: 1.5em;
            }
            
            /* Conteneur de graphique (similaire à .chart-box) */
            .stContainer {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 15px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.05);
                margin-bottom: 25px; /* Espace entre les chart-box dans la grille */
            }
            
            /* Enlever les marges par défaut des colonnes pour mieux contrôler le padding */
            .css-1r6r062 {
                padding: 0 !important;
            }
            
        </style>
        """, unsafe_allow_html=True)
        
        
        # --- Section Tableau de Bord ---
        
        # Charger les données simulées
        df_nom, df_class, df_ind = load_data()
        
        # Titre du rapport
        st.markdown("<h1>Synthèse des Données sur les Immunosuppresseurs (Forme Sèche)</h1>", unsafe_allow_html=True)
        st.write(f"Analyse des molécules {date.today().strftime('%d/%m/%Y')}.")
        
        
        # ----------------------------------------------------
        # Section 1: Distribution Totale (Grid 2 colonnes)
        # ----------------------------------------------------
        
        st.markdown("<h2>Distribution Totale</h2>", unsafe_allow_html=True)
        
        # Création de la grille (grid-container)
        col1, col2 = st.columns(2)
        
        # Graphique 1: Distribution par Nomenclature (Pie Chart)
        with col1:
            with st.container(): # Imite le chart-box
                fig_nom = create_pie_chart(
                    df_nom, 
                    "Distribution par Nomenclature"
                )
                st.plotly_chart(fig_nom, use_container_width=True)
        
        
        # Graphique 2: Distribution par Type de Classification (Bar Chart)
        with col2:
            with st.container(): # Imite le chart-box
                fig_class = create_bar_chart(
                    df_class, 
                    x_col='Classification Groupée', 
                    y_col='Nombre de Molécules', 
                    color_col='Classification Groupée', 
                    title="Distribution par Type de Classification (Top 3)"
                )
                st.plotly_chart(fig_class, use_container_width=True)
        
        
        # ----------------------------------------------------
        # Section 2: Détail par Caractéristique (1 colonne pleine)
        # ----------------------------------------------------
        
        st.markdown("<h2>Détail par Caractéristique</h2>", unsafe_allow_html=True)
        
        # Conteneur pour le graphique d'Indication (s'étend sur toute la largeur)
        with st.container(): # Imite le chart-box
            fig_ind = create_bar_chart(
                df_ind, 
                x_col='Indication', 
                y_col='Nombre de Molécules', 
                color_col='Indication', 
                title="Distribution par Indication"
            )
            st.plotly_chart(fig_ind, use_container_width=True)
            
        st.write("---")

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

