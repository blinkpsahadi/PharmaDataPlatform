import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import re
from datetime import date
from io import StringIO
from contextlib import contextmanager

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

st.markdown("""
<style>
/* Styles pour une meilleure intégration du thème sombre/clair de Streamlit. 
Les couleurs spécifiques au fond clair ont été retirées.
*/
[data-testid="stHeader"], [data-testid="stToolbar"], header {display: none !important;}
/* On garde la sidebar masquée par défaut pour utiliser notre propre navigation 
dans la colonne de gauche (left_col).
*/
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

h1 {
    /* Utilise la couleur primaire du thème Streamlit */
    border-bottom: 3px solid var(--primary-color, #007bff); 
    padding-bottom: 10px;
    margin-bottom: 30px;
    font-size: 2em;
}

h2 {
    margin-top: 40px;
    font-size: 1.5em;
}

/* Le conteneur (st.container) aura un aspect plus intégré au thème */
.stContainer {
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
    margin-bottom: 25px;
}

/* Force la radio de navigation à utiliser tout l'espace de la colonne */
[data-testid="stRadio"] label {
    display: block;
    width: 100%;
    margin-bottom: 5px;
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
    USERS = {}

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
# DB HELPERS & INITIALIZATION
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
    # Utilisation du fichier 'CLASSIFICATION_DES_IMMUNOSUPRESSEURS_ATC_DDD_NOMENCLATURE.xlsx - Forme Séche .csv' 
    # et 'all_pharma.xlsx - drugs.csv' comme base temporaire si la DB n'est pas trouvée, 
    # mais Streamlit ne supporte pas l'accès direct aux fichiers CSV locaux pour des fonctions de mise à jour.
    # On force l'arrêt pour ne pas générer d'erreurs d'accès.
    st.error("❌ Database 'all_pharma.db' not found. Please ensure it is available.")
    st.stop()
    return "dummy_path_to_stop_error" # Fallback

DB_PATH = get_db_path()

@contextmanager
def get_db_connection(db_path):
    """Context manager pour gérer la connexion SQLite, essentielle pour les transactions."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Optionnel, mais utile
        yield conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        yield None
    finally:
        if conn:
            conn.close()

@st.cache_data
def load_data():
    """Charge les données de la table 'drugs' dans un DataFrame."""
    df = pd.DataFrame()
    try:
        with get_db_connection(DB_PATH) as conn:
            if conn:
                df = pd.read_sql_query("SELECT * FROM drugs", conn)
    except Exception as e:
        st.error(f"Error loading 'drugs' table: {e}")
        st.stop()
    
    # Tentative d'ajouter une colonne numérique si elle n'existe pas (pour le Dashboard)
    if 'price_numeric' not in df.columns and 'price' in df.columns:
        # Nettoyage et conversion de la colonne 'price'
        df['price_numeric'] = df['price'].astype(str).str.replace(r'[^\d,.]', '', regex=True).str.replace(',', '.', regex=False)
        df['price_numeric'] = pd.to_numeric(df['price_numeric'], errors='coerce')
        # On pourrait ici mettre à jour la DB si on voulait la persistance, mais on se contente du DF en cache.
        
    return df

def ensure_tables_and_columns():
    """Vérifie et crée la colonne Observations dans 'drugs' et la table 'observations' si nécessaire."""
    try:
        with get_db_connection(DB_PATH) as conn:
            if conn:
                cursor = conn.cursor()
                
                # 1. Vérification/Ajout de la colonne Observations dans 'drugs'
                cursor.execute("PRAGMA table_info(drugs);")
                columns = [info[1] for info in cursor.fetchall()]
                if "Observations" not in columns:
                    cursor.execute("ALTER TABLE drugs ADD COLUMN Observations TEXT;")
                    st.success("Column 'Observations' added to 'drugs' table.")
                
                # 2. Vérification/Création de la table 'observations'
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT NOT NULL,
                        type TEXT,
                        comment TEXT,
                        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                
    except Exception as e:
        st.error(f"Database initialization error: {e}")
        st.stop()

# Exécuter l'initialisation de la DB
ensure_tables_and_columns()


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
        "Menu", 
        menu_options, 
        index=selected_index, 
        key="nav_selection_radio",
        label_visibility="collapsed" # Cache le titre "Menu" du radio
    )
    
    st.markdown("---")
    st.markdown(f"**Connected as:** `{st.session_state.username}`")
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        # Vider le cache de toutes les données lors de la déconnexion
        load_data.clear()
        st.cache_data.clear()
        st.rerun()

