import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import requests
from io import BytesIO
from collections import defaultdict
import re

st.set_page_config(layout="wide")
st.title("🏠 Analyse des rôles d’évaluation foncière par codes CUBF")

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


# 2. Lecture du XML par RL0101Ax
def parse_units_from_rl0101ax(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"Erreur lors du chargement du XML : {e}")
        return pd.DataFrame()

    data = []
    for elem in root.findall(".//RL0101Ax"):
        record = {}
        for sub in elem.iter():
            tag = sub.tag
            text = sub.text.strip() if sub.text else ""
            if tag in ["RL0105A", "RL0311A", "RL0315A", "RL0316A", "RLM02A"]:
                record[tag] = text

        def clean(val):
            try:
                return float(val.replace(",", ".")) if val else 0.0
            except:
                return 0.0

        data.append({
            "RL0105A": record.get("RL0105A", "Inconnu"),
            "RL0311A": clean(record.get("RL0311A")),
            "RL0315A": clean(record.get("RL0315A")),
            "RL0316A": clean(record.get("RL0316A")),
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
            df = parse_units_from_rl0101ax(r.content)
            st.session_state.df_xml = df
        st.success("✅ Fichier XML chargé avec succès.")
    except Exception as e:
        st.error(f"Erreur : {e}")

df_xml = st.session_state.df_xml
if df_xml is not None and not df_xml.empty:
    st.write(f"📊 **Nombre total d’unités :** {len(df_xml)}")
    annee = df_xml["RLM02A"].dropna().unique()
    st.write(f"📅 **Année du rôle :** {', '.join(annee)}")

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
        st.write(f"- **Unités d’évaluation :** {len(df_sel)}")
        st.write(f"- **Total de logements :** {df_sel['RL0311A'].sum():,.0f}")
        st.write(f"- **Valeur moyenne des terrains :** {df_sel['RL0315A'].mean():,.0f} $")
        st.write(f"- **Valeur moyenne des immeubles :** {df_sel['RL0316A'].mean():,.0f} $")

        # Tableau par CUBF
        df_res = (
            df_sel.groupby("RL0105A")
            .agg(
                nb_unites=("RL0105A", "count"),
                total_logements=("RL0311A", "sum"),
                val_terrain_moy=("RL0315A", "mean"),
                val_immeuble_moy=("RL0316A", "mean")
            )
            .reset_index()
            .rename(columns={"RL0105A": "Code CUBF"})
        )

        st.markdown("### 📋 Résumé par CUBF")
        st.dataframe(df_res)

        with st.expander("🔍 Voir les entrées brutes"):
            st.dataframe(df_sel)
else:
    st.info("📄 Aucune donnée chargée.")
