import requests
import json
import os
import sys

# --- KULLANICI BİLGİLERİ ---
EMAIL = "Mr.aykutsen@gmail.com"
PASSWORD = "Aykut01081993.."  # <-- Şifreni tırnak içine yapıştır!

# --- AYARLAR ---
BASE_URL = "https://eu1.tabii.com/apigateway"

# Olası Login Adresleri (Sırayla dener)
LOGIN_URLS_TO_TRY = [
    "https://eu1.tabii.com/apigateway/auth/v1/login",  # En muhtemel adres
    "https://eu1.tabii.com/apigateway/auth/login",
    "https://eu1.tabii.com/auth/v1/login",
    "https://eu1.tabii.com/auth/login"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

def login_and_get_token():
    print("🔑 Giriş deneniyor...")
    payload = {"email": EMAIL, "password": PASSWORD}
    
    for url in LOGIN_URLS_TO_TRY:
        try:
            print(f"URL deneniyor: {url}")
            response = requests.post(url, json=payload, headers=HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("token") or data.get("access_token") or data.get("session", {}).get("token")
                
                if token:
                    print(f"✅ Giriş başarılı! ({url})")
                    return token
            elif response.status_code == 404:
                print(f"❌ Adres bulunamadı (404), bir sonrakine geçiliyor...")
                continue
            else:
                print(f"⚠️ Giriş başarısız. Kod: {response.status_code}, Cevap: {response.text}")
                
        except Exception as e:
            print(f"⚠️ Bağlantı hatası: {e}")
            continue

    print("❌ HATA: Hiçbir login adresi çalışmadı.")
    sys.exit(1)

def get_contents(auth_token):
    print("📡 İçerikler çekiliyor...")
    auth_headers = HEADERS.copy()
    auth_headers["Authorization"] = f"Bearer {auth_token}"
    
    # Genel içerik listesi ID'si (Değişirse burayı güncellemek gerekebilir)
    target_id = "149106_149112"
    api_endpoint = f"{BASE_URL}/pbr/v1/pages/browse/{target_id}"
    
    try:
        response = requests.get(api_endpoint, headers=auth_headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Veri çekilemedi. Kod: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Veri çekme hatası: {e}")
        sys.exit(1)

def generate_files(data, auth_token):
    if not data:
        print("❌ Veri boş!")
        sys.exit(1)

    m3u_content = "#EXTM3U\n"
    json_list = []
    
    items = []
    if "components" in data:
        for comp in data["components"]:
             if "elements" in comp:
                 items.extend(comp["elements"])

    print(f"📄 {len(items)} içerik bulundu. Dosyalar yazılıyor...")

    if len(items) == 0:
        print("⚠️ Liste boş geldi, boş dosya oluşturuluyor.")
        # Hata vermemesi için boş da olsa dosya oluştur
        with open("playlist.m3u", "w") as f: f.write("")
        with open("tabii_data.json", "w") as f: f.write("[]")
        return

    for item in items:
        try:
            media_id = item.get("id")
            title = item.get("title", "Bilinmeyen")
            
            image_url = ""
            if "images" in item and item["images"]:
                image_url = item["images"][0].get("url", "")
                if image_url and not image_url.startswith("http"):
                    image_url = f"https://cms-tabii-assets.tabii.com{image_url}"

            stream_url = f"{BASE_URL}/pbr/v1/media/{media_id}/master.mpd"

            m3u_content += f'#EXTINF:-1 tvg-id="{media_id}" tvg-logo="{image_url}", {title}\n'
            m3u_content += f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n'
            m3u_content += f'#EXTVLCOPT:http-header-authorization=Bearer {auth_token}\n'
            m3u_content += f'{stream_url}\n'

            json_list.append({
                "id": media_id,
                "title": title,
                "thumbnail": image_url,
                "stream_url": stream_url,
                "headers": {"Authorization": f"Bearer {auth_token}"}
            })

        except Exception:
            continue

    with open("playlist.m3u", "w", encoding="utf-8") as f: f.write(m3u_content)
    with open("tabii_data.json", "w", encoding="utf-8") as f: json.dump(json_list, f, indent=4)
    print("✅ Dosyalar hazır!")

if __name__ == "__main__":
    token = login_and_get_token()
    content = get_contents(token)
    generate_files(content, token)
