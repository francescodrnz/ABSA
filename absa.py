import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time
import difflib

load_dotenv()

# --- CONFIGURAZIONE ---
TARGET_TRACKS = 30       # Target finale (usato solo in modalità AI)
MAX_RETRIES = 3          # Tentativi massimi (usato solo in modalità AI)
SPOTIFY_MARKET = 'IT'    # Mercato di riferimento

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, GEMINI_API_KEY]):
    raise ValueError("ERRORE: Credenziali mancanti nel file .env")

# --- SETUP CLIENTS ---
client = genai.Client(api_key=GEMINI_API_KEY)
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope='playlist-modify-public playlist-modify-private playlist-read-private' # Aggiunto read per leggere i duplicati
))

def get_playlist_id_from_link(link):
    """Estrae l'ID puro dal link Spotify."""
    try:
        return link.split("/")[-1].split("?")[0]
    except:
        return None

def get_tracks_from_playlist(playlist_url):
    """Estrae i brani e l'ID della playlist."""
    try:
        playlist_id = get_playlist_id_from_link(playlist_url)
        results = sp.playlist_items(playlist_id, limit=50) # Prendiamo i primi 50 come contesto
        
        tracks_context = []
        for item in results['items']:
            if item['track']:
                artist = item['track']['artists'][0]['name']
                title = item['track']['name']
                tracks_context.append(f"{artist} - {title}")
        
        pl_details = sp.playlist(playlist_id)
        pl_name = pl_details['name']
        
        return pl_name, tracks_context, playlist_id
    except Exception as e:
        print(f"Errore lettura playlist: {e}")
        return None, [], None

def get_existing_uris(playlist_id):
    """Scarica TUTTI gli URI già presenti nella playlist target (gestisce paginazione)."""
    existing_uris = set()
    try:
        print("   (Analisi anti-duplicati in corso...)")
        results = sp.playlist_items(playlist_id, fields="items.track.uri,next")
        items = results['items']
        
        while items:
            for item in items:
                if item.get('track') and item['track'].get('uri'):
                    existing_uris.add(item['track']['uri'])
            
            if results['next']:
                results = sp.next(results)
                items = results['items']
            else:
                items = None
                
        return existing_uris
    except Exception as e:
        print(f"Warning: Impossibile leggere duplicati ({e}). Procedo comunque.")
        return set()

def get_ai_curation(user_input, energy_mode, exclude_list=[], reference_tracks=None):
    print(f" > [Gemini] Elaborazione...")
    
    exclusions = ", ".join(exclude_list[-50:])
    avoid_instruction = ""
    if exclude_list:
        avoid_instruction = f"IMPORTANT: Do NOT include these tracks again: {exclusions}."

    conf = types.GenerateContentConfig(
        temperature=0.9, 
        top_p=0.95,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        ],
        response_mime_type="application/json",
    )
    
    if reference_tracks:
        # Prompt per EXPANSION (Playlist esistente)
        sample_tracks = ", ".join(reference_tracks[:40]) 
        sys_prompt = f"""
        ROLE: Expert Music Curator.
        TASK: Expand an existing playlist with 35 NEW tracks that fit its vibe perfectly.

        SOURCE PLAYLIST SAMPLE:
        [{sample_tracks}]

        ENERGY PROFILE: {energy_mode.upper()}
        USER NOTES: "{user_input if user_input else 'Nessuna - espandi seguendo il vibe naturale della playlist'}"

        ANALYSIS INSTRUCTIONS:
        1. Identify the sonic DNA of the source: genre, era, mood, production style, BPM range.
        2. Find tracks that belong in the same set - a DJ could mix these in seamlessly.
        3. Prioritize artists NOT already in the source playlist.
        4. If USER NOTES are provided, respect them as additional constraints or directions.

        DIVERSITY RULES:
        - Max 1 track per artist already in the source playlist.
        - Max 2 tracks per new artist.
        - Include some deeper cuts, not just obvious choices.

        {avoid_instruction}

        OUTPUT FORMAT: Pure JSON array only, no markdown.
        [{{"artist": "Name", "track": "Title"}}]
        """
    else:
        # Prompt per CREATION (Query testuale)
        sys_prompt = f"""
        ROLE: Expert Music Curator with deep knowledge of global music scenes.
        TASK: Create a playlist of 35 tracks based on user input.

        USER INPUT: "{user_input}"
        ENERGY PROFILE: {energy_mode.upper()}

        INPUT INTERPRETATION (CRITICAL):
        A. GENRE/MOOD (e.g. "Acid Jazz", "sad rainy vibe"):
           -> Generate tracks that perfectly embody that description.
           -> Mix well-known tracks with deeper cuts and hidden gems.

        B. SPECIFIC ARTIST/SONG/ALBUM (e.g. "Radiohead - OK Computer"):
           -> Treat as SEED. Match sonic DNA: tempo, texture, mood, era, production style.
           -> Include the seed track as track #1.
           -> Do NOT just list the artist's discography or their obvious influences.
           -> Explore the full sonic landscape: same scene, same era, unexpected but fitting choices.

        DIVERSITY RULES:
        - Max 2 tracks per artist.
        - Mix eras when appropriate (don't stay stuck in one decade unless the input implies it).
        - Balance: ~40% well-known tracks, ~60% deeper cuts and underrated gems.

        {avoid_instruction}

        OUTPUT FORMAT: Pure JSON array only, no markdown.
        [{{"artist": "Name", "track": "Title"}}]
        """
    
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=sys_prompt,
            config=conf
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Errore AI: {e}")
        return []

