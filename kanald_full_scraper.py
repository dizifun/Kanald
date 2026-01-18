import requests
from bs4 import BeautifulSoup
import json
import re
import os
import urllib3
from tqdm import tqdm

# SSL Uyarılarını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AYARLAR ---
OUTPUT_FOLDER = "KanalD_Arsiv"
BASE_URL = "https://www.kanald.com.tr"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Header (Güncel Chrome Taklidi)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.kanald.com.tr/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}

def clean_text(text):
    if not text: return "Isimsiz"
    text = text.replace("\n", " ").strip()
    return re.sub(r'[<>:"/\\|?*]', '', text)

def create_m3u(category, title, episodes):
    if not episodes:
        return
    
    safe_title = clean_text(title)
    folder_path = os.path.join(OUTPUT_FOLDER, category, safe_title)
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, "playlist.m3u")
    
    print(f"   💾 M3U Oluşturuluyor: {safe_title} ({len(episodes)} Bölüm)")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ep in episodes:
            f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n')
            f.write(f'{ep["stream_url"]}\n')

def extract_stream_url(html_content):
    """HTML içinden m3u8 veya mp4 linkini regex ile çeker."""
    # Yöntem 1: mediaSourcesList JSON yapısı
    patterns = [
        r'mediaSourcesList\.push\(({.*?})\);',
        r'data-media-sources=\'({.*?})\'',
        r'"Hls":{"Path":"(.*?)"}'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        for match in matches:
            if "http" in match and ".m3u8" in match:
                # Basit string temizleme
                if "Path" in match: # JSON ise
                   try:
                       # Bazen regex tam json yakalayamaz, basit parse
                       url = match.split('"Path":"')[1].split('"')[0]
                       return url.replace("\\/", "/")
                   except:
                       pass
                elif match.startswith("http"):
                    return match
    return None

def get_stream_url_from_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        
        # 1. Regex ile ara
        stream = extract_stream_url(r.text)
        if stream: return stream

        # 2. KanalD player yapısı iframe içindeyse (Opsiyonel)
        # iframe_src = soup.find("iframe") ...
        
    except Exception as e:
        print(f"   ❌ URL Hatası: {e}")
    return None

def process_category(category_url, folder_name):
    print(f"\n🚀 Kategori Taranıyor: {folder_name}")
    try:
        r = requests.get(category_url, headers=HEADERS, verify=False)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Kartları bul (CSS Seçicileri güncellendi)
        cards = soup.select(".listing-holder .item, .program-list .item")
        
        if not cards:
            print("   ⚠️ Bu kategoride içerik bulunamadı (CSS değişmiş olabilir).")
            return

        print(f"   Bulunan İçerik Sayısı: {len(cards)}")
        
        # Demo amaçlı sadece ilk 3 diziye bakalım (Hızlı test için, istersen kaldır [:3])
        # Gerçek çalışmada [:3] silinmeli.
        for card in tqdm(cards[:5], desc=folder_name): 
            try:
                a_tag = card.find("a")
                if not a_tag: continue
                
                link = a_tag.get("href")
                full_link = BASE_URL + link if link.startswith("/") else link
                
                title_tag = card.find("h3") or card.find("img")
                title = title_tag.get_text(strip=True) if title_tag else "Bilinmeyen"
                if not title and title_tag and title_tag.name == "img":
                    title = title_tag.get("alt")

                # Şimdi içeriğin bölümlerine gidiyoruz
                # Örnek: /arka-sokaklar -> /arka-sokaklar/bolumler
                episodes_url = full_link + "/bolumler"
                
                r_ep = requests.get(episodes_url, headers=HEADERS, verify=False)
                soup_ep = BeautifulSoup(r_ep.content, "html.parser")
                
                # Bölüm listesi
                ep_items = soup_ep.select(".listing-holder .item")
                valid_episodes = []
                
                # Son 3 bölümü alalım (Hız için)
                for ep_item in ep_items[:3]:
                    ep_a = ep_item.find("a")
                    if not ep_a: continue
                    ep_link = BASE_URL + ep_a.get("href")
                    
                    # Video sayfasına girip m3u8 çek
                    stream_url = get_stream_url_from_page(ep_link)
                    
                    if stream_url:
                        img = ep_item.find("img")
                        img_url = img.get("data-src") or img.get("src") if img else ""
                        ep_name = ep_item.find("h3").get_text(strip=True) if ep_item.find("h3") else "Bolum"
                        
                        valid_episodes.append({
                            "name": ep_name,
                            "stream_url": stream_url,
                            "img": img_url
                        })
                
                if valid_episodes:
                    create_m3u(folder_name, title, valid_episodes)
                    
            except Exception as e:
                # print(f"Hata: {e}")
                continue

    except Exception as e:
        print(f"Genel Hata: {e}")

if __name__ == "__main__":
    # Test için tek bir kategori açtım, çalışırsa diğerlerini açarsın
    process_category("https://www.kanald.com.tr/diziler", "Diziler")
    process_category("https://www.kanald.com.tr/programlar", "Programlar")
