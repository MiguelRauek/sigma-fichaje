#!/usr/bin/env python3
"""
SigmaFichaje — fichaje automático en SigmaTime (sigmatime.es).

Ejecuta el fichaje de entrada o salida en el horario aleatorio configurado.
Sin notificaciones de ningún tipo (ni Telegram ni email): solo registra la
hora de cada fichaje. Sin dependencias externas (solo stdlib), pensado para
GitHub Actions.

Uso:
  python3 sigma_punch.py           # modo diario: entrada + salida (para Pydroid)
  python3 sigma_punch.py --entry   # entrada: aleatoria entre 10:05 y 10:08
  python3 sigma_punch.py --exit    # salida:  segundo aleatorio en [18:00:00, 18:00:59]
  python3 sigma_punch.py --test    # fichar ya (para probar)
  python3 sigma_punch.py --check   # comprobar login y portal SIN fichar nada
  python3 sigma_punch.py --ver     # ver los fichajes de hoy (igual que en la web)

Modo diario (Pydroid): sin argumentos ficha la entrada y luego la salida en la
misma ejecución. Se lanza por la mañana y queda esperando todo el día. Si se
lanza por la noche (después de las 18:02), espera hasta la entrada del día
siguiente y ficha entrada y salida de ese día.

Variables de entorno:
  SIGMA_EMAIL, SIGMA_PASS          # credenciales de sigmatime.es (obligatorias)
  SIGMA_BASE_URL                   # por defecto https://sigmatime.es
  TZ                               # zona horaria, por defecto Europe/Madrid

Credenciales alternativas (para móvil/Pydroid):
  config.json junto al script con {"email": "...", "pass": "..."} se usa si
  faltan SIGMA_EMAIL/SIGMA_PASS. Nunca subir config.json a GitHub.

Flujo (verificado contra sigmatime.es):
  1. POST cf_usu + cf_pass a /acceso.php            -> cookie de sesión
  2. GET  /v2/portal-empleado.php                   -> hash c_usu + fichajes de hoy
  3. POST c_usu + c_tip=1 + fic_subtipo=0 + btn_fichar -> registra el fichaje
  4. GET  /v2/portal-empleado.php                   -> verificar que subió en 1
"""

import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from zoneinfo import ZoneInfo

BASE_URL = os.environ.get("SIGMA_BASE_URL", "https://sigmatime.es").rstrip("/")

try:
    TZ = ZoneInfo(os.environ.get("TZ", "Europe/Madrid"))
except Exception:
    # Android/Pydroid puede no traer la base de datos de zonas: usar la local del dispositivo.
    TZ = datetime.now().astimezone().tzinfo

def _load_credentials():
    """Credenciales: variables de entorno o config.json junto al script."""
    email = os.environ.get("SIGMA_EMAIL", "")
    password = os.environ.get("SIGMA_PASS", "")
    if email and password:
        return email, password
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("email", ""), cfg.get("pass", "")
    except (OSError, ValueError):
        return "", ""

EMAIL, PASS = _load_credentials()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "fichaje.log")
LOCK_PATH = os.path.join(SCRIPT_DIR, "fichaje.lock")

# Último día del modo permanente (DD/MM/AAAA). Vacío = sin límite.
# Poner "" para que no termine nunca, o una fecha para que se apague solo.
LAST_DAY = "25/10/2026"

def log(msg: str) -> None:
    """Escribe en pantalla y en fichaje.log (para ver si arrancó el boot script)."""
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(msg)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {msg}\n")
    except OSError:
        pass

