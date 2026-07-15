#!/usr/bin/env python3
"""
Revisa el feed RSS público del canal de YouTube de El Comisario y agrega a
episodios-data.json / episodios.html cualquier video que todavía no esté
listado, manteniendo siempre los últimos 9 episodios.

El título real de YouTube viene con el formato "Nombre: Bajada" (o
"Nombre. Bajada") — se separa en el primer ":" o "." seguido de espacio
para armar el título de la tarjeta ("EP ##: Nombre") y la bajada, igual
como se hacía a mano hasta ahora. No depende de ninguna key/API: usa el
feed RSS público de YouTube.

Uso: python3 scripts/actualizar_episodios.py
Sale sin error y sin tocar archivos si no hay episodios nuevos.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "episodios-data.json"
HTML_PATH = REPO_ROOT / "episodios.html"

CHANNEL_ID = "UC439PHkUfNl5MjOGGGf4jkQ"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

MAX_EPISODIOS = 9

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

INICIO_MARCA = "<!-- INICIO-EPISODIOS-AUTO -->"
FIN_MARCA = "<!-- FIN-EPISODIOS-AUTO -->"


def obtener_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parsear_entradas(xml_bytes):
    root = ET.fromstring(xml_bytes)
    entradas = []
    for entry in root.findall("atom:entry", NS):
        video_id_el = entry.find("yt:videoId", NS)
        title_el = entry.find("atom:title", NS)
        if video_id_el is None or title_el is None:
            continue
        entradas.append({"videoId": video_id_el.text.strip(), "titulo": title_el.text.strip()})
    return entradas  # el feed viene ordenado del más nuevo al más viejo


def separar_titulo(titulo_youtube):
    """'Nombre: Bajada', 'Nombre. Bajada' o 'Nombre; Bajada' -> (nombre, bajada)."""
    m = re.search(r"[:;.]\s+", titulo_youtube)
    if not m:
        return titulo_youtube.strip(), ""
    nombre = titulo_youtube[: m.start()].strip()
    bajada = titulo_youtube[m.end():].strip()
    return nombre, bajada


def escapar_html(texto):
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def cargar_datos():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def guardar_datos(datos):
    DATA_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generar_bloque_html(episodios):
    # episodios se guarda en orden cronológico ascendente (episodio 1, 2, 3...)
    # pero en la grilla del sitio el más nuevo va primero — se invierte solo
    # para mostrar, no para el archivo de datos.
    partes = []
    for i, ep in enumerate(reversed(episodios), start=1):
        nombre = escapar_html(ep["nombre"])
        bajada = escapar_html(ep["bajada"])
        vid = ep["videoId"]
        partes.append(
            f"""            <!-- Video {i} -->
            <div class="tv-card">
                <div class="tv-marco">
                    <iframe src="https://www.youtube.com/embed/{vid}" allowfullscreen loading="lazy"></iframe>
                </div>
                <div class="tv-info">
                    <h3>EP {ep['episodio']:02d}: {nombre}</h3>
                    <p>{bajada}</p>
                    <a href="https://www.youtube.com/watch?v={vid}" target="_blank" class="btn-youtube">▶ VER EN YOUTUBE</a>
                </div>
            </div>"""
        )
    return "\n            \n".join(partes)


def actualizar_html(episodios):
    html = HTML_PATH.read_text(encoding="utf-8")
    if INICIO_MARCA not in html or FIN_MARCA not in html:
        print("ERROR: no se encontraron los marcadores INICIO/FIN-EPISODIOS-AUTO en episodios.html", file=sys.stderr)
        sys.exit(1)
    antes, resto = html.split(INICIO_MARCA, 1)
    _, despues = resto.split(FIN_MARCA, 1)
    nuevo_bloque = generar_bloque_html(episodios)
    nuevo_html = f"{antes}{INICIO_MARCA}\n{nuevo_bloque}\n        {FIN_MARCA}{despues}"
    HTML_PATH.write_text(nuevo_html, encoding="utf-8")


def main():
    datos = cargar_datos()
    ids_existentes = {ep["videoId"] for ep in datos["episodios"]}

    try:
        entradas = parsear_entradas(obtener_feed())
    except Exception as e:
        print(f"No se pudo leer el feed de YouTube: {e}", file=sys.stderr)
        sys.exit(1)

    # el feed viene del más nuevo al más viejo; para numerar bien los
    # episodios nuevos, los procesamos del más viejo al más nuevo entre
    # los que no están todavía.
    nuevas = [e for e in entradas if e["videoId"] not in ids_existentes]
    nuevas.reverse()

    if not nuevas:
        print("Sin episodios nuevos. No se modifica nada.")
        return

    for entrada in nuevas:
        nombre, bajada = separar_titulo(entrada["titulo"])
        datos["episodios"].append(
            {
                "episodio": datos["nextEpisode"],
                "videoId": entrada["videoId"],
                "nombre": nombre,
                "bajada": bajada,
            }
        )
        print(f"+ Agregado EP {datos['nextEpisode']:02d}: {nombre} ({entrada['videoId']})")
        datos["nextEpisode"] += 1

    # siempre dejar solo los últimos MAX_EPISODIOS (se sacan los más viejos)
    if len(datos["episodios"]) > MAX_EPISODIOS:
        sacados = datos["episodios"][: len(datos["episodios"]) - MAX_EPISODIOS]
        for s in sacados:
            print(f"- Sale EP {s['episodio']:02d}: {s['nombre']} ({s['videoId']})")
        datos["episodios"] = datos["episodios"][-MAX_EPISODIOS:]

    guardar_datos(datos)
    actualizar_html(datos["episodios"])
    print(f"Listo: {len(nuevas)} episodio(s) nuevo(s), quedaron {len(datos['episodios'])} en la grilla.")


if __name__ == "__main__":
    main()
