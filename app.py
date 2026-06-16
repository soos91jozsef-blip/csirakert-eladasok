import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

# --- Oldal beállítások ---
st.set_page_config(page_title="CsíraKert Eladások", page_icon="🌱", layout="wide")

# --- Google Sheets hitelesítés (mezőnként a Secrets-ből) ---
spreadsheet_id = st.secrets["SPREADSHEET_ID"]

service_account_info = {
    "type": st.secrets["TYPE"],
    "project_id": st.secrets["PROJECT_ID"],
    "private_key_id": st.secrets["PRIVATE_KEY_ID"],
    "private_key": st.secrets["PRIVATE_KEY"],
    "client_email": st.secrets["CLIENT_EMAIL"],
    "client_id": st.secrets["CLIENT_ID"],
    "auth_uri": st.secrets["AUTH_URI"],
    "token_uri": st.secrets["TOKEN_URI"],
    "auth_provider_x509_cert_url": st.secrets["AUTH_PROVIDER_X509_CERT_URL"],
    "client_x509_cert_url": st.secrets["CLIENT_X509_CERT_URL"],
    "universe_domain": st.secrets["UNIVERSE_DOMAIN"]
}

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(spreadsheet_id).sheet1

# --- Segédfüggvény a táblázat egyszeri feltöltéséhez ---
def init_sheet():
    """Létrehozza a fejlécet és a 10 évnyi heteket 2026-tól."""
    sheet.clear()
    header = ['Év', 'Hét_száma', 'Hétfő_dátuma', 'Szombat_dátuma', 'Eladott_mennyiség', 'Bevétel']
    sheet.append_row(header)

    kezdo_ev = 2026
    eveks = 10
    aktualis_datum = date(kezdo_ev, 1, 1)
    while aktualis_datum.weekday() != 0:   # első hétfő
        aktualis_datum = aktualis_datum - timedelta(days=1)

    veg_datum = date(kezdo_ev + eveks, 1, 1)
    while aktualis_datum < veg_datum:
        ev = aktualis_datum.isocalendar()[0]
        het_szama = aktualis_datum.isocalendar()[1]
        hetfo = aktualis_datum
        szombat = hetfo + timedelta(days=5)
        if ev < kezdo_ev + eveks:
            sor = [ev, het_szama, str(hetfo), str(szombat), '', '']
            sheet.append_row(sor)
        aktualis_datum = aktualis_datum + timedelta(days=7)

# --- Ellenőrizzük, hogy a táblázat üres-e (csak fejléc van) ---
all_values = sheet.get_all_values()
if len(all_values) <= 1:
    st.sidebar.warning("⚠️ A táblázat még nincs feltöltve hetekkel!")
    if st.sidebar.button("📅 Táblázat előkészítése (10 év hetei)"):
        init_sheet()
        st.sidebar.success("✅ A táblázat sikeresen fel lett töltve 2026-2035 heteivel. Frissítsd az oldalt!")
        st.stop()

# --- Adatok betöltése és gyorsítótárazása ---
@st.cache_data(ttl=60)
def load_data():
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    df['Szombat_dátuma'] = pd.to_datetime(df['Szombat_dátuma'])
    df['Hétfő_dátuma'] = pd.to_datetime(df['Hétfő_dátuma'])
    df['Eladott_mennyiség'] = pd.to_numeric(df['Eladott_mennyiség'], errors='coerce').fillna(0)
    df['Bevétel'] = pd.to_numeric(df['Bevétel'], errors='coerce').fillna(0)
    return df

df = load_data()

# --- Fő felület ---
st.title("🌱 CsíraKert Értékesítési Statisztika")
st.markdown("Minden szombaton aratás, a diagram a heti eladott mennyiségeket mutatja.")

evek = sorted(df['Év'].unique(), reverse=True)
valasztott_ev = st.selectbox("Válassz évet", evek)

df_ev = df[df['Év'] == valasztott_ev].copy()

st.subheader(f"Heti eladások {valasztott_ev}-ben")
fig = px.bar(df_ev, x='Hét_száma', y='Eladott_mennyiség',
             labels={'Hét_száma': 'Hét', 'Eladott_mennyiség': 'Eladott mennyiség'},
             color_discrete_sequence=['#2E8B57'],
             text='Eladott_mennyiség')
fig.update_xaxes(tickmode='linear', dtick=1)
fig.update_traces(texttemplate='%{text}', textposition='outside')
st.plotly_chart(fig, use_container_width=True)

if st.checkbox("Mutasd havi bontásban"):
    df_ev['Hónap'] = df_ev['Szombat_dátuma'].dt.to_period('M')
    havi_df = df_ev.groupby('Hónap')['Eladott_mennyiség'].sum().reset_index()
    havi_df['Hónap'] = havi_df['Hónap'].astype(str)
    fig2 = px.bar(havi_df, x='Hónap', y='Eladott_mennyiség',
                  labels={'Hónap': 'Hónap', 'Eladott_mennyiség': 'Eladott mennyiség'},
                  color_discrete_sequence=['#8B4513'])
    st.plotly_chart(fig2, use_container_width=True)

# --- Adatbevitel oldalsáv ---
st.sidebar.header("📝 Adatok bevitele")
st.sidebar.info("Válassz ki egy szombatot, add meg az eladott mennyiséget, és mentsd el.")
with st.sidebar.form("entry_form"):
    bevitel_datum = st.date_input("Szombat dátuma", date.today())
    if bevitel_datum.weekday() != 5:
        st.warning("⚠️ Csak szombati napot válassz!")
    else:
        ev_bevitel = bevitel_datum.isocalendar()[0]
        het_bevitel = bevitel_datum.isocalendar()[1]
        st.success(f"{ev_bevitel}. év, {het_bevitel}. hét szombatja")

    mennyiseg = st.number_input("Eladott mennyiség", min_value=0.0, step=0.5)
    submitted = st.form_submit_button("💾 Mentés")

    if submitted:
        if bevitel_datum.weekday() != 5:
            st.sidebar.error("Csak szombatot választhatsz!")
        else:
            ev = bevitel_datum.isocalendar()[0]
            het = bevitel_datum.isocalendar()[1]
            cell = df[(df['Év'] == ev) & (df['Hét_száma'] == het)]
            if not cell.empty:
                row_index = cell.index[0] + 2
                sheet.update_cell(row_index, 5, mennyiseg)
                st.sidebar.success("✅ Adatok elmentve! Az oldal frissítése után látszódni fog a diagramon.")
                load_data.clear()
            else:
                st.sidebar.error("❌ Nincs ilyen hét a táblázatban. Először készítsd elő a táblázatot!")

with st.expander("📋 Nyers adatok táblázata"):
    st.dataframe(df_ev)
