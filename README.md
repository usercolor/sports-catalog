# Sports Catalog Auto-Updater 🏆

Sistema de actualización automática semanal del catálogo de indumentaria deportiva.
Usa **GitHub Actions** (gratis) + **Claude API Haiku** (ultra barato) para buscar, 
extraer y agregar nuevos productos automáticamente cada semana.

---

## 💰 Costo estimado

| Componente | Costo |
|---|---|
| GitHub Actions | **GRATIS** (2000 min/mes free en repos públicos) |
| Serper.dev (búsquedas web) | **GRATIS** (2500 búsquedas/mes free tier) |
| Claude API — Haiku | **~$0.25–0.60 por ejecución semanal** |
| **Total mensual** | **~$1–2.50/mes** |

### Por qué Haiku y no Sonnet/Opus:
- Haiku cuesta ~20x menos que Sonnet para el mismo número de tokens
- Para extraer datos estructurados de noticias, Haiku es suficientemente preciso
- Si querés calidad premium, cambiá `claude-haiku-4-5` por `claude-sonnet-4-20250514` 
  en `scripts/update_catalog.py` (~$5-8/mes en lugar de $1-2)

---

## 🚀 Setup paso a paso (15 minutos)

### 1. Crear el repositorio en GitHub

```bash
# Cloná o creá un repo nuevo en GitHub
git init sports-catalog
cd sports-catalog
# Copiá todos los archivos de este proyecto
git add .
git commit -m "Initial setup"
git remote add origin https://github.com/TU-USUARIO/sports-catalog.git
git push -u origin main
```

### 2. Obtener API keys

**Claude API (obligatorio):**
1. Ir a https://console.anthropic.com
2. Settings → API Keys → Create Key
3. Copiar la key (empieza con `sk-ant-...`)

**Serper.dev (opcional pero recomendado — búsqueda más precisa):**
1. Ir a https://serper.dev
2. Registrarse gratis (2500 búsquedas/mes gratuitas)
3. Copiar la API key

### 3. Agregar secrets en GitHub

En tu repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret name | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | Tu key de Claude API (`sk-ant-...`) |
| `SERPER_API_KEY` | Tu key de Serper (opcional) |

### 4. Activar GitHub Pages (para ver el catálogo online)

En tu repo → Settings → Pages:
- Source: **Deploy from a branch**
- Branch: `main` / folder: `/site`
- Guardar

Tu catálogo quedará en: `https://TU-USUARIO.github.io/sports-catalog/`

### 5. Primera ejecución manual

En tu repo → Actions → "Sports Catalog Auto-Update" → Run workflow

---

## ⚙️ Configuración avanzada

### Cambiar frecuencia de actualización

En `.github/workflows/update-catalog.yml`, modificar la línea `cron`:

```yaml
# Cada lunes a las 8am UTC (default)
- cron: '0 8 * * 1'

# Dos veces por semana (lunes y jueves)
- cron: '0 8 * * 1,4'

# Una vez al mes (día 1 a las 8am)
- cron: '0 8 1 * *'
```

### Agregar nuevos deportes o búsquedas

En `scripts/update_catalog.py`, editar el diccionario `SEARCH_QUERIES`:

```python
SEARCH_QUERIES = {
    # ... existing sports ...
    "cricket": [
        "cricket jersey new design 2025 launch",
        "IPL team kit 2025 new",
    ],
    "cycling": [
        "Tour de France team kit 2025 new",
        "UCI cycling jersey sponsor 2025",
    ],
    "esports": [
        "esports team jersey merchandise 2025",
        "gaming organization apparel drop 2025",
    ],
}
```

### Ajustar el modelo de Claude

En `scripts/update_catalog.py`, línea con `model=`:

```python
# Ultra barato (~$0.25/1M tokens input)
model="claude-haiku-4-5"

# Mejor calidad (~$3/1M tokens input)  
model="claude-sonnet-4-20250514"
```

---

## 📁 Estructura del proyecto

```
sports-catalog/
├── .github/
│   └── workflows/
│       └── update-catalog.yml    # GitHub Actions scheduler
├── scripts/
│   └── update_catalog.py         # Script principal Python
├── data/
│   └── products.json             # Base de datos de productos (auto-generado)
├── site/
│   └── index.html                # Catálogo HTML (auto-generado, deployado en Pages)
├── README.md
└── requirements.txt
```

---

## 🔄 ¿Cómo funciona por dentro?

```
Cada lunes 8am UTC:
│
├── 1. GitHub Actions dispara el workflow (GRATIS)
│
├── 2. Para cada deporte en SEARCH_QUERIES:
│   ├── Serper.dev busca noticias de la última semana (GRATIS)
│   └── Google News RSS como fallback (GRATIS)
│
├── 3. Claude Haiku recibe los titulares y extrae productos estructurados
│   └── Costo: ~$0.25-0.60 total por toda la ejecución
│
├── 4. Nuevos productos se mergean en data/products.json
│   └── No duplica productos ya existentes
│
├── 5. Se regenera site/index.html con todos los productos
│
└── 6. GitHub Actions commitea y pushea los cambios
    └── GitHub Pages actualiza automáticamente el sitio
```

---

## 🛠 Correr localmente para probar

```bash
# Instalar dependencias
pip install anthropic requests python-dotenv

# Crear .env local
echo "ANTHROPIC_API_KEY=sk-ant-TU-KEY" > .env
echo "SERPER_API_KEY=TU-SERPER-KEY" >> .env
echo "SPORT_FOCUS=fut" >> .env

# Correr solo para fútbol (más rápido para probar)
SPORT_FOCUS=fut python scripts/update_catalog.py

# Correr para todos los deportes
SPORT_FOCUS=all python scripts/update_catalog.py
```

---

## 📊 Deportes cubiertos automáticamente

| Deporte | Fuentes buscadas |
|---|---|
| ⚽ Fútbol | Footy Headlines, SoccerBible, Football Kit Archive |
| 🏀 Basketball | Basketball Jersey Archive, NBA, SportsLogos.Net |
| ⚾ MLB | MLB.com, ESPN, Baseball Reference |
| 🏈 NFL | NFL.com, ESPN, Pro Football Reference |
| 🏒 NHL | NHL.com, SportsLogos.Net, theicegarden.com |
| 🎾 Tennis | ATP/WTA official, Tennis World |
| 🏎️ Formula 1 | F1.com, Motorsport.com |
| 🏉 Rugby | World Rugby, Planet Rugby |

---

## ❓ FAQ

**¿Se puede limitar a cuántos créditos usa por semana?**  
Sí. En la Anthropic Console podés poner un spending limit mensual. Con $5/mes es más que suficiente.

**¿Qué pasa si Claude extrae un producto incorrecto?**  
El script solo agrega productos que no existen ya (por ID y título). Podés revisar `data/products.json` y borrar manualmente cualquier entrada incorrecta. El próximo run no la vuelve a agregar si la borraste.

**¿Puedo combinar con el catálogo manual que ya tenemos?**  
Sí. Los productos del catálogo manual (sports-catalog-complete.html) los podés importar a `data/products.json` como base inicial. El script los respeta y solo agrega los nuevos.

**¿Funciona sin Serper.dev?**  
Sí. Sin la key de Serper, usa Google News RSS que es completamente gratis (sin límites conocidos para uso razonable).

---

*Costo estimado real de una semana: 8 deportes × 3 queries × 5 results × ~200 tokens = ~24k tokens entrada + ~3k salida = ~$0.007 total para Haiku. Pero sumando overhead y variabilidad, presupuestar $0.30-0.60/semana es conservador.*
