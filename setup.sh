#!/data/data/com.termux/files/usr/bin/bash
# SigmaFichaje - configuracion automatica para Termux
set -e

BASE="https://github.com/MiguelRauek/sigma-fichaje/raw/refs/heads/main"

echo "==> Descargando sigma_punch.py (version mas reciente)..."
if curl -fsSL -o sigma_punch.py "$BASE/sigma_punch.py"; then
  echo "    OK"
elif [ ! -f sigma_punch.py ]; then
  echo ""
  echo "ERROR: no se pudo descargar sigma_punch.py (comprueba la conexion)."
  echo "Puedes descargarlo a mano con el navegador del movil:"
  echo "  Abre: $BASE/sigma_punch.py"
  echo "  Menu (3 puntos) -> Descargar"
  echo "  Luego: cp /sdcard/Download/sigma_punch.py ~/"
  exit 1
else
  echo "    (no se pudo descargar; se usa el sigma_punch.py existente)"
fi

echo "==> 1/4 Instalando paquetes (python, cronie, termux-services)..."
pkg update -y
pkg install -y python cronie termux-services

echo "==> 2/4 Activando crond..."
mkdir -p "$PREFIX/var/service" 2>/dev/null || true
if sv-enable crond 2>/dev/null; then
  echo "    crond activado como servicio"
else
  echo "    (aviso: no se pudo activar el servicio; se arranca crond directamente)"
  crond 2>/dev/null || true
fi

echo "==> 3/4 Credenciales de sigmatime.es"
if [ -f config.json ]; then
  echo "    config.json ya existe, se mantiene."
else
  read -p "    Email: " EMAIL
  read -s -p "    Password: " PASS
  echo ""
  echo "{\"email\": \"$EMAIL\", \"pass\": \"$PASS\"}" > config.json
  chmod 600 config.json
  echo "    config.json creado."
fi

echo "==> 4/4 Programando fichajes (entrada 9:55, salida 18:00)..."
D="$PWD"
echo "55 9 * * * python $D/sigma_punch.py --entry >> $D/fichaje.log 2>&1" > crontab.txt
echo "0 18 * * * python $D/sigma_punch.py --exit >> $D/fichaje.log 2>&1" >> crontab.txt
crontab crontab.txt

echo ""
echo "==> Probando login (no ficha nada)..."
python sigma_punch.py --check || true

echo ""
echo "LISTO. Programacion actual:"
crontab -l
echo ""
echo "Para ver los fichajes de hoy (igual que en la web):"
echo "  python sigma_punch.py --ver"
echo "Para ver el historial:"
echo "  cat fichaje.log"
