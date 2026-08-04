import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

FUSO_ORARIO_ITALIA = ZoneInfo("Europe/Rome")

# Orari di apertura/chiusura dei mercati, in ora italiana (Europe/Rome).
# Definiti una sola volta qui e riusati sia per le "pillole" Aperto/Chiuso
# nella tabella titoli, sia per il riepilogo mercati con il conto alla rovescia.
ORARI_MERCATI = {
    "Borsa Italiana (MTA)": {"suffisso": ".MI", "apertura": dt_time(9, 0), "chiusura": dt_time(17, 30)},
    "USA (NASDAQ / NYSE)": {"suffisso": None, "apertura": dt_time(15, 30), "chiusura": dt_time(22, 0)},
}


def formatta_intervallo(delta):
    """Trasforma un timedelta in una stringa leggibile tipo '3h 35m' o '1g 2h 10m'."""
    secondi_totali = int(delta.total_seconds())
    if secondi_totali < 0:
        secondi_totali = 0
    giorni, resto = divmod(secondi_totali, 86400)
    ore, resto = divmod(resto, 3600)
    minuti, _ = divmod(resto, 60)
    if giorni > 0:
        return f"{giorni}g {ore}h {minuti}m"
    return f"{ore}h {minuti:02d}m"


def calcola_stato_mercato(ora_italia, apertura, chiusura):
    """Dato l'orario attuale (già in fuso Europe/Rome) e gli orari di apertura/chiusura
    di un mercato, restituisce (etichetta_stato, testo_countdown)."""
    apertura_oggi = ora_italia.replace(hour=apertura.hour, minute=apertura.minute, second=0, microsecond=0)
    chiusura_oggi = ora_italia.replace(hour=chiusura.hour, minute=chiusura.minute, second=0, microsecond=0)

    mercato_aperto_oggi = ora_italia.weekday() < 5 and apertura_oggi <= ora_italia <= chiusura_oggi
    if mercato_aperto_oggi:
        return "🟢 Aperto", f"Chiude tra {formatta_intervallo(chiusura_oggi - ora_italia)}"

    # Mercato chiuso: cerca la prossima apertura utile (salta i weekend).
    # NB: non tiene conto delle festività di borsa, solo di sabato/domenica.
    for giorni_da_aggiungere in range(0, 8):
        candidato = ora_italia + timedelta(days=giorni_da_aggiungere)
        candidato_apertura = candidato.replace(hour=apertura.hour, minute=apertura.minute, second=0, microsecond=0)
        if candidato.weekday() < 5 and candidato_apertura > ora_italia:
            etichetta = "🔴 Chiuso (Weekend)" if ora_italia.weekday() >= 5 else "🔴 Chiuso"
            return etichetta, f"Apre tra {formatta_intervallo(candidato_apertura - ora_italia)}"

    return "🔴 Chiuso", "N/D"


def costruisci_tabella_mercati():
    """Costruisce la tabella riassuntiva con lo stato e il countdown di ogni mercato coinvolto."""
    ora_italia = datetime.now(FUSO_ORARIO_ITALIA)
    righe = []
    for nome_mercato, dettagli in ORARI_MERCATI.items():
        stato, countdown = calcola_stato_mercato(ora_italia, dettagli["apertura"], dettagli["chiusura"])
        righe.append({"Mercato": nome_mercato, "Stato": stato, "Countdown": countdown})
    return righe

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
    """Verifica se il mercato di riferimento è aperto o chiuso in base all'ora italiana.
    NB: usiamo esplicitamente il fuso orario Europe/Rome, perché se l'app gira su un
    server ospitato altrove (es. Streamlit Cloud, spesso in UTC), datetime.now() senza
    fuso orario restituirebbe l'ora del server, non quella italiana, falsando il controllo."""
    ora_italia = datetime.now(FUSO_ORARIO_ITALIA)

    if ticker.endswith(".MI"):
        dettagli = ORARI_MERCATI["Borsa Italiana (MTA)"]
    else:
        dettagli = ORARI_MERCATI["USA (NASDAQ / NYSE)"]

    stato, _ = calcola_stato_mercato(ora_italia, dettagli["apertura"], dettagli["chiusura"])
    return f"{stato} (Live)" if stato == "🟢 Aperto" else stato


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


def ottieni_info_dividendi(ticker, qty, tasso_usd_per_eur, is_usa):
    """Stima la prossima data di stacco dividendo e l'importo atteso per la posizione.
    L'importo è una STIMA basata sul dividendo annuo dichiarato (dividendRate) diviso
    per la frequenza storica dei pagamenti (es. trimestrale, semestrale, annuale)."""
    try:
        azione = yf.Ticker(ticker)
        info = azione.info

        ex_div_ts = info.get("exDividendDate")
        dividend_rate = info.get("dividendRate")  # dividendo annuo per azione, valuta originale

        if not dividend_rate:
            return None

        prossima_data = datetime.fromtimestamp(ex_div_ts) if ex_div_ts else None

        # Stima la frequenza dei pagamenti guardando lo storico dell'ultimo anno
        divs = azione.dividends
        frequenza = 1
        if not divs.empty:
            un_anno_fa = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            pagamenti_ultimo_anno = divs[divs.index > un_anno_fa]
            if len(pagamenti_ultimo_anno) > 0:
                frequenza = len(pagamenti_ultimo_anno)

        importo_per_azione = dividend_rate / frequenza
        importo_totale_originale = importo_per_azione * qty
        importo_totale_eur = (
            importo_totale_originale / tasso_usd_per_eur if is_usa else importo_totale_originale
        )

        return {"prossima_data": prossima_data, "importo_eur": importo_totale_eur}
    except Exception:
        return None


