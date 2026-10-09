# Fichaje automático en SigmaTime

Ficha solo, los dos fichajes, sin depender del PC ni de internet en el PC.
Todo ocurre en el móvil (Termux) y el móvil es el único que hace el fichaje.

## Horarios (Europe/Madrid)

| Fichaje | Ventana |
|---|---|
| **Entrada** | Segundo aleatorio entre **10:06:00 y 10:09:59** |
| **Salida** | Segundo aleatorio entre **18:06:00 y 18:09:59** |

El segundo nunca es en punto: `10:07:00`, `18:06:00`, etc. no se usan
(siempre `:01`–`:59`).

Cada día se sortea un segundo nuevo dentro de cada ventana. Nada se ficha
antes de las 10:06 ni antes de las 18:06.

**Ningún fichaje puede registrarse fuera de su rango**, y no es una
costumbre del reloj: lo bloquea el propio programa (`decidir()`), en todos
los modos, `--test` incluido. Si alguien lanzara `--exit` a las 10 de la
mañana o a las 12:00, no se envía nada. Además cada día hay como mucho
dos fichajes: con uno hecha la entrada está hecha, con dos la salida.

**Periodo: hasta el 25/10/2026, incluido.** Ese día ficha y luego se apaga solo.

## Cómo funciona

1. **Login**: POST `cf_usu` + `cf_pass` a `https://sigmatime.es/acceso.php` → cookie de sesión.
2. **Portal**: GET `https://sigmatime.es/v2/portal-empleado.php` → extrae el hash `c_usu`,
   los fichajes de hoy y el `c_tip` que Sigma pone en el formulario (1 = el
   botón está verde y toca ENTRADA; 2/3 = rojo y toca SALIDA).
3. **Comprobar**: `decidir()` cruza el modo pedido (`--entry`/`--exit`) con
   ese `c_tip`, el número de fichajes de hoy **y la hora**:
   - dentro de la ventana y coincide → se pulsa con el `c_tip` del portal;
   - el fichaje de ese modo ya está hecho → se da por bueno, sin error;
   - **fuera de la ventana del modo (entrada 10:06–10:09:59, salida
     18:06–18:09:59) → no se pulsa**, aunque el botón esté en el color
     que sea;
   - no coincide (p. ej. un `--entry` con el botón ya en rojo) → **no se
     pulsa**, para nunca registrar una salida a las 10 de la mañana.
4. **Fichar**: POST `c_usu` + `c_tip` (el leído) + `fic_subtipo=0` (horas
   ordinarias) + `btn_fichar`.
5. **Verificar**: vuelve a leer el portal y comprueba que el contador de hoy
   subió en 1 **y** que el interruptor cambió de color. Si no, se reintenta
   dentro de la ventana.

## Reintentos

Un corte de internet **no** tumba el programa: se registra como fallo y se
reintenta dentro de la ventana.

| | Intentos | Cada cuánto |
|---|---|---|
| Entrada | 8 | 25 s |
| Salida | 10 | 18 s |

Nunca se reintenta fuera de la ventana.

## Si falla: alarma escandalosa

| Fallo | Qué pasa |
|---|---|
| **Sin internet / DNS** | 🔊 Suena el tono de alarma del móvil en bucle, dos veces, sale un cartel y llega un mensaje a Telegram |
| **Ventana pasada sin fichar** (móvil dormido) | 🔊 Igual: alarma + cartel + Telegram |
| Otro motivo (web, hash) | 🔕 Cartel en pantalla + mensaje a Telegram |

El pitido se busca en los sonidos de alarma del sistema; si el móvil no tiene
ninguno, el propio programa genera un WAV de tres pitidos agudos y lo reproduce.
El objetivo es enterarse el mismo día, no al siguiente.

El mensaje a Telegram necesita `telegram_token` y `telegram_chat_id` en
`config.json` (opcionales pero recomendados): aunque el sonido no se oiga,
el mensaje llega. La alarma solo avisa una vez por día y modo (varios
procesos congelados que despiertan tarde no la repiten).

## Arranque automático y batería

Termux:Boot ejecuta `~/.termux/boot/sigma.sh` al encender el móvil, y **se apaga
enseguida**: no se queda despierto.

```bash
#!/data/data/com.termux/files/usr/bin/bash
mkdir -p ~/bin
termux-job-scheduler --job-id 77 --period-ms 900000 --network any \
  --persisted true --script ~/bin/reloj.sh >> fichaje_boot.log 2>&1
exit 0
```

Android programa un trabajo cada 15 minutos. `~/bin/reloj.sh` mira la hora y hace
**nada** salvo que esté en la franja:

