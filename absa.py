import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time

load_dotenv()

# --- CONFIGURAZIONE ---
TARGET_TRACKS = 30       # Target finale di brani validi
MAX_RETRIES = 3          # Tentativi massimi di riempimento
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
    scope='playlist-modify-public'
))

def get_ai_curation(user_input, energy_mode, exclude_list=[]):
    print(f" > [Gemini] Elaborazione query: '{user_input}'...")
    
    # Gestione esclusioni
    exclusions = ", ".join(exclude_list[-50:])
    avoid_instruction = ""
    if exclude_list:
        avoid_instruction = f"IMPORTANT: Do NOT include these tracks again: {exclusions}."

    conf = types.GenerateContentConfig(
        temperature=1.0, 
        top_p=0.95,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        ],
        response_mime_type="application/json",
    )
    
    sys_prompt = f"""
    ROLE: Expert Music Architect & Sonic Curator.
    TASK: Create a playlist of 35 tracks based on the user's input.
    
    USER INPUT: "{user_input}"
    ENERGY PROFILE: {energy_mode.upper()} (Apply strictly).
    
    INPUT INTERPRETATION LOGIC (CRITICAL):
    A. IF input is a GENRE/MOOD (e.g., "Acid Jazz", "Sad rainy vibe"):
       -> Generate tracks that perfectly fit that description.
       
    B. IF input is a SPECIFIC ARTIST/SONG/ALBUM (e.g., "Cosmo", "Radiohead - OK Computer"):
       -> Treat the input as a "SEED". Generate 25 tracks that are SONICALLY SIMILAR to the seed.
       -> Do NOT just list the artist's own top hits. Find similar artists/vibes from the same scene or sonic landscape.
       -> If input is a specific song, match its tempo, key, and atmosphere.

    CONTEXT: User is building a playlist. {avoid_instruction}
    
    OUTPUT FORMAT:
    Pure JSON list of objects: [{{"artist": "Name", "track": "Title"}}].
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

def search_spotify_uris(tracks_data):
    found_uris = []
    
    print(f" > Verifico {len(tracks_data)} brani su Spotify...")
    
    for item in tracks_data:
        artist = item['artist'].strip()
        track = item['track'].strip()
        
        # Query rilassata per massimizzare i risultati su query difficili
        # Prima prova match esatto, se fallisce cerca stringa generica
        queries_to_try = [
            f"track:{track} artist:{artist}",  # Strict
            f"{track} {artist}"               # Loose
        ]
        
        uri = None
        for q in queries_to_try:
            try:
                res = sp.search(q=q, type='track', limit=1, market=SPOTIFY_MARKET)
                if res['tracks']['items']:
                    uri = res['tracks']['items'][0]['uri']
                    print(f"   [OK] {artist} - {track}")
                    break # Trovato, esce dal loop query
            except:
                pass
        
        if uri:
            found_uris.append(uri)
        # else: print(f"   [--] {artist} - {track}") # Decommenta per debug

    return found_uris

def create_playlist_on_spotify(uri_list, name):
    if not uri_list:
        print("Nessun brano valido trovato.")
        return

    user_id = sp.current_user()['id']
    # Nome playlist pulito
    safe_name = name[:60] + "..." if len(name) > 60 else name
    pl = sp.user_playlist_create(user=user_id, name=f"AI {safe_name}", public=True)
    
    # Batching per limitazioni API (max 100)
    for i in range(0, len(uri_list), 100):
        batch = uri_list[i:i+100]
        sp.playlist_add_items(pl['id'], batch)
        
    print(f"\nSUCCESS! Playlist creata: {pl['external_urls']['spotify']}")

if __name__ == "__main__":
    while True:
        target_input = input("\nInserisci Query (es: 'Daft Punk orchestrali', 'Minimal Techno', 'Sanremo 2002', oppure il nome di un artista o album):\n> ")
        if target_input.lower() == 'exit': break
        
        # Energy opzionale (default a skip se premuto invio)
        energy = input("Energy (high/low/[invio per ignorare]): ").strip() or "neutral"
        
        final_uris = []
        tried_history = []
        attempts = 0
        
        while len(final_uris) < TARGET_TRACKS and attempts < MAX_RETRIES:
            if attempts > 0:
                print(f"   ...Recupero altri brani ({len(final_uris)}/{TARGET_TRACKS})...")
            
            ai_data = get_ai_curation(target_input, energy, exclude_list=tried_history)
            
            if not ai_data:
                attempts += 1
                continue
            
            # Aggiorna storico
            for t in ai_data:
                tried_history.append(f"{t['artist']} - {t['track']}")
            
            # Cerca e aggiungi unici
            new_uris = search_spotify_uris(ai_data)
            for uri in new_uris:
                if uri not in final_uris:
                    final_uris.append(uri)
            
            attempts += 1
            if len(final_uris) < TARGET_TRACKS:
                time.sleep(1)

        create_playlist_on_spotify(final_uris, target_input)