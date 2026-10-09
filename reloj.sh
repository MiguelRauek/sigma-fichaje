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
# las 09:56 es lo que permite esperar hasta las 10:09. El candado de pantalla
# lo gestiona sigma_punch.py (termux-wake-lock con contador): aqui NO se toca,
# porque el candado de Termux es global y un termux-wake-unlock de una job
# corta suelta el de las demas (fallo del 09/10/2026: la job de las 09:57
# solto el candado de la de las 09:43, el movil se durmio y la entrada no se
# ficho). Si falta termux-api, el movil se duerme igualmente.
#   entrada  fichar entre 10:06:00 y 10:09:59
#   salida   fichar entre 18:06:00 y 18:09:59
case "$H" in
  09[45][0-9]|100[0-9]|101[0-2]) M=--entry ;;
  175[0-9]|180[0-9]|181[0-2])    M=--exit  ;;
  *) exit 0 ;;
esac

python sigma_punch.py "$M" >> fichaje_boot.log 2>&1
exit 0