def check_similarity(str1, str2):
    """Restituisce un punteggio da 0.0 a 1.0 di similarità tra due stringhe."""
    # Normalizziamo (minuscolo) per evitare problemi di case sensitive
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def search_spotify_uris(tracks_data):
    found_uris = []
    print(f" > Verifico disponibilità di {len(tracks_data)} brani (Modalità STRICT)...")
    
    for item in tracks_data:
        # Gestione robusta keys
        req_artist = item.get('artist', item.get('Artist', '')).strip()
        req_track = item.get('track', item.get('Track', item.get('title', ''))).strip()
        
        if not req_artist or not req_track: continue

        # Troviamo solo con query rigorosa prima
        queries_to_try = [
            f"track:{req_track} artist:{req_artist}", 
            f"{req_track} {req_artist}"
        ]
        
        match_found = False
        
        for q in queries_to_try:
            try:
                res = sp.search(q=q, type='track', limit=1, market=SPOTIFY_MARKET)
                
                if res['tracks']['items']:
                    candidate = res['tracks']['items'][0]
                    
                    # --- FASE DI VERIFICA (THE GUARDRAIL) ---
                    found_artist = candidate['artists'][0]['name']
                    found_track = candidate['name']
                    
                    # Calcoliamo la similarità
                    sim_artist = check_similarity(req_artist, found_artist)
                    sim_track = check_similarity(req_track, found_track)
                    
                    # SOGLIE DI TOLLERANZA:
                    # L'artista deve essere molto simile (> 0.6) o contenuto nella stringa
                    # Il titolo deve essere molto simile (> 0.6)
                    
                    is_artist_valid = sim_artist > 0.6 or req_artist.lower() in found_artist.lower() or found_artist.lower() in req_artist.lower()
                    is_track_valid = sim_track > 0.6 or req_track.lower() in found_track.lower()
                    
                    if is_artist_valid and is_track_valid:
                        uri = candidate['uri']
                        print(f"   [OK] {req_artist} - {req_track}")
                        found_uris.append(uri)
                        match_found = True
                        break # Esci dal loop delle query, abbiamo trovato quello giusto
                    else:
                        # Debug per capire cosa sta scartando (Decommenta se vuoi vedere gli scarti)
                        # print(f"   [X] SCARTATO: Chiesto '{req_artist} - {req_track}' -> Trovato '{found_artist} - {found_track}'")
                        pass
            except Exception as e:
                pass
        
        if not match_found:
             print(f"   [--] {req_artist} - {req_track} (Non trovato o errato)")

    return found_uris

def save_to_spotify(uri_list, name, target_playlist_id=None):
    if not uri_list:
        print("Nessun brano valido trovato.")
        return

    try:
        user_id = sp.current_user()['id']
        playlist_id = target_playlist_id
        
        # Filtro unicità locale (per togliere duplicati generati nello stesso batch)
        unique_uris = list(set(uri_list))

        if not playlist_id:
            # Creazione Nuova
            safe_name = name[:90] + "..." if len(name) > 90 else name
            pl = sp.user_playlist_create(user=user_id, name=f"AI {safe_name}", public=True)
            playlist_id = pl['id']
            print(f"\n[NEW] Creata nuova playlist: {pl['name']}")
        else:
            # Estensione Esistente -> CHECK DUPLICATI REMOTO
            print(f"\n[UPDATE] Controllo duplicati nella playlist ID: {playlist_id}...")
            
            existing_uris = get_existing_uris(playlist_id)
            final_list = []
            duplicates_count = 0
            
            for uri in unique_uris:
                if uri not in existing_uris:
                    final_list.append(uri)
                else:
                    duplicates_count += 1
            
            unique_uris = final_list # Sovrascriviamo la lista con quella pulita
            
            if duplicates_count > 0:
                print(f" > Saltati {duplicates_count} brani già presenti.")
            
            if not unique_uris:
                print(" > Nessun *nuovo* brano da aggiungere.")
                return

        # Aggiunta in batch (max 100)
        for i in range(0, len(unique_uris), 100):
            sp.playlist_add_items(playlist_id, unique_uris[i:i+100])
            
        print(f"SUCCESS! Salvati {len(unique_uris)} brani nuovi.")
        print(f"Link: https://open.spotify.com/playlist/{playlist_id}")

    except Exception as e:
        print(f"\nERRORE SCRITTURA SPOTIFY: {e}")
        print("Nota: Verifica di avere i permessi per modificare questa playlist.")


