import requests
import json
import os
import re
import time
import concurrent.futures

# --- AYARLAR ---
API_KEY = "6fabef7bd74e01efcd81d35c39c4a049"
BASE_URL = "https://api.themoviedb.org/3"
VIDMODY_BASE = "https://vidmody.com/vs"
IMG_URL = "https://image.tmdb.org/t/p/w500"

MAX_PAGES = 500  # Filmler için sayfa sayısı
MAX_WORKERS = 20 # Hız

# Klasörleri oluştur
os.makedirs("output/filmler", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def check_single_url(url):
    """Tek bir linki kontrol eder"""
    try:
        response = requests.head(url, headers=HEADERS, timeout=2, allow_redirects=True)
        if response.status_code == 200:
            return url
    except:
        pass
    return None

def batch_check_urls(url_list):
    """Paralel link kontrolü"""
    valid_urls = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_single_url, url): url for url in url_list}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                valid_urls.add(result)
    return valid_urls

def get_imdb_id(tmdb_id, media_type):
    try:
        url = f"{BASE_URL}/{media_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        return None
    return None

def save_m3u(filename, content_list):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_movies():
    print(f"--- FİLMLER BAŞLIYOR (Paralel Kontrol: {MAX_WORKERS} Thread) ---")
    movies_data = []
    m3u_entries = []

    for page in range(1, MAX_PAGES + 1):
        print(f"Film Sayfası: {page}/{MAX_PAGES}")
        try:
            url = f"{BASE_URL}/movie/popular?api_key={API_KEY}&language=tr-TR&page={page}"
            data = requests.get(url).json()
            results = data.get('results', [])

            pending_checks = []
            movie_map = {}

            for item in results:
                imdb_id = get_imdb_id(item['id'], 'movie')
                if imdb_id:
                    link = f"{VIDMODY_BASE}/{imdb_id}"
                    pending_checks.append(link)
                    movie_map[link] = {
                        "id": imdb_id,
                        "title": item['title'],
                        "poster": f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""
                    }

            if pending_checks:
                active_links = batch_check_urls(pending_checks)
                print(f"  -> {len(active_links)} / {len(pending_checks)} film çalışıyor.")

                for link in active_links:
                    info = movie_map[link]
                    movies_data.append({
                        "id": info['id'],
                        "title": info['title'],
                        "poster": info['poster'],
                        "link": link
                    })
                    m3u_entries.append({
                        "group": "Filmler",
                        "logo": info['poster'],
                        "name": info['title'],
                        "url": link
                    })

        except Exception as e:
            print(f"Hata (Film Sayfa {page}): {e}")

    # Kayıt işlemleri
    with open("output/movies_all.json", "w", encoding="utf-8") as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
    save_m3u("output/movies_all.m3u", m3u_entries)

if __name__ == "__main__":
    start = time.time()
    process_movies()
    print(f"Filmler Tamamlandı. Süre: {int(time.time() - start)} sn.")