| Se ejecuta a | Modo |
|---|---|
| 09:40–10:12 | `--entry` |
| 17:50–18:12 | `--exit` |
| cualquier otra hora | sale sin hacer nada |

Las bandas arrancan antes de la ventana (desde 09:40 ya está dentro) para que
el proceso pueda esperar hasta el segundo sorteado. El candado de pantalla
(`termux-wake-lock`) mantiene el móvil despierto durante esa espera; si falta
`termux-api`, el móvil se duerme y el proceso se congela (fallo del 09/10/2026).

El candado de pantalla lo gestiona `sigma_punch.py` con un **contador**
(`wake_count.txt`): el candado de Termux es global, no por proceso, y una job
corta que hiciera `termux-wake-unlock` soltaba el candado de las demás (la job
de las 09:57 soltó el de las 09:43 y el móvil se durmió). Ahora solo el último
proceso en terminar lo suelta, y `reloj.sh` ya no lo toca.

El cerrojo de fichaje (`fichaje.lock`) **solo se toma al pulsar**, no durante
la espera: varios procesos pueden esperar a la vez y, si uno se congela, otro
ficha. Así el candado de pantalla solo se toma durante el fichaje: **unos
minutos al día en vez de ocho horas**. Android no permite programar más a menudo
que cada 15 minutos, por eso el reloj usa ese periodo y decide con la hora.

Si `termux-job-scheduler` no existiera, el arranque automático no podría
programar nada y no habría fichaje.

### Paquete obligatorio

```bash
pkg install termux-api
```

Trae `termux-job-scheduler` (el reloj), `termux-media-player` y `termux-toast`
(la alarma). **No** es lo mismo que la app Termux:API de F-Droid: el paquete
hay que instalarlo dentro de Termux.

## Requisitos en el móvil

En **Termux** y en **Termux:Boot**:

| Ajuste | Valor |
|---|---|
| Batería | Sin restricciones |
| Ejecución en 2º plano | Permitir |
| Inicio automático | Permitir |
| Notificaciones | activadas |

## Credenciales

Van solo en `config.json` **en el móvil** (`~/config.json`), con esta forma:

```json
{"email": "TU-CORREO", "pass": "TU-CONTRASENA",
 "telegram_token": "TU-TOKEN-DEL-BOT", "telegram_chat_id": "TU-CHAT-ID"}
```

La clave se llama `pass`, no `password`. `telegram_token` y `telegram_chat_id`
son opcionales: activan el aviso por Telegram cuando el fichaje falla (el token
es el del bot que ya usa el PC). Nunca en este repositorio. Si un día
hay que volver a fijarlas, mira los pasos de la página de instrucciones.

## Ficheros

```
sigma_punch.py            el programa que hace el fichaje
reloj.sh                  el reloj: cada 15 min, solo actúa si toca fichar
sigma_boot.sh             arranque automático (va en ~/.termux/boot/sigma.sh)
instrucciones.html        la página con los pasos, se abre en el móvil
cmd.html                  página auxiliar para copiar comandos
INSTRUCCIONES.txt         los mismos pasos en texto plano
skip_dates.txt            días que no se ficha (uno por línea, dd/mm/aaaa)
test_docs.py              los rangos siguen iguales en codigo y docs
test_punch.py             tests de decidir()/punch_once (sin red)
.github/workflows/pages.yml   publica la página y ejecuta los tests
```

## Tests

Dos scripts sin red ni credenciales, en el repo y en el CI:

```bash
python3 test_docs.py   # los rangos siguen iguales en el codigo y en los docs
python3 test_punch.py  # decidir()/punch_once: 54 comprobaciones
```

Si alguno falla, `pages.yml` **no despliega** la página de instrucciones
(el paso de tests va antes de publicar).

## Notas

- El fichero de fichaje es la fuente de verdad: `fichaje.log` en el móvil.
- `Session.get/post` devuelven `(url, html)`. Leerlos al revés fue el fallo que
  dejó el fichaje parado durante días; ahora hay pruebas que lo cubren.
- `fichaje.lock` impide que dos procesos fichen a la vez (el reloj y una
  ejecución manual nunca se pisan). Solo se toma al pulsar, no durante la
  espera: si un proceso se congela esperando, otro puede fichar.
- El fichaje **nunca** corre en GitHub Actions: solo ahí se publica la
  página y se ejecutan los tests. El histórico de acciones automáticas se
  eliminó porque usaban un horario viejo (9:30) y guardaban las credenciales
  del hotel como secretos del repositorio.