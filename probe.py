#!/usr/bin/env python3
"""Sonda: entra en SigmaTime y enseña qué devuelve el portal.

Solo diagnostica. NO ficha nada.
Las credenciales las lee de config.json (nunca se suben a GitHub).
"""
import json
import os
import re
import sys

BASE = "https://sigmatime.es"
HERE = os.path.dirname(os.path.abspath(__file__))


def creds():
    try:
        with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
            c = json.load(f)
        return c.get("email", ""), c.get("pass", "")
    except Exception as e:
        print("No se pudo leer config.json:", e)
        sys.exit(1)


def main():
    try:
        from requests import Session
    except ImportError:
        print("Falta requests. Instala con: pip install requests")
        sys.exit(1)

    email, pw = creds()
    s = Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 13)"})

    print("=== 1. LOGIN ===")
    r = s.post(f"{BASE}/acceso.php",
               data={"cf_usu": email, "cf_pass": pw, "btn_acceso": ""},
               timeout=40, allow_redirects=True)
    print("URL final:", r.url)
    print("HTTP:", r.status_code, "| bytes:", len(r.text))
    print("¿pide login otra vez (name=cf_usu)?", 'name="cf_usu"' in r.text)
    print("¿tiene btn_fichar?", "btn_fichar" in r.text)
    print("¿menciona portal-empleado?", "portal-empleado" in r.text)

    print("\n=== 2. PORTAL ===")
    p = s.get(f"{BASE}/v2/portal-empleado.php",
              headers={"Referer": f"{BASE}/acceso.php"}, timeout=40)
    html = p.text
    print("URL final:", p.url)
    print("HTTP:", p.status_code, "| bytes:", len(html))
    print("¿btn_fichar?", "btn_fichar" in html)
    print("¿Listado de mis?", "Listado de mis" in html)
    m = re.search(r'name="c_usu"[^>]*value="([a-f0-9]+)"', html)
    print("hash c_usu:", m.group(1) if m else "NO ENCONTRADO")

    print("\n=== 3. FORMULARIOS EN LA PAGINA ===")
    for f in re.findall(r"<form[^>]*>", html, re.I)[:6]:
        print(" ", f[:160])
    print("inputshidden:")
    for i in re.findall(r'<input[^>]*type="hidden"[^>]*>', html, re.I)[:12]:
        print(" ", i[:160])
    print("botones:")
    for b in re.findall(r'<(?:button|input)[^>]*(?:type="submit"|name="btn_[^"]*")[^>]*>', html, re.I)[:8]:
        print(" ", b[:160])

    print("\n=== 4. INICIO DE LA PAGINA (2500 caracteres) ===")
    print(html[:2500])


if __name__ == "__main__":
    main()