import pandas as pd
import plotly.express as px
import streamlit as st
import numpy as np
import json
import os

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(page_title="LogiTrack - Analyse Pro", page_icon="📦", layout="wide")

# ==========================================
# 0. FONCTIONS DE SAUVEGARDE (JSON)
# ==========================================
FICHIER_ESPACES = "espaces_logitrack.json"

def charger_espaces():
    if os.path.exists(FICHIER_ESPACES):
        with open(FICHIER_ESPACES, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def sauvegarder_espace(nom):
    espaces = charger_espaces()
    if nom not in espaces:
        espaces.append(nom)
        with open(FICHIER_ESPACES, 'w', encoding='utf-8') as f:
            json.dump(espaces, f)

# ==========================================
# 1. SYSTÈME DE CONNEXION (LOGIN)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Espace Sécurisé LogiTrack")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("Veuillez vous connecter pour accéder au tableau de bord.")
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter"):
            if username == "test" and password == "0000":
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
    st.stop()

# ==========================================
# 2. MENU LATÉRAL : ESPACES & RÉGLAGES
# ==========================================
espaces_existants = charger_espaces()

st.sidebar.title("📦 Mes Espaces")

if not espaces_existants:
    st.sidebar.info("Aucun espace n'a été créé.")
    espace_choisi = None
else:
    espace_choisi = st.sidebar.radio("Sélectionnez le trajet à analyser :", espaces_existants)

st.sidebar.markdown("---")

with st.sidebar.expander("➕ Créer un nouvel espace"):
    nouvel_espace = st.text_input("Nom du module")
    if st.button("Créer"):
        if nouvel_espace and nouvel_espace.strip() != "":
            sauvegarder_espace(nouvel_espace)
            st.success(f"Espace '{nouvel_espace}' créé !")
            st.rerun()

st.sidebar.markdown("---")

st.sidebar.subheader("⚙️ Paramètres d'analyse")
seuil_choc = st.sidebar.number_input("⚡ Seuil de choc violent (G)", min_value=0.5, max_value=10.0, value=1.5, step=0.1)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Se déconnecter"):
    st.session_state['logged_in'] = False
    st.rerun()

# ==========================================
# 3. VERROUILLAGE SI AUCUN ESPACE CHOISI
# ==========================================
if espace_choisi is None:
    st.title("👋 Bienvenue sur LogiTrack")
    st.warning("👈 Veuillez d'abord créer un espace de suivi dans le menu de gauche.")
    st.stop()

# ==========================================
# 4. TABLEAU DE BORD (GESTION DES FICHIERS)
# ==========================================
st.title(f"📊 Analyse des données : {espace_choisi}")

fichier_sauvegarde = f"donnees_{espace_choisi}.csv"
df = None 

# ETAPE A : Les données existent déjà
if os.path.exists(fichier_sauvegarde):
    st.success(f"📂 Données du module '{espace_choisi}' chargées.")
    df = pd.read_csv(fichier_sauvegarde) 
    
    if st.button("🗑️ Vider cet espace et importer un nouveau trajet"):
        os.remove(fichier_sauvegarde)
        st.rerun()

# ETAPE B : Importer des données
else:
    st.info("Aucune donnée pour ce module. Veuillez importer le fichier CSV généré par l'Arduino.")
    uploaded_file = st.file_uploader("📥 Glissez le fichier CSV du boîtier ici", type="csv", key=espace_choisi)

    if uploaded_file:
        columns = [
            'Heure', 'Temp', 'Pression', 'Hum', 'Gaz', 
            'AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ', 
            'Lat', 'Lon', 'Alt', 'Satellites'
        ]
        df_brut = pd.read_csv(uploaded_file, names=columns)
        df_brut.to_csv(fichier_sauvegarde, index=False)
        st.rerun() 

# ==========================================
# 5. AFFICHAGE DES GRAPHIQUES ET ANALYSES
# ==========================================
if df is not None:
    # --- FILTRAGE WIFI VS GPS ---
    # On identifie les lignes qui contiennent des adresses MAC (WiFi)
    mask_wifi = df['Lat'].astype(str).str.contains('MAC_', na=False)
    df_wifi = df[mask_wifi].copy()
    df_gps = df[~mask_wifi].copy()

    # --- NETTOYAGE ET CONVERSION NUMÉRIQUE (Uniquement pour le GPS) ---
    df_gps['Lat'] = pd.to_numeric(df_gps['Lat'], errors='coerce')
    df_gps['Lon'] = pd.to_numeric(df_gps['Lon'], errors='coerce')
    df_gps['Alt'] = pd.to_numeric(df_gps['Alt'], errors='coerce')

    # --- CALCUL DE LA DURÉE RÉELLE (Basé sur le RTC) ---
    try:
        df['temp_time'] = pd.to_datetime(df['Heure'], format='%H:%M:%S')
        debut = df['temp_time'].iloc[0]
        fin = df['temp_time'].iloc[-1]
        delta = fin - debut
        if delta.total_seconds() < 0: delta += pd.Timedelta(days=1)
        affichage_duree = f"{delta.total_seconds() / 60:.1f} min"
    except:
        affichage_duree = "Format Heure Invalide"

    # --- CALCULS PHYSIQUES ---
    df['Acceleration_Totale'] = (df['AccX']**2 + df['AccY']**2 + df['AccZ']**2)**0.5
    df['Angle_Inclinaison'] = np.degrees(np.arccos(np.clip(df['AccZ'] / (df['Acceleration_Totale'] + 1e-6), -1.0, 1.0)))
    df['Etat_Renversement'] = (df['Angle_Inclinaison'] > 60).astype(int)

    # --- FILTRAGES POUR LES ALERTES ---
    chocs = df[df['Acceleration_Totale'] > seuil_choc]
    renversements = df[df['Etat_Renversement'] == 1]

    # --- INDICATEURS CLÉS (KPI) ---
    st.markdown("### 🎯 Résumé du trajet")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temp. Moyenne", f"{round(df['Temp'].mean(), 1)} °C")
    col2.metric(f"Chocs Violents (>{seuil_choc}G)", len(chocs), delta_color="inverse")
    col3.metric("Points WiFi (Entrepôt)", len(df_wifi))
    col4.metric("Durée Enregistrée", affichage_duree)

    st.markdown("---")

    # --- ONGLETS GRAPHIQUES ---
    tab0, tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Carte GPS", "💥 Mouvements & Chocs", "🌡️ Environnement", "⚠️ Journal des Alertes", "🗄️ Données Brutes"])

    with tab0:
        st.subheader("Tracé du parcours (GPS)")
        # On n'affiche que les points GPS valides et non nuls
        df_map = df_gps.dropna(subset=['Lat', 'Lon'])
        df_map = df_map[(df_map['Lat'] != 0.0)]
        
        if not df_map.empty:
            fig_trajet = px.line_mapbox(df_map, lat="Lat", lon="Lon", zoom=12, height=500)
            fig_trajet.update_traces(line=dict(width=4, color='blue'))
            fig_trajet.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":40,"l":0,"b":0})
            st.plotly_chart(fig_trajet, use_container_width=True)
            
            st.subheader("Profil d'Altitude")
            fig_alt = px.area(df_map, x='Heure', y='Alt', title="Altitude (mètres)")
            st.plotly_chart(fig_alt, use_container_width=True)
        else:
            st.warning("📡 Aucun signal GPS. Le colis est actuellement localisé via WiFi (Mode Intérieur).")
            if not df_wifi.empty:
                st.info(f"Dernière borne WiFi détectée : {df_wifi['Lat'].iloc[-1]}")

    with tab1:
        st.subheader("Analyse des Accélérations (Force G)")
        fig_acc = px.line(df, x='Heure', y='Acceleration_Totale', title="Force G Globale")
        fig_acc.add_hline(y=seuil_choc, line_dash="dash", line_color="red")
        st.plotly_chart(fig_acc, use_container_width=True)
        st.plotly_chart(px.line(df, x='Heure', y='Angle_Inclinaison', title="Angle d'inclinaison (°)"), use_container_width=True)

    with tab2:
        st.subheader("Conditions Ambiantes")
        st.plotly_chart(px.line(df, x='Heure', y=['Temp', 'Hum'], title="Température et Humidité"), use_container_width=True)
        st.plotly_chart(px.line(df, x='Heure', y='Pression', title="Pression Atmosphérique"), use_container_width=True)

    with tab3:
        st.subheader("Détail des incidents")
        if not chocs.empty:
            st.warning(f"⚠️ {len(chocs)} chocs violents détectés.")
            st.dataframe(chocs[['Heure', 'Acceleration_Totale', 'Lat', 'Lon']], use_container_width=True)
        if not renversements.empty:
            st.error(f"❌ Le colis a été renversé {len(renversements)} fois.")
        if chocs.empty and renversements.empty:
            st.success("✅ Aucun incident détecté.")

    with tab4:
        st.subheader("Journal de bord complet")
        st.dataframe(df, use_container_width=True)
        csv_export = df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button("📥 Télécharger CSV (Excel)", csv_export, f"LogiTrack_{espace_choisi}.csv", "text/csv")
