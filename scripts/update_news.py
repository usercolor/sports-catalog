"""
update_news.py
==============
Busca noticias de indumentaria deportiva cada 3 días.
Guarda resultados en data/news.json.
Se ejecuta desde GitHub Actions.

Fuentes: Google News RSS (gratis, sin límite) + Serper.dev (opcional)
Claude Haiku genera resúmenes en español.
Costo estimado: ~$0.10-0.30 por ejecución (cada 3 días) = ~$1-3/mes
"""

import os, json, re, datetime, requests, hashlib
import xml.etree.ElementTree as ET

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERPER_API_KEY    = os.getenv("SERPER_API_KEY", "")
DATA_FILE         = "data/news.json"
MAX_NEWS          = 60   # máximo de noticias guardadas
MAX_AGE_DAYS      = 30   # descartar noticias más viejas de 30 días

# ── Fuentes de búsqueda ────────────────────────────────────────────────────

QUERIES = [
    # Fútbol — kits y diseño
    ("fut", "football kit new launch 2025 2026 jersey design"),
    ("fut", "soccer jersey special edition drop 2025 collab"),
    ("fut", "footy headlines kit leaked 2025"),
    ("fut", "camiseta futbol lanzamiento 2025 diseño"),
    # Latam / Uruguay
    ("uru", "indumentaria deportiva argentina uruguay 2025"),
    ("uru", "camiseta futbol sudamerica lanzamiento 2025"),
    ("uru", "ropa deportiva latam diseño 2025"),
    # Basketball
    ("bsk", "NBA jersey new design 2025 2026 city edition"),
    ("bsk", "NBA city edition leaked 2025 2026"),
    ("bsk", "basketball jersey special edition drop 2025"),
    # MLB
    ("mlb", "MLB city connect jersey 2025 new launch"),
    ("mlb", "baseball jersey special edition Nike 2025"),
    # NFL
    ("nfl", "NFL new uniform jersey 2025 2026"),
    ("nfl", "NFL throwback color rush jersey 2025"),
    # NHL
    ("nhl", "NHL jersey new design 2025 winter classic"),
    # Tennis
    ("tennis", "Roland Garros Nike Adidas outfit 2025 2026"),
    ("tennis", "Wimbledon US Open tennis outfit new 2025"),
    # F1
    ("f1", "Formula 1 team merchandise jacket 2025 new"),
    ("f1", "F1 team kit livery merchandise 2025"),
    # Rugby
    ("rugby", "All Blacks Canterbury rugby jersey 2025 new"),
    ("rugby", "Six Nations rugby kit 2025 launch"),
]

SOURCE_MAP = {
    "footyheadlines": "FootyHeadlines",
    "soccerbible": "SoccerBible",
    "kitarchive": "Football Kit Archive",
    "espn": "ESPN",
    "nba.com": "NBA.com",
    "mlb.com": "MLB.com",
    "nfl.com": "NFL.com",
    "nhl.com": "NHL.com",
    "marca": "Marca",
    "as.com": "AS",
    "ole": "Olé",
    "infobae": "Infobae",
    "clarin": "Clarín",
    "elpais": "El País",
    "latercera": "La Tercera",
    "record.com": "Récord MX",
}

# ── Web search ──────────────────────────────────────────────────────────────

def search_news(query: str, num: int = 8) -> list[dict]:
    """Search via Serper.dev (preferred) or Google News RSS (fallback)."""
    if SERPER_API_KEY:
        try:
            resp = requests.post(
                "https://google.serper.dev/news",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": num, "hl": "es", "tbs": "qdr:w"},
                timeout=10
            )
            resp.raise_for_status()
            items = resp.json().get("news", [])
            return [{
                "title":   i.get("title", ""),
                "snippet": i.get("snippet", ""),
                "link":    i.get("link", ""),
                "source":  i.get("source", ""),
                "imageUrl":i.get("imageUrl", ""),
                "date":    i.get("date", ""),
            } for i in items]
        except Exception as e:
            print(f"  Serper error: {e}")

    # Fallback: Google News RSS
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=es&gl=US&ceid=US:es"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall(".//item")[:num]:
            title   = item.findtext("title", "")
            link    = item.findtext("link", "")
            desc    = item.findtext("description", "")
            pubdate = item.findtext("pubDate", "")
            source_el = item.find("source")
            source  = source_el.text if source_el is not None else ""
            # Strip HTML from description
            desc = re.sub('<[^<]+?>', '', desc)
            items.append({"title": title, "snippet": desc[:300],
                          "link": link, "source": source,
                          "imageUrl": "", "date": pubdate})
        return items
    except Exception as e:
        print(f"  RSS error: {e}")
        return []


