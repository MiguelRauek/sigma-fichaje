#!/data/data/com.termux/files/usr/bin/bash
# Se ejecuta cada 15 minutos (lo programa el arranque automatico).
# No hace nada salvo que este cerca de la hora de fichar.
cd $HOME

H=$(date +%H%M)
H=$((10#$H))          # quita el cero inicial (0945 -> 945)

case "$H" in
  094[5-9]|095[0-9]|100[0-2]) M=--entry ;;
  174[5-9]|175[0-9]|180[0-2]) M=--exit  ;;
  *) exit 0 ;;                          # el resto del dia: no gasta nada
esac

# Solo ahora toma el candado, y lo suelta al terminar.
termux-wake-lock
python sigma_punch.py "$M" >> fichaje_boot.log 2>&1
termux-wake-unlock
exit 0