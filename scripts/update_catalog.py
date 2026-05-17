"""
Sports Catalog Auto-Updater
===========================
Runs weekly via GitHub Actions.
Uses Claude Haiku (cheapest model) to minimize API costs.
Estimated cost: ~$0.30-0.80 per weekly run.

Flow:
1. Search for recent sports apparel/kit news (via web search API or RSS)
2. Send compact prompt to Claude Haiku to extract structured product data
3. Merge new products with existing catalog JSON
4. Regenerate the HTML catalog page
5. GitHub Actions commits and pushes the updated files

Required secrets in GitHub repo:
  ANTHROPIC_API_KEY  — your Anthropic API key
  SERPER_API_KEY     — (optional) serper.dev free tier: 2500 searches/month free
"""

import os
import json
import re
import datetime
import requests
import anthropic

# ── CONFIG ─────────────────────────────────────────────────────────────────

SPORT_FOCUS = os.getenv("SPORT_FOCUS", "all")
DATA_FILE   = "data/products.json"
HTML_OUT    = "site/index.html"

# These search queries run each week. Add/remove as needed.
# Each query costs 1 Serper credit (2500/month free on free tier).
SEARCH_QUERIES = {
    "fut": [
        "new football kit launch 2025 2026",
        "soccer jersey special edition drop 2025",
        "football club merchandise collaboration 2025",
    ],
    "nba": [
        "NBA jersey new design 2025 2026 city edition",
        "NBA special edition jersey Chinese New Year 2026",
        "Mitchell Ness throwback new release 2025",
    ],
    "mlb": [
        "MLB city connect jersey 2025 2026 new",
        "baseball jersey special edition Nike 2025",
    ],
    "nfl": [
        "NFL throwback jersey 2025 new uniform",
        "NFL color rush new design 2025 2026",
    ],
    "tennis": [
        "Roland Garros Nike Adidas outfit 2025 2026",
        "Wimbledon official apparel 2025 new",
        "US Open tennis outfit Nike 2025",
    ],
    "formula1": [
        "Formula 1 team merchandise jacket 2025 new",
        "F1 replica race suit 2025 launch",
        "Ferrari Red Bull McLaren merchandise 2025",
    ],
    "nhl": [
        "NHL jersey 2025 2026 new design winter classic",
        "NHL stadium series jersey special edition 2025",
    ],
    "rugby": [
        "rugby jersey All Blacks new 2025 Canterbury",
        "Six Nations rugby kit 2025 2026 new launch",
    ],
}

# ── WEB SEARCH ──────────────────────────────────────────────────────────────

