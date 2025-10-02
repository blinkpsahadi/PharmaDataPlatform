import sqlite3
from datetime import datetime

# Chemin vers la base existante
DB_PATH = "data/all_pharma.db"

# Connexion à la base
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# -------------------------------
# 1️⃣ Renommer les colonnes existantes si nécessaire
# -------------------------------
rename_columns = {
    "Nom complet": "nom",
    "Lien": "lien",
    "Prix": "prix"
}

for old_name, new_name in rename_columns.items():
    # Vérifier si la colonne existe avant de renommer
    cur.execute("PRAGMA table_info(medicaments)")
    columns = [col[1] for col in cur.fetchall()]
    if old_name in columns:
        cur.execute(f"ALTER TABLE medicaments RENAME COLUMN '{old_name}' TO {new_name}")

# -------------------------------
# 2️⃣ Ajouter les colonnes manquantes si elles n'existent pas
# -------------------------------
columns_to_add = {
    'atc': "TEXT",
    'bcs': "TEXT",
    'oeb': "TEXT",
    'bioequivalence': "TEXT",
    'en_algerie': "TEXT DEFAULT 'Oui'",
    'office_hop': "TEXT DEFAULT 'Office'",
    'observation_medicale': "TEXT",
    'observation_commerciale': "TEXT",
    'statut_pipeline': "TEXT DEFAULT 'Nouveau'",
    'date_modif': "TEXT DEFAULT '" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "'"
}

cur.execute("PRAGMA table_info(medicaments)")
existing_cols = [col[1] for col in cur.fetchall()]

for col, col_type in columns_to_add.items():
    if col not in existing_cols:
        cur.execute(f"ALTER TABLE medicaments ADD COLUMN {col} {col_type}")

# -------------------------------
# 3️⃣ Vérifier le résultat
# -------------------------------
cur.execute("PRAGMA table_info(medicaments)")
print("Colonnes finales dans medicaments :")
for col in cur.fetchall():
    print(col)

conn.commit()
conn.close()
print("✅ Base all_pharma.db préparée et harmonisée pour l'app Streamlit")
