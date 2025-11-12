import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import re
from datetime import date # Ajout de l'importation manquante pour la fonction load_data simulée

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

st.markdown("""
<style>
/* IMPORTANT: Suppression de la majorité des styles CSS qui forçaient les couleurs de fond claires 
    pour permettre au mode sombre de Streamlit/navigateur de fonctionner.
    Seuls les ajustements de mise en page réactifs sont conservés. 
*/
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

/* Ajustements pour les titres qui forçaient des couleurs claires.
    Nous conservons le style de bordure, mais la couleur du texte et de la bordure 
    devrait maintenant respecter le thème Streamlit.
*/
h1 {
    /* La couleur sera gérée par le thème Streamlit (noir en clair, blanc en sombre) */
    /* color: #007bff; <-- RETIRÉ */
    border-bottom: 3px solid var(--primary-color, #007bff); /* Utiliser la variable CSS de Streamlit */
    padding-bottom: 10px;
    margin-bottom: 30px;
    font-size: 2em;
}

h2 {
    /* La couleur sera gérée par le thème Streamlit */
    /* color: #34495e; <-- RETIRÉ */
    margin-top: 40px;
    font-size: 1.5em;
}

/* Le conteneur du graphique (chart-box) sera maintenant transparent ou respectera le fond Streamlit */
.stContainer {
    /* background-color: #f9f9f9; <-- RETIRÉ */
    /* border: 1px solid #ddd; <-- RETIRÉ */
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05); /* Laissez une légère ombre */
    margin-bottom: 25px;
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
    # Déplacé le sidebar de navigation dans la section principale pour être en `main_col`
    # Ceci est maintenant fait plus bas dans la section 'APP NAVIGATION'
    pass


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
    # Pour l'environnement de l'immersive, nous ne pouvons pas arrêter l'exécution.
    # st.error("❌ Database not found. Place 'all_pharma.db' in the `data/` folder or next to the app.")
    # st.stop()
    # On retourne un chemin par défaut et on laisse load_data gérer l'échec.
    return "all_pharma.db" 


@st.cache_data
def load_data():
    db = get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db)
        df = pd.read_sql_query("SELECT * FROM drugs", conn)
    except Exception as e:
        # En cas d'erreur de base de données (ex: fichier non trouvé), on crée un DataFrame vide ou simulé
        st.warning(f"Warning: Could not load data from 'drugs' table: {e}. Using simulated data for continuity.")
        # Générer un DataFrame minimal pour éviter les erreurs de colonnes manquantes
        df = pd.DataFrame({
            "name": ["Paracetamol", "Ibuprofen"],
            "scientific_name": ["Acetaminophen", "Isobutylphenylpropanoic acid"],
            "type": ["Analgesic", "NSAID"],
            "price": ["10 EUR", "5 EUR"],
            "Observations": ["Test observation 1", "Test observation 2"],
            "Code ATC": ["N02BE01", "M01AE01"]
        })
    finally:
        if conn:
            conn.close()
    return df

def ensure_observation_column():
    db = get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(drugs);")
        columns = [info[1] for info in cursor.fetchall()]
        if "Observations" not in columns:
            cursor.execute("ALTER TABLE drugs ADD COLUMN Observations TEXT;")
            conn.commit()
    except Exception:
        # Ignorer l'erreur si la base de données n'existe pas
        pass
    finally:
        if conn:
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
    # L'élément de déconnexion est conservé ici
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
                # Utiliser .str.contains sur la colonne convertie en string
                if c in df.columns:
                    mask |= df[c].astype(str).str.contains(search, case=False, na=False)
            
            # Appliquer le masque si au moins une colonne existe et une recherche est effectuée
            if isinstance(mask, pd.Series):
                df = df[mask]
            elif search and not available_cols:
                st.warning("No searchable columns found in data.")
                df = pd.DataFrame()


        items_per_page = 50
        # Gérer le cas où df est vide après la recherche
        total_rows = len(df)
        total_pages = max(1, (total_rows - 1) // items_per_page + 1)
        
        # S'assurer que la valeur par défaut est valide
        if 'product_page' not in st.session_state:
            st.session_state.product_page = 1
        
        # Mettre à jour la page si la page actuelle dépasse le nombre total de pages
        if st.session_state.product_page > total_pages:
            st.session_state.product_page = total_pages
            
        page = st.number_input("Page", min_value=1, max_value=total_pages, 
                               value=st.session_state.product_page, step=1, key="product_page_input")
        st.session_state.product_page = page # Garder l'état
        
        subset = df.iloc[(page - 1) * items_per_page : page * items_per_page]

        if subset.empty:
            st.info("No products found matching your criteria.")
        else:
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
        
        # Helper pour extraire le prix numérique (pas utilisé ici, mais conservé pour la logique)
        def safe_extract(val):
            try:
                # Extrait le premier nombre flottant (supporte les virgules comme séparateur décimal)
                match = re.search(r"[\d]+[.,]?[\d]*", str(val))
                return float(match.group().replace(",", ".")) if match else None
            except Exception:
                return None
                
        # --- Fonctions de simulation de données (à remplacer par vos données réelles) ---
        
        # Renommée load_dashboard_data pour éviter le conflit avec le load_data principal
        @st.cache_data
        def load_dashboard_data():
            """Charge ou simule les données de l'analyse."""
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
        
            # 4. Données de forme galénique
            data_forme = {
                'Forme Galénique': ['Comprimé', 'Gélule', 'Comprimé pelliculé', 'Crème'],
                'Nombre de Molécules': [45, 20, 15, 3] # Exemples basés sur les données du fichier
            }
            df_forme = pd.DataFrame(data_forme)
            
            return df_nomenclature, df_classification, df_indication, df_forme # Retourne df_forme
            
        # --- Fonctions de création de graphiques Plotly ---
        
        # Thème réactif : 'streamlit' pour respecter le thème clair/sombre de Streamlit
        PLOTLY_TEMPLATE = "streamlit" 

        def create_pie_chart(df, names_col, values_col, title):
            """Crée un diagramme circulaire (Pie Chart) Plotly Express."""
            fig = px.pie(
                df,
                names=names_col,
                values=values_col,
                title=title, # Suppression du style en ligne
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template=PLOTLY_TEMPLATE # Utilisation du thème Streamlit
            )
            
            # Amélioration du layout pour le style dashboard
            fig.update_layout(
                showlegend=True,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400, # Fixer la hauteur pour l'alignement dans la grille
                # Suppression des couleurs de fond forcées pour Plotly
                # plot_bgcolor='#f9f9f9', <-- RETIRÉ
                # paper_bgcolor='#f9f9f9', <-- RETIRÉ
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
                title=title, # Suppression du style en ligne
                text_auto=True, # Afficher les valeurs sur les barres
                color_discrete_sequence=px.colors.qualitative.Vivid,
                template=PLOTLY_TEMPLATE # Utilisation du thème Streamlit
            )
            
            # Amélioration du layout
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title=y_title,
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400, # Fixer la hauteur pour l'alignement
                # Suppression des couleurs de fond forcées pour Plotly
                # plot_bgcolor='#f9f9f9', <-- RETIRÉ
                # paper_bgcolor='#f9f9f9', <-- RETIRÉ
            )
            # Retiré textfont_color='black' pour laisser Plotly gérer la couleur du texte en mode sombre
            
            return fig
        
        # --- Styles CSS personnalisés pour imiter le HTML ---
        
        # Suppression du bloc st.markdown avec les styles forcés de #f4f7f6 et #f9f9f9
        # qui était la cause principale de l'incompatibilité avec le dark mode.
        
        
        # --- Section Tableau de Bord ---
        
        # Charger les données simulées (Mise à jour pour recevoir df_forme)
        df_nom, df_class, df_ind, df_forme = load_dashboard_data()
        
        # Titre du rapport
        # Utilisation de st.title pour que Streamlit gère le style du titre principal
        st.markdown("<h1>Synthèse des Données sur les Immunosuppresseurs (Forme Sèche)</h1>", unsafe_allow_html=True)
        st.write(f"Analyse des molécules {date.today().strftime('%d/%m/%Y')}.")
        
        
        # ----------------------------------------------------
        # Section 1: Distribution Totale (Grid 2 colonnes)
        # ----------------------------------------------------
        
        st.markdown("<h2>Distribution par Molécule et Caractéristique</h2>", unsafe_allow_html=True)
        
        # Création de la grille (grid-container)
        col1, col2 = st.columns(2)
        
        # Graphique 1: Distribution par Nomenclature (Pie Chart)
        with col1:
            with st.container(): # Simule le chart-box, le style est maintenant géré par le CSS au début du script
                fig_nom = create_pie_chart(
                    df_nom, 
                    names_col='Statut',
                    values_col='Nombre de Molécules',
                    title="Distribution par Nomenclature"
                )
                st.plotly_chart(fig_nom, use_container_width=True)
        
        
        # Graphique 2: Distribution par Type de Classification (Bar Chart)
        with col2:
            with st.container(): # Simule le chart-box
                fig_class = create_bar_chart(
                    df_class, 
                    x_col='Classification Groupée', 
                    y_col='Nombre de Molécules', 
                    color_col='Classification Groupée', 
                    title="Distribution par Type de Classification (Top 3)"
                )
                st.plotly_chart(fig_class, use_container_width=True)
        
        
        # ----------------------------------------------------
        # Section 2: Détail par Caractéristique (Grille 2 colonnes)
        # AJOUT du graphique de la forme galénique
        # ----------------------------------------------------
        
        st.markdown("<h2>Détail par Indication et Forme Galénique</h2>", unsafe_allow_html=True)
        
        col3, col4 = st.columns(2)
        
        # Graphique 3: Distribution par Indication
        with col3:
            with st.container(): # Simule le chart-box
                fig_ind = create_bar_chart(
                    df_ind, 
                    x_col='Indication', 
                    y_col='Nombre de Molécules', 
                    color_col='Indication', 
                    title="Distribution par Indication"
                )
                st.plotly_chart(fig_ind, use_container_width=True)
        
        # Graphique 4: Distribution par Forme Galénique (NOUVEAU)
        with col4:
            with st.container(): # Simule le chart-box
                fig_forme = create_bar_chart(
                    df_forme, 
                    x_col='Forme Galénique', 
                    y_col='Nombre de Molécules', 
                    color_col='Forme Galénique', 
                    title="Distribution par Forme Galénique"
                )
                st.plotly_chart(fig_forme, use_container_width=True)
                
        st.write("---")
    # OBSERVATIONS
    elif menu == "🧾 Observations":
        st.header("🩺 Commercial & Medical Observations")
        db_path = get_db_path()
        conn = None
        
        try:
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
        except Exception as e:
            st.error(f"Error accessing database for Observations: {e}. Cannot display form.")
            products = [] # Vide la liste de produits pour éviter une erreur dans st.selectbox
        finally:
             if conn:
                 conn.close()

        with st.form("new_obs", clear_on_submit=True):
            product = st.selectbox("Product", ["Type manually..."] + products)
            obs_type = st.selectbox("Type", ["Commercial", "Medical", "Other"])
            if product == "Type manually...":
                product = st.text_input("Manual Product Name")
            comment = st.text_area("💬 Observation")
            submit = st.form_submit_button("💾 Save")
            
            if submit and product and comment:
                conn = None
                try:
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
                    st.success("✅ Observation saved and linked to product.")
                    # st.cache_data.clear() est la bonne manière de vider le cache maintenant
                    load_data.clear() 
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving observation: {e}")
                finally:
                    if conn:
                        conn.close()
            elif submit:
                st.warning("Please enter a product name and an observation.")

        st.markdown("---")
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            df_obs = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
        except Exception:
            df_obs = pd.DataFrame()
        finally:
            if conn:
                conn.close()

        if df_obs.empty:
            st.info("No observations yet.")
        else:
            page_size = 10
            total_pages = max(1, (len(df_obs) - 1) // page_size + 1)
            # S'assurer que la valeur par défaut est valide
            if 'obs_page' not in st.session_state:
                st.session_state.obs_page = 1
            
            # Mettre à jour la page si la page actuelle dépasse le nombre total de pages
            if st.session_state.obs_page > total_pages:
                st.session_state.obs_page = total_pages
                
            page = st.number_input("Page", min_value=1, max_value=total_pages, 
                                   value=st.session_state.obs_page, step=1, key="obs_page_input")
            st.session_state.obs_page = page
            
            start = (page - 1) * page_size
            end = start + page_size
            page_df = df_obs.iloc[start:end]

            for _, row in page_df.iterrows():
                with st.expander(f"{row['product_name']} ({row['type']}) - {row['date']}"):
                    st.write(row["comment"])
