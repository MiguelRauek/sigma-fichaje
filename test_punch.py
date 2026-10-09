#!/usr/bin/env python3
"""Tests offline del fix: decidir() + punch_once (sin red, sin credenciales)."""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sigma_punch as sp

# No tocar el fichaje.log del repo: el test escribe en un temporal.
sp.LOG_PATH = str(Path(tempfile.gettempdir()) / "fichaje-test.log")
sp.LOCK_PATH = str(Path(tempfile.gettempdir()) / "fichaje-test.lock")
sp.ALARM_MARKER = str(Path(tempfile.gettempdir()) / "fichaje-test-alarma.txt")

fails = []

def check(name, got, want):
    ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"{'OK ' if ok else 'FAIL'} {name}")

# --- 1. matriz decidir() -------------------------------------------------
# segundos del dia: 09:00=32400 10:06=36360 10:07=36420 10:09:59=36599
#                    10:11=36660 12:00=43200 18:06=65160 18:07=65220
#                    18:09:59=65399 18:10:00=65400 18:11=65460
M = [
    # (mode, c_tip, before, ahora, accion_esperada, porque)
    ("entry", "1", 0, 36420, "pulsar", "normal: dia limpio, boton verde, en ventana"),
    ("entry", "2", 1, 36420, "hecho",  "BUG DE HOY: entry repetido con boton rojo"),
    ("entry", "1", 1, 36420, "hecho",  "entrada ya hecha"),
    ("entry", "2", 0, 36420, "fallo",  "rojo sin fichajes: no fichar al reves"),
    ("entry", "4", 0, 36420, "fallo",  "c_tip desconocido"),
    ("entry", "1", 0, 36660, "fallo",  "ENTRADA FUERA DE VENTANA (10:11)"),
    ("entry", "1", 0, 32400, "fallo",  "entrada antes de las 10:06 (09:00)"),
    ("exit",  "2", 1, 65220, "pulsar", "normal: boton rojo en la ventana de salida"),
    ("exit",  "3", 1, 65220, "pulsar", "c_tip=3 tambien es salida"),
    ("exit",  "1", 2, 65220, "hecho",  "salida ya hecha y boton vuelve a verde"),
    ("exit",  "2", 2, 65220, "hecho",  "2 fichajes = hecha; nunca un tercero"),
    ("exit",  "1", 1, 65220, "fallo",  "boton en entrada con entrada ya hecha"),
    ("exit",  "1", 0, 65220, "fallo",  "sin entrada todavia"),
    ("exit",  "2", 0, 65220, "fallo",  "rojo sin entrada: no se ficha la salida"),
    ("exit",  "2", 1, 36420, "fallo",  "CLAVE: SALIDA A LAS 10:07 DE LA MANANA"),
    ("exit",  "2", 1, 43200, "fallo",  "salida a mediodia (12:00)"),
    ("exit",  "2", 1, 65399, "pulsar", "ultimo segundo de la ventana (18:09:59)"),
    ("exit",  "2", 1, 65400, "fallo",  "18:10:00 ya fuera de la ventana de salida"),
    ("exit",  "2", 1, 65460, "fallo",  "salida despues de las 18:09:59"),
    ("",      "1", 0, 36420, "pulsar", "--test dentro de la ventana de entrada"),
    ("",      "2", 1, 65220, "pulsar", "--test dentro de la ventana de salida"),
    ("",      "1", 0, 43200, "fallo",  "--test fuera de ventana: no se puede"),
    ("",      "4", 0, 36420, "fallo",  "c_tip desconocido en --test"),
]
for mode, ct, before, ahora, want, why in M:
    got = sp.decidir(mode, ct, before, ahora)
    ok = got[0] == want
    if not ok:
        fails.append(f"decidir({mode},{ct},{before},{ahora}) -> {got} want {want}")
    print(f"{'OK ' if ok else 'FAIL'} decidir({mode or 'test'},c_tip={ct},"
          f"before={before},ahora={ahora}) -> {want} ({why})")

# limites de ventana
check("en_ventana entry 10:06:00", sp.en_ventana("entry", 36360), True)
check("en_ventana entry 10:09:59", sp.en_ventana("entry", 36599), True)
check("en_ventana entry 10:10:00", sp.en_ventana("entry", 36600), False)
check("en_ventana exit 18:06:00", sp.en_ventana("exit", 65160), True)
check("en_ventana exit 18:09:59", sp.en_ventana("exit", 65399), True)
check("en_ventana exit 18:10:00", sp.en_ventana("exit", 65400), False)
check("en_ventana exit 18:11:00", sp.en_ventana("exit", 65460), False)
check("en_ventana exit a las 10:07", sp.en_ventana("exit", 36420), False)

# el segundo de fichaje nunca termina en :00 (10:07:00 no se usa)
viol = []
for _ in range(5000):
    for f, a, b in ((sp.target_entry, sp.ENTRY_START,
                     sp.ENTRY_START + sp.ENTRY_SPAN),
                    (sp.target_exit, sp.EXIT_START,
                     sp.EXIT_START + sp.EXIT_SPAN)):
        t = f()
        if not (a <= t <= b and t % 60 != 0):
            viol.append((f.__name__, t))
