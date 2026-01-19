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

# --- TARAMA SAYFA ARALIĞI ---
# Burayı istediğin gibi değiştir. GitHub Action her çalıştığında bu aralığı tarar.
START_PAGE = 10000   
END_PAGE = 20000     

MAX_WORKERS = 20     # Hız (Aynı anda kontrol edilecek link sayısı)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Klasör kontrolü
os.makedirs("output", exist_ok=True)

def check_single_url(url):
    """Linkin çalışıp çalışmadığını kontrol eder"""
    try:
        response = requests.head(url, headers=HEADERS, timeout=3, allow_redirects=True)
        if response.status_code == 200:
            return url
    except:
        pass
    return None

def batch_check_urls(url_list):
    """Linkleri çoklu (paralel) kontrol eder"""
    valid_urls = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_single_url, url): url for url in url_list}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                valid_urls.add(result)
    return valid_urls

def get_imdb_id(tmdb_id):
    """TMDB ID'den IMDB ID bulur"""
    try:
        url = f"{BASE_URL}/movie/{tmdb_id}/external_ids?api_key={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        pass
    return None

def save_m3u(filename, content_list):
    """Listeyi M3U formatında kaydeder"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_single_page(page, category_name, all_movies_list, m3u_list):
    """Tek bir sayfadaki filmleri işler ve listelere ekler"""
    print(f"-> Sayfa {page} taranıyor... [{category_name}]")
    try:
        # API'den veriyi çek
        url = f"{BASE_URL}/movie/popular?api_key={API_KEY}&language=tr-TR&page={page}"
        response = requests.get(url, timeout=10)
        
        # Eğer sayfa boşsa veya hata varsa atla
        if response.status_code != 200:
            print(f"   X Sayfa {page} alınamadı veya yok (Kod: {response.status_code})")
            return

        data = response.json()
        results = data.get('results', [])
        
        if not results:
            print(f"   ! Sayfa {page} boş geldi.")
            return

        pending_checks = []
        movie_map = {}

        # Filmlerin IMDB ID'lerini bul ve link oluştur
        for item in results:
            imdb_id = get_imdb_id(item['id'])
            if imdb_id:
                link = f"{VIDMODY_BASE}/{imdb_id}"
                pending_checks.append(link)
                movie_map[link] = {
                    "id": imdb_id,
                    "title": item['title'],
                    "poster": f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""
                }

        # Oluşan linkleri kontrol et (Vidmody'de var mı?)
        if pending_checks:
            active_links = batch_check_urls(pending_checks)
            print(f"   ✓ Sayfa {page}: {len(active_links)} aktif film bulundu.")

            for link in active_links:
                info = movie_map[link]
                
                # JSON Verisine Ekle
                all_movies_list.append({
                    "id": info['id'],
                    "title": info['title'],
                    "poster": info['poster'],
                    "link": link,
                    "category": category_name
                })
                
                # M3U Listesine Ekle
                m3u_list.append({
                    "group": category_name,
                    "logo": info['poster'],
                    "name": info['title'],
                    "url": link
                })

    except Exception as e:
        print(f"Hata (Sayfa {page}): {e}")

def main():
    print(f"--- TARAMA BAŞLATILIYOR ---")
    print(f"Hedef Aralık: {START_PAGE} - {END_PAGE}")
    
    movies_data = [] # JSON için
    m3u_entries = [] # M3U için

    # ---------------------------------------------------------
    # ADIM 1: SON EKLENENLER (SAYFA 1)
    # ---------------------------------------------------------
    print("\n[1/2] 'Son Eklenenler' taranıyor (Sayfa 1)...")
    process_single_page(1, "Son Eklenenler", movies_data, m3u_entries)

    # ---------------------------------------------------------
    # ADIM 2: BELİRLENEN ARALIK (FİLMLER)
    # ---------------------------------------------------------
    print(f"\n[2/2] 'Filmler' aralığı taranıyor ({START_PAGE}-{END_PAGE})...")
    
    for page in range(START_PAGE, END_PAGE + 1):
        # Eğer kullanıcı aralığı 1'den başlattıysa, Sayfa 1'i zaten yukarıda taradık.
        # Tekrar taramamak ve listeye çift eklememek için atlıyoruz.
        if page == 1:
            continue
        
        process_single_page(page, "Filmler", movies_data, m3u_entries)

    # ---------------------------------------------------------
    # ADIM 3: KAYDETME
    # ---------------------------------------------------------
    print("\n--- Dosyalar Kaydediliyor ---")
    
    # JSON Kaydet
    json_path = "output/movies_all.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
    
    # M3U Kaydet
    m3u_path = "output/movies_all.m3u"
    save_m3u(m3u_path, m3u_entries)
    
    print(f"İşlem bitti! Toplam {len(m3u_entries)} içerik kaydedildi.")

if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"Toplam Süre: {int(time.time() - start_time)} saniye.")
