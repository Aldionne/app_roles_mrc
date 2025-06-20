import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import requests
from io import BytesIO
from collections import defaultdict
import re

st.set_page_config(layout="wide")
st.title("🏠 Analyse des rôles d'évaluation foncière par codes CUBF")

# --- Dictionnaire MRC -> Région administrative ---
mrc_to_region = {
    "Abitibi": "Abitibi-Témiscamingue",
    "Abitibi-Ouest": "Abitibi-Témiscamingue",
    "Acton": "Montérégie",
    "Antoine-Labelle": "Laurentides",
    "Argenteuil": "Laurentides",
    "Arthabaska": "Centre-du-Québec",
    "Avignon": "Gaspésie–Îles-de-la-Madeleine",
    "Beauce-Centre": "Chaudière-Appalaches",
    "Beauce-Sartigan": "Chaudière-Appalaches",
    "Beauharnois-Salaberry": "Montérégie",
    "Bécancour": "Centre-du-Québec",
    "Bellechasse": "Chaudière-Appalaches",
    "Bonaventure": "Gaspésie–Îles-de-la-Madeleine",
    "Brome-Missisquoi": "Estrie",
    "Caniapiscau": "Côte-Nord",
    "Charlevoix": "Capitale-Nationale",
    "Charlevoix-Est": "Capitale-Nationale",
    "Coaticook": "Estrie",
    "D’Autray": "Lanaudière",
    "Deux-Montagnes": "Laurentides",
    "Drummond": "Centre-du-Québec",
    "Joliette": "Lanaudière",
    "Kamouraska": "Bas-Saint-Laurent",
    "L’Assomption": "Lanaudière",
    "L’Érable": "Centre-du-Québec",
    "L’Île-d’Orléans": "Capitale-Nationale",
    "L’Islet": "Chaudière-Appalaches",
    "La Côte-de-Beaupré": "Capitale-Nationale",
    "La Côte-de-Gaspé": "Gaspésie–Îles-de-la-Madeleine",
    "La Haute-Côte-Nord": "Côte-Nord",
    "La Haute-Gaspésie": "Gaspésie–Îles-de-la-Madeleine",
    "La Haute-Yamaska": "Estrie",
    "La Jacques-Cartier": "Capitale-Nationale",
    "La Matanie": "Bas-Saint-Laurent",
    "La Matapédia": "Bas-Saint-Laurent",
    "La Mitis": "Bas-Saint-Laurent",
    "La Nouvelle-Beauce": "Chaudière-Appalaches",
    "La Rivière-du-Nord": "Laurentides",
    "La Vallée-de-la-Gatineau": "Outaouais",
    "La Vallée-de-l’Or": "Abitibi-Témiscamingue",
    "La Vallée-du-Richelieu": "Montérégie",
    "Lac-Saint-Jean-Est": "Saguenay–Lac-Saint-Jean",
    "Le Domaine-du-Roy": "Saguenay–Lac-Saint-Jean",
    "Le Fjord-du-Saguenay": "Saguenay–Lac-Saint-Jean",
    "Le Golfe-du-Saint-Laurent": "Côte-Nord",
    "Le Granit": "Estrie",
    "Le Haut-Richelieu": "Montérégie",
    "Le Haut-Saint-François": "Estrie",
    "Le Haut-Saint-Laurent": "Montérégie",
    "Le Rocher-Percé": "Gaspésie–Îles-de-la-Madeleine",
    "Le Val-Saint-François": "Estrie",
    "Les Appalaches": "Chaudière-Appalaches",
    "Les Basques": "Bas-Saint-Laurent",
    "Les Chenaux": "Mauricie",
    "Les Collines-de-l’Outaouais": "Outaouais",
    "Les Etchemins": "Chaudière-Appalaches",
    "Les Jardins-de-Napierville": "Montérégie",
    "Les Laurentides": "Laurentides",
    "Les Maskoutains": "Montérégie",
    "Les Moulins": "Lanaudière",
    "Les Pays-d’en-Haut": "Laurentides",
    "Les Sources": "Estrie",
    "Lotbinière": "Chaudière-Appalaches",
    "Manicouagan": "Côte-Nord",
    "Marguerite-D’Youville": "Montérégie",
    "Maria-Chapdelaine": "Saguenay–Lac-Saint-Jean",
    "Maskinongé": "Mauricie",
    "Matawinie": "Lanaudière",
    "Mékinac": "Mauricie",
    "Memphrémagog": "Estrie",
    "Minganie": "Côte-Nord",
    "Montcalm": "Lanaudière",
    "Montmagny": "Chaudière-Appalaches",
    "Nicolet-Yamaska": "Centre-du-Québec",
    "Papineau": "Outaouais",
    "Pierre-De Saurel": "Montérégie",
    "Pontiac": "Outaouais",
    "Portneuf": "Capitale-Nationale",
    "Rimouski-Neigette": "Bas-Saint-Laurent",
    "Rivière-du-Loup": "Bas-Saint-Laurent",
    "Roussillon": "Montérégie",
    "Rouville": "Montérégie",
    "Sept-Rivières": "Côte-Nord",
    "Témiscamingue": "Abitibi-Témiscamingue",
    "Témiscouata": "Bas-Saint-Laurent",
    "Thérèse-De Blainville": "Laurentides",
    "Vaudreuil-Soulanges": "Montérégie"
}

