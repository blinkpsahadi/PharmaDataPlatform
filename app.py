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

# Les identifiants sont maintenant sécurisés dans st.secrets si l'application est déployée.
# Pour le test local, vous pouvez les définir dans un fichier .streamlit/secrets.toml
if "credentials" in st.secrets:
    USERS = dict(st.secrets["credentials"])

def check_password(username, password):
    """Vérifie si le nom d'utilisateur et le mot de passe correspondent."""
    return username in USERS and USERS[username] == password

if not st.session_state.authenticated:
    st.image("https://placehold.co/150x150/007bff/ffffff/png?text=Pharma", width=150)
    st.markdown("# 🔒 Pharma Data Connection")
    with st.form("login_form"):
        user = st.text_input("Username", value="admin")
        pwd = st.text_input("Password", type="password", value="adminpwd")
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
# L'exécution s'arrête ici si l'utilisateur n'est pas authentifié.


# ---------------------------
# DB HELPERS & Data Loading
# ---------------------------
DB_NAME = "all_pharma.db"

@st.cache_data
def get_db_path():
    """Retourne le chemin de la base de données."""
    return DB_NAME

@contextmanager
def get_db_connection(db_path):
    """Context Manager pour gérer la connexion SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    except Exception as e:
        st.error(f"FATAL: Database connection error: {e}")
        conn = None
    finally:
        if conn:
            conn.close()

def create_db_from_csv():
    """Crée la table 'drugs' et 'observations' dans la base de données à partir des données simulées."""
    db_path = get_db_path()
    
    # Snippet de données consolidé et simplifié avec toutes les colonnes requises
    # Ajout de plus de diversité pour les graphiques (total de 7 lignes)
    df_data_snippet = """
