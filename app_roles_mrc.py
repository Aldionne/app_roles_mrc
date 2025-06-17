import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

def parse_xml_to_df(xml_bytes):
    root = ET.fromstring(xml_bytes)

    rows = []
    for ligne in root.findall(".//ligne"):
        record = {}
        for col in ["VERSION", "RLM01A", "RLM02A", "RL0101Gx", "RL0101Ax", "RL0101Ex",
                    "RL0101Fx", "RL0104A", "RL0104B", "RL0104C", "RL0105A",
                    "RL0106A", "RL0107A", "RL0201Gx", "RL0201Hx", "RL0311A"]:
            el = ligne.find(col)
            record[col] = el.text.strip() if el is not None and el.text else None
        rows.append(record)

    df = pd.DataFrame(rows)

    for col in ["RL0106A", "RL0107A", "RL0311A"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    return df

def main():
    st.title("Exploration des codes CUBF - Rôles d'évaluation")

    uploaded_file = st.file_uploader("Importer un fichier XML des rôles d'évaluation", type=["xml"])

    if uploaded_file is not None:
        try:
            xml_bytes = uploaded_file.read()
            df = parse_xml_to_df(xml_bytes)

            # Extraction des codes CUBF uniques
            codes_cubf = df["RL0105A"].dropna().unique()
            codes_cubf = sorted(codes_cubf)

            selected_codes = st.multiselect(
                "Sélectionnez un ou plusieurs codes CUBF :",
                options=codes_cubf
            )

            if selected_codes:
                df_filtered = df[df["RL0105A"].isin(selected_codes)]

                nombre_batiments = len(df_filtered)
                nombre_logements = df_filtered["RL0311A"].sum()
                annees_role = df_filtered["RLM02A"].dropna().unique()
                annees_role_str = ", ".join(sorted(annees_role))

                st.markdown(f"### Résultats pour les codes sélectionnés")
                st.write(f"**Nombre de bâtiments :** {nombre_batiments}")
                st.write(f"**Nombre total de logements :** {nombre_logements}")
                st.write(f"**Année(s) du rôle disponible :** {annees_role_str}")

            else:
                st.info("Veuillez sélectionner au moins un code CUBF pour voir les résultats.")

        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier XML : {e}")

if __name__ == "__main__":
    main()
