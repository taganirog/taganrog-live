# Таганрог Live

Городской информационный портал. Автопарсинг 24/7 через GitHub Actions → GitHub Pages.

**Бесплатно. Без сервера. Работает само.**

---

## Структура

```
├── .github/
│   └── workflows/
│       └── parse.yml       ← автозапуск парсера каждые 30 мин
├── docs/
│   ├── index.html          ← сайт (GitHub Pages раздаёт из папки /docs)
│   └── news.json           ← данные, которые пишет парсер
├── parser.py               ← парсер (запускается в GitHub Actions)
└── README.md
```

---

## Деплой за 5 минут

### Шаг 1 — Создай репозиторий на GitHub
1. Зайди на [github.com](https://github.com) → **New repository**
2. Название: `taganrog-live` (или любое)
3. Видимость: **Public** (обязательно для бесплатного Pages)
4. Нажми **Create repository**

### Шаг 2 — Загрузи файлы
Самый простой способ — через браузер:
1. В репозитории нажми **Add file → Upload files**
2. Загрузи все файлы этого проекта (сохрани структуру папок)
3. Нажми **Commit changes**

Или через git:
```bash
git clone https://github.com/ТВОЙ_НИК/taganrog-live.git
# скопируй файлы проекта внутрь
git add .
git commit -m "Initial commit"
git push
```

### Шаг 3 — Включи GitHub Pages
1. В репозитории: **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main**, папка: **/docs**
4. Нажми **Save**

Через ~1 минуту сайт будет доступен по адресу:
```
https://ТВОЙ_НИК.github.io/taganrog-live
```

### Шаг 4 — Включи права для Actions
1. **Settings → Actions → General**
2. Найди **Workflow permissions**
3. Выбери **Read and write permissions**
4. Нажми **Save**

### Шаг 5 — Запусти парсер вручную (первый раз)
1. Перейди во вкладку **Actions**
2. Найди workflow **"Парсинг новостей Таганрога"**
3. Нажми **Run workflow → Run workflow**

После этого парсер будет запускаться автоматически каждые 30 минут.

---

## Как это работает

```
GitHub Actions (cron каждые 30 мин)
    └─> запускает parser.py
           └─> парсит 6 сайтов
                  └─> обновляет docs/news.json
                         └─> коммитит в репозиторий
                                └─> GitHub Pages отдаёт новый news.json
                                       └─> сайт читает его при загрузке
```

---

## Добавить новый источник новостей

Открой `parser.py` и добавь функцию по шаблону:

```python
def parse_newsite():
    soup = get('https://newsite.ru/news')
    if not soup: return []
    out = []
    for a in soup.select('.news-title a')[:15]:
        title = a.get_text(strip=True)
        url   = 'https://newsite.ru' + a['href']
        out.append(item(title, '', url, 'newsite.ru'))
    return out
```

Затем добавь в функцию `run()`:
```python
for fn in [..., parse_newsite]:
```