def load_skip_dates() -> set:
    """Días en los que NO se ficha: archivo skip_dates.txt junto al script.
    Una fecha por línea en formato DD/MM/YYYY; las líneas con # son comentarios."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skip_dates.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f
                    if line.strip() and not line.strip().startswith("#")}
    except OSError:
        return set()

SKIP_DATES = load_skip_dates()

def today_skipped() -> bool:
    """True si hoy está en skip_dates.txt (no hay que fichar)."""
    return now_local().strftime("%d/%m/%Y") in SKIP_DATES

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ---------------------------------------------------------------------------
# Horarios aleatorios
# ---------------------------------------------------------------------------

def now_local() -> datetime:
    return datetime.now(TZ)

def seconds_of_day(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second

# Ventanas de fichaje.
#   Entrada: 10:00:00 - 10:02:59   (pedido: "entre las 10 y las 10.02")
#   Salida : 18:00:00 - 18:02:59   (pedido: "entre 18 y 18.02")
# Dentro de cada ventana se sortea un segundo, para no fichar siempre igual.
ENTRY_START = 10 * 3600               # 10:00:00
ENTRY_SPAN = 179                      # -> hasta 10:02:59
EXIT_START = 18 * 3600                # 18:00:00
EXIT_SPAN = 179                       # -> hasta 18:02:59

ENTRY_TXT = "10:00:00-10:02:59"
EXIT_TXT = "18:00:00-18:02:59"

def target_entry() -> int:
    """Segundo aleatorio uniforme en [10:00:00, 10:02:59]."""
    return ENTRY_START + random.randint(0, ENTRY_SPAN)

def target_exit() -> int:
    """Segundo aleatorio uniforme en [18:00:00, 18:02:59]."""
    return EXIT_START + random.randint(0, EXIT_SPAN)

def wait_until(target_secs: int, label: str) -> None:
    """Espera hasta que la hora local alcance target_secs (en tramos de 60 s)."""
    while True:
        now = now_local()
        if seconds_of_day(now) >= target_secs:
            return
        delta = target_secs - seconds_of_day(now)
        time.sleep(min(delta, 60))

def wait_until_datetime(target_dt: datetime, label: str) -> None:
    """Espera hasta que la hora local alcance target_dt (en tramos de 60 s)."""
    while True:
        now = now_local()
        if now >= target_dt:
            return
        delta = (target_dt - now).total_seconds()
        time.sleep(min(delta, 60))

# ---------------------------------------------------------------------------
# Cliente HTTP con cookies de sesión
# ---------------------------------------------------------------------------

class Session:
    def __init__(self):
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def _request(self, url: str, data: dict | None, referer: str | None):
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        if data is not None:
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body, headers=headers)
        else:
            req = urllib.request.Request(url, headers=headers)
        with self.opener.open(req, timeout=30) as resp:
            return resp.geturl(), resp.read().decode("utf-8", "replace")

    def get(self, url: str, referer: str | None = None):
        return self._request(url, None, referer)

    def post(self, url: str, data: dict, referer: str | None = None):
        return self._request(url, data, referer)

# ---------------------------------------------------------------------------
# Flujo de fichaje
# ---------------------------------------------------------------------------

def login(s: Session):
    # Session devuelve (url_final, html). Ojo con el orden.
    final_url, html = s.post(
        f"{BASE_URL}/acceso.php",
        {"cf_usu": EMAIL, "cf_pass": PASS, "btn_acceso": ""},
    )
    # La web nueva, tras el login, devuelve una pagina que solo lleva un
    # <script> que abre /v2/portal-empleado.php. Si sigue pidiendo login,
    # el usuario o la contrasena no son correctos.
    if 'name="cf_usu"' in html and "portal-empleado.php" not in html:
        return False, "login fallido (credenciales incorrectas)"
    return True, "login ok"

def get_portal(s: Session):
    final_url, html = s.get(f"{BASE_URL}/v2/portal-empleado.php",
                            referer=f"{BASE_URL}/acceso.php")
    if 'name="cf_usu"' in html:
        return None
    if "btn_fichar" not in html and "Listado de mis" not in html:
        return None
    return html

def extract_cusu(html: str):
    m = re.search(r'name="c_usu"[^>]*value="([a-f0-9]+)"', html)
    return m.group(1) if m else None

def list_today(html: str) -> list:
    """Devuelve las horas (HH:MM:SS) de los fichajes de hoy, como en la web.

    El HTML real es una sola línea con <br> entre días:
      <strong>19/09/2026</strong> <font color="green">09:35:42</font> ... <br>
    """
    today = now_local().strftime("%d/%m/%Y")
    m = re.search(r"<strong>" + today + r"</strong>([\s\S]*?)(?:<br>|</p>)", html)
    if not m:
        return []
    return re.findall(r"\d{2}:\d{2}:\d{2}", m.group(1))

def count_today(html: str) -> int:
    """Cuenta los fichajes (HH:MM:SS) de hoy en el listado del portal."""
    return len(list_today(html))

def do_punch(s: Session, cusu: str) -> str:
    _url, html = s.post(
        f"{BASE_URL}/v2/portal-empleado.php",
        {
            "c_usu": cusu,
            "c_tip": "1",
            "c_coor2": "",
            "fic_subtipo": "0",  # 0 = Horas ordinarias
            "btn_fichar": "",
        },
        referer=f"{BASE_URL}/v2/portal-empleado.php",
    )
    return html

def run_punch():
    """Intenta fichar una vez. NUNCA lanza excepciones.

    Un corte de internet (URLError/DNS) o cualquier fallo inesperado se
    devuelve como (False, motivo) para que punch_once reintente. Antes un
    error de red tumbaba el proceso entero y se perdian los dos fichajes
    del dia.
    """
    try:
        s = Session()
        ok, msg = login(s)
        if not ok:
            return False, msg
        portal = get_portal(s)
        if portal is None:
            return False, "no se pudo leer el portal tras el login"
        before = count_today(portal)
        cusu = extract_cusu(portal)
        if not cusu:
            return False, f"no se encontró el hash c_usu (fichajes de hoy: {before})"
        do_punch(s, cusu)
        portal2 = get_portal(s)
        after = count_today(portal2) if portal2 is not None else -1
        if after == before + 1:
            return True, f"fichaje registrado (hoy: {before} → {after})"
        return False, f"el fichaje no se reflejó (antes={before}, después={after})"
    except Exception as e:          # red, DNS, portal caido, HTML raro...
        return False, f"fallo de conexión ({type(e).__name__}: {e})"

def run_check():
    """Comprueba login + portal y cuenta los fichajes de hoy, SIN fichar."""
    s = Session()
    ok, msg = login(s)
    if not ok:
        return False, msg
    portal = get_portal(s)
    if portal is None:
        return False, "no se pudo leer el portal tras el login"
    before = count_today(portal)
    cusu = extract_cusu(portal)
    if not cusu:
        return False, f"no se encontró el hash c_usu (fichajes de hoy: {before})"
    return True, f"login OK — c_usu={cusu} — fichajes de hoy: {before} (no se ha fichado nada)"

def run_ver():
    """Comprueba login + portal y muestra los fichajes de hoy como en la web."""
    s = Session()
    ok, msg = login(s)
    if not ok:
        return False, msg
    portal = get_portal(s)
    if portal is None:
        return False, "no se pudo leer el portal tras el login"
    cusu = extract_cusu(portal)
    times = list_today(portal)
    if not cusu:
        return False, f"no se encontró el hash c_usu (fichajes de hoy: {len(times)})"
    if not times:
        return True, f"login OK — c_usu={cusu} — hoy NO hay fichajes todavía"
    return True, f"login OK — c_usu={cusu} — fichajes de hoy: {', '.join(times)}"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def punch_once(mode: str, label: str) -> int:
    """Espera a la ventana del modo y ficha con reintentos. Devuelve 0 si OK."""
    base = datetime.combine(now_local().date(), datetime.min.time())

    if mode == "entry":
        target = target_entry()
        window_end, window_txt = ENTRY_START + ENTRY_SPAN, ENTRY_TXT
    elif mode == "exit":
        target = target_exit()
        window_end, window_txt = EXIT_START + EXIT_SPAN, EXIT_TXT
    else:
        target = seconds_of_day(now_local())
        window_end, window_txt = None, ""

    target_dt = base + timedelta(seconds=target)
    log(f"[{label}] objetivo: {target_dt.strftime('%H:%M:%S')} ({TZ})")

    if mode != "test":
        wait_until(target, label)

    # Reintentos. Las ventanas son de 3 minutos, asi que se insiste mas a
    # menudo que antes: la entrada hasta 8 veces cada 25 s y la salida hasta
    # 10 veces cada 18 s, para que quepan varias dentro de la ventana.
    delay, intentos = (25, 8) if mode == "entry" else (18, 10)
    for attempt in range(1, intentos + 1):
        if window_end is not None and seconds_of_day(now_local()) > window_end:
            log(f"[{label}] fuera de la ventana {window_txt}, no se reintenta")
            break
        ok, msg = run_punch()
        log(f"[{label}] intento {attempt}: {'OK' if ok else 'FALLO'} — {msg}")
        if ok:
            return 0
        if attempt < intentos:
            time.sleep(delay)
    return 1

def run_forever() -> int:
    """Modo permanente: ficha entrada y salida todos los días, solo.

    Se relanza a sí mismo cada día hasta LAST_DAY (inclusive) y ahí se apaga
    solo. Pensado para arrancar desde el autoarranque del móvil: una sola vez
    y se mantiene solo sin tener que hacer nada cada día.
    """
    log(f"[Permanente] arrancar — último día {LAST_DAY}")
    while True:
        hoy = now_local().strftime("%d/%m/%Y")
        if LAST_DAY and hoy > LAST_DAY:
            log(f"[Permanente] {hoy} es posterior a {LAST_DAY}; fin del periodo, saliendo")
            return 0
        if not LAST_DAY or hoy <= LAST_DAY:
            if today_skipped():
                log(f"[Permanente] {hoy} está en skip_dates.txt — no se ficha hoy")
            else:
                # Red de seguridad: si run_daily() lance cualquier excepcion
                # inesperada, el modo --forever sigue vivo para manana.
                try:
                    run_daily()
                except Exception as e:
                    log(f"[Permanente] ERROR inesperado: {type(e).__name__}: {e} "
                        f"— se continua, mañana se vuelve a intentar")
                    time.sleep(60)
        # Dorme hasta la entrada del día siguiente.
        manana = now_local() + timedelta(days=1)
        objetivo = manana.replace(hour=ENTRY_START // 3600,
                                  minute=(ENTRY_START % 3600) // 60,
                                  second=0, microsecond=0)
        segundos = (objetivo - now_local()).total_seconds()
        if segundos > 0:
            log(f"[Permanente] durmiendo hasta {objetivo.strftime('%d/%m %H:%M')}")
            time.sleep(segundos)

def run_daily() -> int:
    """Modo diario: entrada + salida en la misma ejecución.

    Si se lanza después de las 18:02 (las ventanas de hoy ya pasaron),
    espera hasta la entrada del día siguiente y ficha ese día.
    """
    now = now_local()
    if seconds_of_day(now) > 18 * 3600 + 119:
        tomorrow = now + timedelta(days=1)
        target_dt = tomorrow.replace(hour=ENTRY_START // 3600,
                                     minute=(ENTRY_START % 3600) // 60,
                                     second=0, microsecond=0)
        log(f"[Diario] hoy ya pasó; esperando a mañana {target_dt.strftime('%H:%M:%S')} ({TZ})")
        wait_until_datetime(target_dt, "Diario")
    rc1 = punch_once("entry", "Entrada")
    rc2 = punch_once("exit", "Salida")
    return 0 if (rc1 == 0 and rc2 == 0) else 1

def _lock_holder() -> int:
    """PID del proceso que ya está fichando, o 0 si no hay ninguno.

    Evita que el arranque automático (07:30) y una ejecución manual fichen
    los dos a la vez. Si el fichero existe pero el proceso ya no está vivo,
    el cerrojo está viejo y se puede reutilizar.
    """
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            pid = int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0
    if pid <= 0 or pid == os.getpid():
        return 0
    try:
        os.kill(pid, 0)  # solo comprueba si existe, no señal
        return pid
    except OSError:
        return 0

def acquire_lock() -> bool:
    """True si este proceso se queda con el cerrojo; False si ya hay otro."""
    pid = _lock_holder()
    if pid:
        return False
    try:
        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError:
        return True  # si no se puede escribir, no bloquear el fichaje
    return True

def release_lock() -> None:
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass

def main() -> int:
    if "--entry" in sys.argv:
        mode, label = "entry", "Entrada"
    elif "--exit" in sys.argv:
        mode, label = "exit", "Salida"
    elif "--test" in sys.argv:
        mode, label = "test", "Prueba"
    elif "--check" in sys.argv:
        mode, label = "check", "Check"
    elif "--ver" in sys.argv:
        mode, label = "ver", "Ver"
    elif "--forever" in sys.argv:
        # Modo permanente: todos los días hasta LAST_DAY, sin intervención.
        mode, label = "forever", "Permanente"
    else:
        # Sin argumentos: modo diario (entrada + salida), pensado para Pydroid.
        mode, label = "daily", "Diario"

    log(f"[{label}] arranque — modo={mode} pid={os.getpid()} argv={' '.join(sys.argv) or '(sin args)'}")

    if not EMAIL or not PASS:
        log("Faltan las variables SIGMA_EMAIL y SIGMA_PASS")
        return 2

    # Cerrojo: solo un proceso puede fichar a la vez (autoarranque + manual).
    # --test/--check/--ver no lo usan: son pruebas y no deben verse bloqueados.
    # --forever lo toma una vez y lo mantiene toda su vida, porque es el
    # proceso que ficha todos los dias: si lo soltara, otro podría duplicar.
    bloqueado = False
    if mode in ("entry", "exit", "daily", "forever"):
        # Tope de fechas tambien para los modos sueltos: si el movil deja de
        # fichar el 25/10 pero sigue programmeado, no debe seguir fichando.
        if LAST_DAY and now_local().strftime("%d/%m/%Y") > LAST_DAY:
            log(f"[{label}] hoy es posterior a {LAST_DAY}; fin del periodo, no se ficha")
            return 0
        if not acquire_lock():
            pid = _lock_holder()
            log(f"[{label}] otro proceso ya está fichando (pid {pid}) — no se duplica, saliendo")
            return 0
        bloqueado = True
        log(f"[{label}] cerrojo tomado (pid {os.getpid()})")

    try:
        # Días en skip_dates.txt: no se ficha (solo modos automáticos; --test/--check/--ver siguen funcionando)
        if mode in ("entry", "exit", "daily") and today_skipped():
            log(f"[{label}] {now_local().strftime('%d/%m/%Y')} está en skip_dates.txt — NO se ficha hoy")
            return 0

        if mode == "check":
            ok, msg = run_check()
            log(f"[Check] {'OK' if ok else 'FALLO'} — {msg}")
            return 0 if ok else 1

        if mode == "ver":
            ok, msg = run_ver()
            log(f"[Ver] {'OK' if ok else 'FALLO'} — {msg}")
            return 0 if ok else 1

        if mode == "forever":
            return run_forever()

        if mode == "daily":
            return run_daily()

        return punch_once(mode, label)
    finally:
        if bloqueado:
            release_lock()

if __name__ == "__main__":
    sys.exit(main())
