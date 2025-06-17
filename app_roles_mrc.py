import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import io

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
    """🔎 Parse le XML en DataFrame — inclut maintenant outils de débogage."""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"❌ Impossible d'analyser le XML : {e}")
        return pd.DataFrame()

    # DEBUG : Affiche les premiers caractères du fichier XML brut
    st.subheader("🛠️ Aperçu brut du XML")
    st.code(xml_bytes[:1000], language="xml")

    rows = []

    # ⚠️ Adapte ce nom à la vraie structure du XML si besoin (ex: 'donnee', 'record')
    for ligne in root.findall(".//ligne"):
        code_cubf = ligne.findtext("RL0105A")
        logements_str = ligne.findtext("RL0311A")
        
        try:
            logements = int(logements_str) if logements_str else 0
        except:
            logements = 0

        if code_cubf is not None:
            rows.append({
                "RL0105A": code_cubf.strip(),
                "RL0311A": logements
            })

    df = pd.DataFrame(rows)

    # DEBUG : Affiche un aperçu des données extraites
    st.subheader("📊 Aperçu des données extraites du XML")
    st.write(f"Nombre total d’enregistrements extraits : {len(df)}")
    if not df.empty:
        st.dataframe(df.head())
    else:
        st.warning("❌ Aucune ligne valide extraite : vérifie les balises ou la structure XML.")
    
    return df

# Récupère les liens vers les rôles d’évaluation
mrc_links = fetch_mrc_roles()

if not mrc_links.empty:
    selected_mrc = st.selectbox("Choisissez une MRC", mrc_links["MRC"])
    selected_url = mrc_links.loc[mrc_links["MRC"] == selected_mrc, "URL"].values[0]
    st.markdown(f"📥 [Télécharger le rôle d’évaluation de {selected_mrc}]({selected_url})")

    if st.button("📂 Charger et analyser le fichier XML"):
        try:
            with st.spinner("Téléchargement et analyse du fichier XML en cours..."):
                response = requests.get(selected_url)
                response.raise_for_status()

                df_xml = parse_xml_to_df(response.content)

                if df_xml.empty:
                    st.warning("⚠️ Aucune donnée valide trouvée dans le fichier XML. Essaie avec une autre MRC ou vérifie la structure XML.")
                else:
                    codes_cubf = sorted(df_xml["RL0105A"].unique())
                    selected_codes = st.multiselect("Sélectionnez les codes CUBF à analyser", options=codes_cubf)

                    if selected_codes:
                        df_filtre = df_xml[df_xml["RL0105A"].isin(selected_codes)]

                        nb_batiments = len(df_filtre)
                        nb_logements = df_filtre["RL0311A"].sum()

                        st.markdown("### ✅ Résultats pour les codes CUBF sélectionnés :")
                        st.write(f"- **Nombre de bâtiments** : {nb_batiments}")
                        st.write(f"- **Nombre de logements** : {nb_logements}")

                        st.dataframe(df_filtre)
                    else:
                        st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")
        except Exception as e:
            st.error(f"❌ Erreur lors de l’analyse du fichier : {e}")
else:
    st.warning("❌ Impossible de récupérer la liste des MRC. Veuillez réessayer plus tard.")
