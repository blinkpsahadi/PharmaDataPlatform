# -*- coding: utf-8 -*-
"""
Script Python pour Google Colab : Analyse des Immunosuppresseurs
Ce script lit les données Excel (.xlsx), génère des visualisations interactives
avec Plotly et les enregistre dans un fichier HTML.
"""

import pandas as pd
import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import os
from datetime import datetime

# --- 1. CONFIGURATION ET NETTOYAGE DES DONNÉES ---

# Nom du fichier téléchargé sur Colab
# IMPORTANT: Utilisation du nom du fichier Excel original
# NOTE: Le nom du fichier a été ajusté en fonction de l'artefact détecté :
FILE_NAME = "CLASSIFICATION_DES_IMMUNOSUPRESSEURS_ATC_DDD_NOMENCLATURE.xlsx"
OUTPUT_HTML_FILE = "rapport_immunsuppresseurs.html"

# Assurez-vous d'avoir installé les dépendances si vous utilisez un nouvel environnement :
# !pip install pandas plotly openpyxl

def load_and_prepare_data(file_path):
    """Charge le fichier Excel, gère les lignes d'en-tête et normalise les colonnes."""
    print(f"Chargement du fichier : {file_path}")

    # Lecture du fichier Excel (.xlsx) avec openpyxl
    # Nous lisons la première feuille (sheet_name=0) et définissons la deuxième ligne (index 1) comme l'en-tête.
    df = pd.read_excel(file_path, header=1, sheet_name=0)

    # Nettoyage de base : retirer les lignes entièrement vides
    df.dropna(how='all', inplace=True)

    # --- VÉRIFICATION DES NOMS DE COLONNES ET RENOMMAGE ---
    # Dictionnaire de mappage des colonnes : {Nom EXACT dans Excel : Nom standard utilisé dans le script}
    column_mapping = {
        'DCI': 'DCI',
        'Forme': 'Forme',
        'Laboratoire Fabricant': 'Laboratoire Fabricant',
        'Nomenclature': 'Nomenclature',
        'INDICATION': 'Indication', # Renomme 'INDICATION' (majuscules) en 'Indication' (casse standard)
        'Type de Classification': 'Type de Classification', # Le nom exact trouvé
    }

    rename_dict = {}
    found_cols = df.columns.tolist()

    print("Noms des colonnes trouvées après chargement :", found_cols)

    required_cols_to_map = list(column_mapping.keys())

    for excel_name, script_name in column_mapping.items():
        # Trouver la colonne exacte
        if excel_name in found_cols:
            rename_dict[excel_name] = script_name
        # Gérer le cas où la casse diffère (ex: 'indication' au lieu de 'INDICATION')
        elif excel_name.upper() in found_cols and excel_name.upper() != excel_name:
            rename_dict[excel_name.upper()] = script_name
        # Gérer le cas où la colonne est en minuscule
        elif excel_name.lower() in found_cols and excel_name.lower() != excel_name:
            rename_dict[excel_name.lower()] = script_name


    # --- Vérification critique que les colonnes nécessaires sont présentes ---
    # On vérifie que les clés standardisées (les valeurs du dictionnaire de mapping) existent dans le df après renommage simulé
    current_cols = set(found_cols)
    for excel_name, script_name in column_mapping.items():
        if excel_name in rename_dict:
            current_cols.add(script_name)

    missing_cols = [script_name for excel_name, script_name in column_mapping.items() if script_name not in current_cols]

    if missing_cols:
        raise ValueError(f"Colonnes manquantes ou mal nommées après la vérification. Les colonnes requises dans le script sont : {list(column_mapping.values())}. Colonnes trouvées (initiales) : {found_cols}")

    df.rename(columns=rename_dict, inplace=True)

    # Remplacement des valeurs manquantes (NaN) par une chaîne claire pour les graphiques
    df.fillna({'Laboratoire Fabricant': 'Non Spécifié', 'Indication': 'Non Spécifiée', 'Nomenclature': 'Non Spécifié', 'DCI': 'Non Spécifiée'}, inplace=True)

    # Conversion des colonnes de texte en chaînes et suppression des espaces blancs
    cols_to_clean = ['Forme', 'Indication', 'Laboratoire Fabricant', 'Nomenclature', 'Type de Classification', 'DCI']
    for col in cols_to_clean:
        if col in df.columns:
            # Nettoyage et capitalisation des premières lettres
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].apply(lambda x: x.capitalize() if x.lower() not in ['nan', 'non spécifié'] else x)

    # --- AJOUT DU NETTOYAGE SPÉCIFIQUE POUR LA NOMENCLATURE ---
    if 'Nomenclature' in df.columns:
        # Remplacer les chaînes vides (qui ne sont pas NaN) par 'Non Spécifié'
        df['Nomenclature'].replace('', 'Non Spécifié', inplace=True)
        # Assurer l'uniformité de la casse pour les valeurs clés
        df['Nomenclature'] = df['Nomenclature'].apply(lambda x: x.capitalize() if isinstance(x, str) else x)
    # --------------------------------------------------------

    print(f"Données chargées. Nombre de lignes après nettoyage : {len(df)}")
    return df

