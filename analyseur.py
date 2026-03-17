import pandas as pd
import plotly.express as px
import streamlit as st
import numpy as np
import os

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(
    page_title="LogiTrack - Suivi GPS & Chocs", 
    page_icon="🌍", 
    layout="wide"
)

# Style CSS pour améliorer l'apparence
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_exists=True)

# ==========================================
# 1. SYSTÈME DE CONNEXION
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Espace Sécurisé LogiTrack")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("Veuillez vous connecter pour accéder aux données de transport.")
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter"):
            # Liste des utilisateurs autorisés
            utilisateurs = {"test": "0000", "hugo": "1234"}
            if username in utilisateurs and password == utilisateurs[username]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
    st.stop()

# ==========================================
# 2. MENU LATÉRAL & IMPORTATION
# ==========================================
st.sidebar.title("🚀 Contrôle LogiTrack")
st.sidebar.markdown("---")

# Paramètres d'analyse
seuil_choc = st.sidebar.slider("⚡ Seuil d'alerte Choc (G)", 1.0, 8.0, 2.0, 0.1)
seuil_angle = st.sidebar.slider("📐 Seuil Renversement (°)", 30, 180, 60, 5)

st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader("📥 Importer le fichier LOG.CSV de la carte SD", type="csv")

if st.sidebar.button("🚪 Se déconnecter"):
    st.session_state['logged_in'] = False
    st.rerun()

# ==========================================
# 3. TRAITEMENT DES DONNÉES
# ==========================================
if uploaded_file is not None:
    # Ordre des colonnes défini dans le code Arduino
    COLONNES = [
        'Heure', 'Lat', 'Lon', 'Alt', 'Temp', 'Pression', 
        'Hum', 'Gaz', 'AccX', 'AccY', 'AccZ', 'GyrX', 'GyrY', 'GyrZ'
    ]
    
    try:
        # Lecture du CSV
        df = pd.read_csv(uploaded_file, names=COLONNES)

        # --- CALCULS PHYSIQUES ---
        # Accélération résultante (Norme du vecteur)
        df['G_Total'] = np.sqrt(df['AccX']**2 + df['AccY']**2 + df['AccZ']**2)
        
        # Angle d'inclinaison par rapport à la verticale (Z)
        df['Angle'] = np.degrees(np.arccos(np.clip(df['AccZ'] / (df['G_Total'] + 1e-6), -1.0, 1.0)))

        # --- INDICATEURS CLÉS (KPI) ---
        st.title("📊 Analyse du Trajet")
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        chocs_count = len(df[df['G_Total'] > seuil_choc])
        renversements = len(df[df['Angle'] > seuil_angle])
        
        kpi1.metric("Chocs Violents", f"{chocs_count}", delta=None, delta_color="inverse")
        kpi2.metric("Alertes Angle", f"{renversements}", delta=None, delta_color="inverse")
        kpi3.metric("Temp. Max", f"{df['Temp'].max():.1f} °C")
        kpi4.metric("Altitude Max", f"{df['Alt'].max():.0f} m")

        # --- ONGLETS D'AFFICHAGE ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "🗺️ Suivi GPS", 
            "💥 Mouvements & Chocs", 
            "🌡️ Environnement", 
            "📋 Journal des Alertes"
        ])

        # ONGLET 1 : CARTE GPS
        with tab1:
            st.subheader("Parcours du module")
            # Nettoyage des points GPS invalides (souvent 0.0 au démarrage)
            df_map = df[(df['Lat'] != 0) & (df['Lon'] != 0)].copy()
            df_map = df_map.rename(columns={'Lat': 'lat', 'Lon': 'lon'})
            
            if not df_map.empty:
                # Affichage de la carte Streamlit
                st.map(df_map, zoom=12)
                
                # Profil d'altitude
                st.subheader("Profil d'altitude")
                fig_alt = px.area(df_map, x='Heure', y='Alt', title="Variation d'altitude (m)", color_discrete_sequence=['#3498db'])
                st.plotly_chart(fig_alt, use_container_width=True)
            else:
                st.warning("📍 Aucune coordonnée GPS valide détectée. Vérifiez que le module était à l'extérieur.")

        # ONGLET 2 : CHOCS ET MOUVEMENTS
        with tab2:
            st.subheader("Analyse des forces et inclinaison")
            col_a, col_b = st.columns(2)
            
            with col_a:
                fig_g = px.line(df, x='Heure', y='G_Total', title="Force G Totale")
                fig_g.add_hline(y=seuil_choc, line_dash="dash", line_color="red", annotation_text="Seuil Alerte")
                st.plotly_chart(fig_g, use_container_width=True)
            
            with col_b:
                fig_ang = px.line(df, x='Heure', y='Angle', title="Angle d'inclinaison (°)")
                fig_ang.add_hline(y=seuil_angle, line_dash="dot", line_color="orange")
                st.plotly_chart(fig_ang, use_container_width=True)

        # ONGLET 3 : ENVIRONNEMENT
        with tab3:
            st.subheader("Données atmosphériques")
            fig_env = px.line(df, x='Heure', y=['Temp', 'Hum'], title="Température (°C) et Humidité (%)")
            st.plotly_chart(fig_env, use_container_width=True)
            
            fig_gaz = px.line(df, x='Heure', y='Gaz', title="Qualité de l'air (Indice Gaz)")
            st.plotly_chart(fig_gaz, use_container_width=True)

        # ONGLET 4 : JOURNAL DES ALERTES
        with tab4:
            st.subheader("Liste des incidents critiques")
            alertes = df[(df['G_Total'] > seuil_choc) | (df['Angle'] > seuil_angle)]
            
            if not alertes.empty:
                st.warning(f"Attention : {len(alertes)} points dépassent les seuils de sécurité.")
                st.dataframe(alertes[['Heure', 'Lat', 'Lon', 'G_Total', 'Angle', 'Temp']], use_container_width=True)
                
                # Bouton d'export des alertes
                csv = alertes.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Télécharger le rapport d'incidents", data=csv, file_name="alertes_transport.csv", mime="text/csv")
            else:
                st.success("✅ Aucun incident détecté sur ce trajet.")

    except Exception as e:
        st.error(f"Erreur lors de l'analyse du fichier : {e}")
        st.info("Vérifiez que le format du fichier CSV correspond bien au code Arduino.")

else:
    # Page d'accueil quand aucun fichier n'est chargé
    st.title("📦 Bienvenue sur LogiTrack")
    st.info("Veuillez importer un fichier **LOG.CSV** depuis le menu latéral pour commencer l'analyse.")
    
    # Image illustrative ou guide
    st.markdown("""
    ### Comment ça marche ?
    1. Récupérez la carte SD de votre module **Starter-X**.
    2. Insérez-la dans votre ordinateur.
    3. Importez le fichier via le menu à gauche.
    4. Visualisez le trajet, les chocs et les conditions environnementales.
    """)