# 1. Chargement des territoires
@st.cache_data(ttl=3600)
def fetch_territories():
    url = "https://www.donneesquebec.ca/recherche/api/3/action/datastore_search"
    resource_id = "d2db6102-9215-4abc-9b5b-2c37f2e12618"
    records = []
    offset = 0
    limit = 100
    while True:
        r = requests.get(f"{url}?resource_id={resource_id}&limit={limit}&offset={offset}")
        if r.status_code != 200:
            return pd.DataFrame()
        out = r.json()["result"]
        records.extend(out["records"])
        if len(out["records"]) < limit:
            break
        offset += limit
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()
    df = df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "Territoire", "lien": "URL"})
    def classify_territory(name):
        name_upper = name.upper()
        mrc_indicators = ["MRC", "M.R.C.", "MUNICIPALITÉ RÉGIONALE", "REGIONAL COUNTY", "COMMUNAUTÉ MÉTROPOLITAINE", "AGGLOMÉRATION"]
        municipality_indicators = ["VILLE DE", "CITY OF", "MUNICIPALITY OF", "MUNICIPALITÉ DE", "CANTON DE", "TOWNSHIP OF", "VILLAGE DE", "VILLAGE OF", "PAROISSE DE", "PARISH OF"]
        for indicator in mrc_indicators:
            if indicator in name_upper:
                return "MRC"
        for indicator in municipality_indicators:
            if indicator in name_upper:
                return "Municipalité"
        if len(name.split()) <= 2 and not any(x in name_upper for x in ["MRC", "COMMUNAUTÉ"]):
            return "Municipalité"
        return "Municipalité"
    df["Type"] = df["Territoire"].apply(classify_territory)
    df["Région"] = df["Territoire"].apply(lambda x: mrc_to_region.get(x, "Inconnue"))
    return df.sort_values(["Type", "Territoire"])

# Interface de sélection
st.subheader("🏛️ Sélection du territoire")
df_territories = fetch_territories()
if df_territories.empty:
    st.error("Impossible de charger les territoires.")
    st.stop()
col1, col2, col3 = st.columns([1, 2, 2])
with col1:
    territory_type = st.selectbox("Type de territoire", ["Tous", "MRC", "Municipalité"])
with col2:
    region_list = ["Toutes"] + sorted(df_territories["Région"].unique())
    selected_region = st.selectbox("Région administrative", region_list)
filtered_df = df_territories.copy()
if territory_type != "Tous":
    filtered_df = filtered_df[filtered_df["Type"] == territory_type]
if selected_region != "Toutes":
    filtered_df = filtered_df[filtered_df["Région"] == selected_region]
with col3:
    selected_territory = st.selectbox("📍 Territoire", filtered_df["Territoire"])
selected_row = filtered_df[filtered_df["Territoire"] == selected_territory]
selected_url = selected_row["URL"].values[0]
selected_type = selected_row["Type"].values[0]
st.markdown(f"📋 **Type :** {selected_type}")
st.markdown(f"📥 [Télécharger le fichier XML de {selected_territory}]({selected_url})")


