import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

st.set_page_config(page_title="My Pharma Dashboard", page_icon="💊", layout="wide")

# --- Inject responsive detection script ---
detect_script = """
    <script>
    const width = window.innerWidth;
    const isMobile = width < 768;
    window.parent.postMessage({ isMobile }, "*");
    </script>
"""
st.markdown(detect_script, unsafe_allow_html=True)

# Container for device detection
if "is_mobile" not in st.session_state:
    st.session_state.is_mobile = False

# Receive width info
st.markdown("""
<script>
window.addEventListener('message', (event) => {
    if (event.data.isMobile !== undefined) {
        window.streamlitSend({type:'streamlit:setSessionState',data:{is_mobile:event.data.isMobile}});
    }
});
</script>
""", unsafe_allow_html=True)

# --- Dynamic CSS ---
st.markdown("""
<style>
[data-testid="stToolbar"] {visibility: hidden; height: 0;}

.block-container {
    padding: 1rem 2rem;
}

@media (max-width: 768px) {
    .block-container {padding: 0.5rem 0.8rem !important;}
    .stMarkdown, .stTextInput, .stSelectbox, .stTextArea {font-size: 14px !important;}
    .stButton>button {width: 100% !important;}
    .stExpander {margin-bottom: 0.8rem !important;}
    h1,h2,h3 {font-size: 1.1rem !important;}
}
</style>
""", unsafe_allow_html=True)

# --- Authentication (same as before) ---
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
                st.error("Incorrect Username or Password")
    st.stop()
else:
    # Hide sidebar completely on mobile
    if not st.session_state.is_mobile:
        st.sidebar.markdown(f"**Connected as:** {st.session_state.username}")
        if st.sidebar.button("🔓 Logout"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        st.markdown(f"✅ Logged in as **{st.session_state.username}**")

# --- DB Functions ---
@st.cache_data
def get_db_path():
    for path in [
        "data/all_pharma.db", "all_pharma.db",
        os.path.join(os.getcwd(), "data", "all_pharma.db")
    ]:
        if os.path.exists(path):
            return path
    st.error("❌ Database not found.")
    st.stop()

@st.cache_data
def load_data():
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("SELECT * FROM drugs", conn)
    conn.close()
    return df

def extract_price(val):
    try:
        return float(str(val).replace("DA", "").replace(",", ".").strip())
    except:
        return None

# --- NAVIGATION (mobile = top menu) ---
if st.session_state.is_mobile:
    menu = st.selectbox(
        "📱 Navigate",
        ["🏠 Home", "💊 Products", "📊 Dashboard", "🧾 Observations"]
    )
else:
    menu = st.sidebar.radio(
        "Navigation",
        ["🏠 Home", "💊 Products", "📊 Dashboard", "🧾 Observations"]
    )

# --- PAGES ---
if menu == "🏠 Home":
    st.title("💊 Pharma Data Platform")
    st.markdown("Welcome to the Pharmaceutical Management & Analysis Platform 📊")

elif menu == "💊 Products":
    st.header("💊 List of Products")
    df = load_data()
    search = st.text_input("🔍 Search by name or substance")
    if search:
        df = df[df["name"].str.contains(search, case=False, na=False) |
                df["type"].str.contains(search, case=False, na=False)]

    items_per_page = 50 if st.session_state.is_mobile else 100
    total_pages = max(1, (len(df) - 1) // items_per_page + 1)
    page = st.number_input("Page", 1, total_pages, 1)
    subset = df.iloc[(page-1)*items_per_page : page*items_per_page]

    for _, row in subset.iterrows():
        with st.expander(f"💊 {row['name']}"):
            st.write(f"**ATC:** {row.get('atc', 'N/A')}")
            st.write(f"**Type:** {row.get('type', 'N/A')}")
            st.write(f"**Price:** {row.get('price', 'N/A')}")
            if 'description' in df.columns and row.get("description"):
                st.markdown(row["description"], unsafe_allow_html=True)

elif menu == "📊 Dashboard":
    st.header("📊 Global Analysis")
    df = load_data()
    df["Prix_num"] = df["price"].apply(extract_price)

    for col in ["atc", "bcs", "oeb", "bioequivalence"]:
        if col in df.columns:
            fig = px.pie(df, names=col, title=f"By {col.upper()}")
            st.plotly_chart(fig, use_container_width=True, height=400 if st.session_state.is_mobile else 600)

    if "type" in df.columns:
        fig = px.pie(df, names="type", title="Therapeutical Classes")
        st.plotly_chart(fig, use_container_width=True)

    if df["Prix_num"].notna().any():
        top10 = df.nlargest(10, "Prix_num")
        fig = px.bar(top10, x="name", y="Prix_num", title="Top 10 Most Expensive Medicines")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "🧾 Observations":
    st.header("🩺 Commercial & Medical Observations")

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        type TEXT,
        comment TEXT,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
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
            conn.execute("INSERT INTO observations (product_name, type, comment) VALUES (?, ?, ?)",
                         (product, obs_type, comment))
            conn.commit()
            conn.close()
            st.success("✅ Observation saved.")
            st.rerun()

    st.markdown("---")
    conn = sqlite3.connect(db_path)
    df_obs = pd.read_sql_query("SELECT * FROM observations ORDER BY date DESC", conn)
    conn.close()

    if df_obs.empty:
        st.info("No observations yet.")
    else:
        for _, row in df_obs.iterrows():
            with st.expander(f"{row['product_name']} ({row['type']}) - {row['date']}"):
                st.write(row['comment'])


