def parse_xml_to_df(xml_bytes):
    import pandas as pd
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)

    rows = []
    # Chaque "ligne" est un enregistrement
    for ligne in root.findall(".//ligne"):
        record = {}
        # On récupère toutes les colonnes visibles dans l'extrait
        for col in ["VERSION", "RLM01A", "RLM02A", "RL0101Gx", "RL0101Ax", "RL0101Ex",
                    "RL0101Fx", "RL0104A", "RL0104B", "RL0104C", "RL0105A",
                    "RL0106A", "RL0107A", "RL0201Gx", "RL0201Hx"]:
            el = ligne.find(col)
            record[col] = el.text.strip() if el is not None and el.text else None
        rows.append(record)

    df = pd.DataFrame(rows)

    # Conversion de colonnes numériques selon besoin, par exemple RL0106A, RL0107A
    for col in ["RL0106A", "RL0107A"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    return df
import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import io

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

def analyze_xml_content(xml_bytes):
    """Analyse le contenu XML et compte logements et bâtiments"""
    root = ET.fromstring(xml_bytes)

    # A adapter selon la structure exacte du XML
    # Exemple hypothétique :
    logements = root.findall(".//logement")
    nb_logements = len(logements)

    batiments = root.findall(".//batiment")
    nb_batiments = len(batiments)

    return nb_logements, nb_batiments

mrc_links = fetch_mrc_roles()

if not mrc_links.empty:
    selected_mrc = st.selectbox("Choisissez une MRC", mrc_links["MRC"])
    selected_url = mrc_links.loc[mrc_links["MRC"] == selected_mrc, "URL"].values[0]
    st.markdown(f"📥 [Télécharger le rôle d’évaluation de {selected_mrc}]({selected_url})")

    if st.button("Analyser le fichier XML"):
        try:
            with st.spinner("Téléchargement et analyse du fichier XML en cours..."):
                response = requests.get(selected_url)
                response.raise_for_status()

                nb_logements, nb_batiments = analyze_xml_content(response.content)

                df_result = pd.DataFrame([{
                    "MRC": selected_mrc,
                    "Nombre de logements": nb_logements,
                    "Nombre de bâtiments": nb_batiments
                }])

                st.dataframe(df_result)

        except Exception as e:
            st.error(f"Erreur lors de l’analyse du fichier : {e}")
else:
    st.warning("Impossible de récupérer la liste des MRC. Veuillez réessayer plus tard.")
