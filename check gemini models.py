from google import genai
from dotenv import load_dotenv
import os

load_dotenv()
# Configura la chiave
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def list_models():
    print(f"--- Modelli Disponibili (SDK google-genai v1.0) ---\n")
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Recupera tutti i modelli
        # Nota: La paginazione è gestita automaticamente dall'iteratore
        for model in client.models.list():
            
            # Filtro rapido: Mostriamo solo i modelli "Gemini" (ignoriamo i vecchi PaLM o embedding)
            if "gemini" in model.name.lower():
                print(f"ID: {model.name}")
                print(f" > Nome: {model.display_name}")
                print("-" * 30)

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    list_models()