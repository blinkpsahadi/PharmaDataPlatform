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
# PLOTLY CHART HELPER FUNCTION
# ---------------------------
def create_count_chart_streamlit(df, column, chart_type='bar', molecule_col='name', title_suffix=""):
    """
    Crée un graphique de comptage (Barre ou Camembert) pour une colonne catégorielle, 
    en agrégeant les noms des molécules (colonne 'name' ou spécifiée) pour le survol.
    Adapté pour Streamlit.
    """
    
    # 1. Filtration des valeurs vides ou manquantes pour la colonne cible
    valid_df = df[df[column].astype(str).str.strip() != ""].copy()
    if valid_df.empty or molecule_col not in valid_df.columns:
        return None, f"No valid data or '{molecule_col}' column found for {column.upper()}."

    # 2. Agrégation: compte et agrégation des noms de molécules
    counts = valid_df.groupby(column).agg(
        Count=(molecule_col, 'size'),
        # Agrège les noms de molécules uniques et les sépare par un saut de ligne HTML
        Molecule_List=(molecule_col, lambda x: '<br>' + '<br>'.join(x.unique()))
    ).reset_index()
    
    title = f"Distribution by {column.upper()} {title_suffix}"
    custom_data = ['Molecule_List'] 

    if chart_type == 'pie':
        # Style Pie Chart (avec ajustement de la légende pour éviter le débordement)
        hover_text_pie = "<b>%{label}</b><br>Count : %{value}<br>Molecules : %{customdata[0]}<extra></extra>"
        fig = px.pie(
            counts, 
            values='Count', 
            names=column, 
            title=title,
            color=column,
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hole=.3, 
            custom_data=custom_data
        )
        fig.update_traces(textposition='auto', textinfo='percent', hovertemplate=hover_text_pie)
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            uniformtext_minsize=12, uniformtext_mode='hide', showlegend=True,
            template='plotly_white'
        )
        
    else: # Default Bar chart
        # Style Bar Chart
        bar_hover_text = "<b>%{x}</b><br>Count : %{y}<br>Molecules : %{customdata[0]}<extra></extra>"

        fig = px.bar(
            counts, 
            x=column, 
            y='Count', 
            title=title,
            color=column,
            color_discrete_sequence=px.colors.qualitative.Dark24,
            text='Count',
            custom_data=custom_data
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside', hovertemplate=bar_hover_text)
        fig.update_layout(
            xaxis={'categoryorder':'total descending'}, 
            yaxis_title="Count of Molecules",
            template='plotly_white'
        )

    # Uniformisation de la hauteur (500px) et des marges pour les deux types de graphiques
    fig.update_layout(
        height=500,
        margin=dict(t=50, l=20, r=20, b=20)
    )

    return fig, None


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
                st.write(f"**Scientific name:** {row.get('scientific_name', 'N/A')}")
                st.write(f"**Code ATC:** {row.get('Code ATC', 'N/A')}") # Correction ATC
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
        
        # Préparation des données de prix
        def safe_extract(val):
            try:
                match = re.search(r"[\d,.]+", str(val))
                # Nettoyage de la valeur : retire la virgule pour la conversion float
                return float(match.group().replace(",", "")) if match else None
            except Exception:
                return None
                
        df["Prix_num"] = df["price"].apply(safe_extract)
        df = df.fillna("")

        # Colonne contenant les noms de molécules pour le survol
        molecule_column_name = 'name' 

        # Graphiques catégoriels (Maintenant en BAR CHARTS avec survol interactif)
        # Note: Le Code ATC peut être soit 'Code ATC' soit 'Code_ATC' selon la DB, 
        # on utilise ici 'Code ATC' comme convention pour le titre.
        categorical_cols = ["Code ATC", "bcs", "oeb", "bioequivalence"]
        
        # Affichage en deux colonnes pour les petits graphiques
        cols = st.columns(2)
        col_index = 0
        
        for col in categorical_cols:
            if col in df.columns:
                # Utilisation du Bar Chart par défaut pour la lisibilité
                fig, error = create_count_chart_streamlit(df, col, chart_type='bar', molecule_col=molecule_column_name)
                
                if fig:
                    with cols[col_index % 2]:
                        st.plotly_chart(fig, use_container_width=True)
                    col_index += 1
                elif error:
                    st.info(f"No valid data to display for {col.upper()}.")

        # Cas spécial: 'type' column (Classes Thérapeutiques)
        # Affiché sur la pleine largeur
        if "type" in df.columns:
            fig_class, error_class = create_count_chart_streamlit(df, "type", chart_type='bar', molecule_col=molecule_column_name)
            
            if fig_class:
                fig_class.update_layout(title="Therapeutical Classes") # Titre spécifique
                st.plotly_chart(fig_class, use_container_width=True)
            elif error_class:
                st.info(error_class)


        # Graphiques de prix (inchangés dans leur principe, mais avec style uniforme)
        valid_prices = df[pd.to_numeric(df["Prix_num"], errors="coerce").notna()].copy()
        valid_prices["Prix_num"] = valid_prices["Prix_num"].astype(float)

        if not valid_prices.empty:
            st.markdown("---")
            st.subheader("Price Analysis")

            # Top 10 Bar Chart (prix)
            top10 = valid_prices.nlargest(10, "Prix_num")
            fig_top10 = px.bar(top10, x="name", y="Prix_num", 
                     title="Top 10 Most Expensive Medicines",
                     template='plotly_white',
                     height=500) # Hauteur uniforme
            st.plotly_chart(fig_top10, use_container_width=True)

            # Price Distribution Histogram
            fig_hist = px.histogram(valid_prices, x="Prix_num", nbins=20, 
                           title="Price Distribution",
                           template='plotly_white',
                           height=500) # Hauteur uniforme
            st.plotly_chart(fig_hist, use_container_width=True)
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