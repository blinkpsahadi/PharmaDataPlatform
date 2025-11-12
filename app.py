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
# DB HELPERS & Data Loading
# ---------------------------
DB_NAME = "all_pharma.db"

@st.cache_data
def get_db_path():
    # En environnement réel, cela trouve le chemin du fichier.
    # Dans l'immersive, nous nous fions à la création/existence du fichier dans le CWD (current working directory)
    return DB_NAME

def create_db_from_csv():
    """Crée la table 'drugs' dans la base de données à partir des données du fichier joint."""
    db_path = get_db_path()
    conn = None
    
    # Simuler le chargement du fichier CSV/Excel fourni dans le contexte
    # Les fichiers joints sont accessibles sous forme de chaînes de texte/csv
    # Nous utilisons le fichier 'CLASSIFICATION_DES_IMMUNOSUPRESSEURS_ATC_DDD_NOMENCLATURE.xlsx - Forme Séche .csv'
    # car il contient les colonnes de classification détaillées nécessaires au dashboard.
    try:
        # Tenter de charger les données du fichier de classification
        csv_snippet = """
CLASSIFICATION DES IMMUNOSUPRESSEURS,,,,,,,,,,,,,,,
N°,DCI,ATC Code,,DDD (OMS) ,Unité,NOM DE MARQUE,Laboratoire Fabricant,Nomenclature,Dosage,Forme,CLASSIFICATION,CODE ATC,ORIGINE,CLASSE OEB,INDICATION
12,PIMECROLIMUS,D11AH02,,Pas de DDD assignée,Pas de DDD assignée,Hors Nomenclature,Hors Nomenclature,Hors Nomenclature,0.01,Crème,Antineoplasiques et immunomodulateurs,L04AX05,CHIMIQUE,OEB 4 ET 5,CYTOSTATIQUES
16,Imatinib,L01EA01,PROTEIN KINASE INHIBITORS,0.4,g,CEMILIC / IMATIB 400,HIKMA PHARMA ALGERIA,Présent,,Gélule,Antineoplasiques et immunomodulateurs,L04AX05,CHIMIQUE,OEB 4 ET 5,CYTOSTATIQUES
17,Imatinib,L01EA01,PROTEIN KINASE INHIBITORS,0.4,g,CEMILIC / IMATIB 401,HIKMA PHARMA ALGERIA,Présent,,Comprimé pelliculé,Antimétabolites et autres agents antiprolifératifs ,L04AX01 ,CHIMIQUE,OEB 4 ET 5,CYTOSTATIQUES
18,Dasatinib,L01EA02,PROTEIN KINASE INHIBITORS,0.1,g,ELPIX,HIKMA PHARMA ALGERIA,Présent,,Comprimé pelliculé,Antimétabolites et autres agents antiprolifératifs ,L04AX01 ,CHIMIQUE,OEB 4 ET 5,CYTOSTATIQUES
"""
        # Utiliser les données brutes du second fichier pour une meilleure représentativité
        # (Snippet 'all_pharma.xlsx - drugs.csv')
        df_base_snippet = """
scientific_name,Code_ATC,therapeutic_class,description,type,source,name,dosage,price,Observations
Methadone syrup 5mg ,N07BC02,ANTALGIQUES ,,Syrup,,Methadone syrup 5mg ,5mg ,,""
Dasatinib Comp/gles 100mg ,L01EA02,ONCOLOGIE,,Comprimé,HIKMA PHARMA ALGERIA,ELPIX,100mg,1000 EUR,""
Nilotinib Comprimé 200mg,L01EA03,ONCOLOGIE,,Gélule,NOVARTIS PHARMA SCHWEIZ AG,TASIGNA,200mg,2000 EUR,""
Everolimus Comprimé 10mg,L04AH02,IMMUNOSUPRESSEUR,,Comprimé,NOVARTIS PHARMA SCHWEIZ AG,AFINITOR,10 mg,500 EUR,""
Léflunomide Comprimé 20mg,L04AK01,ALKYLATING AGENTS,Immunosupresseur,Comprimé,AVENTIS PHARMA S.A,ARAVA,20 mg,150 EUR,""
Tériflunomide Comprimé 14mg,L04AK02,ALKYLATING AGENTS,Immunosupresseur,Comprimé,,,14 mg,250 EUR,""
Pimecrolimus Crème 1%,D11AH02,CYTOSTATIQUES,Immunosupresseur,Crème,Hors Nomenclature,Hors Nomenclature,0.01,50 EUR,""
"""
        # Crée un DataFrame en utilisant les colonnes du second fichier pour Products
        df_base = pd.read_csv(StringIO(df_base_snippet), sep=',')
        
        # Le Dashboard a besoin des colonnes : Nomenclature, Classification, Indication, Forme
        # Ajoutons ces colonnes (simulées pour l'exemple, mais nécessaires pour éviter les erreurs)
        # En réalité, il faudrait un merge avec le fichier CLASSIFICATION ou s'assurer que ces colonnes
        # sont dans le fichier "all_pharma.xlsx" original.
        df_base['Nomenclature'] = ['Présent', 'Présent', 'Présent', 'Présent', 'Présent', 'Hors nomenclature', 'Hors nomenclature']
        df_base['Classification Groupée'] = ['Autres', 'Protein kinase inhibitors', 'Protein kinase inhibitors', 'Inhibiteurs de mTOR', 'Alkylating agents', 'Alkylating agents', 'Autres']
        df_base['Indication'] = ['ANTALGIQUES', 'Oncologie', 'Oncologie', 'Immunosupresseur', 'Immunosupresseur', 'Immunosupresseur', 'Cytostatiques']
        df_base['Forme Galénique'] = ['Syrup', 'Comprimé', 'Gélule', 'Comprimé', 'Comprimé', 'Comprimé', 'Crème']
        
        # Renommer les colonnes de la base pour correspondre aux attentes (et à la logique Streamlit)
        df_base = df_base.rename(columns={
            'name': 'name',
            'scientific_name': 'scientific_name',
            'Code_ATC': 'Code ATC',
            'type': 'type', # Type (forme galénique si pas de 'Forme Galénique' plus tard)
            'price': 'price',
            'Observations': 'Observations'
        })
        
        conn = sqlite3.connect(db_path)
        df_base.to_sql('drugs', conn, if_exists='replace', index=False)
        
        # Créer la table 'observations' si elle n'existe pas
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

    except Exception as e:
        # Cette erreur ne devrait pas se produire dans l'immersive car les données sont en dur
        st.error(f"FATAL: Database initialization error: {e}")
        
    finally:
        if conn:
            conn.close()

