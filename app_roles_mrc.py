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

    df = pd.DataFrame(rows)
    return df

# Étape principale
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
                    st.warning("⚠️ Aucune donnée valide trouvée dans le fichier XML.")
                else:
                    st.subheader("🎯 Sélection des codes CUBF à analyser")

                    codes_cubf = sorted(df_xml["RL0105A"].dropna().unique())
                    cubf_groups = defaultdict(list)
                    for code in codes_cubf:
                        try:
                            prefix = int(code) // 100 * 100
                        except:
                            prefix = code
                        cubf_groups[prefix].append(code)

                    with st.form("form_cubf"):
                        select_all = st.checkbox("✅ Sélectionner tous les codes CUBF")

                        selected_codes = []
                        for group, codes in sorted(cubf_groups.items()):
                            cols = st.columns(4)
                            for idx, code in enumerate(sorted(codes)):
                                col = cols[idx % len(cols)]
                                if select_all:
                                    checked = True
                                else:
                                    checked = col.checkbox(f"{code}", key=f"code_{code}")
                                if checked:
                                    selected_codes.append(code)

                        submitted = st.form_submit_button("Analyser les codes sélectionnés")

                    if submitted:
                        if selected_codes:
                            df_filtre = df_xml[df_xml["RL0105A"].isin(selected_codes)]
                            nb_total = len(df_filtre)
                            nb_logements = df_filtre["RL0311A"].sum()

                            st.markdown("### ✅ Résultats globaux pour les codes CUBF sélectionnés :")
                            st.write(f"- **Nombre total de bâtiments (entrées)** : {nb_total}")
                            st.write(f"- **Nombre total de logements** : {nb_logements}")

                            st.markdown("### 📌 Détail par code CUBF sélectionné :")
                            resume = df_filtre.groupby("RL0105A").agg(
                                nombre_batiments=("RL0105A", "count"),
                                total_logements=("RL0311A", "sum")
                            ).reset_index().rename(columns={"RL0105A": "Code CUBF"})

                            st.dataframe(resume)

                            with st.expander("🔍 Voir les données filtrées complètes"):
                                st.dataframe(df_filtre)
                        else:
                            st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")
        except Exception as e:
            st.error(f"❌ Erreur lors de l’analyse du fichier : {e}")
else:
    st.warning("❌ Impossible de récupérer la liste des MRC. Veuillez réessayer plus tard.")
