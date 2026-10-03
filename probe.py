#!/usr/bin/env python3
"""Sonda: entra en SigmaTime y enseña qué devuelve el portal.

Solo diagnostica. NO ficha nada.
Usa el mismo cliente HTTP que sigma_punch.py (solo librerias de Python).
Las credenciales las lee de config.json (nunca se suben a GitHub).
"""
import re
import sys

import sigma_punch as sp


def main():
    s = sp.Session()

    print("=== 1. LOGIN ===")
    try:
        ok, msg = sp.login(s)
        print("login:", ok, "-", msg)
    except Exception as e:
        print("login: EXCEPCION", type(e).__name__, e)
        ok = False

    print("\n=== 2. PORTAL ===")
    try:
        html, final = s.post(f"{sp.BASE_URL}/acceso.php",
                             {"cf_usu": sp.EMAIL, "cf_pass": sp.PASS,
                              "btn_acceso": ""})
        print("(esta es la respuesta que recibe el programa tras el login)")
        print("bytes:", len(html))
        print("URL final:", final)
        print("pide login otra vez?", 'name="cf_usu"' in html)
        print("tiene btn_fichar?", "btn_fichar" in html)
        print("menciona portal-empleado?", "portal-empleado" in html)
        print("menciona Listado de mis?", "Listado de mis" in html)

        print("\n--- donde se pierde: GET al portal ---")
        ph, pfinal = s.get(f"{sp.BASE_URL}/v2/portal-empleado.php",
                           referer=f"{sp.BASE_URL}/acceso.php")
        print("bytes:", len(ph), "| URL final:", pfinal)
        print("tiene btn_fichar?", "btn_fichar" in ph)
        print("menciona Listado de mis?", "Listado de mis" in ph)
        m = re.search(r'name="c_usu"[^>]*value="([a-f0-9]+)"', ph)
        print("hash c_usu:", m.group(1) if m else "NO ENCONTRADO")

        print("\n--- formularios ---")
        for f in re.findall(r"<form[^>]*>", ph, re.I)[:6]:
            print(" ", f[:170])
        print("--- hidden ---")
        for i in re.findall(r'<input[^>]*>', ph, re.I)[:15]:
            if "hidden" in i.lower():
                print(" ", i[:170])
        print("--- botones ---")
        for b in re.findall(r"<(?:button|input)[^>]*>", ph, re.I)[:20]:
            if "submit" in b.lower() or "btn_" in b.lower():
                print(" ", b[:170])

        print("\n=== 3. PRIMEROS 1800 CARACTERES DEL PORTAL ===")
        print(ph[:1800])
    except Exception as e:
        print("EXCEPCION:", type(e).__name__, e)


if __name__ == "__main__":
    main()