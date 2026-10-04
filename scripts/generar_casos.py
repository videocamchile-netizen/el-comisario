#!/usr/bin/env python3
"""
Genera una página propia por cada caso (caso/<episodio>-<slug>.html), un índice
casos.html y las entradas del sitemap, para que Google pueda indexar cada
episodio por separado.

Reglas de seguridad (esto NO toca nada sensible del sitio):
- Solo LEE episodios-data.json (la grilla de 9). No lo modifica.
- Escribe únicamente: casos-archivo.json, caso/*.html, casos.html, y el bloque
  entre <!-- INICIO-CASOS-AUTO --> / <!-- FIN-CASOS-AUTO --> de sitemap.xml.
- casos-archivo.json solo crece: un caso que sale de la grilla de 9 conserva su
  página (así Google nunca ve una página que desaparece).
- Todo el texto sale de lo que el canal ya escribió en YouTube (título y
  descripción). No se inventa ni se resume nada.

Uso: python3 scripts/generar_casos.py
"""
import html
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "episodios-data.json"
ARCHIVO = ROOT / "casos-archivo.json"
CASOS_DIR = ROOT / "caso"
INDICE = ROOT / "casos.html"
SITEMAP = ROOT / "sitemap.xml"

SITE = "https://elcomisario.cl"
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UC439PHkUfNl5MjOGGGf4jkQ"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
INI = "<!-- INICIO-CASOS-AUTO -->"
FIN = "<!-- FIN-CASOS-AUTO -->"


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    if len(t) > 45:
        t = t[:45].rsplit("-", 1)[0]  # cortar en límite de palabra
    return t.strip("-") or "caso"


def e(s):
    return html.escape(s or "", quote=True)


def extras_del_feed():
    """videoId -> {fecha, descripcion}. Si YouTube falla, devuelve {} y seguimos."""
    try:
        req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as ex:  # noqa: BLE001
        print(f"Aviso: no se pudo leer el feed ({ex}); se usan solo los datos locales.")
        return {}
    out = {}
    for ent in root.findall("atom:entry", NS):
        vid = ent.find("yt:videoId", NS)
        if vid is None:
            continue
        pub = ent.find("atom:published", NS)
        desc = ent.find("media:group/media:description", NS)
        out[vid.text.strip()] = {
            "fecha": (pub.text.strip() if pub is not None else ""),
            "descripcion": (desc.text.strip() if desc is not None and desc.text else ""),
        }
    return out


def limpiar_descripcion(d):
    """Quita líneas de promoción/links/hashtags; deja solo texto narrativo."""
    lineas = []
    for l in (d or "").splitlines():
        l = l.strip()
        if not l or re.search(r"https?://|www\.|@\w|^#|suscr|whatsapp|instagram|facebook|tiktok", l, re.I):
            continue
        lineas.append(l)
    return "\n".join(lineas)[:1500]


def cargar_archivo():
    if ARCHIVO.exists():
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    return {"casos": []}