check("5000 tiradas: nunca en punto (:00) y dentro de la ventana", viol, [])

# --- 2. helpers de HTML --------------------------------------------------
today = sp.now_local().strftime("%d/%m/%Y")
verde = (f'<input type="hidden" name="c_tip" value="1">'
         f'<strong>{today}</strong> <font color="green">10:06:00</font><br>')
rojo = (f'<input type="hidden" value="2" name="c_tip">'
        f'<strong>{today}</strong> <font color="red">10:06:00</font> '
        f'<font color="red">18:07:11</font><br>')
check("leer_c_tip verde", sp.leer_c_tip(verde), "1")
check("leer_c_tip rojo invertido", sp.leer_c_tip(rojo), "2")
check("estado_boton verde", sp.estado_boton(verde)[0], "1")
check("count_today 1", sp.count_today(verde), 1)
check("count_today 2", sp.count_today(rojo), 2)
check("fallo_es_de_red si", sp.fallo_es_de_red("error: URLError: sin conexión"), True)
check("fallo_es_de_red no", sp.fallo_es_de_red("login fallido (credenciales incorrectas)"), False)

# --- 3. punch_once con run_punch simulado -------------------------------
alarms, avisos = [], []
sp.alarma = lambda *a: alarms.append(a[0])
sp.aviso = lambda m: avisos.append(m)
sp.time.sleep = lambda *_: None
sp.wait_until = lambda *a, **k: None

def fijar_hora(h, m, s):
    d = datetime.now(sp.TZ).replace(hour=h, minute=m, second=s, microsecond=0)
    sp.now_local = lambda: d

# A) ventana pasada + ya hecho -> 0, sin alarma
seq = iter([(True, "la entrada ya estaba registrada (hoy: 1)")])
sp.run_punch = lambda mode="", pulsar=True: next(seq)
fijar_hora(10, 11, 0); alarms.clear(); avisos.clear()
check("A ventana pasada+hecho -> 0", sp.punch_once("entry", "T-A"), 0)
check("A sin alarma", alarms, [])

# B) ventana pasada + NO hecho -> 1 + alarma
sp.run_punch = lambda mode="", pulsar=True: (
    False, "solo consulta: todavia no estaba hecho (ENTRADA (boton verde))")
fijar_hora(10, 11, 0); alarms.clear()
check("B ventana pasada+no hecho -> 1", sp.punch_once("entry", "T-B"), 1)
check("B alarma disparada", len(alarms), 1)

# C) reintento: fallo de verificacion y luego "hecho" -> 0, sin aviso
calls = []
def sim_c(mode="", pulsar=True):
    calls.append((mode, pulsar))
    if len(calls) == 1:
        return False, "el fichaje no subio en la verificacion"
    return True, "la entrada ya estaba registrada (hoy: 1)"
sp.run_punch = sim_c
fijar_hora(10, 6, 0); alarms.clear(); avisos.clear(); calls.clear()
check("C reintento hecho -> 0", sp.punch_once("entry", "T-C"), 0)
check("C sin alarma/aviso", (alarms, avisos), ([], []))
check("C paso modo entry", [c[0] for c in calls], ["entry", "entry"])

# D) internet caido toda la ventana -> 1 + alarma de red
sp.run_punch = lambda mode="", pulsar=True: (
    False, "fallo de red: URLError: <urlopen error timed out>")
fijar_hora(10, 6, 0); alarms.clear(); avisos.clear()
check("D sin internet -> 1", sp.punch_once("entry", "T-D"), 1)
check("D alarma de red", len(alarms), 1)
check("D mensaje contiene internet", "internet" in alarms[0], True)

# E) salida: 1 intento falla y luego hecho -> 0
calls.clear(); sp.run_punch = sim_c
fijar_hora(18, 6, 0); alarms.clear(); avisos.clear()
check("E exit -> 0", sp.punch_once("exit", "T-E"), 0)
check("E modo exit", [c[0] for c in calls], ["exit", "exit"])

# F) cerrojo ocupado al principio y luego libre -> se espera y se consigue
orig_acquire = sp.acquire_lock
lock_calls = []
def sim_lock():
    lock_calls.append(1)
    return len(lock_calls) >= 2
sp.acquire_lock = sim_lock
fijar_hora(10, 6, 0)
check("F cerrojo ocupado->libre", sp._esperar_cerrojo(36599), True)
check("F reintento de cerrojo", len(lock_calls), 2)

# G) cerrojo ocupado hasta el cierre de la ventana -> False
sp.acquire_lock = lambda: False
fijar_hora(10, 10, 0)
check("G cerrojo ocupado al cerrarse la ventana", sp._esperar_cerrojo(36599), False)
sp.acquire_lock = orig_acquire

print()
if fails:
    print(f"{len(fails)} FALLOS:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("TODO OK")
