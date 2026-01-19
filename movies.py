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

MAX_WORKERS = 25  # Hız
PAGE_DEPTH_ARCHIVE = 5  # Geçmiş yıllar için her türden kaç sayfa derinliğe inilsin?
PAGE_DEPTH_NEW = 10     # Son eklenenler için kaç sayfa bakılsın? (Daha geniş tuttum)

# Klasör Kontrolü
os.makedirs("output", exist_ok=True)
JSON_FILE = "output/movies_all.json"
M3U_FILE = "output/movies_all.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- KATEGORİ AYARLARI ---
# 1. Vitrin Yılları (Bu yıllardaki popülerler "Son Eklenenler" olur)
NEW_YEARS = [2026, 2025] 

# 2. Arşiv Yılları (Bunlar türlere ayrılır)
ARCHIVE_YEARS = range(2024, 1985, -1)

# 3. Tür Listesi
GENRES = {
    28: "Aksiyon",
    12: "Macera",
    16: "Animasyon",
    35: "Komedi",
    80: "Suç",
    99: "Belgesel",
    18: "Dram",
    10751: "Aile",
    14: "Fantastik",
    27: "Korku",
    9648: "Gizem",
    10749: "Romantik",
    878: "Bilim Kurgu",
    53: "Gerilim",
    10752: "Savaş"
}

def load_existing_data():
    """Eski veriyi yükler"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_ids = {item['id'] for item in data if 'id' in item}
                print(f"--- HAFIZA: {len(data)} film mevcut. ---")
                return data, existing_ids
        except:
            pass
    return [], set()

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
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        pass
    return None

def save_m3u(filename, content_list):
    """M3U Kaydederken 'Son Eklenenler' grubunu en başa koyar"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        
        # Listeyi sıralayalım: Önce "Son Eklenenler", sonra diğerleri
        # Lambda fonksiyonu: Grup adı "Son Eklenenler" ise 0 (en başa), değilse 1 (sonra)
        sorted_list = sorted(content_list, key=lambda x: 0 if x.get("category") == "Son Eklenenler" else 1)
        
        for item in sorted_list:
            group = item.get("category", "Filmler")
            title = item.get("title", "Bilinmeyen")
            f.write(f'#EXTINF:-1 group-title="{group}" tvg-logo="{item.get("poster", "")}", {title}\n')
            f.write(f'{item.get("link", "")}\n')

def process_batch(api_url, category_name, existing_ids, all_movies, add_year_to_title=False):
    """Verilen API URL'sini işler ve listeye ekler"""
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200: return

        results = response.json().get('results', [])
        if not results: return

        pending_checks = []
        movie_map = {}
        
        # Sadece veritabanında OLMAYANLARI al
        unknown_movies = [m for m in results if m['id'] not in existing_ids]

        for item in unknown_movies:
            imdb_id = get_imdb_id(item['id'])
            if imdb_id and imdb_id not in existing_ids: # İkinci kontrol
                link = f"{VIDMODY_BASE}/{imdb_id}"
                pending_checks.append(link)
                
                # Başlık düzeni (İsteğe bağlı yıl ekleme)
                title_text = item['title']
                if add_year_to_title and item.get('release_date'):
                    year_str = item['release_date'].split('-')[0]
                    title_text = f"{title_text} ({year_str})"

                movie_map[link] = {
                    "id": item['id'],
                    "imdb": imdb_id,
                    "title": title_text,
                    "poster": f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else "",
                    "category": category_name
                }

        if pending_checks:
            active_links = batch_check_urls(pending_checks)
            count = 0
            for link in active_links:
                info = movie_map[link]
                if info['id'] not in existing_ids:
                    existing_ids.add(info['id']) # ID'yi kilitle (Başka grup alamasın)
                    all_movies.append({
                        "id": info['id'],
                        "title": info['title'],
                        "poster": info['poster'],
                        "link": link,
                        "category": info['category']
                    })
                    count += 1
            if count > 0:
                print(f"   + {count} film eklendi -> {category_name}")

    except Exception as e:
        print(f"Hata: {e}")

def main():
    start_time = time.time()
    all_movies, existing_ids = load_existing_data()
    
    # --- ADIM 1: SON EKLENENLER (VİTRİN) ---
    # Burası en önemlisi. 2026 ve 2025'in en popülerlerini "Son Eklenenler" yapar.
    # Bu ID'ler kilitlendiği için sonraki aşamalarda tekrar eklenmez.
    print("\n--- ADIM 1: VİTRİN (SON EKLENENLER) ---")
    for year in NEW_YEARS:
        print(f"> {year} Yılı Vitrini Taranıyor...")
        for page in range(1, PAGE_DEPTH_NEW + 1):
            url = f"{BASE_URL}/discover/movie?api_key={API_KEY}&language=tr-TR&sort_by=popularity.desc&primary_release_year={year}&page={page}"
            process_batch(url, "Son Eklenenler", existing_ids, all_movies, add_year_to_title=False)

    # --- ADIM 2: YERLİ FİLMLER (TÜRKİYE) ---
    # Tüm yıllardaki Türk filmlerini "Filmler | Yerli" klasörüne toplar.
    print("\n--- ADIM 2: YERLİ FİLMLER ---")
    for page in range(1, 11): # İlk 10 sayfa yerli film
        url = f"{BASE_URL}/discover/movie?api_key={API_KEY}&language=tr-TR&sort_by=popularity.desc&with_original_language=tr&page={page}"
        process_batch(url, "Filmler | Yerli", existing_ids, all_movies, add_year_to_title=True)

    # --- ADIM 3: ARŞİV (YILLAR VE TÜRLER) ---
    # Geriye kalanlar türlerine göre dağılır.
    # Eğer film yukarıdaki "Son Eklenenler"de varsa, burası onu atlar (Duplicate olmaz).
    print("\n--- ADIM 3: GENEL ARŞİV TARANIYOR ---")
    for year in ARCHIVE_YEARS:
        print(f"> Yıl: {year} işleniyor...")
        for genre_id, genre_name in GENRES.items():
            # Her türden 3-5 sayfa alalım
            for page in range(1, PAGE_DEPTH_ARCHIVE + 1):
                url = f"{BASE_URL}/discover/movie?api_key={API_KEY}&language=tr-TR&sort_by=popularity.desc&primary_release_year={year}&with_genres={genre_id}&page={page}"
                process_batch(url, f"Filmler | {genre_name}", existing_ids, all_movies, add_year_to_title=True)

    # --- KAYIT ---
    print("\n--- KAYDEDİLİYOR ---")
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=4)
    
    save_m3u(M3U_FILE, all_movies)
    print(f"İşlem bitti. Toplam Film: {len(all_movies)}")
    print(f"Süre: {int(time.time() - start_time)} sn.")

if __name__ == "__main__":
    main()
