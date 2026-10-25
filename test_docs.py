#!/usr/bin/env python3
"""Comprueba que los rangos de fichaje siguen iguales en el codigo y en los
documentos. Si alguien cambia un rango en sigma_punch.py y olvida los docs
(esto ha pasado: el README decia 09:46 y la banda empieza en 09:40), este
test falla y el despliegue de Pages se para.

Solo usa la libreria estandar. No toca red ni credenciales.

  python3 test_docs.py      -> todo OK (salida 0) o FAIL (salida 1)
"""
import ast
import fnmatch
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails = []


def ok(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def hhmmss(s):
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


# --- 1. constantes de sigma_punch.py --------------------------------------
NOMBRES = ("ENTRY_START", "ENTRY_SPAN", "EXIT_START", "EXIT_SPAN",
           "ENTRY_TXT", "EXIT_TXT", "LAST_DAY",
           "ENTRY_START_2", "ENTRY_SPAN_2", "EXIT_START_2", "EXIT_SPAN_2",
           "ENTRY_TXT_2", "EXIT_TXT_2", "VENTANA_NUEVA_DESDE")
vals = {}
for node in ast.parse((HERE / "sigma_punch.py").read_text(encoding="utf-8")).body:
    if (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in NOMBRES):
        try:
            vals[node.targets[0].id] = eval(
                compile(ast.Expression(node.value), "<c>", "eval"),
                {"__builtins__": {}})
        except Exception as exc:  # noqa: BLE001
            fails.append(f"constante {node.targets[0].id}: {exc}")

faltan = [n for n in NOMBRES if n not in vals]
ok(not faltan, f"constantes presentes en sigma_punch.py (faltan: {faltan})")

# --- 2. coherencia interna: ventana calculada vs texto mostrado ----------
vent = {
    "entrada": (vals["ENTRY_START"], vals["ENTRY_START"] + vals["ENTRY_SPAN"]),
    "salida": (vals["EXIT_START"], vals["EXIT_START"] + vals["EXIT_SPAN"]),
}
vent2 = {
    "entrada": (vals["ENTRY_START_2"], vals["ENTRY_START_2"] + vals["ENTRY_SPAN_2"]),
    "salida": (vals["EXIT_START_2"], vals["EXIT_START_2"] + vals["EXIT_SPAN_2"]),
}
ok(vals["ENTRY_TXT"] == f'{hhmmss(vent["entrada"][0])}-{hhmmss(vent["entrada"][1])}',
   f'ENTRY_TXT coherente con ENTRY_START/SPAN -> {vals["ENTRY_TXT"]}')
ok(vals["EXIT_TXT"] == f'{hhmmss(vent["salida"][0])}-{hhmmss(vent["salida"][1])}',
   f'EXIT_TXT coherente con EXIT_START/SPAN -> {vals["EXIT_TXT"]}')
ok(vals["ENTRY_TXT_2"] == f'{hhmmss(vent2["entrada"][0])}-{hhmmss(vent2["entrada"][1])}',
   f'ENTRY_TXT_2 coherente con ENTRY_START_2/SPAN_2 -> {vals["ENTRY_TXT_2"]}')
ok(vals["EXIT_TXT_2"] == f'{hhmmss(vent2["salida"][0])}-{hhmmss(vent2["salida"][1])}',
   f'EXIT_TXT_2 coherente con EXIT_START_2/SPAN_2 -> {vals["EXIT_TXT_2"]}')

# --- 2b. la ventana antigua: salida = entrada + 8 h exactas ---------------
ok(vent["salida"][0] - vent["entrada"][0] == 8 * 3600
   and vent["salida"][1] - vent["entrada"][1] == 8 * 3600,
   "ventana antigua: salida = entrada + 8 h (los dos extremos)")

# --- 3. la politica en si: no ha cambiado de sitio ------------------------
ok(vent["entrada"] == (10 * 3600 + 5 * 60, 10 * 3600 + 8 * 60 + 59),
   "ventana de entrada antigua fijada en 10:05:00-10:08:59")
ok(vent["salida"] == (18 * 3600 + 5 * 60, 18 * 3600 + 8 * 60 + 59),
   "ventana de salida antigua fijada en 18:05:00-18:08:59")
ok(vals["ENTRY_SPAN"] == 239 and vals["EXIT_SPAN"] == 239,
   "duraciones antiguas: entrada 239 s, salida 239 s")
ok(vent2["entrada"] == (9 * 3600 + 59 * 60, 10 * 3600 + 1 * 60 + 59),
   "ventana de entrada nueva fijada en 09:59:00-10:01:59")
ok(vent2["salida"] == (18 * 3600, 18 * 3600 + 8 * 60 + 59),
   "ventana de salida nueva fijada en 18:00:00-18:08:59")
ok(vals["ENTRY_SPAN_2"] == 179 and vals["EXIT_SPAN_2"] == 539,
   "duraciones nuevas: entrada 179 s, salida 539 s (9 min)")
ok(vals["VENTANA_NUEVA_DESDE"] == "19/10/2026",
   f'VENTANA_NUEVA_DESDE = {vals["VENTANA_NUEVA_DESDE"]}')

# --- 4. cada doc sigue mencionando los extremos ---------------------------
DOCS = ("README.md", "INSTRUCCIONES.txt", "instrucciones.html", "reloj.sh")
for doc in DOCS:
    txt = (HERE / doc).read_text(encoding="utf-8")
    for tok in ("10:05", "10:08", "18:05", "18:08",
                "09:59", "10:01", "18:00"):
        ok(tok in txt, f"{doc} menciona {tok}")

# --- 5. sin restos de los rangos viejos -----------------------------------
# 18:10:59 el final viejo de la salida; 10:11/18:11:59/10:10:00 los finales
# viejos de la entrada; y los rangos anteriores a este cambio
# (10:06-10:09 / 18:06-18:09). OJO: 18:02 y 18:08 ya NO son viejos: la
# ventana nueva de salida acaba en 18:08:59.
VIEJOS = ("18:10:59", "10:11", "18:11:59", "10:10:00",
          "10:06", "10:09", "18:06", "18:09")
for doc in DOCS:
    txt = (HERE / doc).read_text(encoding="utf-8")
    for viejo in VIEJOS:
        ok(viejo not in txt, f"{doc} sin restos de rangos viejos ({viejo})")

# --- 6. las bandas del reloj cubren las dos ventanas ----------------------
# Los jobs corren cada 15 min, así que la banda tiene que ser continua y
# tener mas de 15 min, o podria saltarse la ventana.
reloj = (HERE / "reloj.sh").read_text(encoding="utf-8")
globs = re.findall(r"^\s*([0-9|\[\]-]+)\)\s+M=(--\w+)", reloj, re.M)
for nombre, v in (("antigua", vent), ("nueva", vent2)):
    for modo, (a, b) in v.items():
        flag = "--entry" if modo == "entrada" else "--exit"
        patrones = [p for pat, m in globs if m == flag for p in pat.split("|")]
        ok(bool(patrones), f"reloj.sh declara banda para {modo} ({nombre})")
        cubren = [
            f"{t // 3600:02d}{(t % 3600) // 60:02d}"
            for t in range(a, b + 1, 60)
            if any(fnmatch.fnmatch(f"{t // 3600:02d}{(t % 3600) // 60:02d}", p)
                   for p in patrones)
        ]
        total = len(list(range(a, b + 1, 60)))
        ok(len(cubren) == total,
           f"reloj.sh: banda {modo} ({nombre}) cubre toda la ventana "
           f"({len(cubren)}/{total} minutos)")
for modo, (a, b) in vent.items():
    flag = "--entry" if modo == "entrada" else "--exit"
    patrones = [p for pat, m in globs if m == flag for p in pat.split("|")]
    if patrones:
        todos = sorted(
            int(f"{h:02d}{m:02d}")
            for h in range(24) for m in range(60)
            if any(fnmatch.fnmatch(f"{h:02d}{m:02d}", p) for p in patrones)
        )
        minutos = [(t // 100) * 60 + t % 100 for t in todos]
        continuo = (minutos == list(range(minutos[0], minutos[-1] + 1))
                    if minutos else False)
        dur = (minutos[-1] - minutos[0] + 1) if minutos else 0
        ok(continuo and dur >= 16,
           f"reloj.sh: banda {modo} continua de {dur} min (>=16 para un "
           f"job de 15 min)")

# --- 7. ultimo dia coherente en el codigo y en los docs -------------------
ok(vals["LAST_DAY"] == "30/10/2026", f'LAST_DAY = {vals["LAST_DAY"]}')
for doc in ("README.md", "INSTRUCCIONES.txt", "instrucciones.html"):
    txt = (HERE / doc).read_text(encoding="utf-8")
    ok(vals["LAST_DAY"] in txt, f"{doc} menciona {vals['LAST_DAY']}")

# --- 8. los `grep` de verificacion del instrucciones.html apuntan a algo
#        que realmente esta en el repositorio ------------------------------
html = (HERE / "instrucciones.html").read_text(encoding="utf-8")
for patron, fichero in re.findall(r'grep -c "([^"]+)" ([A-Za-z0-9_./]+)', html):
    if (HERE / fichero).exists():
        contenido = (HERE / fichero).read_text(encoding="utf-8")
        ok(patron in contenido,
           f'instrucciones.html: "{patron}" esta en {fichero}')
for url in re.findall(r"sigma-fichaje/main/([A-Za-z0-9_./-]+)", html):
    ok((HERE / url).exists(), f"instrucciones.html descarga {url} (existe)")

print()
if fails:
    print(f"FALLOS: {len(fails)}")
    sys.exit(1)
print("TODO OK")
