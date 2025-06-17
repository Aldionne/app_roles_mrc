import streamlit as st
import pandas as pd
import requests
import zipfile
import io

# Titre de l'application
st.title("🔍 Explorer les rôles d’évaluation foncière du Québec")

# Fonction pour aller chercher les MRC et leurs liens via l’API de Données Québec
@st.cache_data
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
        records.extend(data["records"])
        if len(data["records"]) < limit:
            break
        offset += limit

    df = pd.DataFrame(records)
    df = df[["title", "url"]].rename(columns={"title": "MRC", "url": "URL"})
    df = df.sort_values("MRC").reset_index(drop=True)
    return df

# Charger les liens
mrc_links = fetch_mrc_roles()

# Sélection de la MRC
selected_mrc = st.selectbox("Choisissez une MRC", mrc_links["MRC"])

# Affichage du lien de téléchargement
selected_url = mrc_links.loc[mrc_links["MRC"] == selected_mrc, "URL"].values[0]
st.markdown(f"📥 [Télécharger le rôle d’évaluation de {selected_mrc}]({selected_url})")

# Option de traitement du fichier zip (optionnelle)
if st.button("Analyser le contenu du fichier ZIP"):
    st.info("Téléchargement et lecture du fichier en cours...")
    try:
        response = requests.get(selected_url)
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            txt_files = [f for f in zip_file.namelist() if f.endswith(".txt")]
            st.success(f"{len(txt_files)} fichier(s) texte trouvé(s) dans l’archive :")
            for f in txt_files:
                st.write(f)

            if txt_files:
                with zip_file.open(txt_files[0]) as file:
                    df = pd.read_csv(file, sep="|", encoding="latin1", dtype=str, nrows=1000)
                    st.dataframe(df.head(20))

    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")
