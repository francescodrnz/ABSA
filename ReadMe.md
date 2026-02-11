# AI Music Curator: The Anti-Algo Engine

Tool CLI per la generazione di playlist Spotify basate su analisi semantica e sonora tramite LLM. Progettato per il "crate digging" automatizzato e la scoperta di musica underground, ignorando le logiche commerciali degli algoritmi nativi.

---

### Core Logic
* **Intelligence:** Sfrutta la serie Gemini 3 per associazioni astratte e analisi di sottogeneri oscuri.
* **Anti-Commercial Bias:** Filtra attivamente tracce mainstream/top-40.
* **Energy Cycles Management:** Supporta input specifici adattarsi al mood dell'utente.
    * `High Energy`: Focus, stimolazione, strutture complesse.
    * `Low Energy`: Decompressione, minimalismo, texture costanti.

---

### 1. Prerequisiti
* **Spotify Developer Account:** Registra un'app su [Spotify Dashboard](https://developer.spotify.com/dashboard).
    * `Redirect URI`: `http://127.0.0.1:8080/`
* **Google AI Studio:** Ottieni una API Key su [Google AI Studio](https://aistudio.google.com/).
* **Python 3.10+**

### 2. Installazione
```bash
pip install google-genai spotipy python-dotenv
```

### 3. Setup Credenziali
Crea un file chiamato `.env` nella cartella principale del progetto. Incolla al suo interno le seguenti variabili (senza spazi attorno all'uguale):

SPOTIPY_CLIENT_ID=incolla_qui_il_tuo_client_id
SPOTIPY_CLIENT_SECRET=incolla_qui_il_tuo_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8080/
GEMINI_API_KEY=incolla_qui_la_tua_chiave_AIza...

> **Nota:** Il file `.env` contiene dati sensibili. Non condividerlo mai e assicurati che sia elencato nel tuo `.gitignore`.

### 4. Utilizzo
Esegui lo script da terminale:

python curator.py

**Workflow Operativo:**
1. **Target:** Inserisci un artista, un genere o una descrizione atmosferica (es. *"Dark disco strumentale per programmare"*).
2. **Energy Mode:** - `High`: Seleziona brani con ritmi sostenuti, poliritmi e strutture stimolanti (Focus/Active).
   - `Low`: Seleziona ambient, downtempo e texture ripetitive (Decompression/Rest).
3. **Auth:** Al primo avvio, si aprirà il browser per l'autorizzazione Spotify. Incolla l'URL di redirect nel terminale se richiesto.
4. **Output:** Lo script genererà una playlist (prefisso `AI`) direttamente nel tuo account Spotify.

### Struttura del Progetto
- `curator.py`: Script principale (Logica AI + Integrazione Spotify).
- `.env`: Credenziali private (Escluso dal version control).
- `.gitignore`: File di configurazione per ignorare dati sensibili e cache.
- `.cache`: File generato automaticamente contenente i token di sessione (Da non caricare su GitHub).

### Troubleshooting
- **Errore `Invalid Redirect URI`:** Verifica che l'URI inserito nella Dashboard di Spotify (Settings -> Redirect URIs) sia identico byte-per-byte a quello nel file `.env` (incluso lo slash finale `/`).
- **Errore `400 API Key`:** La chiave Gemini è errata o mal copiata. Rigenerala su Google AI Studio.
- **Errore `Rate Limit Exceeded`:** Hai superato le richieste gratuite al minuto. Attendi 60 secondi o modifica lo script per usare un modello `flash` invece di `pro`.