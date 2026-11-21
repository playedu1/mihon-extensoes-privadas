from bs4 import BeautifulSoup
import requests
from urllib.parse import urlencode, urlparse
import time

ROOT = "https://blitztoons.com"
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 15; Mobile) AppleWebKit/537.36 Chrome/130.0.0.0 Mobile Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"})

queries = [
    {},
    {"q": "mortos"}, {"busca": "mortos"}, {"search": "mortos"},
    {"pesquisa": "mortos"}, {"nome": "mortos"}, {"titulo": "mortos"}, {"termo": "mortos"},
    {"genero": "acao"}, {"tipo": "comic"}, {"status": "ongoing"},
    {"ordem": "recentes", "p": "2"},
]
for params in queries:
    url = ROOT + "/obras" + ("?" + urlencode(params) if params else "")
    print("\nURL", url, flush=True)
    try:
        response = session.get(url, timeout=20)
        print("status", response.status_code, "final", response.url, "html", len(response.content))
        if response.status_code != 200:
            print("body", response.text[:200])
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        h1 = soup.select_one("h1")
        print("heading", h1.get_text(" ", strip=True) if h1 else "")
        main = soup.select_one("main") or soup
        texts = main.get_text(" ", strip=True)
        for needle in ("obras encontradas", "obra encontrada", "Nenhuma obra"):
            i = texts.find(needle)
            if i != -1: print("summary", texts[max(i - 20, 0):i + 60])
        anchors = main.select("a[href*='/obra/']")
        print("links", len(anchors))
        for a in anchors[:4]: print("card", a.get("href"), a.get_text(" ", strip=True)[:130], "html", str(a)[:400])
        if not params:
            for f in soup.select("form"):
                print("FORM", str(f)[:3500])
            for el in soup.select("input, select"):
                print("FIELD", str(el)[:700])
            for a in main.select("a[href*='genero=']")[:8]:
                print("GENRE", a.get_text(" ", strip=True), a.get("href"))
            for a in main.select("a[href*='ordem=']")[:5]:
                print("SORT", a.get_text(" ", strip=True), a.get("href"))
    except Exception as e:
        print("ERROR", repr(e))
    time.sleep(0.6)


# Diagnostico da leitura (nao acessa capitulos restritos).
# O catalogo pode continuar funcionando enquanto imagens passam a ser carregadas por JS.
print("\n=== DIAGNOSTICO DO LEITOR ===", flush=True)
import re
from urllib.parse import urlsplit
from collections import Counter
for chapter in ("/ler/pronto-acao/2", "/ler/mestre-dos-dragoes/268"):
    url = ROOT + chapter
    try:
        response = session.get(url, timeout=25, headers={"Referer": ROOT + "/"})
        soup = BeautifulSoup(response.text, "html.parser")
        print("\nCHAPTER", chapter, "HTTP", response.status_code, "final", response.url,
              "html_bytes", len(response.content), "content_type", response.headers.get("Content-Type"),
              "redirects", len(response.history), flush=True)
        print("images_total", len(soup.select("img")),
              "alt_paginas", len(soup.select("img[alt^='Página ']")),
              "scripts", len(soup.select("script")),
              "next_data", bool(soup.select_one("script#__NEXT_DATA__")),
              "rsc_flight", "__next_f.push" in response.text,
              flush=True)
        for img in soup.select("img")[:12]:
            print("IMG", {
                "alt": img.get("alt", "")[:48],
                "src": img.get("src", "")[:140],
                "data-src": img.get("data-src", "")[:140],
                "srcset": img.get("srcset", "")[:140],
                "loading": img.get("loading"),
            }, flush=True)
        for script in soup.select("script[src]")[:20]:
            print("SCRIPT", script.get("src", "")[:160], flush=True)
        for term in ("capitulo-imagens", "chapter-images", "chapterImages", "pageImages",
                     "imageUrls", "images", "paginas", "pages", "/api/", "reader"):
            matches = list(re.finditer(re.escape(term), response.text, re.I))
            if matches:
                print("PATTERN", term, "count", len(matches), flush=True)
                for match in matches[:2]:
                    snippet = response.text[max(0, match.start()-110):match.end()+140]
                    print("CONTEXT", re.sub(r"\s+", " ", snippet)[:320], flush=True)
        urls = [
            img.get("data-src") or img.get("data-original") or img.get("src")
            for img in soup.select("img[alt^='Página ']")
        ]
        for src in [u for u in urls if u and u.startswith("http")][:2]:
            try:
                im = session.get(src, headers={"Referer": url}, timeout=15, stream=True)
                print("IMAGE_TEST", urlsplit(src).netloc, urlsplit(src).path[:140],
                      "HTTP", im.status_code, "type", im.headers.get("Content-Type"),
                      "redirects", len(im.history), flush=True)
                im.close()
            except Exception as exc:
                print("IMAGE_ERROR", type(exc).__name__, str(exc)[:120], flush=True)
    except Exception as exc:
        print("CHAPTER_ERROR", chapter, type(exc).__name__, str(exc)[:240], flush=True)
