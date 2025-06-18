import streamlit as st 
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

st.set_page_config(layout="wide")
st.title("🔍 Analyse des rôles d’évaluation foncière du Québec par codes CUBF")

@st.cache_data(ttl=3600)
def fetch_mrc_roles():
    resource_id = "d2db6102-9215-4abc-9b5b-2c37f2e12618"
    base_url = "https://www.donneesquebec.ca/recherche/api/3/action/datastore_search"
    records = []
    offset = 0
    limit = 100

    while True:
        url = f"{base_url}?resource_id={resource_id}&limit={limit}&offset={offset}"
        response = requests.get(url)
        if response.status_code != 200:
            st.error("❌ Erreur lors du téléchargement de la liste des MRC.")
            return pd.DataFrame()
        data = response.json()["result"]

        if "records" not in data or len(data["records"]) == 0:
            st.warning("⚠️ Aucun enregistrement trouvé.")
            return pd.DataFrame()

        records.extend(data["records"])
        if len(data["records"]) < limit:
            break
        offset += limit

    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()
    if "nom du territoire" not in df.columns or "lien" not in df.columns:
        st.error("❌ Colonnes manquantes dans les données.")
        return pd.DataFrame()
    return df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "MRC", "lien": "URL"}).sort_values("MRC")

def parse_xml_to_df(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse XML : {e}")
        return pd.DataFrame()

    rows = []

    # ✅ Trouver toutes les unités d'évaluation, peu importe leur balise parente
    for ue in root.iter():
        # On identifie une unité d'évaluation comme un noeud qui contient au moins un code CUBF (RL0105A)
        if ue.find("RL0105A") is not None:
            row = {
                "RL0105A": ue.findtext("RL0105A") or "Inconnu",  # Code CUBF
                "RL0311A": ue.findtext("RL0311A"),               # Nb logements
                "RL0315A": ue.findtext("RL0315A"),               # Valeur terrain
                "RL0316A": ue.findtext("RL0316A"),               # Valeur immeuble
                "RLM02A":  ue.findtext("RLM02A")                 # Année du rôle
            }

            # Nettoyage et conversions
            for key in ["RL0311A", "RL0315A", "RL0316A"]:
                try:
                    row[key] = int(row[key]) if row[key] else 0
                except:
                    row[key] = 0

            row["RL0105A"] = row["RL0105A"].strip()
            rows.append(row)

    return pd.DataFrame(rows)

# Initialisation
if "df_xml" not in st.session_state:
    st.session_state.df_xml = None

df_mrc = fetch_mrc_roles()
if df_mrc.empty:
    st.stop()

selected_mrc = st.selectbox("📍 Choisissez une MRC", df_mrc["MRC"])
selected_url = df_mrc[df_mrc["MRC"] == selected_mrc]["URL"].values[0]
st.markdown(f"📥 [Télécharger le fichier XML de {selected_mrc}]({selected_url})")

if st.button("📂 Charger et analyser le fichier XML"):
    try:
        with st.spinner("Chargement du fichier XML..."):
            response = requests.get(selected_url)
            response.raise_for_status()
            st.session_state.df_xml = parse_xml_to_df(response.content)
        st.success("✅ Fichier XML chargé avec succès.")
    except Exception as e:
        st.error(f"Erreur : {e}")

df_xml = st.session_state.df_xml
if df_xml is not None and not df_xml.empty:
    st.subheader("🎯 Sélection des codes CUBF")

    codes_cubf = sorted(df_xml["RL0105A"].dropna().unique())

    # Regrouper par millier
    grouped = defaultdict(list)
    for code in codes_cubf:
        try:
            code_int = int(code)
            millier = (code_int // 1000) * 1000
        except:
            millier = "Inconnu"
        grouped[millier].append(code)

    with st.form("form_cubf"):
        select_all = st.checkbox("✅ Tout sélectionner", key="select_all")
        selected_codes = []

        for millier in sorted(grouped.keys()):
            with st.expander(f"{millier}–{millier + 999}" if isinstance(millier, int) else "Codes inconnus"):
                cols = st.columns(4)
                for idx, code in enumerate(sorted(grouped[millier])):
                    col = cols[idx % 4]
                    if select_all or col.checkbox(code, key=f"code_{code}"):
                        selected_codes.append(code)

        submitted = st.form_submit_button("📊 Analyser les codes sélectionnés")

    if submitted:
        if selected_codes:
            df_filtre = df_xml[df_xml["RL0105A"].isin(selected_codes)]

            # ✅ Récupérer l'année du rôle (supposée constante)
            annees_role = df_filtre["RLM02A"].dropna().unique()
            st.markdown(f"**📅 Année du rôle d’évaluation :** `{', '.join(annees_role)}`")

            # ✅ Statistiques globales
            total_unites = len(df_filtre)
            total_logements = df_filtre["RL0311A"].sum()
            moyenne_terrain = df_filtre["RL0315A"].mean()
            moyenne_immeuble = df_filtre["RL0316A"].mean()

            st.markdown("### ✅ Résultats")
            st.write(f"- **Nombre total d’unités d’évaluation sélectionnées** : {total_unites}")
            st.write(f"- **Nombre total de logements** : {total_logements}")
            st.write(f"- **Valeur moyenne des terrains** : {moyenne_terrain:,.0f} $")
            st.write(f"- **Valeur moyenne des immeubles** : {moyenne_immeuble:,.0f} $")

            df_resume = (
                df_filtre.groupby("RL0105A")
                .agg(
                    nb_unites=("RL0105A", "count"),
                    nb_logements=("RL0311A", "sum"),
                    valeur_terrain_moy=("RL0315A", "mean"),
                    valeur_immeuble_moy=("RL0316A", "mean")
                )
                .reset_index()
                .rename(columns={"RL0105A": "Code CUBF"})
            )

            st.markdown("### 📋 Résumé par CUBF")
            st.dataframe(df_resume)

            with st.expander("🔍 Détails bruts des entrées filtrées"):
                st.dataframe(df_filtre)
        else:
            st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")
else:
    st.info("📄 Aucune donnée chargée. Cliquez sur le bouton ci-dessus pour analyser le fichier XML.")
