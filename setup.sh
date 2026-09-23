#!/data/data/com.termux/files/usr/bin/bash
# SigmaFichaje - configuracion automatica para Termux
set -e

echo "==> 1/4 Instalando paquetes (python, cronie, termux-services)..."
pkg update -y
pkg install -y python cronie termux-services tzdata

echo "==> 2/4 Descargando sigma_punch.py..."
curl -fsSL -O https://raw.githubusercontent.com/MiguelRauek/sigma-fichaje/main/sigma_punch.py

echo "==> 3/4 Activando crond..."
sv-enable crond

echo "==> 4/4 Programando fichajes (entrada 9:30, salida 17:55)..."
D="$PWD"
echo "30 9 * * * python $D/sigma_punch.py --entry >> $D/fichaje.log 2>&1" > crontab.txt
echo "55 17 * * * python $D/sigma_punch.py --exit >> $D/fichaje.log 2>&1" >> crontab.txt
crontab crontab.txt

echo ""
echo "LISTO. Ahora haz 2 cosas:"
echo ""
echo "1) Crea config.json con tus credenciales de sigmatime.es:"
echo "   echo '{\"email\": \"TU_EMAIL\", \"pass\": \"TU_PASS\"}' > config.json"
echo ""
echo "2) Prueba que el login funciona (no ficha nada):"
echo "   python sigma_punch.py --check"
echo ""
echo "Para ver la programacion: crontab -l"
echo "Para ver los fichajes: cat fichaje.log"
