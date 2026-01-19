import requests
import re
import json
import time

# --- AYARLAR ---
BASE_DOMAIN = "https://vidsrc-embed.ru"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{BASE_DOMAIN}/",
    "Origin": BASE_DOMAIN,
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

# --- İÇERİK LİSTESİ ---
# Buraya eklemek istediğin film ve dizileri yazarsın.
# type: 'movie' veya 'tv'
# seasons: Sadece 'tv' ise kaç sezon/bölüm tarayacağını belirtirsin.
CONTENT_LIST = [
    {
        "id": "tt0944947", 
        "name": "Game of Thrones", 
        "type": "tv", 
        "image": "https://image.tmdb.org/t/p/w500/1XS1oqL89opfnbGw83TrgnpKoAT.jpg",
        "seasons": [
            {"season_num": 1, "episode_count": 10}, # 1. Sezon 10 bölüm
            # {"season_num": 2, "episode_count": 10} # İstersen diğer sezonları böyle ekle
        ]
    },
    {
        "id": "tt5433140", 
        "name": "Hızlı ve Öfkeli 10", 
        "type": "movie",
        "image": "https://image.tmdb.org/t/p/w500/fiVW06jE7z9YnO4trhaMEdclSiC.jpg"
    }
]

def get_m3u8_link(url):
    """Verilen URL'e gider ve kaynak kodunda .m3u8 linkini arar."""
    try:
        # Referer header'ını dinamik olarak o anki URL yapıyoruz
        current_headers = HEADERS.copy()
        current_headers["Referer"] = url
        
        print(f"--> Taranıyor: {url}")
        response = requests.get(url, headers=current_headers, timeout=10)
        
        if response.status_code == 200:
            # Regex 1: Doğrudan .m3u8 linki
            match = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', response.text)
            if match:
                return match.group(1)
            
            # Regex 2: "file": "..." yapısı (Playerjs formatı)
            match_file = re.search(r'file:\s*["\'](https?://[^"\']+\.m3u8)["\']', response.text)
            if match_file:
                return match_file.group(1)
                
    except Exception as e:
        print(f"Hata: {e}")
    return None

def main():
    playlist_data = []
    m3u_content = "#EXTM3U\n"

    for item in CONTENT_LIST:
        imdb_id = item["id"]
        name = item["name"]
        poster = item.get("image", "")

        if item["type"] == "movie":
            # Film URL Yapısı: https://vidsrc-embed.ru/embed/movie/{id}
            target_url = f"{BASE_DOMAIN}/embed/movie/{imdb_id}"
            m3u8 = get_m3u8_link(target_url)
            
            if m3u8:
                print(f"✅ BULUNDU: {name}")
                playlist_data.append({"name": name, "url": m3u8, "image": poster, "group": "Filmler"})
                m3u_content += f'#EXTINF:-1 group-title="Filmler" tvg-logo="{poster}",{name}\n{m3u8}\n'
            else:
                print(f"❌ BULUNAMADI: {name}")
            
            time.sleep(1.5) # Anti-spam beklemesi

        elif item["type"] == "tv":
            # Dizi URL Yapısı: https://vidsrc-embed.ru/embed/tv/{id}/{season}/{episode}
            for season in item["seasons"]:
                s_num = season["season_num"]
                e_count = season["episode_count"]
                
                for ep_num in range(1, e_count + 1):
                    episode_name = f"{name} S{s_num:02d}E{ep_num:02d}"
                    target_url = f"{BASE_DOMAIN}/embed/tv/{imdb_id}/{s_num}/{ep_num}"
                    
                    m3u8 = get_m3u8_link(target_url)
                    
                    if m3u8:
                        print(f"✅ BULUNDU: {episode_name}")
                        playlist_data.append({"name": episode_name, "url": m3u8, "image": poster, "group": name})
                        m3u_content += f'#EXTINF:-1 group-title="{name}" tvg-logo="{poster}",{episode_name}\n{m3u8}\n'
                    else:
                        print(f"❌ BULUNAMADI: {episode_name}")
                    
                    time.sleep(1.5)

    # Dosyaları Kaydet
    with open("playlist.json", "w", encoding="utf-8") as f:
        json.dump(playlist_data, f, ensure_ascii=False, indent=4)
        
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print("\n🎉 İşlem Bitti! playlist.json ve playlist.m3u güncellendi.")

if __name__ == "__main__":
    main()