# Exécuter la création de la DB une fois au début
create_db_from_csv()


@st.cache_data
def load_data():
    db = get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db)
        # Charger TOUTES les colonnes disponibles
        df = pd.read_sql_query("SELECT * FROM drugs", conn)
        
        # Normalisation des noms de colonnes pour les pages Products et Dashboard
        if 'scientific_name' in df.columns:
            df = df.rename(columns={'scientific_name': 'scientific_name'}) # Assurer le nommage cohérent
        if 'Code_ATC' in df.columns:
             df = df.rename(columns={'Code_ATC': 'Code ATC'}) # Assurer le nommage cohérent
        
        # Remplacer les NaN/None dans les colonnes de recherche/affichage par des chaînes vides
        df = df.fillna('')
        
    except Exception as e:
        st.error(f"❌ Database error on loading: {e}. Cannot run app without data.")
        # Créer un DataFrame minimal si la DB est inaccessible
        df = pd.DataFrame({
            "name": ["Placeholder Drug"],
            "scientific_name": ["Simulated Substance"],
            "type": ["Test Type"],
            "price": ["0 EUR"],
            "Observations": ["Database connection failed."],
            "Code ATC": ["N/A"],
            "Nomenclature": ["N/A"],
            "Classification Groupée": ["N/A"],
            "Indication": ["N/A"],
            "Forme Galénique": ["N/A"]
        })
    finally:
        if conn:
            conn.close()
    return df

