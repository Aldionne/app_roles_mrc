import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

st.set_page_config(layout="wide")
st.title("🔍 Analyse des rôles d’évaluation foncière du Québec selon codes CUBF")

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
        response.raise_for_status()
        data = response.json()["result"]

        if "records" not in data or len(data["records"]) == 0:
            st.warning("⚠️ Aucun enregistrement trouvé dans les résultats de l’API.")
            return pd.DataFrame()

        records.extend(data["records"])
        if len(data["records"]) < limit:
            break
        offset += limit

    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()

    if "nom du territoire" not in df.columns or "lien" not in df.columns:
        st.error("❌ Les colonnes attendues ne sont pas disponibles.")
        st.write("Voici les colonnes disponibles :", df.columns.tolist())
        return pd.DataFrame()

    df = df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "MRC", "lien": "URL"})
    df = df.sort_values("MRC").reset_index(drop=True)
    return df

def parse_xml_to_df(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"❌ Impossible d'analyser le XML : {e}")
        return pd.DataFrame()

    rows = []
    for ue in root.findall(".//RLUEx"):
        code_cubf = ue.findtext("RL0105A")
        logements_str = ue.findtext("RL0311A")

        try:
            logements = int(logements_str) if logements_str else 0
        except:
            logements = 0

        if code_cubf:
            rows.append({
                "RL0105A": code_cubf.strip(),
                "RL0311A": logements
            })

    return pd.DataFrame(rows)

# App principale
mrc_links = fetch_mrc_roles()

if not mrc_links.empty:
    selected_mrc = st.selectbox("Choisissez une MRC", mrc_links["MRC"])
    selected_url = mrc_links.loc[mrc_links["MRC"] == selected_mrc, "URL"].values[0]
    st.markdown(f"📥 [Télécharger le rôle d’évaluation de {selected_mrc}]({selected_url})")

    if st.button("📂 Charger le fichier XML"):
        try:
            with st.spinner("Téléchargement et analyse du fichier XML en cours..."):
                response = requests.get(selected_url)
                response.raise_for_status()
                df_xml = parse_xml_to_df(response.content)

            if df_xml.empty:
                st.warning("⚠️ Aucune donnée valide trouvée dans le fichier XML.")
            else:
                st.session_state["df_xml"] = df_xml  # Enregistrer dans la session
        except Exception as e:
            st.error(f"❌ Erreur lors du téléchargement : {e}")

# Si un fichier a été chargé avec succès
if "df_xml" in st.session_state:
    df_xml = st.session_state["df_xml"]
    st.subheader("🎯 Sélection des codes CUBF à analyser")

    codes_cubf = sorted(df_xml["RL0105A"].dropna().unique())

    # Regroupement
