import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import requests
from io import BytesIO
from collections import defaultdict
import re

st.set_page_config(layout="wide")
st.title("🏠 Analyse des rôles d'évaluation foncière par codes CUBF")

# 1. Téléchargement des MRC et liens
@st.cache_data(ttl=3600)
def fetch_mrc_roles():
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
    return df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "MRC", "lien": "URL"}).sort_values("MRC")


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


# 3. Interface utilisateur
if "df_xml" not in st.session_state:
    st.session_state.df_xml = None

df_mrc = fetch_mrc_roles()
if df_mrc.empty:
    st.error("Impossible de charger les MRC.")
    st.stop()

selected_mrc = st.selectbox("📍 Choisissez une MRC", df_mrc["MRC"])
selected_url = df_mrc[df_mrc["MRC"] == selected_mrc]["URL"].values[0]
st.markdown(f"📥 [Télécharger le fichier XML de {selected_mrc}]({selected_url})")

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
            file_name=f"analyse_cubf_{selected_mrc.replace(' ', '_')}.csv",
            mime="text/csv"
        )

        with st.expander("🔍 Voir les entrées brutes"):
            st.dataframe(df_sel, use_container_width=True)
            
            # Option pour télécharger les données brutes
            csv_raw = df_sel.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger les données brutes (CSV)",
                data=csv_raw,
                file_name=f"donnees_brutes_{selected_mrc.replace(' ', '_')}.csv",
                mime="text/csv"
            )

else:
    st.info("📄 Aucune donnée chargée. Veuillez sélectionner une MRC et charger le fichier XML.")
