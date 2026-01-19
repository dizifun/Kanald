import json
import os
import time
import concurrent.futures
import requests

# --- AYARLAR ---
API_KEY = "6fabef7bd74e01efcd81d35c39c4a049"
BASE_URL = "https://api.themoviedb.org/3"
VIDMODY_BASE = "https://vidmody.com/vs"
IMG_URL = "https://image.tmdb.org/t/p/w500"

# --- TARAMA AYARLARI ---
# Hangi yıllar arasındaki filmleri çekmek istiyorsun?
START_YEAR = 2020  # Burayı 1990 yaparsan çok daha fazla film gelir
END_YEAR = 2026    # Günümüz

MAX_WORKERS = 20   # Hız

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

os.makedirs("output", exist_ok=True)

def check_single_url(url):
    try:
        response = requests.head(url, headers=HEADERS, timeout=2, allow_redirects=True)
        if response.status_code == 200:
            return url
    except:
        pass
    return None

def batch_check_urls(url_list):
    valid_urls = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_single_url, url): url for url in url_list}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                valid_urls.add(result)
    return valid_urls

def get_imdb_id(tmdb_id):
    try:
        url = f"{BASE_URL}/movie/{tmdb_id}/external_ids?api_key={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        pass
    return None

def save_m3u(filename, content_list):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        # Son Eklenenleri en başa koymak için listeyi ters çevirebiliriz veya olduğu gibi bırakırız
        # Burada "category"ye göre gruplama zaten yapılıyor.
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_year(year, all_movies, m3u_entries):
    """Belirli bir yılın popüler filmlerini çeker"""
    print(f"\n--- {year} YILI TARANIYOR ---")
    
    # Her yıl için ilk 20 sayfayı tarasak yeterli (20 sayfa * 20 film = 400 film/yıl)
    # İstersen buradaki range(1, 21)'i range(1, 51) yapabilirsin.
    for page in range(1, 30): 
        try:
            # Discover API kullanıyoruz (Yıla göre filtreleme için şart)
            url = f"{BASE_URL}/discover/movie?api_key={API_KEY}&language=tr-TR&sort_by=popularity.desc&primary_release_year={year}&page={page}"
            response = requests.get(url)
            
            if response.status_code != 200:
                continue

            results = response.json().get('results', [])
            if not results:
                break

            pending_checks = []
            movie_map = {}

            for item in results:
                imdb_id = get_imdb_id(item['id'])
                if imdb_id:
                    link = f"{VIDMODY_BASE}/{imdb_id}"
                    pending_checks.append(link)
                    movie_map[link] = {
                        "id": imdb_id,
                        "title": item['title'],
                        "poster": f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else "",
                        "year": str(year)
                    }

            if pending_checks:
                active_links = batch_check_urls(pending_checks)
                print(f"   {year} - Sayfa {page}: {len(active_links)} film bulundu.")

                for link in active_links:
                    info = movie_map[link]
                    
                    # Kategori Mantığı:
                    # 2026 ve 2025 filmleri "Son Eklenenler" olsun
                    # Diğerleri "Filmler" olsun
                    category = "Son Eklenenler" if year >= 2025 else "Filmler"

                    all_movies.append({
                        "id": info['id'],
                        "title": info['title'],
                        "poster": info['poster'],
                        "link": link,
                        "category": category
                    })
                    
                    m3u_entries.append({
                        "group": category,
                        "logo": info['poster'],
                        "name": info['title'],
                        "url": link
                    })

        except Exception as e:
            print(f"Hata: {e}")

def main():
    start_time = time.time()
    movies_data = []
    m3u_entries = []

    # Belirlediğimiz yılları geriye doğru tarıyoruz (En yeniler en üstte olsun)
    for year in range(END_YEAR, START_YEAR - 1, -1):
        process_year(year, movies_data, m3u_entries)

    # Dosyaları Kaydet
    print("\n--- Dosyalar Kaydediliyor ---")
    with open("output/movies_all.json", "w", encoding="utf-8") as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
    
    save_m3u("output/movies_all.m3u", m3u_entries)
    print(f"Toplam {len(m3u_entries)} film bulundu.")
    print(f"İşlem Süresi: {int(time.time() - start_time)} saniye.")

if __name__ == "__main__":
    main()