name,scientific_name,Code ATC,price,Observations,Nomenclature,Classification Groupée,Indication,Forme Galénique,price_numeric
ELPIX,Dasatinib,L01EA02,1000 EUR,,Présent,Protein kinase inhibitors,Oncologie,Comprimé,1000.0
TASIGNA,Nilotinib,L01EA03,2000 EUR,Expensive.,Présent,Protein kinase inhibitors,Oncologie,Gélule,2000.0
AFINITOR,Everolimus,L04AH02,500 EUR,Under review.,Présent,Inhibiteurs de mTOR,Immunosupresseur,Comprimé,500.0
ARAVA,Léflunomide,L04AK01,150 EUR,,Présent,Alkylating agents,Immunosupresseur,Comprimé,150.0
TERIFLUNO,Tériflunomide,L04AK02,250 EUR,New Entry.,Hors nomenclature,Alkylating agents,Immunosupresseur,Comprimé,250.0
PIMECROLIMUS CR,Pimecrolimus,D11AH02,50 EUR,Topical use.,Hors nomenclature,Autres,Dermatologie,Crème,50.0
SYRUP METHADONE 5,Methadone,N07BC02,10 EUR,,Présent,Autres,Antalgiques,Syrup,10.0
PAIN RX,Oxycodone,N02AA05,100 EUR,,Présent,Opioïdes,Antalgiques,Comprimé,100.0
IBUPROFEN,Ibuprofen,M01AE01,5 EUR,,Hors nomenclature,AINS,Inflammation,Comprimé,5.0
CETIRIZINE,Cetirizine,R06AE07,8 EUR,,Présent,Antihistaminiques,Allergie,Gélule,8.0
FENRIR,Lisinopril,C09AA03,12 EUR,,Présent,IEC,Cardiologie,Comprimé,12.0
"""
    
    try:
        with get_db_connection(db_path) as conn:
            if conn:
                # Lire l'extrait CSV en utilisant StringIO
                df_base = pd.read_csv(StringIO(df_data_snippet))
                
                # S'assurer que les colonnes ont le bon type (même si price_numeric est déjà dans le snippet)
                if 'price_numeric' not in df_base.columns:
                     df_base['price_numeric'] = df_base['price'].apply(
                        lambda x: float(str(x).replace(' EUR', '').replace(',', '.')) if x else 0
                    )
                
                # Écrire les données dans la table 'drugs'
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
        # L'erreur est gérée par le context manager, mais on peut ré-afficher si la connexion échoue
        pass

# Exécuter la création de la DB une fois au début
create_db_from_csv()


@st.cache_data
def load_data():
    """Charge les données de la table 'drugs'."""
    db = get_db_path()
    df = pd.DataFrame()
    try:
        with get_db_connection(db) as conn:
            if conn:
                # Charger TOUTES les colonnes disponibles
                df = pd.read_sql_query("SELECT * FROM drugs", conn)
                # Remplacer les NaN/None par des chaînes vides pour la recherche
                df = df.fillna('')
                # S'assurer que price_numeric est un nombre pour les calculs de dashboard
                if 'price_numeric' in df.columns:
                    df['price_numeric'] = pd.to_numeric(df['price_numeric'], errors='coerce').fillna(0)
                else:
                    df['price_numeric'] = 0.0

    except Exception as e:
        st.error(f"❌ Database error on loading: {e}. Cannot run app without data.")
        # Créer un DataFrame minimal si la DB est inaccessible (pour la robustesse de l'UI)
        df = pd.DataFrame({
            "name": ["Placeholder Drug"],
            "scientific_name": ["Simulated Substance"],
            "Code ATC": ["N/A"],
            "price": ["0 EUR"],
            "Observations": ["Database connection failed."],
            "Nomenclature": ["N/A"],
            "Classification Groupée": ["N/A"],
            "Indication": ["N/A"],
            "Forme Galénique": ["N/A"],
            "price_numeric": [0.0]
        })
    return df


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
        
        # Vérification des colonnes critiques après chargement
        required_cols = ['Nomenclature', 'Classification Groupée', 'Indication', 'Forme Galénique', 'price_numeric']
        if df.empty or not all(col in df.columns for col in required_cols):
            st.error("Data required for the Dashboard is missing or incomplete.")
            st.stop()
            
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
            
            # 5. Prix moyen par Classification Groupée (NOUVEAU KPI)
            df_price_class = df_products.groupby('Classification Groupée').agg(
                Moyenne_Prix=('price_numeric', 'mean'),
                Total_Molécules=('name', 'count')
            ).reset_index()
            
            return df_nomenclature, df_classification, df_indication, df_forme, df_price_class

        # --- Fonctions de création de graphiques Plotly ---
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
        
        def create_price_bar_chart(df, x_col, y_col, title):
            """Crée un diagramme à barres pour le prix moyen."""
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
                yaxis_title="Prix Moyen (EUR)",
                showlegend=False,
                margin=dict(l=20, r=20, t=50, b=20),
                height=400,
            )
            fig.update_xaxes(tickangle=45, tickfont=dict(size=10))
            return fig

        
        # --- Section Tableau de Bord ---
        
        # Charger les données réelles du tableau de bord
        df_nom, df_class, df_ind, df_forme, df_price_class = calculate_dashboard_data(df)
        
        # Titre du rapport
        st.markdown("<h1>Synthèse des Données Pharmaceutiques Générales</h1>", unsafe_allow_html=True)
        st.write(f"Analyse des **{len(df)}** molécules au **{date.today().strftime('%d/%m/%Y')}**.")
        
        
        # ----------------------------------------------------
        # Section 1: Indicateurs Clés et Distribution (Grid 2 colonnes)
        # ----------------------------------------------------
        
        st.markdown("<h2>Distribution par Nomenclature et Classification</h2>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        # Graphique 1: Distribution par Nomenclature (Pie Chart)
        with col1:
            with st.container(): 
                fig_nom = create_pie_chart(
                    df_nom, 
                    names_col='Statut',
                    values_col='Nombre de Molécules',
                    title="Distribution par Statut de Nomenclature"
                )
                st.plotly_chart(fig_nom, use_container_width=True)
        
        # Graphique 2: Distribution par Type de Classification (Bar Chart)
        with col2:
            with st.container(): 
                fig_class = create_bar_chart(
                    df_class, 
                    x_col='Classification Groupée', 
                    y_col='Nombre de Molécules', 
                    color_col='Classification Groupée', 
                    title="Distribution par Classification Groupée (Top N)"
                )
                st.plotly_chart(fig_class, use_container_width=True)
        
        
        # ----------------------------------------------------
        # Section 2: Détail par Caractéristique et Prix
        # ----------------------------------------------------
        
        st.markdown("<h2>Détail Thérapeutique et Analyse des Prix</h2>", unsafe_allow_html=True)
        
        col3, col4 = st.columns(2)
        
        # Graphique 3: Distribution par Indication
        with col3:
            with st.container(): 
                fig_ind = create_bar_chart(
                    df_ind, 
                    x_col='Indication', 
                    y_col='Nombre de Molécules', 
                    color_col='Indication', 
                    title="Distribution par Indication"
                )
                st.plotly_chart(fig_ind, use_container_width=True)
        
        # Graphique 4: Distribution par Forme Galénique
        with col4:
            with st.container(): 
                fig_forme = create_bar_chart(
                    df_forme, 
                    x_col='Forme Galénique', 
                    y_col='Nombre de Molécules', 
                    color_col='Forme Galénique', 
                    title="Distribution par Forme Galénique"
                )
                st.plotly_chart(fig_forme, use_container_width=True)
        
        st.markdown("---")
        
        # Graphique 5: Prix Moyen par Classification Groupée (Utilise toute la largeur)
        with st.container():
            fig_price = create_price_bar_chart(
                df_price_class.sort_values(by='Moyenne_Prix', ascending=False),
                x_col='Classification Groupée',
                y_col='Moyenne_Prix',
                title="Prix Moyen par Classification Groupée (EUR)"
            )
            st.plotly_chart(fig_price, use_container_width=True)


    # OBSERVATIONS
    elif menu == "🧾 Observations":
        st.header("🩺 Commercial & Medical Observations")
        db_path = get_db_path()
        products = []
        
        try:
            with get_db_connection(db_path) as conn:
                if conn:
                    # Charger la liste des produits existants pour le selectbox
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
                    with get_db_connection(db_path) as conn:
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
            with get_db_connection(db_path) as conn:
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
                                    value=st.session_state.obs_page, step=1, key="obs_page_input")
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