dati_totali = []
dati_dividendi = []
titoli_falliti = []
guadagno_totale_giornaliero_eur = 0.0
totale_dividendi_stimati_eur = 0.0
prossima_data_assoluta = None

st.subheader("Andamento rispetto alla chiusura della sessione precedente")

with st.spinner("Aggiornamento prezzi e tasso di cambio in corso..."):

    ### 1. Recupera il tasso di cambio corrente (es. 1 Euro = 1.15 USD)

    tasso_usd_per_eur = ottieni_tasso_cambio_eur_usd()

    ### Mostra una piccola nota informativa sul tasso di cambio rilevato

    st.caption(f"Tasso di cambio applicato: 1 € = {round(tasso_usd_per_eur, 4)} $")

    ### 1bis. Mostra lo stato dei mercati coinvolti con il conto alla rovescia

    st.write("### 🕒 Stato dei Mercati")
    df_mercati = pd.DataFrame(costruisci_tabella_mercati())
    st.dataframe(df_mercati, use_container_width=True, hide_index=True)

    ### 2. Elabora i titoli in portafoglio

    for azione in MIO_PORTAFOGLIO:
        ticker = azione["ticker"]
        qty = azione["quantita"]

        try:
            info_azione = yf.Ticker(ticker)
            # Usiamo una finestra più ampia di "2d": se c'è stato un giorno di festa
            # di borsa (es. in Italia), period="2d" può restituire solo 1 riga (o 0)
            # e il titolo sparirebbe silenziosamente dalla tabella. Con 5 giorni e
            # scartando le righe vuote, prendiamo comunque le ultime due chiusure valide.
            storico = info_azione.history(period="5d").dropna(subset=["Close"])
        except Exception as errore:
            titoli_falliti.append({"Titolo": ticker, "Motivo": f"Errore di rete/API: {errore}"})
            continue

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
                #"Prezzo Attuale (€)": f"{round(prezzo_corrente_eur, 2)} €",
                "Valore Posizione (€)": f"{round(valore_totale_eur, 2)} €",
                "Var. Giornaliera (€)": f"{round(impatto_giornaliero_eur, 2)} €",
                "Var. %": f"{round(variazione_percentuale, 2)}%"
            })

            ### 3bis. Stima prossimo dividendo per questo titolo

            info_div = ottieni_info_dividendi(ticker, qty, tasso_usd_per_eur, is_usa)
            if info_div:
                totale_dividendi_stimati_eur += info_div["importo_eur"]
                if info_div["prossima_data"] and (
                    prossima_data_assoluta is None or info_div["prossima_data"] < prossima_data_assoluta
                ):
                    prossima_data_assoluta = info_div["prossima_data"]

                dati_dividendi.append({
                    "Titolo": ticker,
                    "Prossimo Stacco": (
                        info_div["prossima_data"].strftime("%d/%m/%Y")
                        if info_div["prossima_data"] else "N/D"
                    ),
                    "Importo Stimato (€)": f"{round(info_div['importo_eur'], 2)} €"
                })
        else:
            righe_trovate = len(storico)
            titoli_falliti.append({
                "Titolo": ticker,
                "Motivo": f"Solo {righe_trovate} chiusura/e valida/e trovata/e negli ultimi 5 giorni "
                          f"(possibile festività di borsa o ticker non riconosciuto da Yahoo Finance)."
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

### 6. Mostra la stima dei prossimi dividendi

st.write("---")
st.write("### 💰 Prossimi Dividendi Stimati")

if dati_dividendi:
    if prossima_data_assoluta:
        st.info(
            f"📅 Il prossimo stacco dividendo previsto è il "
            f"**{prossima_data_assoluta.strftime('%d/%m/%Y')}**, e nei prossimi 12 mesi il portafoglio "
            f"dovrebbe incassare circa **{round(totale_dividendi_stimati_eur, 2)} €** di dividendi complessivi "
            f"(stima basata sui dati storici, non garantita)."
        )
    else:
        st.info(
            f"Non è stata trovata una data di stacco precisa per i prossimi dividendi, ma il portafoglio "
            f"dovrebbe incassare circa **{round(totale_dividendi_stimati_eur, 2)} €** nei prossimi 12 mesi "
            f"(stima basata sui dati storici, non garantita)."
        )

    df_div = pd.DataFrame(dati_dividendi).sort_values("Prossimo Stacco")
    st.dataframe(df_div, use_container_width=True, hide_index=True)
    st.caption(
        "⚠️ Le date e gli importi sono stime basate sui dati disponibili su Yahoo Finance "
        "(dividendo annuo dichiarato / frequenza storica dei pagamenti). Possono essere imprecisi "
        "o mancanti, specialmente per i titoli italiani."
    )
else:
    st.caption("Nessuna informazione sui dividendi disponibile per i titoli in portafoglio.")

### 7. Diagnostica: titoli che non è stato possibile caricare

if titoli_falliti:
    with st.expander(f"⚠️ {len(titoli_falliti)} titolo/i non caricato/i correttamente — clicca per i dettagli"):
        st.dataframe(pd.DataFrame(titoli_falliti), use_container_width=True, hide_index=True)