# 2. Lecture du XML corrigée pour la structure RLUEx
def parse_units_from_xml(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"Erreur lors du chargement du XML : {e}")
        return pd.DataFrame()

    data = []
    
    # Trouver tous les éléments RLUEx
    rlue_elements = root.findall(".//RLUEx")
    
    if not rlue_elements:
        st.error("Aucun élément RLUEx trouvé dans le XML")
        return pd.DataFrame()
    
    st.info(f"🔍 Trouvé {len(rlue_elements)} éléments RLUEx dans le XML")
    
    for elem in rlue_elements:
        record = {}
        
        # Extraire les données directement des enfants de RLUEx
        for child in elem:
            if child.tag == "RL0105A":
                record["RL0105A"] = child.text.strip() if child.text else ""
            elif child.tag == "RL0311A":
                record["RL0311A"] = child.text.strip() if child.text else ""
            elif child.tag == "RLM02A":
                record["RLM02A"] = child.text.strip() if child.text else ""
            elif child.tag == "RL0402A":  # Valeur terrain
                record["RL0315A"] = child.text.strip() if child.text else ""
            elif child.tag == "RL0403A":  # Valeur bâtiment
                record["RL0316A"] = child.text.strip() if child.text else ""
        
        # Extraire l'année du niveau racine si pas trouvée
        if "RLM02A" not in record:
            year_elem = root.find("RLM02A")
            if year_elem is not None:
                record["RLM02A"] = year_elem.text.strip() if year_elem.text else ""

        def clean_numeric(val):
            if not val:
                return 0.0
            try:
                # Nettoyer les valeurs numériques
                cleaned = val.replace(",", ".").replace(" ", "")
                return float(cleaned)
            except:
                return 0.0

        # Ajouter seulement si on a au moins le code CUBF
        if record.get("RL0105A"):
            data.append({
                "RL0105A": record.get("RL0105A", "Inconnu"),
                "RL0311A": clean_numeric(record.get("RL0311A")),
                "RL0315A": clean_numeric(record.get("RL0315A")),
                "RL0316A": clean_numeric(record.get("RL0316A")),
                "RLM02A": record.get("RLM02A", "Inconnue")
            })

    return pd.DataFrame(data)


# 3. Interface utilisateur avec filtres par type de territoire
if "df_xml" not in st.session_state:
    st.session_state.df_xml = None

df_territories = fetch_territories()
if df_territories.empty:
    st.error("Impossible de charger les territoires.")
    st.stop()

# Filtres pour type de territoire
st.subheader("🏛️ Sélection du territoire")

col1, col2 = st.columns([1, 3])

with col1:
    territory_type = st.selectbox(
        "Type de territoire",
        ["Tous", "MRC", "Municipalité"],
        help="MRC = Municipalités Régionales de Comté (regroupent plusieurs municipalités)\nMunicipalité = Villes, villages, cantons individuels"
    )

# Filtrer selon le type sélectionné
if territory_type == "Tous":
    df_filtered = df_territories
else:
    df_filtered = df_territories[df_territories["Type"] == territory_type]

with col2:
    if not df_filtered.empty:
        selected_territory = st.selectbox(
            f"📍 Choisissez un territoire ({len(df_filtered)} disponibles)",
            df_filtered["Territoire"],
            format_func=lambda x: f"🏛️ {x}" if df_territories[df_territories["Territoire"] == x]["Type"].iloc[0] == "MRC" else f"🏘️ {x}"
        )
        selected_url = df_filtered[df_filtered["Territoire"] == selected_territory]["URL"].values[0]
        selected_type = df_filtered[df_filtered["Territoire"] == selected_territory]["Type"].values[0]
        
        st.markdown(f"📋 **Type :** {selected_type}")
        st.markdown(f"📥 [Télécharger le fichier XML de {selected_territory}]({selected_url})")
    else:
        st.warning(f"Aucun territoire de type '{territory_type}' trouvé.")
        st.stop()

# Statistiques des territoires
with st.expander("📊 Statistiques des territoires"):
    type_counts = df_territories["Type"].value_counts()
    for territory_type, count in type_counts.items():
        st.write(f"- **{territory_type}** : {count} territoires")
    
    st.write(f"- **Total** : {len(df_territories)} territoires")

if st.button("📂 Charger et analyser le fichier XML"):
    try:
        with st.spinner("Chargement en cours..."):
            r = requests.get(selected_url)
            r.raise_for_status()
            df = parse_units_from_xml(r.content)
            st.session_state.df_xml = df
        st.success(f"✅ Fichier XML chargé avec succès. {len(df)} unités trouvées.")
    except Exception as e:
        st.error(f"Erreur : {e}")

