import requests

# --- CONFIGURATION ---
SHORT_LIVED_TOKEN = "THAANCkA39sTlBUVRRX2trak1US2x1Um9LWmtwbEtWeDBZAWjA1VXE5ZAzA4V3BMdEtpVHhpcHVhVmhUb3ZA1MGNUcWNLMTY4ZA2VQbUZAEY0N4eERTOVRTRWphZAjF5Ry1GZAEtUb1l4d0JGODF3Vng0Q01CVHhvYkgtZAWZA0c29oeHVXM0tXWjNCOEpiWVprVkNHRklMdG9JLUFhalUxYXBKaVFfZATd0dloZD"
CLIENT_SECRET = "3951e957aab7a37f4b0b626f71ca7cd9"


def get_long_lived_token():
    url = "https://graph.threads.net/access_token"

    params = {
        "grant_type": "th_exchange_token",
        "client_secret": CLIENT_SECRET,
        "access_token": SHORT_LIVED_TOKEN,
    }

    print("Échange du token en cours...")
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        print("\n✅ SUCCÈS ! Voici votre Token Longue Durée (60 jours) :")
        print("-" * 20)
        print(data.get("access_token"))
        print("-" * 20)
        print(
            "Copiez ce nouveau token et remplacez l'ancien dans votre script de publication."
        )
    else:
        print("\n❌ Erreur :", response.text)


if __name__ == "__main__":
    get_long_lived_token()
