cd C:\Users\Felipe\Downloads\sports-tracker

python -c "
import json

with open('data/products.json', encoding='utf-8') as f:
    catalog = json.load(f)

products = catalog['products']
last_updated = catalog.get('last_updated','2026-05-17')[:10]

cards = ''
for p in products:
    icon = {'fut':'26BD','bsk':'1F3C0','mlb':'26BE','nfl':'1F3C8','nhl':'1F3D2','tennis':'1F3BE','formula1':'1F3CE','rugby':'1F3C9','sel':'1F30D','tr':'1F4AA','mer':'1F6CD','fab':'1F3ED'}.get(p.get('cat',''),'1F4E6')
    tags = ''.join(f'<span class=tag>{t}</span>' for t in p.get('tags',[])[:4])
    prices = ''.join(f'<div class=pv><span class=pl>{pv[\"l\"]}</span>{pv[\"v\"]}</div>' for pv in p.get('prices',[])[:3])
    links = ''.join(f'<a class=lk href=\"{lk[\"u\"]}\" target=_blank>{lk[\"t\"]}</a>' for lk in p.get('links',[])[:3])
    cards += f'<div class=\"card\" data-cat=\"{p.get(\"cat\",\"\")}\"><div class=vis>&#x{icon};<span class=badge>{p.get(\"cat\",\"\").upper()}</span><span class=dbadge>{p.get(\"date\",\"\")}</span></div><div class=body><h3>{p.get(\"t\",\"\")}</h3><p class=sub>{p.get(\"sub\",\"\")}</p><div class=tags>{tags}</div><div class=prices>{prices}</div><div class=links>{links}</div></div></div>'

