import pandas as pd
import plotly.express as px
import streamlit as st
import numpy as np

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(
    page_title="LogiTrack - Suivi GPS & Chocs", 
    page_icon="🌍", 
    layout="wide"
)

# ==========================================
# 1. SYSTÈME DE CONNEXION
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Espace Sécurisé LogiTrack")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter"):
            utilisateurs = {"test": "0000", "hugo": "1234"}
            if username in utilisateurs and password == utilisateurs[username]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
    st.stop()

# ==========================================
# 2. MENU LATÉRAL
# ==========================================
st.sidebar.title("🚀 Contrôle LogiTrack")
seuil_choc = st.sidebar.slider("⚡ Seuil d'alerte Choc (G)", 1.0, 8.0, 2.0, 0.1)
seuil_angle = st.sidebar.slider("📐 Seuil Renversement (°)", 30, 180, 60, 5)

uploaded_file = st.sidebar.file_uploader("📥 Importer LOG.CSV", type="csv")

if st.sidebar.button("🚪 Se déconnecter"):
    st.session_state['logged_in'] = False
    st.rerun()

# ==========================================
# 3. TRAITEMENT DES DONNÉES
# ==========================================
if uploaded_file is not None:
    # Ordre des colonnes (doit matcher ton code Arduino)
    COLONNES = [
        'Heure', 'Lat', 'Lon', 'Alt', 'Temp', 'Pression', 
        'Hum', 'Gaz', 'AccX', 'AccY', 'AccZ', 'GyrX', 'GyrY', 'GyrZ'
    ]
    
    try:
        df = pd.read_csv(uploaded_file, names=COLONNES)

        # Calculs physiques
        df['G_Total'] = np.sqrt(df['AccX']**2 + df['AccY']**2 + df['AccZ']**2)
        df['Angle'] = np.degrees(np.arccos(np.clip(df['AccZ'] / (df['G_Total'] + 1e-6), -1.0, 1.0)))

        st.title("📊 Analyse du Trajet")
        
        # Indicateurs rapides
        k1, k2, k3 = st.columns(3)
        k1.metric("Chocs détectés", len(df[df['G_Total'] > seuil_choc]))
        k2.metric("Temp. Max", f"{df['Temp'].max():.1f} °C")
        k3.metric("Altitude Max", f"{df['Alt'].max():.0f} m")

        # Onglets
        tab1, tab2, tab3 = st.tabs(["🗺️ Carte GPS", "💥 Chocs", "🌡️ Environnement"])

        with tab1:
            df_map = df[(df['Lat'] != 0) & (df['Lon'] != 0)].rename(columns={'Lat': 'lat', 'Lon': 'lon'})
            if not df_map.empty:
                st.map(df_map)
                st.plotly_chart(px.line(df_map, x='Heure', y='Alt', title="Profil d'altitude (m)"))
            else:
                st.warning("📍 Aucune donnée GPS valide.")

        with tab2:
            st.plotly_chart(px.line(df, x='Heure', y='G_Total', title="Forces G"))
            st.plotly_chart(px.line(df, x='Heure', y='Angle', title="Inclinaison (°)"))

        with tab3:
            st.plotly_chart(px.line(df, x='Heure', y=['Temp', 'Hum'], title="Météo"))

    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
else:
    st.title("📦 LogiTrack")
    st.info("Importez un fichier CSV pour voir la carte et les analyses.")