# ---------------------------
# MAIN CONTENT
# ---------------------------
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
        
        filtered_df = df.copy()
        if search:
            search_cols = ["name", "scientific_name", "Code ATC", "Classification Groupée", "Indication"]
            mask = False
            for c in search_cols:
                if c in filtered_df.columns:
                    # Utiliser .str.contains sur la colonne convertie en string
                    mask |= filtered_df[c].astype(str).str.contains(search, case=False, na=False)
            
            if isinstance(mask, pd.Series):
                filtered_df = filtered_df[mask]
            else:
                st.warning("No searchable columns found in data.")
                filtered_df = pd.DataFrame()

        items_per_page = 10 # Réduit à 10 pour une meilleure pagination avec le petit jeu de données
        # Gérer le cas où df est vide après la recherche
        total_rows = len(filtered_df)
        total_pages = max(1, (total_rows - 1) // items_per_page + 1)
        
        # S'assurer que la page actuelle est valide
        if 'product_page' not in st.session_state:
            st.session_state.product_page = 1
        
        if total_rows == 0:
            st.info("No products found matching your criteria.")
        else:
            # Mettre à jour la page si la page actuelle dépasse le nombre total de pages
            if st.session_state.product_page > total_pages:
                st.session_state.product_page = total_pages
                
            col_page_input, col_page_text = st.columns([1, 3])
            
            with col_page_input:
                page = st.number_input("Page", min_value=1, max_value=total_pages, 
                                        value=st.session_state.product_page, step=1, 
                                        key="product_page_input", label_visibility="collapsed")
            
            with col_page_text:
                st.markdown(f"**Page {page} of {total_pages}** ({total_rows} items total)")
            
            st.session_state.product_page = page # Garder l'état
            
            subset = filtered_df.iloc[(page - 1) * items_per_page : page * items_per_page]

            for _, row in subset.iterrows():
                # Utilise le nom scientifique si disponible, sinon le nom commercial dans le titre de l'expander
                title_display = f"💊 {row['name']} ({row.get('scientific_name', 'N/A')})" if row.get('scientific_name') else f"💊 {row['name']}"
                with st.expander(title_display):
                    st.write(f"**Scientific name:** {row.get('scientific_name', 'N/A')}")
                    st.write(f"**Code ATC:** {row.get('Code ATC', 'N/A')}")
                    st.write(f"**Indication:** {row.get('Indication', 'N/A')}")
                    st.write(f"**Classification Groupée:** {row.get('Classification Groupée', 'N/A')}")
                    form_display = row.get('Forme Galénique', 'N/A')
                    st.write(f"**Forme Galénique:** {form_display}")
                    st.write(f"**Nomenclature Status:** {row.get('Nomenclature', 'N/A')}")
                    st.write(f"**Price:** {row.get('price', 'N/A')}")
                    
                    obs_text = row.get("Observations", "")
                    st.markdown("**🩺 Latest Observation:**")
                    if obs_text and str(obs_text).strip() != "":
                        st.info(obs_text)
                    else:
                        st.write("_No observation recorded for this product._")

    # DASHBOARD
    elif menu == "📊 Dashboard":
        st.header("📊 Global Analysis")
        df = load_data()
        
        # --- Préparation des Données: Nettoyage et Création de 'price_numeric' ---
        # La colonne 'price' est souvent une chaîne de caractères (parfois avec des virgules comme décimales).
        if 'price' in df.columns:
            # Remplacer les virgules par des points et convertir en numérique
            df['price_numeric'] = df['price'].astype(str).str.replace(',', '.', regex=False)
            df['price_numeric'] = pd.to_numeric(df['price_numeric'], errors='coerce')
        else:
            df['price_numeric'] = pd.NA
            st.warning("Column 'price' not found. Price analysis is skipped.")
    
        # --- Nouveaux En-têtes Critiques pour l'Analyse ---
        required_cols = ['therapeutic_class', 'Code_ATC', 'type', 'source', 'price_numeric']
        
        # Vérification des colonnes critiques après chargement
        for col in required_cols:
            # Note: 'price_numeric' est créé ci-dessus, donc nous vérifions si l'originale existe
            if col in ['price_numeric']:
                continue 
            
            if col not in df.columns:
                df[col] = pd.NA
                st.warning(f"Column '{col}' not found. Dashboard calculations might be incomplete.")
    
        if df.empty:
            st.error("Data required for the Dashboard is missing or empty.")
            st.stop()
            
        # --- Fonction réelle de chargement et calcul des données pour le tableau de bord ---
        @st.cache_data
        def calculate_dashboard_data(df_products):
            """Calcule les DataFrames de synthèse à partir des données complètes."""
            
            # 1. Distribution par Classe Thérapeutique (Utilise 'therapeutic_class')
            df_class_therapy = df_products.groupby('therapeutic_class', dropna=True)['name'].count().reset_index()
            df_class_therapy.columns = ['Classe Thérapeutique', 'Nombre de Molécules']
            
            # 2. Distribution par Code ATC (Top 3 + Autres)
            counts_atc = df_products.groupby('Code_ATC', dropna=True)['name'].count()
            top_n = 5 # Montrer plus d'ATC pour une meilleure granularité
            
            if len(counts_atc) > top_n:
                top_classes = counts_atc.nlargest(top_n).index.tolist()
                # Renommer la colonne temporairement pour le regroupement
                df_products['Code_ATC_Grouped'] = df_products['Code_ATC'].apply(
                    lambda x: x if x in top_classes else 'Autres Codes ATC' if pd.notna(x) else 'Inconnu'
                )
                df_atc_grouped = df_products.groupby('Code_ATC_Grouped')['name'].count().reset_index()
                df_atc_grouped.columns = ['Code ATC Groupé', 'Nombre de Molécules']
            else:
                df_atc_grouped = counts_atc.reset_index()
                df_atc_grouped.columns = ['Code ATC Groupé', 'Nombre de Molécules']
            
            # 3. Distribution par Type (Forme Galénique la plus proche)
            df_type = df_products.groupby('type', dropna=True)['name'].count().reset_index()
            df_type.columns = ['Type de Forme (Galénique)', 'Nombre de Molécules']
            df_type = df_type.sort_values(by='Nombre de Molécules', ascending=False)
            
            # 4. Distribution par Source (Fabricant/Source de Données)
            df_source = df_products.groupby('source', dropna=True)['name'].count().reset_index()
            df_source.columns = ['Source (Fabricant/Données)', 'Nombre de Molécules']
            df_source = df_source.sort_values(by='Nombre de Molécules', ascending=False)
            
            # 5. Prix moyen par Classe Thérapeutique (Utilise 'therapeutic_class' et 'price_numeric')
            # Exclure les NaNs dans 'price_numeric' pour le calcul
            df_price_class = df_products[df_products['price_numeric'].notna()].groupby('therapeutic_class').agg(
                Moyenne_Prix=('price_numeric', 'mean'),
                Total_Molécules=('name', 'count')
            ).reset_index()
            df_price_class.columns = ['Classe Thérapeutique', 'Moyenne_Prix', 'Total_Molécules']
            
            return df_class_therapy, df_atc_grouped, df_type, df_source, df_price_class
    
        # --- Fonctions de création de graphiques Plotly (Inchagées car génériques) ---
        PLOTLY_TEMPLATE = "streamlit"
    
        def create_pie_chart(df, names_col, values_col, title):
            """Crée un diagramme circulaire (Pie Chart) Plotly Express."""
            if df.empty:
                return None
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
            if df.empty:
                return None
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
        
        def create_price_bar_chart(df, x_col, y_col, title):
            """Crée un diagramme à barres pour le prix moyen."""
            if df.empty:
                return None
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=x_col,
                title=title,
                text_auto='.2s', # Afficher la valeur avec 2 décimales si possible
                color_discrete_sequence=px.colors.qualitative.Safe,
                template=PLOTLY_TEMPLATE
            )
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title="Prix Moyen", # Unité non précisée, mais on suppose un prix
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
            )
            fig.update_xaxes(tickangle=45, tickfont=dict(size=10))
            return fig
    
        
        # --- Section Tableau de Bord ---
        
        # Charger les données réelles du tableau de bord
        df_class_therapy, df_atc_grouped, df_type, df_source, df_price_class = calculate_dashboard_data(df)
        
        # Titre du rapport
        st.markdown("<h1>Synthèse des Données Pharmaceutiques Générales</h1>", unsafe_allow_html=True)
        st.write(f"Analyse des **{len(df)}** molécules au **{date.today().strftime('%d/%m/%Y')}**.")
        
        
        # ----------------------------------------------------
        # Section 1: Graphique 1 - Distribution par Classe Thérapeutique
        # ----------------------------------------------------
        
        st.markdown("<h2>1. Distribution par Classe Thérapeutique</h2>", unsafe_allow_html=True)
        
        with st.container(): # Utilisation d'un conteneur pour assurer la pleine largeur
            fig_class_therapy = create_pie_chart(
                df_class_therapy, 
                names_col='Classe Thérapeutique',
                values_col='Nombre de Molécules',
                title="Distribution par Classe Thérapeutique"
            )
            if fig_class_therapy:
                st.plotly_chart(fig_class_therapy, use_container_width=True)
            else:
                st.info("No data for therapeutic class distribution.")
        
        st.markdown("---") # Séparateur visuel
        
        # ----------------------------------------------------
        # Section 2: Graphique 2 - Distribution par Code ATC
        # ----------------------------------------------------
        
        st.markdown("<h2>2. Distribution par Code ATC</h2>", unsafe_allow_html=True)
    
        with st.container():
            fig_atc = create_bar_chart(
                df_atc_grouped, 
                x_col='Code ATC Groupé', 
                y_col='Nombre de Molécules', 
                color_col='Code ATC Groupé', 
                title="Distribution par Code ATC Groupé (Top N)"
            )
            if fig_atc:
                st.plotly_chart(fig_atc, use_container_width=True)
            else:
                st.info("No data for ATC code distribution.")
    
        st.markdown("---") # Séparateur visuel
    
        # ----------------------------------------------------
        # Section 3: Graphique 3 - Distribution par Type de Forme
        # ----------------------------------------------------
    
        st.markdown("<h2>3. Top 10 Distributions par Type de Forme (Galénique)</h2>", unsafe_allow_html=True)
    
        with st.container():
            fig_type = create_bar_chart(
                df_type.head(10), # Limité au top 10 pour la lisibilité
                x_col='Type de Forme (Galénique)', 
                y_col='Nombre de Molécules', 
                color_col='Type de Forme (Galénique)', 
                title="Top 10 Distributions par Type de Forme"
            )
            if fig_type:
                st.plotly_chart(fig_type, use_container_width=True)
            else:
                st.info("No data for Type (Forme Galénique) distribution.")
    
        st.markdown("---") # Séparateur visuel
    
        # ----------------------------------------------------
        # Section 4: Graphique 4 - Distribution par Source (Fabricant)
        # ----------------------------------------------------
    
        st.markdown("<h2>4. Top 10 Distributions par Source (Fabricant/Données)</h2>", unsafe_allow_html=True)
        
        with st.container():
            fig_source = create_bar_chart(
                df_source.head(10), # Limité au top 10 pour la lisibilité
                x_col='Source (Fabricant/Données)', 
                y_col='Nombre de Molécules', 
                color_col='Source (Fabricant/Données)', 
                title="Top 10 Distributions par Source"
            )
            if fig_source:
                st.plotly_chart(fig_source, use_container_width=True)
            else:
                st.info("No data for Source distribution.")
    
        st.markdown("---") # Séparateur visuel
        
        # ----------------------------------------------------
        # Section 5: Graphique 5 - Prix Moyen par Classe Thérapeutique
        # ----------------------------------------------------
        
        st.markdown("<h2>5. Prix Moyen par Classe Thérapeutique</h2>", unsafe_allow_html=True)
        
        with st.container():
            fig_price = create_price_bar_chart(
                df_price_class.sort_values(by='Moyenne_Prix', ascending=False),
                x_col='Classe Thérapeutique',
                y_col='Moyenne_Prix',
                title="Prix Moyen par Classe Thérapeutique"
            )
            if fig_price:
                st.plotly_chart(fig_price, use_container_width=True)
            else:
                st.info("No numerical price data available for price analysis.")
    # OBSERVATIONS
    elif menu == "🧾 Observations":
        st.header("🩺 Commercial & Medical Observations")
        
        products = []
        
        try:
            with get_db_connection(DB_PATH) as conn:
                if conn:
                    # Charger la liste des produits existants pour le selectbox
                    # Utiliser le nom des médicaments pour le formulaire
                    df_products = pd.read_sql_query("SELECT DISTINCT name FROM drugs ORDER BY name", conn)
                    products = df_products["name"].tolist()
        except Exception as e:
            st.error(f"Error accessing database for Products list: {e}. Cannot display form.")

        
        with st.form("new_obs", clear_on_submit=True):
            st.subheader("Add New Observation")
            
            # Gestion de la saisie manuelle/sélection de produit
            product_options = ["Type manually..."] + products
            product_selected = st.selectbox("Product", product_options, index=0)
            
            final_product_name = ""
            if product_selected == "Type manually...":
                final_product_name = st.text_input("Manual Product Name")
            else:
                final_product_name = product_selected
                
            obs_type = st.selectbox("Type", ["Commercial", "Medical", "Other"])
            comment = st.text_area("💬 Observation")
            submit = st.form_submit_button("💾 Save Observation")
            
            if submit and final_product_name and comment:
                try:
                    with get_db_connection(DB_PATH) as conn:
                        if conn:
                            # 1. Insertion dans la table des observations
                            conn.execute(
                                "INSERT INTO observations (product_name, type, comment) VALUES (?, ?, ?)",
                                (final_product_name, obs_type, comment)
                            )
                            
                            # 2. Mise à jour de la colonne 'Observations' dans la table 'drugs' (uniquement si le produit existe)
                            # On ne met à jour que la dernière observation dans la table drugs
                            conn.execute(
                                "UPDATE drugs SET Observations = ? WHERE name = ?",
                                (comment, final_product_name)
                            )
                            conn.commit()
                            st.success(f"✅ Observation saved for {final_product_name}.")
                            # Vider le cache de données pour recharger le DF mis à jour
                            load_data.clear()  
                            # Redémarrer après l'enregistrement pour vider le formulaire et recharger la liste
                            st.rerun() 
                            
                except Exception as e:
                    st.error(f"Error saving observation: {e}")
            elif submit:
                st.warning("Please enter a product name and an observation.")

        st.markdown("---")
        st.subheader("Recent Observations History")
        
        df_obs = pd.DataFrame()
        try:
            with get_db_connection(DB_PATH) as conn:
                if conn:
                    df_obs = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
        except Exception:
            st.error("Could not load observations history.")

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
                                    value=st.session_state.obs_page, step=1, key="obs_page_input", 
                                    label_visibility="collapsed") # Ajout d'une visibilité réduite pour l'input
            st.markdown(f"**Page {page} of {total_pages}** ({total_rows} items total)", help="History Pagination")
            st.session_state.obs_page = page
            
            start = (page - 1) * page_size
            end = start + page_size
            page_df = df_obs.iloc[start:end]

            for _, row in page_df.iterrows():
                # Formater la date/heure pour un affichage plus propre
                # La date est stockée comme 'YYYY-MM-DD HH:MM:SS.sss' par CURRENT_TIMESTAMP
                date_display = row['date'][:19].replace('-', '/').replace(' ', ' - ')
                with st.expander(f"{row['product_name']} ({row['type']}) - **{date_display}**"):
                    st.write(row["comment"])