# --- 2. FONCTIONS DE CRÉATION DE GRAPHIQUES ---

def create_count_chart(df, column, chart_type='bar'):
    """
    Crée un graphique de comptage (Barre ou Camembert) pour une colonne catégorielle,
    avec la liste des DCI affichée au survol.
    """

    # Agrégation des données : compte et agrégation des DCI
    counts = df.groupby(column).agg(
        Count=('DCI', 'size'),
        # Agrège les DCI uniques et les sépare par un saut de ligne HTML
        DCI_List=('DCI', lambda x: '<br>' + '<br>'.join(x.unique()))
    ).reset_index()

    # Définition du titre
    title = f"Distribution par {column}"

    # Configuration du modèle de survol (hovertemplate)
    hover_text_pie = "<b>%{label}</b><br>Molécules : %{value}<br>Liste des DCI : %{customdata[0]}<extra></extra>"

    if chart_type == 'pie':
        # Graphique en camembert
        fig = px.pie(
            counts,
            values='Count',
            names=column,
            title=title,
            color=column,
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hole=.3,
            custom_data=['DCI_List'] # Ajout de la liste des DCI comme donnée personnalisée
        )
        # Utilisation de 'auto' pour la position et 'percent' pour l'info pour maximiser la lisibilité
        fig.update_traces(textposition='auto', textinfo='percent',
                          hovertemplate=hover_text_pie)

        # Ajout de la configuration de la légende pour éviter l'overflow
        fig.update_layout(
            uniformtext_minsize=12, uniformtext_mode='hide', showlegend=True,
            legend=dict(
                orientation="h",  # Légende horizontale
                yanchor="bottom",
                y=-0.15,          # Position légèrement sous le graphique
                xanchor="center",
                x=0.5
            )
        )

    else: # Bar chart
        # Configuration du modèle de survol pour les barres
        bar_hover_text = "<b>%{x}</b><br>Molécules : %{y}<br>Liste des DCI : %{customdata[0]}<extra></extra>"

        fig = px.bar(
            counts,
            x=column,
            y='Count',
            title=title,
            color=column,
            color_discrete_sequence=px.colors.qualitative.Dark24,
            text='Count',
            custom_data=['DCI_List'] # Ajout de la liste des DCI comme donnée personnalisée
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside', hovertemplate=bar_hover_text)
        fig.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_title="Nombre de Molécules")

    # Réduction de la hauteur globale pour un meilleur ajustement dans le grid-container
    fig.update_layout(
        title_font_size=20,
        margin=dict(t=50, l=20, r=20, b=20),
        height=500, # Hauteur ajustée
        template='plotly_white'
    )
    return fig