html = open('index.html','w',encoding='utf-8')
html.write('''<!DOCTYPE html>
<html lang=es>
<head>
<meta charset=UTF-8>
<meta name=viewport content=\"width=device-width,initial-scale=1\">
<title>Sports Catalog</title>
<link href=\"https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap\" rel=stylesheet>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#08080b;color:#edeae4;font-family:DM Sans,sans-serif;font-size:14px}
#tb{position:fixed;top:0;left:0;right:0;height:52px;background:rgba(8,8,11,.95);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,.07);display:flex;align-items:center;gap:12px;padding:0 20px;z-index:100}
.logo{font-size:16px;font-weight:600;color:#e8c97a}
.meta{margin-left:auto;font-size:11px;color:#5a5650}
.meta b{color:#e8c97a}
#ctrl{position:sticky;top:52px;z-index:90;background:rgba(8,8,11,.95);backdrop-filter:blur(16px);border-bottom:1px solid rgba(255,255,255,.07);padding:10px 20px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fp{padding:4px 12px;border-radius:20px;font-size:11px;font-weight:500;cursor:pointer;border:1px solid rgba(255,255,255,.13);background:transparent;color:#9b9590;transition:all .15s;white-space:nowrap}
.fp.on,.fp:hover{background:#e8c97a;color:#08080b;border-color:#e8c97a}
.sep{width:1px;height:16px;background:rgba(255,255,255,.13)}
#si{flex:1;min-width:140px;background:#16161e;border:1px solid rgba(255,255,255,.13);border-radius:8px;padding:6px 12px;color:#edeae4;font-size:13px;outline:none}
#si:focus{border-color:#e8c97a}
#rc{font-size:11px;color:#5a5650;font-family:monospace;white-space:nowrap}
#rc b{color:#e8c97a}
#grid{padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
.card{background:#16161e;border:1px solid rgba(255,255,255,.07);border-radius:14px;overflow:hidden;display:flex;flex-direction:column;transition:border-color .2s,transform .2s}
.card:hover{border-color:rgba(255,255,255,.18);transform:translateY(-2px)}
.card.hide{display:none}
.vis{aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;font-size:44px;position:relative;background:rgba(255,255,255,.04)}
.badge{position:absolute;top:8px;left:8px;font-size:9px;font-weight:600;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,.6);color:rgba(255,255,255,.8)}
.dbadge{position:absolute;bottom:8px;right:8px;font-size:9px;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,.6);color:rgba(255,255,255,.7)}
.body{padding:12px;flex:1;display:flex;flex-direction:column}
h3{font-size:12px;font-weight:600;color:#edeae4;margin-bottom:3px;line-height:1.3}
.sub{font-size:11px;color:#9b9590;margin-bottom:8px;line-height:1.35}
.tags{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px}
.tag{font-size:10px;padding:2px 6px;border-radius:4px;background:#1e1e28;color:#5a5650;border:1px solid rgba(255,255,255,.07)}
.prices{display:flex;flex-wrap:wrap;gap:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.07);margin-top:auto}
.pv{font-family:monospace;font-size:12px;color:#e8c97a}
.pl{font-size:10px;color:#5a5650;display:block;margin-bottom:1px;font-family:sans-serif}
.links{display:flex;flex-direction:column;gap:3px;margin-top:8px}
.lk{font-size:10px;color:#5b9cf6;text-decoration:none}
.lk::before{content:\"↗ \"}
.lk:hover{color:#e8c97a}
#footer{padding:20px;border-top:1px solid rgba(255,255,255,.07);font-size:11px;color:#5a5650;text-align:center;line-height:1.8}
@media(max-width:600px){#grid{grid-template-columns:1fr 1fr;padding:12px;gap:10px}.body{padding:9px}}
</style>
</head>
<body>
<header id=tb>
  <div class=logo>&#x1F3C6; Sports Catalog</div>
  <div class=meta>Actualizado <b>''' + last_updated + '''</b> &middot; <b id=tc>''' + str(len(products)) + '''</b> productos</div>
</header>
<div id=ctrl>
  <button class=\"fp on\" onclick=\"filt('all',this)\">Todos</button>
  <div class=sep></div>
  <button class=fp onclick=\"filt('fut',this)\">&#x26BD; F&uacute;tbol</button>
  <button class=fp onclick=\"filt('bsk',this)\">&#x1F3C0; Basketball</button>
  <button class=fp onclick=\"filt('mlb',this)\">&#x26BE; MLB</button>
  <button class=fp onclick=\"filt('nfl',this)\">&#x1F3C8; NFL</button>
  <button class=fp onclick=\"filt('nhl',this)\">&#x1F3D2; NHL</button>
  <button class=fp onclick=\"filt('tennis',this)\">&#x1F3BE; Tenis</button>
  <button class=fp onclick=\"filt('formula1',this)\">&#x1F3CE; F1</button>
  <button class=fp onclick=\"filt('rugby',this)\">&#x1F3C9; Rugby</button>
  <div class=sep></div>
  <button class=fp onclick=\"filt('sel',this)\">&#x1F30D; Selecciones</button>
  <button class=fp onclick=\"filt('mer',this)\">&#x1F6CD; Merch</button>
  <button class=fp onclick=\"filt('fab',this)\">&#x1F3ED; Fabricaci&oacute;n</button>
  <div class=sep></div>
  <input id=si type=text placeholder=\"Buscar producto, marca, deporte...\" oninput=\"doS(this.value)\">
  <div id=rc><b id=rn>''' + str(len(products)) + '''</b> productos</div>
</div>
<div id=grid>''' + cards + '''</div>
<footer id=footer>Sports Catalog &middot; Actualizaci&oacute;n autom&aacute;tica semanal &middot; ''' + last_updated + '''</footer>
<script>
let CF=\"all\",CS=\"\";
function filt(c,b){CF=c;document.querySelectorAll(\".fp\").forEach(x=>x.classList.remove(\"on\"));b.classList.add(\"on\");render();}
function doS(v){CS=v.toLowerCase();render();}
function render(){let n=0;document.querySelectorAll(\".card\").forEach(card=>{const mc=CF==\"all\"||card.dataset.cat==CF;const ms=!CS||card.textContent.toLowerCase().includes(CS);if(mc&&ms){card.classList.remove(\"hide\");n++;}else card.classList.add(\"hide\");});document.getElementById(\"rn\").textContent=n;document.getElementById(\"tc\").textContent=n;}
render();
</script>
</body>
</html>''')
html.close()
print('index.html generado OK')
"

git add index.html
git commit -m "Add sports catalog"
git push