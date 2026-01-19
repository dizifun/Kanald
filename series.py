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

MAX_PAGES = 500  # Dizi için sayfa sayısı
MAX_WORKERS = 20 # Hız

os.makedirs("output/diziler", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

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

def save_m3u(filename, content_list):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_series():
    print(f"--- DİZİLER BAŞLIYOR (Paralel Kontrol: {MAX_WORKERS} Thread) ---")
    series_data_all = []
    m3u_entries_all = []

    for page in range(1, MAX_PAGES + 1):
        print(f"Dizi Sayfası: {page}/{MAX_PAGES}")
        try:
            url = f"{BASE_URL}/tv/popular?api_key={API_KEY}&language=tr-TR&page={page}"
            data = requests.get(url).json()

            for item in data.get('results', []):
                tmdb_id = item['id']
                imdb_id = get_imdb_id(tmdb_id, 'tv')

                if imdb_id:
                    raw_name = item['name']
                    file_name = sanitize_filename(raw_name)
                    poster = f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""

                    details_url = f"{BASE_URL}/tv/{tmdb_id}?api_key={API_KEY}"
                    details = requests.get(details_url).json()

                    all_episode_links = []
                    episode_info_map = {}

                    for season in details.get('seasons', []):
                        s_num = season['season_number']
                        ep_count = season['episode_count']
                        if s_num > 0:
                            for ep in range(1, ep_count + 1):
                                link = f"{VIDMODY_BASE}/{imdb_id}/s{s_num}/e{ep:02d}"
                                all_episode_links.append(link)
                                episode_info_map[link] = {"season": s_num, "episode": ep}

                    if all_episode_links:
                        active_links = batch_check_urls(all_episode_links)
                        if active_links:
                            print(f"  [OK] {raw_name}: {len(active_links)} bölüm aktif.")
                            
                            series_obj = {"id": imdb_id, "name": raw_name, "poster": poster, "episodes": []}
                            series_m3u_local = []
                            
                            sorted_links = sorted(list(active_links), key=lambda x: (episode_info_map[x]['season'], episode_info_map[x]['episode']))

                            for link in sorted_links:
                                info = episode_info_map[link]
                                series_obj["episodes"].append({
                                    "season": info['season'],
                                    "episode": info['episode'],
                                    "link": link
                                })
                                m3u_entry = {
                                    "group": raw_name,
                                    "logo": poster,
                                    "name": f"{raw_name} - S{info['season']} B{info['episode']}",
                                    "url": link
                                }
                                series_m3u_local.append(m3u_entry)
                                m3u_entries_all.append(m3u_entry)

                            with open(f"output/diziler/{file_name}.json", "w", encoding="utf-8") as f:
                                json.dump(series_obj, f, ensure_ascii=False, indent=4)
                            save_m3u(f"output/diziler/{file_name}.m3u", series_m3u_local)
                            
                            series_data_all.append(series_obj)
                        else:
                            print(f"  [X] {raw_name}: Bölüm yok.")

        except Exception as e:
            print(f"Hata (Dizi Sayfa {page}): {e}")

    with open("output/series_all.json", "w", encoding="utf-8") as f:
        json.dump(series_data_all, f, ensure_ascii=False, indent=4)
    save_m3u("output/series_all.m3u", m3u_entries_all)

if __name__ == "__main__":
    start = time.time()
    process_series()
    print(f"Diziler Tamamlandı. Süre: {int(time.time() - start)} sn.")