def create_all_charts(df):
    """Génère tous les graphiques requis et retourne leur code HTML."""

    charts_html = []

    # 1. Classification (Type) - BAR CHART
    classification_counts = df['Type de Classification'].value_counts()
    top_n = 8
    top_classifications = classification_counts.nlargest(top_n).index

    df_class = df.copy()
    # Regrouper les petites catégories pour la clarté
    df_class['Classification Groupée'] = df_class['Type de Classification'].apply(
        lambda x: x if x in top_classifications else 'Autres Classifications'
    )

    fig1 = create_count_chart(df_class, 'Classification Groupée', chart_type='bar')
    fig1.update_layout(title="Distribution par Type de Classification (Top 8 et Autres)")
    charts_html.append(plot(fig1, output_type='div', include_plotlyjs=False))

    # 2. Forme - Bar Chart
    fig2 = create_count_chart(df, 'Forme', chart_type='bar')
    charts_html.append(plot(fig2, output_type='div', include_plotlyjs=False))

    # 3. Indication - Bar Chart
    fig3 = create_count_chart(df, 'Indication', chart_type='bar')
    charts_html.append(plot(fig3, output_type='div', include_plotlyjs=False))

    # 4. Laboratoire Fabricant - Bar Chart
    # Regrouper les petits laboratoires pour la clarté
    top_labs = df['Laboratoire Fabricant'].value_counts().nlargest(10).index
    df_labs = df.copy()
    df_labs['Laboratoire Fabricant Groupé'] = df_labs['Laboratoire Fabricant'].apply(
        lambda x: x if x in top_labs else 'Autres Laboratoires'
    )
    fig4 = create_count_chart(df_labs, 'Laboratoire Fabricant Groupé', chart_type='bar')
    fig4.update_layout(title="Distribution par Laboratoire Fabricant (Top 10 + Autres)")
    charts_html.append(plot(fig4, output_type='div', include_plotlyjs=False))

    # 5. Nomenclature - Pie Chart (Binaire)
    fig5 = create_count_chart(df, 'Nomenclature', chart_type='pie')
    charts_html.append(plot(fig5, output_type='div', include_plotlyjs=False))

    return charts_html

# --- 3. ASSEMBLAGE FINAL DE LA PAGE HTML ---

def generate_final_html(charts_html_list, output_file):
    """Crée le fichier HTML final en intégrant les graphiques et le style."""

    # La librairie Plotly doit être incluse une seule fois (via CDN)
    plotly_js_cdn = '<script src="https://cdn.plot.ly/plotly-2.30.0.min.js" charset="utf-8"></script>'

    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport d'Analyse des Immunosuppresseurs - {datetime.now().strftime('%Y-%m-%d')}</title>
    {plotly_js_cdn}
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f4f7f6;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #fff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #007bff;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
            margin-bottom: 30px;
            font-size: 2em;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            font-size: 1.5em;
        }}
        .chart-box {{
            background-color: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .grid-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Synthèse des Données sur les Immunosuppresseurs (Forme Sèche)</h1>
        <p>Analyse des molécules {datetime.now().strftime('%d/%m/%Y')}.</p>

        <h2>Distribution Totale</h2>

        <div class="grid-container">
            <div class="chart-box">
                <!-- Graphique Nomenclature (Pie Chart) -->
                {charts_html_list[4]}
            </div>
            <div class="chart-box">
                <!-- Graphique Type de Classification (Bar Chart) -->
                {charts_html_list[0]}
            </div>
        </div>

        <h2>Détail par Caractéristique</h2>

        <div class="chart-box">
            <!-- Graphique Indication (Bar Chart) -->
            {charts_html_list[2]}
        </div>

        <div class="chart-box">
            <!-- Graphique Forme (Bar Chart) -->
            {charts_html_list[1]}
        </div>

        <div class="chart-box">
            <!-- Graphique Laboratoire Fabricant (Bar Chart) -->
            {charts_html_list[3]}
        </div>

        <p style="text-align: center; margin-top: 40px; font-size: 0.8em; color: #666;">Rapport généré par le script d'analyse des données.</p>
    </div>
</body>
</html>
    """

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ Fichier HTML interactif généré avec succès : {output_file}")


# --- 4. EXÉCUTION PRINCIPALE ---
if __name__ == "__main__":
    try:
        # 1. Charger et préparer les données
        data_frame = load_and_prepare_data(FILE_NAME)

        # 2. Créer les graphiques
        all_charts_html = create_all_charts(data_frame)

        # 3. Générer le rapport HTML
        generate_final_html(all_charts_html, OUTPUT_HTML_FILE)

        # 4. Afficher un message de confirmation
        print("\n--- ÉTAPES SUIVANTES ---")
        print(f"Le fichier de rapport HTML '{OUTPUT_HTML_FILE}' est prêt.")
        print("Téléchargez ce fichier et ouvrez-le dans votre navigateur pour visualiser les graphiques interactifs.")

    except FileNotFoundError:
        print(f"\nERREUR: Le fichier '{FILE_NAME}' n'a pas été trouvé.")
        print(f"Veuillez vous assurer que le fichier Excel est présent dans le même répertoire.")
    except Exception as e:
        if 'data_frame' in locals():
            print(f"\nSuggestion : Vérifiez le nom exact des colonnes. Colonnes trouvées : {data_frame.columns.tolist()}")
        print(f"\nUne erreur inattendue s'est produite : {e}")
