#!/data/data/com.termux/files/usr/bin/bash
# SigmaFichaje - configuracion automatica para Termux
set -e

if [ ! -f sigma_punch.py ]; then
  echo "ERROR: sigma_punch.py no esta en esta carpeta."
  echo "Descargalo desde GitHub y copialo aqui:"
  echo "  cp /sdcard/Download/sigma_punch.py ~/"
  exit 1
fi

echo "==> 1/3 Instalando paquetes (python, cronie, termux-services)..."
pkg update -y
pkg install -y python cronie termux-services tzdata

echo "==> 2/3 Activando crond..."
sv-enable crond

echo "==> 3/3 Programando fichajes (entrada 9:30, salida 17:55)..."
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
