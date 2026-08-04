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

### Pulsante di aggiornamento manuale + orario ultimo aggiornamento
# Nota: lo script non usa cache, quindi ogni rerun (incluso il click su questo bottone)
# riscarica già tutti i dati da Yahoo Finance. st.rerun() forza comunque il rerun in modo
# esplicito e affidabile, invece di contare solo sul comportamento implicito del bottone.

col_refresh, col_timestamp = st.columns([1, 4])
with col_refresh:
    if st.button("🔄 Aggiorna dati"):
        st.rerun()
with col_timestamp:
    st.caption(f"Ultimo aggiornamento: {datetime.now(FUSO_ORARIO_ITALIA).strftime('%d/%m/%Y %H:%M:%S')}")

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


def ottieni_prezzi_quote(ticker):
    """Recupera prezzo attuale e chiusura precedente direttamente dai campi che Yahoo Finance
    usa per calcolare la variazione % mostrata sui siti di borsa (previousClose / currentPrice),
    invece di ricostruirli dallo storico giornaliero. Per alcuni titoli .MI lo storico su finestre
    brevi risultava incompleto (chiusure "raw" mancanti per giorni di borsa realmente aperti),
    facendo confrontare il prezzo attuale con una chiusura di 4-5 giorni prima e gonfiando la
    variazione % calcolata. Usando gli stessi campi diretti di Yahoo evitiamo il problema.
    Ritorna anche l'orario dell'ultimo aggiornamento del prezzo (regularMarketTime): quando un
    mercato è chiuso o non ha ancora aperto "oggi", il prezzo/variazione mostrati si riferiscono
    all'ultima sessione conclusa, non necessariamente alla giornata corrente per quel mercato.
    Ritorna: (oggetto Ticker, dict info, prezzo_attuale, prezzo_precedente, etichetta_fonte, orario_quotazione)."""
    azione = yf.Ticker(ticker)
    try:
        info = azione.info or {}
    except Exception:
        info = {}

    prezzo_corrente = info.get("currentPrice") or info.get("regularMarketPrice")
    prezzo_precedente = info.get("previousClose") or info.get("regularMarketPreviousClose")

    orario_ts = info.get("regularMarketTime")
    orario_quotazione = (
        datetime.fromtimestamp(orario_ts, tz=FUSO_ORARIO_ITALIA) if orario_ts else None
    )

    if prezzo_corrente is not None and prezzo_precedente is not None:
        return (
            azione, info, float(prezzo_corrente), float(prezzo_precedente),
            "quote Yahoo (previousClose)", orario_quotazione
        )

    # Fallback: se i campi diretti non sono disponibili, ricostruiamo dallo storico giornaliero
    try:
        storico = azione.history(period="1mo", auto_adjust=False).dropna(subset=["Close"])
        if len(storico) >= 2:
            return (
                azione, info,
                float(storico["Close"].iloc[-1]), float(storico["Close"].iloc[-2]),
                "storico giornaliero (fallback)", storico.index[-1].to_pydatetime()
            )
    except Exception:
        pass

    return azione, info, None, None, "non disponibile", None


