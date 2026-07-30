import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

### Configurazione della pagina

st.set_page_config(page_title="Il mio Portafoglio", layout="wide", page_icon="📈")
st.title("📈 Monitoraggio Portafoglio Azionario (in €)")

### DEFINISCI QUI I TUOI INVESTIMENTI

MIO_PORTAFOGLIO = [
    {"ticker": "ENEL.MI", "quantita": 148}, 
    {"ticker": "ENI.MI", "quantita": 74},  
    {"ticker": "BMPS.MI", "quantita": 160},     
    {"ticker": "ISP.MI", "quantita": 601},
    {"ticker": "PST.MI", "quantita": 162},     
    {"ticker": "DAL", "quantita": 27},
    {"ticker": "PH", "quantita": 3},
    {"ticker": "GD", "quantita": 5},
    {"ticker": "COST", "quantita": 2},
    {"ticker": "PG", "quantita": 8},
    {"ticker": "JPM", "quantita": 14},
    {"ticker": "AIG", "quantita": 27},
    {"ticker": "GOOGL", "quantita": 20},
    {"ticker": "XOM", "quantita": 21},
	{"ticker": "GILD", "quantita": 11},
	{"ticker": "JPM", "quantita": 14},
	{"ticker": "MSFT", "quantita": 8},
	{"ticker": "LLY", "quantita": 3},
    {"ticker": "BABA", "quantita": 5},
	{"ticker": "AMZN", "quantita": 20},
    
]


def verifica_stato_mercato(ticker):
    """Verifica se il mercato di riferimento è aperto o chiuso in base all'ora italiana."""
    ora_attuale = datetime.now().time()
    giorno_settimana = datetime.now().weekday()

    if giorno_settimana >= 5:
        return "🔴 Chiuso (Weekend)"

    if ticker.endswith(".MI"):
        inizio = datetime.strptime("09:00", "%H:%M").time()
        fine = datetime.strptime("17:30", "%H:%M").time()
        return "🟢 Aperto (Live)" if inizio <= ora_attuale <= fine else "🔴 Chiuso"
    else:
        inizio = datetime.strptime("15:30", "%H:%M").time()
        fine = datetime.strptime("22:00", "%H:%M").time()
        return "🟢 Aperto (Live)" if inizio <= ora_attuale <= fine else "🔴 Chiuso"


def ottieni_tasso_cambio_eur_usd():
    """Scarica il tasso di cambio EUR/USD attuale da Yahoo Finance.
    Restituisce quanti Dollari servono per comprare 1 Euro (es. 1.15)."""
    try:
        cambio = yf.Ticker("EURUSD=X")
        storico = cambio.history(period="1d")
        if not storico.empty:
            return storico['Close'].iloc[-1]
        return 1.15  # Valore di backup in caso di errore di connessione
    except:
        return 1.15


dati_totali = []
guadagno_totale_giornaliero_eur = 0.0

st.subheader("Andamento rispetto alla chiusura della sessione precedente")

with st.spinner("Aggiornamento prezzi e tasso di cambio in corso..."):

    ### 1. Recupera il tasso di cambio corrente (es. 1 Euro = 1.15 USD)

    tasso_usd_per_eur = ottieni_tasso_cambio_eur_usd()

    ### Mostra una piccola nota informativa sul tasso di cambio rilevato

    st.caption(f"Tasso di cambio applicato: 1 € = {round(tasso_usd_per_eur, 4)} $")

    ### 2. Elabora i titoli in portafoglio

    for azione in MIO_PORTAFOGLIO:
        ticker = azione["ticker"]
        qty = azione["quantita"]

        info_azione = yf.Ticker(ticker)
        storico = info_azione.history(period="2d")

        if len(storico) >= 2:
            prezzo_chiusura_ieri = storico['Close'].iloc[-2]
            prezzo_corrente = storico['Close'].iloc[-1]

            ### Calcoli della variazione nella valuta originale del titolo

            variazione_unitaria_originale = prezzo_corrente - prezzo_chiusura_ieri
            variazione_percentuale = (variazione_unitaria_originale / prezzo_chiusura_ieri) * 100

            valore_totale_originale = prezzo_corrente * qty
            impatto_giornaliero_originale = variazione_unitaria_originale * qty

            ### 3. CONVERSIONE IN EURO SE IL TITOLO È AMERICANO (NON FINISCE CON .MI)

            is_usa = not ticker.endswith(".MI")

            if is_usa:
                # Se il titolo è in dollari, dividiamo per il tasso di cambio per ottenere gli Euro
                prezzo_corrente_eur = prezzo_corrente / tasso_usd_per_eur
                valore_totale_eur = valore_totale_originale / tasso_usd_per_eur
                impatto_giornaliero_eur = impatto_giornaliero_originale / tasso_usd_per_eur
            else:
                # Se è già in Euro, i valori rimangono invariati
                prezzo_corrente_eur = prezzo_corrente
                valore_totale_eur = valore_totale_originale
                impatto_giornaliero_eur = impatto_giornaliero_originale

            ### Somma il guadagno/perdita convertito al totale del portafoglio

            guadagno_totale_giornaliero_eur += impatto_giornaliero_eur

            stato_mercato = verifica_stato_mercato(ticker)

            dati_totali.append({
                "Stato Mercato": stato_mercato,
                "Titolo": ticker,
                "Quantità": qty,
                "Prezzo Attuale (€)": f"{round(prezzo_corrente_eur, 2)} €",
                "Valore Posizione (€)": f"{round(valore_totale_eur, 2)} €",
                "Var. Giornaliera (€)": f"{round(impatto_giornaliero_eur, 2)} €",
                "Var. %": f"{round(variazione_percentuale, 2)}%"
            })

### 4. Mostra la RISPOSTA SECCA in cima (Tutto convertito coerentemente in Euro)

if guadagno_totale_giornaliero_eur >= 0:
    st.success(f"### Oggi stai GUADAGNANDO:  +{round(guadagno_totale_giornaliero_eur, 2)} € rispetto a ieri.")
else:
    st.error(f"### Oggi stai PERDENDO:  {round(guadagno_totale_giornaliero_eur, 2)} € rispetto a ieri.")

### 5. Mostra la tabella dei dettagli

st.write("### 📊 Dettaglio Titoli nel Portafoglio")
if dati_totali:
    df = pd.DataFrame(dati_totali)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("Non è stato possibile recuperare i dati dei titoli. Verifica i ticker.")