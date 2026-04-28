"""
Таганрог Live — парсер для GitHub Actions
Результат пишет в docs/news.json (раздаётся GitHub Pages)

pip install requests beautifulsoup4 lxml
python parser.py --once
"""

import requests
import json
import hashlib
import logging
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger('tg-parser')

OUTPUT_PATH = 'docs/news.json'
MAX_ITEMS   = 120   # сколько хранить в файле

CATEGORIES = {
    'zhkh':   ['водоканал', 'вода', 'отключен', 'авария', 'порыв', 'жкх', 'коммунал',
                'электроснабжени', 'теплоснабжени', 'канализац', 'свет', 'газ'],
    'mchs':   ['мчс', 'предупрежден', 'нагон', 'наводнен', 'ветер', 'шторм', 'погода',
                'пожар', 'чрезвычайн', 'уровень воды', 'азовское'],
    'works':  ['ремонт', 'строительств', 'реконструкц', 'дорог', 'перекрыт', 'работы на'],
    'events': ['праздник', 'фестиваль', 'выставк', 'концерт', 'мероприяти', 'конкурс'],
}
URGENT_WORDS = ['авария', 'срочно', 'внимание', 'опасность', 'нагон', 'отключен', 'без воды', 'без света']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; TaganrogLiveBot/1.0)',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

# ───────────── helpers ─────────────
def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def categorize(text: str):
    low = text.lower()
    is_urgent = any(w in low for w in URGENT_WORDS)
    for cat, kws in CATEGORIES.items():
        if any(k in low for k in kws):
            return cat, is_urgent
    return 'news', is_urgent

def get(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=14)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, 'lxml')
    except Exception as e:
        log.warning(f'Ошибка {url}: {e}')
        return None

def item(title, desc, url, source, dt=None):
    cat, urgent = categorize(f'{title} {desc}')
    # форматируем время
    display_time = None
    if dt:
        # пробуем распарсить ISO формат
        try:
            from dateutil import parser as dp
            parsed = dp.parse(dt)
            # переводим в МСК (+3)
            display_time = (parsed + timedelta(hours=3)).strftime('%d.%m %H:%M')
        except Exception:
            display_time = str(dt)[:16]
    if not display_time:
        display_time = (datetime.now() + timedelta(hours=3)).strftime('%d.%m %H:%M')
    return {
        'id':           make_id(url),
        'title':        title.strip()[:200],
        'desc':         desc.strip()[:300],
        'url':          url,
        'source':       source,
        'category':     cat,
        'is_urgent':    urgent,
        'published_at': display_time,
        'parsed_at':    (datetime.now() + timedelta(hours=3)).isoformat(),
    }

# ───────────── парсеры ─────────────
def parse_donday():
    soup = get('https://donday-taganrog.ru')
    if not soup: return []
    out = []
    for el in soup.select('article, .post, .entry')[:15]:
        a = el.select_one('h2 a[href], h3 a[href], .entry-title a')
        if not a: continue
        title = a.get_text(strip=True)
        url   = a['href']
        if not url.startswith('http'):
            url = 'https://donday-taganrog.ru' + url
        p = el.select_one('.excerpt, p')
        desc = p.get_text(strip=True)[:200] if p else ''
        # реальная дата со страницы
        time_el = el.select_one('time[datetime], .date, .post-date, .entry-date')
        dt = None
        if time_el:
            dt = time_el.get('datetime') or time_el.get_text(strip=True)
        if len(title) > 10:
            out.append(item(title, desc, url, 'donday-taganrog.ru', dt))
    log.info(f'donday: {len(out)}')
    return out

def parse_bloknot():
    soup = get('https://bloknot-taganrog.ru/news')
    if not soup: return []
    out = []
    seen = set()
    for el in soup.select('.news-list-item, .news-item, article')[:20]:
        a = el.select_one('a[href*="/news/"]')
        if not a: continue
        title = a.get_text(strip=True)
        url   = a['href']
        if not url.startswith('http'):
            url = 'https://bloknot-taganrog.ru' + url
        if len(title) < 15 or url in seen: continue
        seen.add(url)
        # реальная дата
        time_el = el.select_one('time[datetime], .date, .news-date, .time')
        dt = None
        if time_el:
            dt = time_el.get('datetime') or time_el.get_text(strip=True)
        out.append(item(title, '', url, 'bloknot-taganrog.ru', dt))
    log.info(f'bloknot: {len(out)}')
    return out