def ottieni_info_dividendi(azione, info, qty, tasso_usd_per_eur, is_usa):
    """Stima la prossima data di stacco dividendo e l'importo atteso per la posizione.
    L'importo è una STIMA basata sul dividendo annuo dichiarato (dividendRate) diviso
    per la frequenza storica dei pagamenti (es. trimestrale, semestrale, annuale).
    Riceve 'azione' (oggetto Ticker) e 'info' (dict) già scaricati da ottieni_prezzi_quote,
    per evitare di richiamare due volte l'API Yahoo per lo stesso titolo."""
    try:
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
dettaglio_debug = []
guadagno_oggi_eur = 0.0
guadagno_sessioni_precedenti_eur = 0.0
titoli_sessione_precedente = []
totale_dividendi_stimati_eur = 0.0
prossima_data_assoluta = None
oggi_italia = datetime.now(FUSO_ORARIO_ITALIA).date()

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
    st.caption(
        "ℹ️ Se un mercato è chiuso o non ha ancora aperto oggi, prezzo e variazione % mostrati "
        "per i suoi titoli si riferiscono all'ultima sessione conclusa (colonna 'Aggiornato al' "
        "nella tabella sotto), non necessariamente alla giornata corrente per quel mercato."
    )

    ### 2. Elabora i titoli in portafoglio

    for azione_item in MIO_PORTAFOGLIO:
        ticker = azione_item["ticker"]
        qty = azione_item["quantita"]

        try:
            azione_obj, info, prezzo_corrente, prezzo_chiusura_ieri, fonte_prezzo, orario_quotazione = (
                ottieni_prezzi_quote(ticker)
            )
        except Exception as errore:
            titoli_falliti.append({"Titolo": ticker, "Motivo": f"Errore di rete/API: {errore}"})
            continue

        if prezzo_corrente is not None and prezzo_chiusura_ieri is not None:

            ### Calcoli della variazione nella valuta originale del titolo

            variazione_unitaria_originale = prezzo_corrente - prezzo_chiusura_ieri
            variazione_percentuale = (variazione_unitaria_originale / prezzo_chiusura_ieri) * 100

            dettaglio_debug.append({
                "Titolo": ticker,
                "Fonte": fonte_prezzo,
                "Chiusura precedente (raw)": round(prezzo_chiusura_ieri, 4),
                "Prezzo attuale (raw)": round(prezzo_corrente, 4),
                "Var. % calcolata": f"{round(variazione_percentuale, 2)}%",
            })

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

            ### Conta il guadagno/perdita nel totale "di oggi" SOLO se la quotazione si riferisce
            ### davvero alla sessione odierna. Se il mercato di quel titolo non ha ancora aperto
            ### oggi, il suo numero riguarda una sessione già conclusa (es. ieri) e sommarlo al
            ### totale odierno significherebbe contare due volte un guadagno già realizzato.

            sessione_e_di_oggi = orario_quotazione is not None and orario_quotazione.date() == oggi_italia

            if sessione_e_di_oggi:
                guadagno_oggi_eur += impatto_giornaliero_eur
            else:
                guadagno_sessioni_precedenti_eur += impatto_giornaliero_eur
                titoli_sessione_precedente.append({
                    "Titolo": ticker,
                    "Var. Giornaliera (€)": f"{round(impatto_giornaliero_eur, 2)} €",
                    "Riferita al": orario_quotazione.strftime("%d/%m/%Y") if orario_quotazione else "N/D"
                })

            stato_mercato = verifica_stato_mercato(ticker)

            dati_totali.append({
                "Stato Mercato": stato_mercato,
                "Titolo": ticker,
                "Quantità": qty,
                "Prezzo Attuale (€)": f"{round(prezzo_corrente_eur, 2)} €",
                "Valore Posizione (€)": f"{round(valore_totale_eur, 2)} €",
                "Var. Giornaliera (€)": f"{round(impatto_giornaliero_eur, 2)} €",
                "Var. %": f"{round(variazione_percentuale, 2)}%",
                "Aggiornato al": orario_quotazione.strftime("%d/%m %H:%M") if orario_quotazione else "N/D"
            })

            ### 3bis. Stima prossimo dividendo per questo titolo

            info_div = ottieni_info_dividendi(azione_obj, info, qty, tasso_usd_per_eur, is_usa)
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
            titoli_falliti.append({
                "Titolo": ticker,
                "Motivo": f"Prezzo attuale e/o chiusura precedente non disponibili "
                          f"(ultima fonte tentata: {fonte_prezzo})."
            })

### 4. Mostra la RISPOSTA SECCA in cima (Tutto convertito coerentemente in Euro)
# Conta solo i mercati che hanno già mosso OGGI: se un mercato non ha ancora aperto,
# il suo numero si riferisce a una sessione già passata e già riflessa nel valore di ieri,
# quindi non va aggiunto qui per evitare di contare due volte lo stesso guadagno.

if guadagno_oggi_eur >= 0:
    st.success(f"### Oggi stai GUADAGNANDO:  +{round(guadagno_oggi_eur, 2)} € rispetto a ieri.")
else:
    st.error(f"### Oggi stai PERDENDO:  {round(guadagno_oggi_eur, 2)} € rispetto a ieri.")

if titoli_sessione_precedente:
    segno = "+" if guadagno_sessioni_precedenti_eur >= 0 else ""
    st.info(
        f"⏳ **{len(titoli_sessione_precedente)} titolo/i non hanno ancora aperto oggi** "
        f"(la loro ultima sessione disponibile vale {segno}{round(guadagno_sessioni_precedenti_eur, 2)} €, "
        f"già riflessi nel valore del portafoglio da quella sessione — non incluso nel numero sopra "
        f"per evitare di contarlo due volte)."
    )
    with st.expander("Titoli in attesa di apertura odierna"):
        st.dataframe(pd.DataFrame(titoli_sessione_precedente), use_container_width=True, hide_index=True)

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

### 8. Debug: date e prezzi "raw" usati per calcolare la variazione %
# Utile per capire se una variazione % sembra "sbagliata": qui si vede esattamente
# quale chiusura precedente e quale prezzo attuale sono stati usati nel calcolo,
# così si può confrontare con quanto mostrato da Borsa Italiana o da altre fonti.

with st.expander("🔍 Debug: prezzi raw usati nel calcolo della variazione %"):
    if dettaglio_debug:
        st.dataframe(pd.DataFrame(dettaglio_debug), use_container_width=True, hide_index=True)
    else:
        st.caption("Nessun dato disponibile.")