# --- FUNZIONE DI INPUT INTELLIGENTE ---
def smart_input():
    print("\n" + "="*50)
    print("MODALITÀ DISPONIBILI:")
    print(" 1. Query Testuale (es. 'Techno Detroit')")
    print(" 2. Link Playlist (es. https://open.spotify.com/...)")
    print(" 3. JSON Raw (Incolla pure il blocco multi-riga, basta che inizi con '[')")
    
    try:
        user_in = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        return 'exit'

    if user_in.startswith("["):
        buffer = user_in
        while True:
            try:
                json.loads(buffer)
                print(f" > [System] JSON valido rilevato ({len(buffer)} caratteri).")
                return buffer
            except json.JSONDecodeError:
                try:
                    next_line = input()
                    buffer += " " + next_line
                except (EOFError, KeyboardInterrupt):
                    return buffer 
    
    return user_in

# --- MAIN LOOP ---
if __name__ == "__main__":
    while True:
        target_input = smart_input()
        if target_input.lower() == 'exit': break
        
        # --- MODALITÀ 1: JSON MANUALE ---
        if target_input.startswith("["):
            try:
                manual_data = json.loads(target_input)
                print(f" > Rilevato JSON Manuale con {len(manual_data)} tracce.")
                
                mode = input(" > [N]uova Playlist o [E]stendi esistente? (n/e): ").lower()
                
                target_pl_id = None
                pl_name = "Imported JSON"
                
                if mode == 'e':
                    link = input(" > Incolla Link Playlist Target: ").strip()
                    target_pl_id = get_playlist_id_from_link(link)
                else:
                    pl_name = input(" > Nome della Nuova Playlist: ").strip()

                uris = search_spotify_uris(manual_data)
                save_to_spotify(uris, pl_name, target_pl_id)
                continue 

            except json.JSONDecodeError:
                print("ERRORE: JSON non valido.")
                continue

        # --- SETUP MODALITÀ AI ---
        energy = input("Energy (high/low/[invio per ignorare]): ").strip() or "neutral"
        
        reference_tracks = None
        target_playlist_id = None 
        
        # --- MODALITÀ 2: LINK SPOTIFY ---
        if "spotify.com/playlist" in target_input:
            pl_name, reference_tracks, extracted_id = get_tracks_from_playlist(target_input)
            
            if reference_tracks:
                print(f" > Letta playlist: '{pl_name}' ({len(reference_tracks)} brani).")
                target_input = f"Expansion of: {pl_name}" 
                
                choice = input(f" > Vuoi aggiungere i brani a QUESTA playlist esistente? (s/n): ").lower()
                if choice == 's':
                    target_playlist_id = extracted_id
                else:
                    print(" > OK. Modalità: NEW PLAYLIST.")
            else:
                continue

        # --- MODALITÀ 3: QUERY TESTUALE ---
        final_uris = []
        tried_history = [] 
        
        if reference_tracks:
            tried_history.extend(reference_tracks)

        attempts = 0
        while len(final_uris) < TARGET_TRACKS and attempts < MAX_RETRIES:
            if attempts > 0:
                print(f"   ...Recupero ({len(final_uris)}/{TARGET_TRACKS})...")
            
            ai_data = get_ai_curation(target_input, energy, exclude_list=tried_history, reference_tracks=reference_tracks)
            
            if not ai_data:
                attempts += 1
                continue
            
            for t in ai_data:
                tried_history.append(f"{t['artist']} - {t['track']}")
            
            new_uris = search_spotify_uris(ai_data)
            
            for uri in new_uris:
                if uri not in final_uris:
                    final_uris.append(uri)
            
            attempts += 1
            if len(final_uris) < TARGET_TRACKS:
                time.sleep(1)

        save_to_spotify(final_uris, target_input, target_playlist_id)