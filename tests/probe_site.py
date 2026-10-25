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
