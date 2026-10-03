#!/data/data/com.termux/files/usr/bin/bash
# Arranque automatico (Termux:Boot).
# NO se queda despierto: solo programa el reloj de fichaje y se apaga.
# El candado (wake lock) lo toma reloj.sh solo durante el fichaje, unos
# minutos al dia, en vez de 8 horas.
mkdir -p ~/bin

# --job-id 77 sustituye el trabajo anterior con el mismo id, asi que
# repetir esto en cada arranque es seguro. --persisted true hace que el
# trabajo sobreviva a reinicios del movil.
# Android no deja programar cada menos de 15 min (900000 ms), por eso
# reloj.sh comprueba la hora y solo trabaja cuando toca.
termux-job-scheduler \
  --job-id 77 \
  --period-ms 900000 \
  --network any \
  --persisted true \
  --script ~/bin/reloj.sh >> fichaje_boot.log 2>&1

exit 0