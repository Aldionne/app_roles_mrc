import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import re
from collections import defaultdict

st.set_page_config(layout="wide")
st.title("🔍 Analyse des rôles d’évaluation foncière du Québec par codes CUBF")

# ---------- Chargement de la liste des MRC et liens XML ----------
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
            return pd.DataFrame()

        records.extend(data["records"])
        if len(data["records"]) < limit:
            break
        offset += limit

    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()
    return df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "MRC", "lien": "URL"}).sort_values("MRC")


# ---------- Lecture et extraction XML ----------
def parse_xml_to_df(xml_bytes):
    def parse_int(text):
        try:
            if text is None:
                return 0
            cleaned = re.sub(r"[^\d.]", "", text.replace(",", "."))
            return int(float(cleaned)) if cleaned else 0
        except:
            return 0

    def parse_float(text):
        try:
            if text is None:
                return 0.0
            cleaned = re.sub(r"[^\d.]", "", text.replace(",", "."))
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0

    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse XML : {e}")
        return pd.DataFrame()

    rows = []
    for elem in root.iter():
        cubf_elem = elem.find("RL0105A")
        if cubf_elem is not None:
            row = {
                "RL0105A": cubf_elem.text.strip() if cubf_elem.text else "Inconnu",
                "RL0311A": parse_int(elem.findtext("RL0311A")),
                "RL0315A": parse_float(elem.findtext("RL0315A")),
                "RL0316A": parse_float(elem.findtext("RL0316A")),
                "RLM02A": elem.findtext("RLM02A", "Inconnue").strip()
            }
            rows.append(row)

    return pd.DataFrame(rows)


# ---------- Interface Streamlit ----------
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
    st.write(f"🔢 **Nombre total d’unités d’évaluation dans le fichier** : {len(df_xml)}")
    annee_roles = df_xml["RLM02A"].dropna().unique()
    st.markdown(f"📆 **Année du rôle d’évaluation :** {', '.join(annee_roles)}")

    st.subheader("🎯 Sélection des codes CUBF")

    codes_cubf = sorted(df_xml["RL0105A"].dropna().unique())

    grouped = defaultdict(list)
    for code in codes_cubf:
        try:
            code_int = int(code)
            if 1000 <= code_int <= 9999:
                millier = (code_int // 1000) * 1000
            else:
                millier = "Hors-plage"
        except:
            millier = "Inconnu"
        grouped[millier].append(code)

    with st.form("form_cubf"):
        select_all = st.checkbox("✅ Tout sélectionner", key="select_all")
        selected_codes = []

        for millier in sorted(grouped.keys()):
            with st.expander(f"{millier}–{millier + 999}" if isinstance(millier, int) else f"{millier}"):
                cols = st.columns(4)
                for idx, code in enumerate(sorted(grouped[millier])):
                    col = cols[idx % 4]
                    if select_all or col.checkbox(code, key=f"code_{code}"):
                        selected_codes.append(code)

        submitted = st.form_submit_button("📊 Analyser les codes sélectionnés")

    if submitted:
        if selected_codes:
            df_filtre = df_xml[df_xml["RL0105A"].isin(selected_codes)]

            total_batiments = len(df_filtre)
            total_logements = df_filtre["RL0311A"].sum()
            moyenne_terrain = df_filtre["RL0315A"].mean()
            moyenne_immeuble = df_filtre["RL0316A"].mean()

            st.markdown("### ✅ Résultats")
            st.write(f"- **Nombre total d’unités d’évaluation sélectionnées** : {total_batiments}")
            st.write(f"- **Nombre total de logements** : {total_logements}")
            st.write(f"- **Valeur moyenne des terrains** : {moyenne_terrain:,.0f} $")
            st.write(f"- **Valeur moyenne des immeubles** : {moyenne_immeuble:,.0f} $")

            df_resume = (
                df_filtre.groupby("RL0105A")
                .agg(
                    nb_unites=("RL0105A", "count"),
                    nb_logements=("RL0311A", "sum"),
                    val_moy_terrain=("RL0315A", "mean"),
                    val_moy_immeuble=("RL0316A", "mean")
                )
                .reset_index()
                .rename(columns={"RL0105A": "Code CUBF"})
                .sort_values("Code CUBF")
            )

            st.dataframe(df_resume)

            with st.expander("📄 Voir toutes les entrées filtrées"):
                st.dataframe(df_filtre)

        else:
            st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")
else:
    st.info("📄 Aucune donnée chargée. Cliquez sur le bouton ci-dessus pour analyser le fichier XML.")
