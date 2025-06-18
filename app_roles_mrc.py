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
            st.warning("⚠️ Aucun enregistrement trouvé.")
            return pd.DataFrame()

        records.extend(data["records"])
        if len(data["records"]) < limit:
            break
        offset += limit

    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()

    if "nom du territoire" not in df.columns or "lien" not in df.columns:
        st.error("❌ Colonnes manquantes.")
        st.write("Colonnes disponibles :", df.columns.tolist())
        return pd.DataFrame()

    df = df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "MRC", "lien": "URL"})
    return df.sort_values("MRC").reset_index(drop=True)

def parse_xml_to_df(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"❌ Erreur XML : {e}")
        return pd.DataFrame()

    rows = []
    for ue in root.findall(".//RLUEx"):
        code_cubf = ue.findtext("RL0105A")
        logements_str =_