def parse_mytaganrog():
    out = []
    seen = set()
    for page_url in ['https://mytaganrog.com/', 'https://mytaganrog.com/taganrog_news/']:
        soup = get(page_url)
        if not soup: continue
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            if not href.startswith('http'):
                href = 'https://mytaganrog.com' + href
            title = a.get_text(strip=True)
            if len(title) < 15 or href in seen: continue
            if 'mytaganrog.com' not in href: continue
            if any(x in href for x in ['/taganrog_news/', '/novosti', '/tegi/']):
                seen.add(href)
                out.append(item(title, '', href, 'mytaganrog.com'))
            if len(out) >= 15: break
    log.info(f'mytaganrog: {len(out)}')
    return out

def parse_vodokanal():
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.get('https://tgnvoda.ru/avarii.php', headers=HEADERS, timeout=14, verify=False)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, 'lxml')
    except Exception as e:
        log.warning(f'vodokanal: {e}')
        return []
    out = []
    for el in soup.select('p, .content p, li')[:15]:
        text = el.get_text(strip=True)
        if len(text) < 25 or len(text) > 600: continue
        title = text[:120]
        desc  = text[120:320] if len(text) > 120 else ''
        url   = f'https://tgnvoda.ru/avarii.php#{make_id(text)}'
        out.append(item(title, desc, url, 'tgnvoda.ru'))
    log.info(f'vodokanal: {len(out)}')
    return out

def parse_kommersant():
    soup = get('https://www.kommersant.ru/search/results?search_query=таганрог&search_type=news')
    if not soup: return []
    out = []
    for a in soup.select('a[href]')[:40]:
        title = a.get_text(strip=True)
        url   = a.get('href', '')
        if not url.startswith('http'):
            url = 'https://www.kommersant.ru' + url
        if len(title) > 20 and '/doc/' in url:
            out.append(item(title, '', url, 'kommersant.ru'))
        if len(out) >= 10: break
    log.info(f'kommersant: {len(out)}')
    return out

def parse_mchs():
    soup = get('https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya')
    if not soup: return []
    out = []
    keywords = ['таганрог', 'азов', 'нагон', 'дон', 'ростов']
    for a in soup.select('a[href]')[:30]:
        title = a.get_text(strip=True)
        low   = title.lower()
        if not any(k in low for k in keywords): continue
        url = a['href']
        if not url.startswith('http'):
            url = 'https://61.mchs.gov.ru' + url
        if len(title) > 15:
            out.append(item(title, '', url, 'mchs.gov.ru'))
    log.info(f'mchs: {len(out)}')
    return out

# ───────────── агрегация ─────────────
def load_existing() -> dict:
    try:
        with open(OUTPUT_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'items': []}

def run():
    log.info(f'=== Парсинг {datetime.now().strftime("%d.%m.%Y %H:%M")} ===')

    existing = load_existing()
    seen_ids = {n['id'] for n in existing.get('items', [])}

    fresh = []
    for fn in [parse_donday, parse_bloknot, parse_mytaganrog,
               parse_vodokanal, parse_kommersant, parse_mchs]:
        try:
            fresh.extend(fn())
        except Exception as e:
            log.error(f'{fn.__name__}: {e}')

    new_items = [n for n in fresh if n['id'] not in seen_ids]
    log.info(f'Новых: {len(new_items)}')

    all_items = new_items + existing.get('items', [])
    all_items = list({n['id']: n for n in all_items}.values())  # дедупликация
    all_items = sorted(all_items, key=lambda x: x['parsed_at'], reverse=True)[:MAX_ITEMS]

    stats = {c: sum(1 for n in all_items if n['category'] == c)
             for c in ['zhkh','mchs','works','events','news']}
    stats['total'] = len(all_items)

    output = {
        'last_updated': (datetime.now() + __import__('datetime').timedelta(hours=3)).isoformat(),
        'stats':        stats,
        'items':        all_items,
    }

    os.makedirs('docs', exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f'Сохранено {len(all_items)} новостей → {OUTPUT_PATH}')

if __name__ == '__main__':
    run()
