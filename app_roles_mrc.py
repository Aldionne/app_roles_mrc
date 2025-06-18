import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import requests
from io import BytesIO

st.title("Analyse des rôles d’évaluation foncière du Québec selon codes CUBF")

# Liste des MRC disponibles
mrc_data = pd.read_csv("mrc_roles.csv")  # suppose un fichier local avec les MRC et URL XML

selected_mrc = st.selectbox("Sélectionnez une MRC", mrc_data["nom du territoire"])

if selected_mrc:
    url = mrc_data.loc[mrc_data["nom du territoire"] == selected_mrc, "lien"].values[0]
    
    try:
        response = requests.get(url)
        tree = ET.parse(BytesIO(response.content))
        root = tree.getroot()

        data = []
        for batiment in root.findall(".//RL0101Gx"):
            cubf = batiment.findtext("RL0105A", default="")  # code CUBF
            logements = batiment.findtext("RL0311A", default="0")  # nb de logements

            # Ajout d'un enregistrement
            data.append({
                "RL0105A": cubf,
                "RL0311A": int(logements) if logements.isdigit() else 0
            })

        df = pd.DataFrame(data)

        codes_cubf_disponibles = sorted(df["RL0105A"].unique())
        codes_selectionnes = st.multiselect("Codes CUBF à inclure", codes_cubf_disponibles, default=codes_cubf_disponibles)

        if codes_selectionnes:
            df_filtre = df[df["RL0105A"].isin(codes_selectionnes)]

            st.write("Nombre total de bâtiments :", len(df_filtre))
            st.write("Nombre total de logements :", df_filtre["RL0311A"].sum())
            st.dataframe(df_filtre)
        else:
            st.info("ℹ️ Veuillez sélectionner au moins un code CUBF.")

    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier XML : {e}")
