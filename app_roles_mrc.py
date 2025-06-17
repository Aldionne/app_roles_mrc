import streamlit as st
import pandas as pd
import requests
import zipfile
import io
import xml.etree.ElementTree as ET

st.title("🔍 Explorer les rôles d’évaluation foncière du Québec")

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

def analyze_xml_file(file_bytes):
    """Analyse un fichier XML pour compter logements et bâtiments"""
    tree = ET.parse(io.BytesIO(file_bytes))
    root = tree.getroot()

    # Exemple : hypothèse sur la structure XML, à adapter selon la vraie structure

    # Compter les logements
    logements = root.findall(".//logement")  # XPath à adapter
    nb_logements = len(logements)

    # Compter les bâtiments
    batiments = root.findall(".//batiment")  # XPath à adapter
    nb_batiments = len(batiments)

    return nb_logements, nb_batiments

mrc_links = fetch_mrc_roles()

if not mrc_links.empty:
    selected_mrc = st.selectbox("Choisissez une MRC", mrc_links["MRC"])
    selected_url = mrc_links.loc[mrc_links["MRC"] == selected_mrc, "URL"].values[0]
    st.markdown(f"📥 [Télécharger le rôle d’évaluation de {selected_mrc}]({selected_url})")

    if st.button("Analyser le contenu du fichier ZIP (XML)"):
        try:
            with st.spinner("Téléchargement et analyse du fichier en cours..."):
                response = requests.get(selected_url)
                response.raise_for_status()

                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                    xml_files = [f for f in zip_file.namelist() if f.endswith(".xml")]

                    if not xml_files:
                        st.warning("Aucun fichier XML trouvé dans l’archive ZIP.")
                    else:
                        st.success(f"{len(xml_files)} fichier(s) XML trouvé(s) dans l’archive :")
                        for f in xml_files:
                            st.write(f)

                        results = []
                        for xml_file in xml_files:
                            with zip_file.open(xml_file) as file:
                                file_bytes = file.read()
                                nb_logements, nb_batiments = analyze_xml_file(file_bytes)
                                results.append({
                                    "Fichier": xml_file,
                                    "Nombre de logements": nb_logements,
                                    "Nombre de bâtiments": nb_batiments
                                })
                        df_res = pd.DataFrame(results)
                        st.dataframe(df_res)
        except Exception as e:
            st.error(f"Erreur lors de l’analyse du fichier : {e}")

else:
    st.warning("Impossible de récupérer la liste des MRC. Veuillez réessayer plus tard.")