def search_web(query: str, num_results: int = 5) -> list[dict]:
    """
    Uses Serper.dev (free tier: 2500 searches/month).
    Falls back to a simple RSS/news scrape if no Serper key.
    """
    serper_key = os.getenv("SERPER_API_KEY")
    
    if serper_key:
        url = "https://google.serper.dev/news"
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": num_results, "gl": "us", "hl": "en", "tbs": "qdr:w"}  # past week
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            items = resp.json().get("news", [])
            return [{"title": i.get("title",""), "snippet": i.get("snippet",""), "link": i.get("link","")} for i in items]
        except Exception as e:
            print(f"  Serper search failed: {e}")
    
    # Fallback: Google News RSS (no API key needed, free)
    rss_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en&gl=US&ceid=US:en"
    try:
        resp = requests.get(rss_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        # Simple XML parse without lxml
        items = []
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', resp.text)[1:]  # skip feed title
        descs  = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>', resp.text)[1:]
        links  = re.findall(r'<link>(.*?)</link>', resp.text)[1:]
        for i in range(min(num_results, len(titles))):
            items.append({
                "title":   titles[i] if i < len(titles) else "",
                "snippet": re.sub('<[^<]+?>', '', descs[i]) if i < len(descs) else "",
                "link":    links[i] if i < len(links) else "",
            })
        return items
    except Exception as e:
        print(f"  RSS fallback failed: {e}")
        return []


# ── CLAUDE EXTRACTION ────────────────────────────────────────────────────────

def extract_products_with_claude(news_items: list[dict], sport: str) -> list[dict]:
    """
    Sends news snippets to Claude Haiku (cheapest model) and asks it to
    extract structured product data. Returns a list of product dicts.
    Prompt is kept SHORT to minimize tokens = minimize cost.
    """
    if not news_items:
        return []
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Build a compact news digest (limit chars to control token cost)
    news_text = ""
    for item in news_items[:8]:  # max 8 items
        news_text += f"- {item['title']}: {item['snippet'][:200]}\n"
    
    today = datetime.date.today().isoformat()
    
    prompt = f"""You are a sports apparel analyst. Today is {today}.
Extract NEW product drops from these news items about {sport} apparel/merchandise.
Return ONLY a JSON array. Each item must have these fields:
- id: short slug (e.g. "lakers-city-2026")
- cat: one of [fut, bsk, mlb, nfl, sel, tr, mer, tennis, formula1, nhl, rugby]  
- t: product title (max 50 chars)
- sub: subtitle with brand, details (max 120 chars)
- tags: array of 3-5 string tags
- date: launch/release date or season (e.g. "Nov 2025", "Jan 2026")
- prices: array of {{l: label, v: price string}} (1-3 items)
- links: array of {{t: link label, u: URL}} (1-3 real URLs from the news)
- brand: brand name (Nike, Adidas, Puma, etc.)
- special: true if this is a limited/special edition drop

Only include products that are CLEARLY announced or released. Skip vague items.
If no clear products found, return [].

NEWS ITEMS:
{news_text}

JSON array only, no other text:"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5",  # cheapest model — ~$0.25/1M input tokens
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        # Clean potential markdown fences
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        products = json.loads(raw)
        if isinstance(products, list):
            return products
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
    except Exception as e:
        print(f"  Claude API error: {e}")
    
    return []


# ── DATA MANAGEMENT ──────────────────────────────────────────────────────────

def load_existing_products() -> dict:
    """Load the existing product catalog from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"products": [], "last_updated": None, "version": 1}


def merge_products(existing: dict, new_products: list[dict]) -> dict:
    """Merge new products into existing catalog, avoiding duplicates."""
    existing_ids = {p.get("id", "") for p in existing.get("products", [])}
    existing_titles = {p.get("t", "").lower() for p in existing.get("products", [])}
    
    added = 0
    for product in new_products:
        pid = product.get("id", "")
        title = product.get("t", "").lower()
        
        # Skip if already exists (by ID or very similar title)
        if pid in existing_ids or title in existing_titles:
            continue
        
        # Add metadata
        product["added_date"] = datetime.date.today().isoformat()
        product["auto_generated"] = True
        
        existing["products"].append(product)
        existing_ids.add(pid)
        existing_titles.add(title)
        added += 1
    
    existing["last_updated"] = datetime.datetime.now().isoformat()
    existing["total_products"] = len(existing["products"])
    
    print(f"  Added {added} new products. Total: {len(existing['products'])}")
    return existing


