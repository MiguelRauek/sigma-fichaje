#!/data/data/com.termux/files/usr/bin/bash
# Se ejecuta cada 15 minutos (lo programa el arranque automatico).
# No hace nada salvo que este cerca de la hora de fichar.
cd $HOME

H=$(date +%H%M)          # 4 digitos, con el cero: 0945, 1756, 1002

# Latido: una linea cada 15 minutos. Sirve para comprobar desde el PC que
# el reloj sigue vivo, sin depender de "termux-job-scheduler --list".
echo "$(date '+%d/%m %H:%M:%S') reloj activo" >> fichaje_boot.log

# OJO: los patrones son de 4 digitos porque $H conserva el cero inicial.
# Si se quita con $((10#$H)), 09:57 pasa a ser 957 y ya no coincide con
# ningun patron, y la entrada se queda sin hacer. No hacerlo.
#
# Las bandas arrancan ANTES de la ventana de fichaje: el reloj despertando a
# las 09:56 es lo que permite esperar hasta las 10:08. El candado de pantalla
# lo gestiona sigma_punch.py (termux-wake-lock con contador): aqui NO se toca,
# porque el candado de Termux es global y un termux-wake-unlock de una job
# corta suelta el de las demas (fallo del 09/10/2026: la job de las 09:57
# solto el candado de la de las 09:43, el movil se durmio y la entrada no se
# ficho). Si falta termux-api, el movil se duerme igualmente.
#   entrada  fichar entre 10:05:00 y 10:08:59 (hasta el 18/10/2026)
#            y entre 09:59:00 y 10:01:59 (desde el 19/10/2026)
#   salida   fichar entre 18:05:00 y 18:08:59 (hasta el 18/10/2026)
#            y entre 18:00:00 y 18:08:59 (desde el 19/10/2026)
case "$H" in
  09[45][0-9]|100[0-9]|101[0-2]) M=--entry ;;
  175[0-9]|180[0-9])             M=--exit  ;;
  *) M="" ;;
esac

# ---------------------------------------------------------------------------
# AUTOACTUALIZACION (solo fuera de las bandas de fichaje)
#
# Nunca corre en banda: asi una comprobacion lenta o sin cobertura no puede
# retrasar un fichaje. Se pide solo la cabecera (HEAD) y se compara el ETag
# del repo con el guardado al lado del fichero; solo se baja el fichero si de
# verdad cambio. Si cambia algo, se avisa por Telegram.
#
# Se hace con python3 (no con curl) porque python3 ya es imprescindible para
# fichar y curl puede no estar instalado en Termux.
# ---------------------------------------------------------------------------
if [ -z "$M" ]; then
  python3 - >> fichaje_boot.log 2>&1 <<'PY'
import json, os, urllib.parse, urllib.request

REPO = "https://raw.githubusercontent.com/MiguelRauek/sigma-fichaje/main"
HOME = os.path.expanduser("~")
FICHEROS = [
    (os.path.join(HOME, "sigma_punch.py"), "sigma_punch.py"),
    (os.path.join(HOME, "bin", "reloj.sh"), "reloj.sh"),
]

def etag_remoto(nombre):
    req = urllib.request.Request(REPO + "/" + nombre, method="HEAD")
    with urllib.request.urlopen(req, timeout=10) as r:
        return (r.headers.get("ETag") or "").strip().strip('"')

def descargar(nombre):
    with urllib.request.urlopen(REPO + "/" + nombre, timeout=25) as r:
        return r.read()

cambiados = []
for ruta, nombre in FICHEROS:
    try:
        if not os.path.exists(ruta):
            continue
        etag = etag_remoto(nombre)
        if not etag:
            continue
        marca = ruta + ".etag"
        try:
            with open(marca, encoding="utf-8") as f:
                previo = f.read().strip()
        except OSError:
            previo = ""
        if etag == previo:
            continue
        datos = descargar(nombre)
        if not datos:
            continue
        try:
            with open(ruta, "rb") as f:
                antes = f.read()
        except OSError:
            antes = b""
        tmp = ruta + ".nuevo"
        with open(tmp, "wb") as f:
            f.write(datos)
        if datos != antes:
            os.replace(tmp, ruta)          # reemplazo atomico
            try:
                os.chmod(ruta, 0o700)
            except OSError:
                pass
            cambiados.append(nombre)
        else:
            os.remove(tmp)
        with open(marca, "w", encoding="utf-8") as f:
            f.write(etag)
    except Exception as e:
        print("update:", nombre, "fallo:", e)

if cambiados:
    print("actualizado:", " ".join(cambiados))
    try:
        with open(os.path.join(HOME, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        tok = cfg.get("telegram_token", "")
        chat = cfg.get("telegram_chat_id", "")
        if tok and chat:
            texto = "SIGMAFICHAJE: reloj actualizado — " + ", ".join(cambiados)
            datos = urllib.parse.urlencode(
                {"chat_id": chat, "text": texto}).encode()
            urllib.request.urlopen(urllib.request.Request(
                "https://api.telegram.org/bot%s/sendMessage" % tok,
                data=datos), timeout=20)
            print("aviso enviado")
    except Exception as e:
        print("aviso fallo:", e)
PY
fi

[ -z "$M" ] && exit 0

python sigma_punch.py "$M" >> fichaje_boot.log 2>&1
exit 0
