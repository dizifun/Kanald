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

# Dosya Yolları
OUTPUT_DIR = "output"
JSON_FILE = os.path.join(OUTPUT_DIR, "movies_all.json")
M3U_FILE = os.path.join(OUTPUT_DIR, "movies_all.m3u")
STATE_FILE = "taram_durumu.json" # Nerede kaldığımızı tutan dosya

# Tarama Ayarları
BATCH_SIZE = 1000  # Her çalışmada kaç sayfa ilerleyecek
MAX_WORKERS = 20   # Hız

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Klasörleri oluştur
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- YARDIMCI FONKSİYONLAR ---

def load_existing_data():
    """Var olan veritabanını yükler, yoksa boş başlatır."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Listeyi ID bazlı sözlüğe çevir (Daha hızlı kontrol için)
                return {item['id']: item for item in data}
        except:
            return {}
    return {}

def load_state():
    """Son kalınan sayfayı yükler."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"last_page": 1}

def save_state(page):
    """Nerede kaldığımızı kaydeder."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_page": page}, f)

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

def get_imdb_id(tmdb_id, media_type):
    try:
        url = f"{BASE_URL}/{media_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        return None
    return None

def save_database(movie_dict):
    """Verileri JSON ve M3U olarak kaydeder."""
    # Dict'i listeye çevir
    movies_list = list(movie_dict.values())
    
    # JSON Kaydet
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(movies_list, f, ensure_ascii=False, indent=4)
    
    # M3U Kaydet
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in movies_list:
            # M3U formatında başlık ve link
            group = "Filmler"
            logo = item.get('poster', '')
            name = item.get('title', 'Bilinmeyen')
            url = item.get('link', '')
            f.write(f'#EXTINF:-1 group-title="{group}" tvg-logo="{logo}", {name}\n')
            f.write(f'{url}\n')

# --- ANA İŞLEM ---

def process_page_range(start_page, end_page, current_db):
    """Belirli bir sayfa aralığını tarar ve veritabanını günceller."""
    print(f"\n--- Tarama Başlıyor: Sayfa {start_page} ile {end_page} arası ---")
    
    for page in range(start_page, end_page + 1):
        print(f"İşleniyor: Sayfa {page}...")
        try:
            url = f"{BASE_URL}/movie/popular?api_key={API_KEY}&language=tr-TR&page={page}"
            resp = requests.get(url)
            
            if resp.status_code != 200:
                print(f"  -> Sayfa {page} erişilemedi veya bitti.")
                break # API limiti veya sayfa sonu
                
            data = resp.json()
            results = data.get('results', [])
            
            if not results:
                print("  -> Bu sayfada sonuç yok.")
                break

            pending_checks = []
            movie_map = {}

            # Filmleri Hazırla
            for item in results:
                tmdb_id = item.get('id')
                
                # Eğer veritabanında zaten varsa ve linki çalışıyorsa atla (Hız optimizasyonu)
                # İstersen burayı kaldırıp her seferinde kontrol ettirebilirsin.
                # Ancak imdb_id çekmek maliyetli olduğu için önce bunu yapıyoruz.
                
                imdb_id = get_imdb_id(tmdb_id, 'movie')
                
                if imdb_id:
                    # Eğer bu ID zaten kayıtlıysa, tekrar check etmeye gerek var mı?
                    # "Her seferinde güncelle" dediğin için check ediyoruz.
                    link = f"{VIDMODY_BASE}/{imdb_id}"
                    
                    # Kontrol listesine ekle
                    pending_checks.append(link)
                    movie_map[link] = {
                        "id": imdb_id,
                        "title": item['title'],
                        "poster": f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else "",
                        "link": link
                    }

            # Toplu Link Kontrolü
            if pending_checks:
                active_links = batch_check_urls(pending_checks)
                count_new = 0
                
                for link in active_links:
                    info = movie_map[link]
                    
                    # Veritabanına Ekle / Güncelle (ID anahtar olduğu için üstüne yazar)
                    if info['id'] not in current_db:
                        count_new += 1
                    
                    current_db[info['id']] = info
                
                print(f"  -> Sayfa {page} tamamlandı. {len(active_links)} aktif link bulundu. ({count_new} yeni)")

        except Exception as e:
            print(f"Hata (Sayfa {page}): {e}")
            time.sleep(1) # Hata durumunda az bekle

    return current_db

def main():
    start_time = time.time()
    
    # 1. Mevcut Veritabanını Yükle
    print("Mevcut veritabanı yükleniyor...")
    movie_db = load_existing_data()
    print(f"Mevcut Film Sayısı: {len(movie_db)}")

    # 2. Durumu Yükle (Nerede kalmıştık?)
    state = load_state()
    last_page = state['last_page']
    
    # 3. ÖZEL İSTEK: Her zaman önce 1. Sayfayı Tara (Güncellemeler için)
    print("\n!!! GÜNCEL KONTROLÜ (Sayfa 1) !!!")
    movie_db = process_page_range(1, 1, movie_db)

    # 4. Kaldığımız yerden devam et (Batch tarama)
    start_page = last_page
    # Eğer son kaldığı yer 1 ise ve biz zaten 1'i taradıysak 2'den başlasın
    if start_page == 1: 
        start_page = 2
        
    end_page = start_page + BATCH_SIZE
    
    print(f"\nBatch Tarama Başlatılıyor: {start_page} -> {end_page}")
    movie_db = process_page_range(start_page, end_page, movie_db)

    # 5. Kaydet
    print("\nDosyalar Kaydediliyor...")
    save_database(movie_db)
    
    # 6. Bir sonraki başlangıç noktasını kaydet
    save_state(end_page + 1)
    
    print(f"\n--- İŞLEM TAMAMLANDI ---")
    print(f"Toplam Süre: {int(time.time() - start_time)} sn.")
    print(f"Toplam Film: {len(movie_db)}")
    print(f"Bir sonraki tarama {end_page + 1}. sayfadan başlayacak.")

if __name__ == "__main__":
    main()