# La fonction ensure_observation_column n'est plus strictement nécessaire car
# la création/remplacement de la table `drugs` garantit sa présence,
# mais on la conserve si jamais elle était nécessaire pour une DB préexistante
# def ensure_observation_column(): ...
# ensure_observation_column()


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
        st.info("Navigate to the **Products** page to view data, or **Dashboard** to see the analysis.")

    # PRODUCTS
    elif menu == "💊 Products":
        st.header("💊 List of Products")
        df = load_data()

        search = st.text_input("🔍 Search by name or substance")
        if search:
            search_cols = ["name", "scientific_name", "type"] # 'type' est la forme galénique dans l'original
            mask = False
            for c in search_cols:
                if c in df.columns:
                    # Utiliser .str.contains sur la colonne convertie en string
                    mask |= df[c].astype(str).str.contains(search, case=False, na=False)
            
            if isinstance(mask, pd.Series):
                df = df[mask]
            else:
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
                    # Tenter de récupérer les colonnes nécessaires
                    st.write(f"**Scientific name:** {row.get('scientific_name', 'N/A')}")
                    st.write(f"**Code ATC:** {row.get('Code ATC', 'N/A')}")
                    st.write(f"**Indication/Class:** {row.get('Indication', row.get('therapeutic_class', 'N/A'))}")
                    st.write(f"**Forme Galénique:** {row.get('Forme Galénique', row.get('type', 'N/A'))}")
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
        
        if df.empty or 'Nomenclature' not in df.columns:
            st.error("Data required for the Dashboard (Nomenclature, Classification Groupée, Indication, Forme Galénique) is missing or incomplete.")
            st.stop()
            
        # Helper pour extraire le prix numérique (non utilisé pour les graphiques actuels)
        def safe_extract(val):
            try:
                # Extrait le premier nombre flottant (supporte les virgules comme séparateur décimal)
                match = re.search(r"[\d]+[.,]?[\d]*", str(val))
                return float(match.group().replace(",", ".")) if match else None
            except Exception:
                return None
                
        # --- Fonction réelle de chargement et calcul des données pour le tableau de bord ---
        @st.cache_data
        def calculate_dashboard_data(df_products):
            """Calcule les DataFrames de synthèse à partir des données complètes."""
            
            # 1. Distribution par Nomenclature
            df_nomenclature = df_products.groupby('Nomenclature')['name'].count().reset_index()
            df_nomenclature.columns = ['Statut', 'Nombre de Molécules']
            
            # 2. Distribution par Classification Groupée (Top 3 + Autres)
            counts_class = df_products.groupby('Classification Groupée')['name'].count()
            top_n = 3
            if len(counts_class) > top_n:
                top_classes = counts_class.nlargest(top_n).index.tolist()
                df_products['Classification Groupée Grouped'] = df_products['Classification Groupée'].apply(
                    lambda x: x if x in top_classes else 'Autres/Autres Molécules'
                )
                df_classification = df_products.groupby('Classification Groupée Grouped')['name'].count().reset_index()
                df_classification.columns = ['Classification Groupée', 'Nombre de Molécules']
            else:
                df_classification = counts_class.reset_index()
                df_classification.columns = ['Classification Groupée', 'Nombre de Molécules']

            
            # 3. Distribution par Indication (Top N)
            df_indication = df_products.groupby('Indication')['name'].count().reset_index()
            df_indication.columns = ['Indication', 'Nombre de Molécules']
            df_indication = df_indication.sort_values(by='Nombre de Molécules', ascending=False)
            
            # 4. Distribution par Forme Galénique (Top N)
            df_forme = df_products.groupby('Forme Galénique')['name'].count().reset_index()
            df_forme.columns = ['Forme Galénique', 'Nombre de Molécules']
            df_forme = df_forme.sort_values(by='Nombre de Molécules', ascending=False)
            
            return df_nomenclature, df_classification, df_indication, df_forme

        # --- Fonctions de création de graphiques Plotly (inchangées) ---
        PLOTLY_TEMPLATE = "streamlit"

        def create_pie_chart(df, names_col, values_col, title):
            """Crée un diagramme circulaire (Pie Chart) Plotly Express."""
            fig = px.pie(
                df,
                names=names_col,
                values=values_col,
                title=title,
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template=PLOTLY_TEMPLATE
            )
            fig.update_layout(
                showlegend=True,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
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
                title=title,
                text_auto=True,
                color_discrete_sequence=px.colors.qualitative.Vivid,
                template=PLOTLY_TEMPLATE
            )
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title=y_title,
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
            )
            # Optimisation de la rotation des étiquettes si elles sont trop longues
            fig.update_xaxes(tickangle=45, tickfont=dict(size=10)) 
            
            return fig
        
        # --- Section Tableau de Bord ---
        
        # Charger les données réelles du tableau de bord
        df_nom, df_class, df_ind, df_forme = calculate_dashboard_data(df)
        
        # Titre du rapport
        st.markdown("<h1>Synthèse des Données Pharmaceutiques Générales</h1>", unsafe_allow_html=True)
        st.write(f"Analyse des molécules au {date.today().strftime('%d/%m/%Y')}.")
        
        
        # ----------------------------------------------------
        # Section 1: Distribution Totale (Grid 2 colonnes)
        # ----------------------------------------------------
        
        st.markdown("<h2>Distribution par Nomenclature et Classification</h2>", unsafe_allow_html=True)
        
        # Création de la grille (grid-container)
        col1, col2 = st.columns(2)
        
        # Graphique 1: Distribution par Nomenclature (Pie Chart)
        with col1:
            with st.container(): # Simule le chart-box
                fig_nom = create_pie_chart(
                    df_nom, 
                    names_col='Statut',
                    values_col='Nombre de Molécules',
                    title="Distribution par Statut de Nomenclature"
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
                    title="Distribution par Classification Groupée (Top N)"
                )
                st.plotly_chart(fig_class, use_container_width=True)
        
        
        # ----------------------------------------------------
        # Section 2: Détail par Caractéristique (Grille 2 colonnes)
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
                    title="Distribution par Indication (Classes Thérapeutiques)"
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
                    title="Distribution par Forme Galénique (Top N)"
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
            # La table 'observations' est créée au démarrage dans create_db_from_csv
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
                    # Vider le cache de données pour recharger le DF mis à jour
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
        st.subheader("Recent Observations")
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
            total_rows = len(df_obs)
            total_pages = max(1, (total_rows - 1) // page_size + 1)
            
            if 'obs_page' not in st.session_state:
                st.session_state.obs_page = 1
            
            if st.session_state.obs_page > total_pages:
                st.session_state.obs_page = total_pages
                
            page = st.number_input("Page", min_value=1, max_value=total_pages, 
                                   value=st.session_state.obs_page, step=1, key="obs_page_input")
            st.session_state.obs_page = page
            
            start = (page - 1) * page_size
            end = start + page_size
            page_df = df_obs.iloc[start:end]

            for _, row in page_df.iterrows():
                # Formater la date/heure pour un affichage plus propre
                date_display = row['date'][:16].replace('T', ' ')
                with st.expander(f"{row['product_name']} ({row['type']}) - {date_display}"):
                    st.write(row["comment"])