def pagina_caso(c, otros):
    titulo = f"{c['nombre']}: {c['bajada']}".strip(": ")
    titulo_pag = f"Caso {c['nombre']} — El Comisario, Episodio {c['episodio']}"
    desc_meta = (c["bajada"] or f"Caso {c['nombre']}") + f" — Episodio {c['episodio']} de El Comisario, periodismo de investigación y denuncia en Chile."
    url = f"{SITE}/caso/{c['archivo']}"
    thumb = f"https://i.ytimg.com/vi/{c['videoId']}/hqdefault.jpg"
    ld = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": titulo,
        "description": c.get("descripcion") or desc_meta,
        "thumbnailUrl": [thumb],
        "embedUrl": f"https://www.youtube.com/embed/{c['videoId']}",
        "contentUrl": f"https://www.youtube.com/watch?v={c['videoId']}",
        "publisher": {"@type": "Organization", "name": "El Comisario", "url": SITE + "/"},
    }
    if c.get("fecha"):
        ld["uploadDate"] = c["fecha"]
    desc_html = ""
    if c.get("descripcion"):
        parrafos = "".join(f"<p>{e(p)}</p>" for p in c["descripcion"].split("\n"))
        desc_html = f'<section class="texto"><h2>Sobre este episodio</h2>{parrafos}</section>'
    otros_html = "".join(
        f'<li><a href="/caso/{o["archivo"]}">Ep. {o["episodio"]} · {e(o["nombre"])}</a></li>' for o in otros
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{e(titulo_pag)}</title>
    <meta name="description" content="{e(desc_meta)}">
    <link rel="canonical" href="{url}">
    <meta property="og:type" content="video.other">
    <meta property="og:title" content="{e(titulo_pag)}">
    <meta property="og:description" content="{e(desc_meta)}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{thumb}">
    <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: 'Segoe UI', Arial, sans-serif; background: #050a14; color: white; }}
        .navbar {{ display: flex; justify-content: space-between; padding: 20px 50px; background: linear-gradient(180deg, rgba(11,21,40,.98), rgba(11,21,40,.85)); align-items: center; border-bottom: 1px solid rgba(255,180,0,.08); }}
        .navbar a {{ color: white; text-decoration: none; margin: 0 15px; font-size: 14px; letter-spacing: 1px; }}
        .navbar a:hover {{ color: #ffb400; }}
        .btn-amarillo {{ background: linear-gradient(135deg, #ffb400, #e6a200); color: #050a14 !important; padding: 12px 24px; font-weight: bold; border-radius: 6px; margin: 0 !important; }}
        .wrap {{ max-width: 860px; margin: 0 auto; padding: 50px 20px 70px; }}
        .ep {{ color: #ffb400; letter-spacing: 3px; font-size: 13px; text-transform: uppercase; }}
        h1 {{ font-size: 2.2rem; margin: 10px 0 8px; color: #ffb400; }}
        .bajada {{ color: #a0a5b0; font-size: 1.1rem; margin: 0 0 28px; }}
        .video {{ position: relative; padding-bottom: 56.25%; height: 0; border-radius: 10px; overflow: hidden; border: 1px solid rgba(255,180,0,.2); }}
        .video iframe {{ position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }}
        .texto {{ margin-top: 34px; }}
        .texto h2, .mas h2 {{ color: #ffb400; font-size: 1.2rem; }}
        .texto p {{ color: #c8ccd6; line-height: 1.7; }}
        .cta {{ margin-top: 34px; padding: 22px 25px; border: 1px solid rgba(255,180,0,.15); border-radius: 8px; background: rgba(255,255,255,.03); color: #a0a5b0; line-height: 1.6; }}
        .cta a {{ color: #ffb400; }}
        .mas ul {{ list-style: none; padding: 0; }}
        .mas li {{ padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,.06); }}
        .mas a {{ color: white; text-decoration: none; }}
        .mas a:hover {{ color: #ffb400; }}
        .footer {{ text-align: center; padding: 30px; border-top: 1px solid rgba(255,180,0,.05); }}
        .footer p {{ color: #556; font-size: 12px; margin: 0; letter-spacing: 1px; }}
        @media (max-width: 900px) {{ .navbar {{ flex-wrap: wrap; justify-content: center; padding: 10px; gap: 6px; }} h1 {{ font-size: 1.6rem; }} }}
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="logo"><img src="/img/logon.png" alt="Logo El Comisario" style="height: 60px;"></div>
        <div class="links">
            <a href="/index.html">INICIO</a>
            <a href="/episodios.html">EPISODIOS</a>
            <a href="/quienes-somos.html">QUIÉNES SOMOS</a>
            <a href="/faq.html">PREGUNTAS</a>
            <a href="/contacto.html">CONTACTO</a>
        </div>
        <a href="/index.html" class="btn-amarillo">VER CANAL</a>
    </nav>
    <main class="wrap">
        <div class="ep">El Comisario · Episodio {c['episodio']}</div>
        <h1>{e(c['nombre'])}</h1>
        <p class="bajada">{e(c['bajada'])}</p>
        <div class="video">
            <iframe src="https://www.youtube-nocookie.com/embed/{c['videoId']}" title="{e(titulo)}" loading="lazy" allow="accelerometer; encrypted-media; picture-in-picture" allowfullscreen></iframe>
        </div>
        {desc_html}
        <div class="cta">¿Tienes información sobre este caso o quieres compartir tu testimonio? Escríbenos desde <a href="/contacto.html">Contacto</a>. Mira todos los casos en <a href="/casos.html">el archivo de casos</a>.</div>
        <section class="mas"><h2>Otros casos</h2><ul>{otros_html}</ul></section>
    </main>
    <footer class="footer"><p>© 2026 El Comisario · Donde las víctimas tienen voz</p></footer>
</body>
</html>
"""


def pagina_indice(casos):
    items = "".join(
        f'<li><a href="/caso/{c["archivo"]}"><span>Ep. {c["episodio"]}</span> {e(c["nombre"])}'
        f'<em>{e(c["bajada"])}</em></a></li>'
        for c in casos
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archivo de casos — El Comisario</title>
    <meta name="description" content="Todos los casos tratados en El Comisario, periodismo de investigación y denuncia en Chile. Cada episodio con su video.">
    <link rel="canonical" href="{SITE}/casos.html">
    <style>
        body {{ margin: 0; font-family: 'Segoe UI', Arial, sans-serif; background: #050a14; color: white; }}
        .wrap {{ max-width: 860px; margin: 0 auto; padding: 50px 20px 70px; }}
        h1 {{ color: #ffb400; }}
        a.volver {{ color: #ffb400; text-decoration: none; }}
        ul {{ list-style: none; padding: 0; }}
        li a {{ display: block; padding: 14px 0; border-bottom: 1px solid rgba(255,255,255,.08); color: white; text-decoration: none; }}
        li a:hover {{ color: #ffb400; }}
        li span {{ color: #ffb400; font-size: 13px; letter-spacing: 2px; margin-right: 8px; }}
        li em {{ display: block; color: #a0a5b0; font-style: normal; margin-top: 4px; font-size: .95rem; }}
    </style>
</head>
<body>
    <main class="wrap">
        <p><a class="volver" href="/index.html">← Volver al inicio</a> · <a class="volver" href="/episodios.html">Últimos episodios</a></p>
        <h1>Archivo de casos</h1>
        <ul>{items}</ul>
    </main>
</body>
</html>
"""


def actualizar_sitemap(casos):
    s = SITEMAP.read_text(encoding="utf-8")
    bloque = INI + "\n" + "\n".join(
        [f"  <url><loc>{SITE}/casos.html</loc><priority>0.6</priority></url>"]
        + [f"  <url><loc>{SITE}/caso/{c['archivo']}</loc><priority>0.5</priority></url>" for c in casos]
    ) + "\n  " + FIN
    if INI in s and FIN in s:
        s = re.sub(re.escape(INI) + r".*?" + re.escape(FIN), lambda m: bloque, s, flags=re.S)
    else:
        s = s.replace("</urlset>", f"  {bloque}\n</urlset>")
    SITEMAP.write_text(s, encoding="utf-8")


def main():
    grilla = json.loads(DATA.read_text(encoding="utf-8"))["episodios"]
    arch = cargar_archivo()
    por_id = {c["videoId"]: c for c in arch["casos"]}
    extras = extras_del_feed()

    for ep in grilla:
        c = por_id.get(ep["videoId"])
        if c is None:
            c = {"episodio": ep["episodio"], "videoId": ep["videoId"]}
            por_id[ep["videoId"]] = c
        c["nombre"], c["bajada"] = ep["nombre"].strip(), ep["bajada"].strip()
        c["archivo"] = c.get("archivo") or f"{c['episodio']}-{slug(c['nombre'])}.html"  # URL fija una vez creada
        x = extras.get(ep["videoId"])
        if x:
            c["fecha"] = c.get("fecha") or x["fecha"]
            c["descripcion"] = c.get("descripcion") or limpiar_descripcion(x["descripcion"])

    casos = sorted(por_id.values(), key=lambda c: c["episodio"], reverse=True)
    ARCHIVO.write_text(json.dumps({"casos": casos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    CASOS_DIR.mkdir(exist_ok=True)
    for c in casos:
        otros = [o for o in casos if o is not c][:6]
        (CASOS_DIR / c["archivo"]).write_text(pagina_caso(c, otros), encoding="utf-8")
    INDICE.write_text(pagina_indice(casos), encoding="utf-8")
    actualizar_sitemap(casos)
    print(f"OK: {len(casos)} casos en el archivo.")


if __name__ == "__main__":
    main()
