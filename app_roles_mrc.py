import streamlit as st 
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

st.set_page_config(layout="wide")
st.title("🔍 Analyse des rôles d’évaluation foncière du Québec par codes CUBF")

# Charger le dictionnaire des CUBF
@st.cache_data
def load_cubf_dict():
    xls = pd.ExcelFile("CUBF_MEFQ (11).xlsx")
    df = pd.read_excel(xls, sheet_name="MAJ2024")
    df = df[df["CUBF"].apply(lambda x: isinstance(x, int) and 1000 <= x <= 9999)]
    df["CUBF_str"] = df["CUBF"].astype(str)
    df["Libelle"] = df["CUBF_str"] + " - " + df["DESCRIPTION"]
    return (
        df.set_index("CUBF_str")["DESCRIPTION"].to_dict(),
        df.set_index("CUBF_str")["Libelle"].to_dict()
    )

dict_cubf, dict_libelle = load_cubf_dict()

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
    return df[["nom du territoire", "lien"]].rename(columns={"nom du territoire": "MRC", "lien": "URL"}).sort_values("MRC")

def parse_xml_to_df(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse XML : {e}")
        return pd.DataFrame()

    rows = []
    for ue in root.findall(".//RLUEx"):
        code_cubf_raw = ue.findtext("RL0105A")
        code_cubf = code_cubf_raw.strip() if code_cubf_raw and code_cubf_raw.strip().isdigit() else "Inconnu"
        logements_str = ue.findtext("RL0311A")
        try:
            logements = int(logements_str) if logements_str and logements_str.isdigit() else 0
        except:
            logements = 0
        rows.append({
            "Code_CUBF": code_cubf,
            "Logements": logements,
            "Libelle": dict_libelle.get(code_cubf, "Inconnu")
        })

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

    codes_cubf = sorted(df_xml["Code_CUBF"].dropna().unique())

    grouped = defaultdict(list)
    for code in codes_cubf:
        try:
            code_int = int(code)
            millier = (code_int // 1000) * 1000
        except:
            millier = "Inconnu"
        grouped[millier].append(code)

    sorted_groupes = sorted([k for k in grouped if isinstance(k, int)]) + ["Inconnu"]

    with st.form("form_cubf"):
        select_all = st.checkbox("✅ Tout sélectionner", key="select_all")
        selected_codes = []

        for millier in sorted_groupes:
            with st.expander(f"{millier}–{millier + 999}" if isinstance(millier, int) else "Codes inconnus"):
                cols = st.columns(2)
                for idx, code in enumerate(sorted(grouped[millier])):
                    col = cols[idx % 2]
                    label = dict_libelle.get(code, f"{code} - Inconnu")
                    if select_all or col.checkbox(label, key=f"code_{code}"):
                        selected_codes.append(code)

        submitted = st.form_submit_button("📊 Analyser les codes sélectionnés")

    if submitted:
        if selected_codes:
            df_filtre = df_xml[df_xml["Code_CUBF"].isin(selected_codes)]
            total_batiments = len(df_filtre)
            total_logements = df_filtre["Logements"].sum()

            st.markdown("### ✅ Résultats")
            st.write(f"- **Nombre total d’unités sélectionnées** : {total_batiments}")
            st.write(f"- **Nombre total de logements** : {total_logements}")

            df_resume = (
                df_filtre.groupby(["Code_CUBF", "Libelle"])
                .agg(nb_batiments=("Code_CUBF", "count"), nb_logements=("Logements", "sum"))
                .reset_index()
            )

            st.dataframe(df_resume)

            with st.expander("🔍 Détails bruts des entrées filtrées"):
                st.dataframe(df_filtre)
        else:
            st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")
else:
    st.info("📄 Aucune donnée chargée. Cliquez sur le bouton ci-dessus pour analyser le fichier XML.")
