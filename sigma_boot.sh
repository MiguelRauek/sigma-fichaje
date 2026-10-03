#!/data/data/com.termux/files/usr/bin/bash
# Arranque automatico (Termux:Boot).
# NO se queda despierto: solo programa el reloj de fichaje y se apaga.
# El candado (wake lock) lo toma reloj.sh solo durante el fichaje, unos
# minutos al dia, en vez de 8 horas.
mkdir -p ~/bin

# Android no deja programar cada menos de 15 min, por eso el reloj.sh
# comprueba la hora y solo trabaja si toca.
termux-job-scheduler --job-id 77 --period 900000 --network any \
  --force-schedule --script ~/bin/reloj.sh >> fichaje_boot.log 2>&1 \
|| termux-job-scheduler --job-id 77 --period 900000 --network any \
  --force-schedule ~/bin/reloj.sh >> fichaje_boot.log 2>&1

exit 0