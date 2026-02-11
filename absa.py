import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google import genai
from google.genai import types # Import necessario per la config
from dotenv import load_dotenv
import os

load_dotenv()
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

def get_ai_curation(user_input, energy_mode="neutral"):
    print(f" > [Gemini] Analisi: '{user_input}' (Mode: {energy_mode})...")
    
    sys_prompt = f"""
    ROLE: Elite Underground Music Curator.
    TASK: Generate a playlist JSON based on user input: "{user_input}".
    CONTEXT: User needs distinct sonic textures.
    ENERGY: {energy_mode.upper()}
    
    CONSTRAINTS:
    1. STRICTLY NO CHART-TOPPING POP.
    2. Focus on "B-sides", deep cuts, underground scenes.
    3. Output 30 tracks.
    4. RESPONSE FORMAT: Pure JSON list of objects [{{"artist": "Name", "track": "Title"}}].
    5. NO markdown, NO text, just the raw JSON string.
    """
    
    try:
        generation_config = genai.types.GenerateContentConfig(
            temperature=1.0,  # Massimo caos creativo (default è circa 0.4 per Flash)
            top_p=0.95,
        )

        # Aggiorna la chiamata
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=sys_prompt,
            config=generation_config
        )
        
        text = response.text
        # Pulizia JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
        
    except Exception as e:
        print(f"Errore AI: {e}")
        return []

def build_playlist(tracks, playlist_name):
    if not tracks: return
    user_id = sp.current_user()['id']
    uri_list = []
    
    print(f" > Ricerca {len(tracks)} tracce su Spotify...")
    
    for item in tracks:
        query = f"track:{item['track']} artist:{item['artist']}"
        try:
            res = sp.search(q=query, type='track', limit=1)
            if res['tracks']['items']:
                uri = res['tracks']['items'][0]['uri']
                uri_list.append(uri)
                print(f"   [OK] {item['artist']} - {item['track']}")
            else:
                print(f"   [--] {item['artist']} - {item['track']}")
        except:
            pass

    if uri_list:
        pl = sp.user_playlist_create(user=user_id, name=f"AI: {playlist_name}", public=True)
        sp.playlist_add_items(pl['id'], uri_list)
        print(f"\nSUCCESS. Playlist creata: {pl['external_urls']['spotify']}")
    else:
        print("\nFAIL. Nessuna traccia trovata.")

if __name__ == "__main__":
    while True:
        target = input("\nInserisci Genere/Artista (o 'exit'): ")
        if target.lower() == 'exit': break
        energy = input("Energy (high/low/skip): ")
        
        data = get_ai_curation(target, energy)
        build_playlist(data, target)