import pandas as pd
import plotly.express as px
import streamlit as st
import numpy as np
import json
import os

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(page_title="Starter X - Analyse Pro", page_icon="📦", layout="wide")

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
    st.title("🔐 Espace Sécurisé Starter X")
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

# 2.A : Liste cliquable des modules
if not espaces_existants:
    st.sidebar.info("Aucun espace n'a été créé.")
    espace_choisi = None
else:
    espace_choisi = st.sidebar.radio("Sélectionnez le trajet à analyser :", espaces_existants)

st.sidebar.markdown("---")

# 2.B : Création d'un nouvel espace
with st.sidebar.expander("➕ Créer un nouvel espace"):
    nouvel_espace = st.text_input("Nom du module")
    if st.button("Créer"):
        if nouvel_espace and nouvel_espace.strip() != "":
            sauvegarder_espace(nouvel_espace)
            st.success(f"Espace '{nouvel_espace}' créé !")
            st.rerun()

st.sidebar.markdown("---")

# 2.C : Réglage dynamique par l'utilisateur
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
    st.title("👋 Bienvenue sur Starter X Analyse")
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
        columns = ['Heure', 'Temp', 'Pression', 'Hum', 'Gaz', 'AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']
        df_brut = pd.read_csv(uploaded_file, names=columns)
        df_brut.to_csv(fichier_sauvegarde, index=False)
        st.rerun() 

# ==========================================
# 5. AFFICHAGE DES GRAPHIQUES ET ANALYSES
# ==========================================
if df is not None:
    # --- CALCULS PHYSIQUES (CORRIGÉS : Tout est calculé AVANT de filtrer) ---
    
    # 1. Accélération Globale
    df['Acceleration_Totale'] = (df['AccX']**2 + df['AccY']**2 + df['AccZ']**2)**0.5
    
    # 2. Angle d'inclinaison (Ajout d'une protection contre la division par zéro avec + 1e-6)
    df['Angle_Inclinaison'] = np.degrees(np.arccos(np.clip(df['AccZ'] / (df['Acceleration_Totale'] + 1e-6), -1.0, 1.0)))
    
    # 3. État de renversement (Angle > 60 degrés)
    df['Etat_Renversement'] = (df['Angle_Inclinaison'] > 60).astype(int)

    # --- FILTRAGES POUR LES ALERTES ---
    chocs = df[df['Acceleration_Totale'] > seuil_choc]
    renversements = df[df['Etat_Renversement'] == 1]

    # --- INDICATEURS CLÉS (KPI) ---
    st.markdown("### 🎯 Résumé du trajet")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temp. Moyenne", f"{round(df['Temp'].mean(), 1)} °C")
    col2.metric(f"Chocs Violents (>{seuil_choc}G)", len(chocs), delta_color="inverse")
    col3.metric("Instants Renversés (>60°)", len(renversements), delta_color="inverse")
    col4.metric("Durée Enregistrée", f"{len(df)*200/1000/60:.1f} min")

    st.markdown("---")

    # --- ONGLETS GRAPHIQUES ---
    tab1, tab2, tab3, tab4 = st.tabs(["💥 Mouvements & Chocs", "🌡️ Environnement", "⚠️ Journal des Alertes", "🗄️ Données & Export"])

    with tab1:
        st.subheader("Analyse des Accélérations (Chocs)")
        fig_acc = px.line(df, x='Heure', y='Acceleration_Totale', title="Force G Globale ressentie par le colis")
        fig_acc.add_hline(y=seuil_choc, line_dash="dash", line_color="red", annotation_text=f"Seuil ({seuil_choc}G)")
        st.plotly_chart(fig_acc, use_container_width=True)

        st.subheader("Inclinaison du Colis (Angle en degrés)")
        fig_angle = px.line(df, x='Heure', y='Angle_Inclinaison', title="0° = Droit | 90° = Sur le côté | 180° = À l'envers")
        fig_angle.add_hline(y=60, line_dash="dot", line_color="orange", annotation_text="Seuil de Renversement (60°)")
        st.plotly_chart(fig_angle, use_container_width=True)

    with tab2:
        st.subheader("Données atmosphériques (Température & Humidité)")
        fig_env = px.line(df, x='Heure', y=['Temp', 'Hum'], title="Évolution Température (°C) et Humidité (%)")
        st.plotly_chart(fig_env, use_container_width=True)

        st.subheader("Données atmosphériques (Pression & Gaz)")
        fig_pres = px.line(df, x='Heure', y=['Pression', 'Gaz'], title="Évolution Pression et Gaz")
        st.plotly_chart(fig_pres, use_container_width=True)

    with tab3:
        st.subheader("Détail des incidents critiques")
        if not renversements.empty:
            st.error(f"❌ Le colis a été renversé {len(renversements)} fois (Inclinaison > 60°).")
        if not chocs.empty:
            st.warning(f"⚠️ {len(chocs)} chocs violents ont été enregistrés (>{seuil_choc}G).")
            # C'est ici que ça bloquait : maintenant 'Angle_Inclinaison' existe bien dans 'chocs'
            st.dataframe(chocs[['Heure', 'Acceleration_Totale', 'Angle_Inclinaison']], use_container_width=True)
        if renversements.empty and chocs.empty:
            st.success("✅ Aucun incident détecté. Trajet parfait !")

    with tab4:
        st.subheader("Données Brutes")
        st.write("Tableau complet des valeurs enregistrées par le capteur.")
        st.dataframe(df, use_container_width=True)
        
        # Bouton d'export Excel
        csv_export = df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button(
            label="📥 Exporter les données vers Excel (CSV)",
            data=csv_export,
            file_name=f"Export_{espace_choisi}.csv",
            mime="text/csv"
        )