# ── Claude Haiku summarizer ─────────────────────────────────────────────────

def summarize_batch(items: list[dict], cat: str) -> list[dict]:
    """Send a batch of news items to Claude Haiku, get structured summaries."""
    if not items or not ANTHROPIC_API_KEY:
        return []

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    news_text = ""
    for i, item in enumerate(items[:10]):
        news_text += f"{i+1}. TÍTULO: {item['title']}\n   SNIPPET: {item['snippet'][:200]}\n   URL: {item['link']}\n   FUENTE: {item.get('source','')}\n\n"

    today = datetime.date.today().isoformat()
    prompt = f"""Sos un analista de indumentaria deportiva. Hoy es {today}. Categoría: {cat}.

Analizá estas noticias sobre kits/uniformes/merchandising deportivo y extraé solo las relevantes.
Devolvé un JSON array. Cada item debe tener:
- id: slug único (e.g. "lakers-city-nov-2025")
- cat: "{cat}"
- title: titular en español (max 80 chars), claro y atractivo
- summary: resumen en español de 2-3 líneas (max 200 chars), con los datos clave
- source: nombre de la fuente (FootyHeadlines, ESPN, Marca, etc.)
- url: la URL de la noticia
- date: fecha ISO (YYYY-MM-DD) si la podés inferir, sino "{today}"
- image: URL de imagen si está disponible, sino ""
- relevant: true si es sobre diseño/lanzamiento de kit/merch deportivo, false si es sobre resultados de partidos

Solo incluí noticias con relevant=true. Si ninguna es relevante, devolvé [].
JSON array solamente, sin texto adicional:

{news_text}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [p for p in parsed if p.get("relevant", True)]
    except Exception as e:
        print(f"  Claude error ({cat}): {e}")
    return []


# ── Dedup & merge ───────────────────────────────────────────────────────────

def news_id(item: dict) -> str:
    """Stable ID based on URL."""
    return hashlib.md5(item.get("url", item.get("title", "")).encode()).hexdigest()[:12]


def load_existing() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"news": [], "last_updated": None}


def merge(existing: dict, new_items: list[dict]) -> dict:
    cutoff = (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    # Remove old items
    kept = [n for n in existing.get("news", []) if n.get("date", "9999") >= cutoff]
    existing_ids = {news_id(n) for n in kept}

    added = 0
    for item in new_items:
        nid = news_id(item)
        if nid not in existing_ids:
            item["added_date"] = datetime.date.today().isoformat()
            kept.append(item)
            existing_ids.add(nid)
            added += 1

    # Sort by date desc, keep latest MAX_NEWS
    kept.sort(key=lambda x: x.get("date", ""), reverse=True)
    kept = kept[:MAX_NEWS]

    print(f"  Added {added} new items. Total: {len(kept)}")
    return {
        "news": kept,
        "last_updated": datetime.datetime.now().isoformat(),
        "total": len(kept)
    }


def save(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"News Updater — {datetime.date.today()}")
    print(f"{'='*55}\n")

    existing = load_existing()
    print(f"Existing news: {len(existing.get('news', []))}\n")

    all_new = []
    for cat, query in QUERIES:
        print(f"🔍 [{cat.upper()}] {query[:50]}")
        raw_items = search_news(query, num=6)
        print(f"   Found {len(raw_items)} raw items")
        if raw_items:
            summarized = summarize_batch(raw_items, cat)
            print(f"   Extracted {len(summarized)} relevant news")
            all_new.extend(summarized)

    updated = merge(existing, all_new)
    save(updated)
    print(f"\n✅ Done. Total news: {updated['total']}")


if __name__ == "__main__":
    main()
