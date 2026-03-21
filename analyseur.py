import pandas as pd
import plotly.express as px
import streamlit as st
import numpy as np
import json
import os
import requests

# ==========================================
# 0. CONFIGURATION & CLÉ API
# ==========================================
st.set_page_config(page_title="LogiTrack - Dashboard Expert", page_icon="📦", layout="wide")

# TA CLÉ API GOOGLE OPÉRATIONNELLE :
GOOGLE_API_KEY = "AIzaSyAmJaTrwAV4ahAjO5pCTG-YWI-pWWyrQLE" 

# ==========================================
# 1. GESTION DES ESPACES (JSON)
# ==========================================
FICHIER_JSON = "espaces_logitrack.json"

def charger_espaces():
    if os.path.exists(FICHIER_JSON):
        try:
            with open(FICHIER_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def sauvegarder_espace(nom):
    espaces = charger_espaces()
    if nom not in espaces:
        espaces.append(nom)
        with open(FICHIER_JSON, 'w', encoding='utf-8') as f:
            json.dump(espaces, f)

# ==========================================
# 2. FONCTION GÉOLOCALISATION WIFI (GOOGLE)
# ==========================================
def geolocaliser_wifi(mac_raw):
    """Interroge Google pour transformer une adresse MAC en Lat/Lon"""
    if not mac_raw or "00:00:00" in str(mac_raw) or mac_raw == "0.0":
        return None, None
    
    mac_clean = str(mac_raw).replace("MAC_", "")
    url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={GOOGLE_API_KEY}"
    payload = {"considerIp": "false", "wifiAccessPoints": [{"macAddress": mac_clean}]}
    
    try:
        r = requests.post(url, json=payload, timeout=5)
        res = r.json()
        if 'location' in res:
            return res['location']['lat'], res['location']['lng']
    except:
        return None, None
    return None, None

# ==========================================
# 3. LOGIN & NAVIGATION
# ==========================================
if 'logged_in' not in st.session_state: 
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Accès Sécurisé LogiTrack")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        if u == "test" and p == "0000":
            st.session_state['logged_in'] = True
            st.rerun()
    st.stop()

espaces = charger_espaces()
st.sidebar.title("📦 Mes Trajets")
espace_choisi = st.sidebar.radio("Choisir un trajet :", espaces) if espaces else None

with st.sidebar.expander("➕ Créer un espace"):
    n_esp = st.text_input("Nom du module")
    if st.button("Ajouter") and n_esp:
        sauvegarder_espace(n_esp)
        st.rerun()

st.sidebar.markdown("---")
seuil_choc = st.sidebar.number_input("⚡ Seuil de choc (G)", 0.5, 10.0, 1.5, step=0.1)

if st.sidebar.button("🚪 Déconnexion"):
    st.session_state['logged_in'] = False
    st.rerun()

# ==========================================
# 4. TRAITEMENT DES DONNÉES
# ==========================================
if espace_choisi:
    st.title(f"📊 Analyse : {espace_choisi}")
    f_csv = f"donnees_{espace_choisi}.csv"
    
    if os.path.exists(f_csv):
        df = pd.read_csv(f_csv)
        if st.sidebar.button("🗑️ Vider l'espace"):
            os.remove(f_csv)
            st.rerun()
    else:
        uploaded = st.file_uploader("📥 Importer LOG.CSV", type="csv")
        if uploaded:
            cols = ['Heure','Temp','Pression','Hum','Gaz','AccX','AccY','AccZ','GyroX','GyroY','GyroZ','Lat','Lon','Alt','Sat']
            df = pd.read_csv(uploaded, names=cols, header=None)
            df.to_csv(f_csv, index=False)
            st.rerun()
        else: st.stop()

    # --- CALCULS ---
    df['G'] = (df['AccX']**2 + df['AccY']**2 + df['AccZ']**2)**0.5
    # Inclinaison
    df['Angle'] = np.degrees(np.arccos(np.clip(df['AccZ'] / (df['G'] + 1e-6), -1.0, 1.0)))
    
    is_wifi = df['Lat'].astype(str).str.contains('MAC_', na=False)
    chocs = df[df['G'] > seuil_choc]
    renversements = df[df['Angle'] > 60]

    # --- PRÉPARATION CARTE ---
    points_map = []
    df_gps = df[~is_wifi].copy()
    df_gps['Lat'] = pd.to_numeric(df_gps['Lat'], errors='coerce')
    df_gps['Lon'] = pd.to_numeric(df_gps['Lon'], errors='coerce')
    
    for _, row in df_gps.dropna(subset=['Lat', 'Lon']).iterrows():
        if row['Lat'] != 0:
            points_map.append({'Heure': row['Heure'], 'Lat': row['Lat'], 'Lon': row['Lon'], 'Type': 'GPS (Extérieur)'})

    df_wifi = df[is_wifi].copy()
    if not df_wifi.empty:
        with st.spinner("🌍 Localisation WiFi via Google..."):
            macs_uniques = df_wifi['Lat'].unique()
            cache_geo = {m: geolocaliser_wifi(m) for m in macs_uniques}
            for _, row in df_wifi.iterrows():
                lat_w, lon_w = cache_geo.get(row['Lat'], (None, None))
                if lat_w:
                    points_map.append({'Heure': row['Heure'], 'Lat': lat_w, 'Lon': lon_w, 'Type': 'WiFi (Intérieur)'})

    # --- AFFICHAGE ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temp. Moy", f"{df['Temp'].mean():.1f}°C")
    c2.metric("Chocs Violents", len(chocs))
    c3.metric("Zones WiFi", len(df_wifi))
    try:
        df['t'] = pd.to_datetime(df['Heure'], format='%H:%M:%S')
        delta = df['t'].iloc[-1] - df['t'].iloc[0]
        if delta.total_seconds() < 0: delta += pd.Timedelta(days=1)
        c4.metric("Durée", f"{delta.total_seconds()/60:.1f} min")
    except: c4.metric("Durée", "N/A")

    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Carte", "📈 Graphiques", "⚠️ Alertes", "📄 Données Brutes"])
    
    with tab1:
        if points_map:
            df_map = pd.DataFrame(points_map).sort_values('Heure')
            fig = px.line_mapbox(df_map, lat="Lat", lon="Lon", color="Type", zoom=13, height=600)
            fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Aucune donnée de localisation.")

    with tab2:
        st.plotly_chart(px.line(df, x='Heure', y='G', title="Force G"), use_container_width=True)
        st.plotly_chart(px.line(df, x='Heure', y=['Temp', 'Hum'], title="Environnement"), use_container_width=True)
        st.plotly_chart(px.line(df, x='Heure', y='Angle', title="Inclinaison (0°=Droit)"), use_container_width=True)

    with tab3:
        st.subheader("Journal des incidents critiques")
        if not chocs.empty:
            st.warning(f"💥 {len(chocs)} impacts détectés au-dessus de {seuil_choc}G")
            st.dataframe(chocs[['Heure', 'G', 'Temp', 'Lat', 'Lon']], use_container_width=True)
        if not renversements.empty:
            st.error(f"🔄 {len(renversements)} moments de basculement détectés (>60°)")
            st.dataframe(renversements[['Heure', 'Angle', 'G']], use_container_width=True)
        if chocs.empty and renversements.empty:
            st.success("✅ Aucun incident majeur à signaler sur ce trajet.")

    with tab4:
        st.subheader("Journal de bord complet")
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Télécharger CSV", df.to_csv(index=False), f"LogiTrack_{espace_choisi}.csv")