def save_products(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── HTML GENERATION ──────────────────────────────────────────────────────────

def generate_html(catalog: dict) -> str:
    """Generate the complete HTML catalog page from product data."""
    products_json = json.dumps(catalog["products"], ensure_ascii=False)
    last_updated = catalog.get("last_updated", "Unknown")[:10]
    total = catalog.get("total_products", len(catalog["products"]))
    
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sports Catalog — Auto-updated {last_updated}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#08080b;--bg3:#16161e;--bg4:#1e1e28;--b:rgba(255,255,255,0.07);--b2:rgba(255,255,255,0.13);--tx:#edeae4;--tx2:#9b9590;--tx3:#5a5650;--gold:#e8c97a;--green:#52c98a;--blue:#5b9cf6;--red:#e05a3a;--pink:#e06fa8;--sans:'DM Sans',system-ui,sans-serif;--mono:'DM Mono',monospace}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:var(--sans);font-size:14px}}
#tb{{position:fixed;top:0;left:0;right:0;z-index:100;height:52px;background:rgba(8,8,11,.94);backdrop-filter:blur(20px);border-bottom:1px solid var(--b);display:flex;align-items:center;gap:12px;padding:0 20px}}
.logo{{font-size:16px;font-weight:600;color:var(--gold)}}
.meta{{margin-left:auto;font-size:11px;color:var(--tx3);font-family:var(--mono)}}
.meta span{{color:var(--gold)}}
#ctrl{{padding:62px 20px 12px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;background:var(--bg);border-bottom:1px solid var(--b);position:sticky;top:52px;z-index:90;background:rgba(8,8,11,.94);backdrop-filter:blur(16px)}}
.fp{{padding:4px 12px;border-radius:20px;font-size:11px;font-weight:500;cursor:pointer;border:1px solid var(--b2);background:transparent;color:var(--tx2);transition:all .15s;white-space:nowrap}}
.fp.on,.fp:hover{{background:var(--gold);color:#08080b;border-color:var(--gold)}}
.sep{{width:1px;height:16px;background:var(--b2)}}
#si{{flex:1;min-width:160px;background:var(--bg3);border:1px solid var(--b2);border-radius:8px;padding:6px 12px;color:var(--tx);font-size:13px;outline:none}}
#si:focus{{border-color:var(--gold)}}
#rc{{font-size:11px;color:var(--tx3);font-family:var(--mono);white-space:nowrap}}
#rc span{{color:var(--gold)}}
#grid{{padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
.card{{background:var(--bg3);border:1px solid var(--b);border-radius:12px;overflow:hidden;display:flex;flex-direction:column;transition:border-color .2s,transform .2s;animation:fu .25s ease forwards}}
.card:hover{{border-color:var(--b2);transform:translateY(-2px)}}
.card.hide{{display:none}}
@keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.vis{{aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;font-size:40px}}
.badge{{position:absolute;top:8px;left:8px;font-size:9px;font-weight:600;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,.5);color:rgba(255,255,255,.85)}}
.dbadge{{position:absolute;bottom:8px;right:8px;font-size:9px;font-weight:500;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,.6);color:rgba(255,255,255,.8)}}
.new-badge{{position:absolute;top:8px;right:8px;font-size:9px;font-weight:700;padding:2px 8px;border-radius:8px;background:var(--green);color:#08080b}}
.body{{padding:11px;flex:1;display:flex;flex-direction:column}}
.body h3{{font-size:12px;font-weight:600;color:var(--tx);margin-bottom:2px;line-height:1.3}}
.sub{{font-size:11px;color:var(--tx2);margin-bottom:7px;line-height:1.3}}
.tags{{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:7px}}
.tag{{font-size:10px;padding:2px 6px;border-radius:4px;background:var(--bg4);color:var(--tx3);border:1px solid var(--b)}}
.tag.g{{background:rgba(82,201,138,.1);color:var(--green);border-color:rgba(82,201,138,.22)}}
.tag.s{{background:rgba(224,90,58,.1);color:var(--red);border-color:rgba(224,90,58,.22)}}
.prices{{display:flex;flex-wrap:wrap;gap:7px;padding-top:7px;border-top:1px solid var(--b);margin-top:auto}}
.pv{{font-family:var(--mono);font-size:12px;color:var(--gold)}}
.pl{{font-size:10px;color:var(--tx3);display:block;margin-bottom:1px}}
.links{{display:flex;flex-direction:column;gap:3px;margin-top:7px}}
.lk{{font-size:10px;color:var(--blue);text-decoration:none;display:flex;align-items:center;gap:3px}}
.lk::before{{content:'↗';font-size:9px}}
.lk:hover{{color:var(--gold)}}
#footer{{padding:24px 20px;border-top:1px solid var(--b);font-size:11px;color:var(--tx3);line-height:1.8}}
#footer a{{color:var(--blue);text-decoration:none}}
@media(max-width:640px){{#grid{{grid-template-columns:1fr 1fr;padding:12px 14px;gap:10px}}.body{{padding:9px}}}}
</style>
</head>
<body>
<header id="tb">
  <div class="logo">Sports Catalog</div>
  <div class="meta">Actualizado <span>{last_updated}</span> · <span id="tc">{total}</span> productos · Auto-refresh semanal</div>
</header>
<div id="ctrl">
  <button class="fp on" onclick="filt('all',this)">Todos</button>
  <div class="sep"></div>
  <button class="fp" onclick="filt('fut',this)">⚽ Fútbol</button>
  <button class="fp" onclick="filt('bsk',this)">🏀 Basketball</button>
  <button class="fp" onclick="filt('mlb',this)">⚾ MLB</button>
  <button class="fp" onclick="filt('nfl',this)">🏈 NFL</button>
  <button class="fp" onclick="filt('nhl',this)">🏒 NHL</button>
  <button class="fp" onclick="filt('tennis',this)">🎾 Tennis</button>
  <button class="fp" onclick="filt('formula1',this)">🏎️ F1</button>
  <button class="fp" onclick="filt('rugby',this)">🏉 Rugby</button>
  <div class="sep"></div>
  <button class="fp" onclick="filt('sel',this)">🌍 Selecciones</button>
  <button class="fp" onclick="filt('mer',this)">🛍 Merch</button>
  <button class="fp" onclick="filt('fab',this)">🏭 Fabricación</button>
  <button class="fp" onclick="filt('new',this)">✨ Nuevos</button>
  <div class="sep"></div>
  <input id="si" type="text" placeholder="Buscar producto, marca, evento…" oninput="doS(this.value)">
  <div id="rc"><span id="rn">0</span> productos</div>
</div>
<div id="grid"></div>
<footer id="footer">
  <strong style="color:var(--tx2)">Sports Catalog</strong> · Actualización automática semanal vía GitHub Actions + Claude API ·
  Última actualización: {last_updated} · {total} productos indexados ·
  <a href="https://github.com" target="_blank">Ver código fuente en GitHub</a>
</footer>
<script>
const ALL = {products_json};

const CAT_ICONS = {{
  fut:'⚽',bsk:'🏀',mlb:'⚾',nfl:'🏈',nhl:'🏒',
  tennis:'🎾',formula1:'🏎️',rugby:'🏉',
  sel:'🌍',tr:'💪',mer:'🛍',fab:'🏭'
}};
const CAT_BG = {{
  fut:'rgba(82,201,138,.15)',bsk:'rgba(232,201,122,.15)',
  mlb:'rgba(91,156,246,.15)',nfl:'rgba(224,90,58,.15)',
  nhl:'rgba(91,156,246,.12)',tennis:'rgba(232,201,122,.12)',
  formula1:'rgba(224,90,58,.12)',rugby:'rgba(155,127,232,.12)',
  sel:'rgba(91,156,246,.12)',tr:'rgba(155,127,232,.12)',
  mer:'rgba(224,111,168,.12)',fab:'rgba(82,201,138,.12)'
}};

let CF='all', CS='';
const today = new Date();
const recentMs = 14 * 24 * 60 * 60 * 1000; // 14 days = "new"

function isNew(p) {{
  if (!p.added_date) return false;
  return (today - new Date(p.added_date)) < recentMs;
}}

function render() {{
  const g = document.getElementById('grid');
  g.innerHTML = '';
  const sq = CS.toLowerCase();
  let n = 0;
  ALL.forEach((p, i) => {{
    const mc = CF === 'all' || p.cat === CF || (CF === 'new' && isNew(p));
    const ms = !sq || p.t?.toLowerCase().includes(sq) || p.sub?.toLowerCase().includes(sq)
               || (p.tags||[]).some(t => t.toLowerCase().includes(sq))
               || (p.brand||'').toLowerCase().includes(sq);
    if (!mc || !ms) {{ const d=document.createElement('div');d.className='card hide';g.appendChild(d); return; }}
    n++;
    const icon = CAT_ICONS[p.cat] || '📦';
    const bg = CAT_BG[p.cat] || 'rgba(255,255,255,.05)';
    const tags = (p.tags||[]).slice(0,4).map((t,j) =>
      `<span class="tag ${{j===0?'g':p.special?'s':""}}">${{t}}</span>`).join('');
    const prices = (p.prices||[]).slice(0,3).map(pv =>
      `<div class="pv"><span class="pl">${{pv.l}}</span>${{pv.v}}</div>`).join('');
    const links = (p.links||[]).slice(0,3).map(lk =>
      `<a class="lk" href="${{lk.u}}" target="_blank" rel="noopener">${{lk.t}}</a>`).join('');
    const d = document.createElement('div');
    d.className = 'card';
    d.style.animationDelay = `${{(i%30)*0.02}}s`;
    d.innerHTML = `
      <div class="vis" style="background:${{bg}}">${{icon}}
        <span class="badge">${{p.cat?.toUpperCase()}}</span>
        ${{p.date ? `<span class="dbadge">${{p.date}}</span>` : ''}}
        ${{isNew(p) ? '<span class="new-badge">NUEVO</span>' : ''}}
      </div>
      <div class="body">
        <h3>${{p.t}}</h3>
        <div class="sub">${{p.sub}}</div>
        <div class="tags">${{tags}}</div>
        <div class="prices">${{prices}}</div>
        <div class="links">${{links}}</div>
      </div>`;
    g.appendChild(d);
  }});
  document.getElementById('rn').textContent = n;
  document.getElementById('tc').textContent = n;
}}

function filt(cat, btn) {{
  CF = cat;
  document.querySelectorAll('.fp').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  render();
}}
function doS(v) {{ CS = v; render(); }}
render();
</script>
</body>
</html>"""


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"Sports Catalog Auto-Updater — {datetime.date.today()}")
    print(f"Sport focus: {SPORT_FOCUS}")
    print(f"{'='*60}\n")
    
    # 1. Load existing catalog
    catalog = load_existing_products()
    print(f"Loaded {len(catalog['products'])} existing products\n")
    
    # 2. Determine which sports to search
    if SPORT_FOCUS == "all":
        sports_to_search = list(SEARCH_QUERIES.keys())
    else:
        sports_to_search = [SPORT_FOCUS] if SPORT_FOCUS in SEARCH_QUERIES else list(SEARCH_QUERIES.keys())
    
    # 3. Search and extract for each sport
    all_new_products = []
    
    for sport in sports_to_search:
        queries = SEARCH_QUERIES.get(sport, [])
        print(f"🔍 Searching: {sport.upper()}")
        
        sport_news = []
        for query in queries:
            results = search_web(query, num_results=5)
            sport_news.extend(results)
            print(f"   '{query}': {len(results)} results")
        
        if sport_news:
            print(f"   Sending {len(sport_news)} news items to Claude Haiku...")
            new_products = extract_products_with_claude(sport_news, sport)
            print(f"   Extracted {len(new_products)} products")
            all_new_products.extend(new_products)
        print()
    
    # 4. Merge new products with existing catalog
    print(f"Merging {len(all_new_products)} new products...")
    updated_catalog = merge_products(catalog, all_new_products)
    
    # 5. Save updated JSON
    save_products(updated_catalog)
    print(f"Saved to {DATA_FILE}")
    
    # 6. Regenerate HTML
    os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
    html = generate_html(updated_catalog)
    with open(HTML_OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated HTML: {HTML_OUT}")
    
    # 7. Print summary
    print(f"\n{'='*60}")
    print(f"✅ Done! Total products: {updated_catalog['total_products']}")
    print(f"   New this run: {len(all_new_products)}")
    print(f"   Last updated: {updated_catalog['last_updated'][:19]}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
