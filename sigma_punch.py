#!/usr/bin/env python3
"""
SigmaFichaje — fichaje automático en SigmaTime (sigmatime.es).

Ejecuta el fichaje de entrada o salida en el horario aleatorio configurado.
Sin notificaciones de ningún tipo (ni Telegram ni email): solo registra la
hora de cada fichaje. Sin dependencias externas (solo stdlib), pensado para
GitHub Actions.

Uso:
  python3 sigma_punch.py --entry   # entrada: aleatoria entre 9:57 y 10:03
  python3 sigma_punch.py --exit    # salida:  segundo aleatorio en [18:00:00, 18:02:59]
  python3 sigma_punch.py --test    # fichar ya (para probar)
  python3 sigma_punch.py --check   # comprobar login y portal SIN fichar nada

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

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ---------------------------------------------------------------------------
# Horarios aleatorios
# ---------------------------------------------------------------------------

def now_local() -> datetime:
    return datetime.now(TZ)

def seconds_of_day(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second

def target_entry() -> int:
    """Aleatoria uniforme en [9:57:00, 10:03:59]. Siempre entre 9:57 y 10:03."""
    return 9 * 3600 + 57 * 60 + random.randint(0, 419)

def target_exit() -> int:
    """Segundo aleatorio uniforme en [18:00:00, 18:02:59]. Nunca antes de 18:00:00."""
    return 18 * 3600 + random.randint(0, 179)

def wait_until(target_secs: int, label: str) -> None:
    """Espera hasta que la hora local alcance target_secs (en tramos de 60 s)."""
    while True:
        now = now_local()
        if seconds_of_day(now) >= target_secs:
            return
        delta = target_secs - seconds_of_day(now)
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
        with self.opener.open(req, timeout=90) as resp:
            return resp.geturl(), resp.read().decode("utf-8", "replace")

    def get(self, url: str, referer: str | None = None):
        return self._request(url, None, referer)

    def post(self, url: str, data: dict, referer: str | None = None):
        return self._request(url, data, referer)

# ---------------------------------------------------------------------------
# Flujo de fichaje
# ---------------------------------------------------------------------------

def login(s: Session):
    html, final_url = s.post(
        f"{BASE_URL}/acceso.php",
        {"cf_usu": EMAIL, "cf_pass": PASS, "btn_acceso": ""},
    )
    if 'name="cf_usu"' in html:
        return False, "login fallido (credenciales incorrectas o web no accesible)"
    if "btn_fichar" in html or "portal-empleado" in final_url:
        return True, "login ok"
    return False, "respuesta inesperada tras el login"

def get_portal(s: Session):
    html, _ = s.get(f"{BASE_URL}/v2/portal-empleado.php", referer=f"{BASE_URL}/acceso.php")
    if "btn_fichar" not in html and "Listado de mis" not in html:
        return None
    return html

def extract_cusu(html: str):
    m = re.search(r'name="c_usu"[^>]*value="([a-f0-9]+)"', html)
    return m.group(1) if m else None

def count_today(html: str) -> int:
    """Cuenta los fichajes (HH:MM:SS) de hoy en el listado del portal.

    El HTML real es una sola línea con <br> entre días:
      <strong>19/09/2026</strong> <font color="green">09:35:42</font> ... <br>
    """
    today = now_local().strftime("%d/%m/%Y")
    m = re.search(r"<strong>" + today + r"</strong>([\s\S]*?)(?:<br>|</p>)", html)
    if not m:
        return 0
    return len(re.findall(r"\d{2}:\d{2}:\d{2}", m.group(1)))

def do_punch(s: Session, cusu: str) -> str:
    html, _ = s.post(
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

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if "--entry" in sys.argv:
        mode, label = "entry", "Entrada"
    elif "--exit" in sys.argv:
        mode, label = "exit", "Salida"
    elif "--test" in sys.argv:
        mode, label = "test", "Prueba"
    elif "--check" in sys.argv:
        mode, label = "check", "Check"
    else:
        print("Uso: sigma_punch.py --entry | --exit | --test | --check")
        return 2

    if not EMAIL or not PASS:
        print("Faltan las variables SIGMA_EMAIL y SIGMA_PASS")
        return 2

    if mode == "check":
        ok, msg = run_check()
        print(f"[Check] {'OK' if ok else 'FALLO'} — {msg}")
        return 0 if ok else 1

    if mode == "entry":
        target = target_entry()
    elif mode == "exit":
        target = target_exit()
    else:
        target = seconds_of_day(now_local())

    base = datetime.combine(now_local().date(), datetime.min.time())
    target_dt = base + timedelta(seconds=target)
    print(f"[{label}] objetivo: {target_dt.strftime('%H:%M:%S')} ({TZ})")

    if mode != "test":
        wait_until(target, label)

    # Reintentos: entrada cada 90 s; salida cada 30 s y nunca más allá de 18:02:59.
    delay = 90 if mode == "entry" else 30
    last_msg = "sin intentos"
    for attempt in range(1, 4):
        ok, msg = run_punch()
        last_msg = msg
        print(f"[{label}] intento {attempt}: {'OK' if ok else 'FALLO'} — {msg}")
        if ok:
            return 0
        if attempt < 3:
            if mode == "exit" and seconds_of_day(now_local()) > 18 * 3600 + 179:
                print("[Salida] fuera de la ventana 18:00:00–18:02:59, no se reintenta")
                break
            time.sleep(delay)

    return 1

if __name__ == "__main__":
    sys.exit(main())