df_xml = st.session_state.df_xml
if df_xml is not None and not df_xml.empty:
    st.write(f"📊 **Nombre total d'unités :** {len(df_xml)}")
    annee = df_xml["RLM02A"].dropna().unique()
    st.write(f"📅 **Année du rôle :** {', '.join(annee)}")

    # Afficher quelques statistiques de base
    st.write(f"🏷️ **Codes CUBF uniques :** {df_xml['RL0105A'].nunique()}")
    st.write(f"🏠 **Total logements :** {df_xml['RL0311A'].sum():,.0f}")
    
    # Sélection des CUBF
    st.subheader("🎯 Sélection des codes CUBF")
    codes_cubf = sorted(df_xml["RL0105A"].unique())

    grouped = defaultdict(list)
    for code in codes_cubf:
        try:
            val = int(code)
            millier = (val // 1000) * 1000
        except:
            millier = "Autres"
        grouped[millier].append(code)

    with st.form("filter_form"):
        select_all = st.checkbox("✅ Tout sélectionner", key="select_all")
        selected = []
        
        for group in sorted(grouped.keys()):
            with st.expander(f"{group} – {group + 999}" if isinstance(group, int) else str(group)):
                cols = st.columns(4)
                for i, code in enumerate(sorted(grouped[group])):
                    col = cols[i % 4]
                    if select_all or col.checkbox(code, key=f"cb_{code}"):
                        selected.append(code)
        
        submitted = st.form_submit_button("📊 Analyser")

    if submitted:
        if not selected:
            st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")
            st.stop()

        df_sel = df_xml[df_xml["RL0105A"].isin(selected)]

        # Résumé
        st.markdown("### ✅ Résultats globaux")
        st.write(f"- **Unités d'évaluation sélectionnées :** {len(df_sel)}")
        st.write(f"- **Total de logements :** {df_sel['RL0311A'].sum():,.0f}")
        
        # Calculer les moyennes seulement pour les valeurs non-nulles
        terrain_non_zero = df_sel[df_sel['RL0315A'] > 0]['RL0315A']
        immeuble_non_zero = df_sel[df_sel['RL0316A'] > 0]['RL0316A']
        
        if len(terrain_non_zero) > 0:
            st.write(f"- **Valeur moyenne des terrains :** {terrain_non_zero.mean():,.0f} $ (sur {len(terrain_non_zero)} unités)")
        else:
            st.write("- **Valeur moyenne des terrains :** N/A")
            
        if len(immeuble_non_zero) > 0:
            st.write(f"- **Valeur moyenne des immeubles :** {immeuble_non_zero.mean():,.0f} $ (sur {len(immeuble_non_zero)} unités)")
        else:
            st.write("- **Valeur moyenne des immeubles :** N/A")

        # Tableau par CUBF
        df_res = (
            df_sel.groupby("RL0105A")
            .agg(
                nb_unites=("RL0105A", "count"),
                total_logements=("RL0311A", "sum"),
                val_terrain_moy=("RL0315A", lambda x: x[x > 0].mean() if (x > 0).any() else 0),
                val_immeuble_moy=("RL0316A", lambda x: x[x > 0].mean() if (x > 0).any() else 0),
                val_terrain_total=("RL0315A", "sum"),
                val_immeuble_total=("RL0316A", "sum")
            )
            .reset_index()
            .rename(columns={
                "RL0105A": "Code CUBF",
                "nb_unites": "Nb unités",
                "total_logements": "Total logements",
                "val_terrain_moy": "Valeur terrain moy.",
                "val_immeuble_moy": "Valeur immeuble moy.",
                "val_terrain_total": "Valeur terrain total",
                "val_immeuble_total": "Valeur immeuble total"
            })
        )

        # Formater les valeurs monétaires
        for col in ["Valeur terrain moy.", "Valeur immeuble moy.", "Valeur terrain total", "Valeur immeuble total"]:
            df_res[col] = df_res[col].apply(lambda x: f"{x:,.0f} $" if x > 0 else "N/A")

        st.markdown("### 📋 Résumé par CUBF")
        st.dataframe(df_res, use_container_width=True)

        # Option pour télécharger les résultats
        csv = df_res.to_csv(index=False)
        st.download_button(
            label="📥 Télécharger le résumé (CSV)",
            data=csv,
            file_name=f"analyse_cubf_{selected_territory.replace(' ', '_')}.csv",
            mime="text/csv"
        )

        with st.expander("🔍 Voir les entrées brutes"):
            st.dataframe(df_sel, use_container_width=True)
            
            # Option pour télécharger les données brutes
            csv_raw = df_sel.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger les données brutes (CSV)",
                data=csv_raw,
                file_name=f"donnees_brutes_{selected_territory.replace(' ', '_')}.csv",
                mime="text/csv"
            )

else:
    st.info("📄 Aucune donnée chargée. Veuillez sélectionner une MRC et charger le fichier XML.")
