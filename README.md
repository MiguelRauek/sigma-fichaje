# Fichaje automático en SigmaTime

Ficha solo, los dos fichajes, sin depender del PC ni de internet en el PC.
Todo ocurre en el móvil (Termux) y el móvil es el único que hace el fichaje.

## Horarios (Europe/Madrid)

| Fichaje | Ventana |
|---|---|
| **Entrada** | Segundo aleatorio entre **10:05:00 y 10:08:59** |
| **Salida** | Segundo aleatorio entre **18:00:00 y 18:00:59** |

Cada día se sortea un segundo nuevo dentro de cada ventana. Nada se ficha
antes de las 10:05 ni antes de las 18:00.

**Periodo: hasta el 25/10/2026, incluido.** Ese día ficha y luego se apaga solo.

## Cómo funciona

1. **Login**: POST `cf_usu` + `cf_pass` a `https://sigmatime.es/acceso.php` → cookie de sesión.
2. **Portal**: GET `https://sigmatime.es/v2/portal-empleado.php` → extrae el hash `c_usu` y cuenta los fichajes de hoy.
3. **Fichar**: POST `c_usu` + `c_tip=1` + `fic_subtipo=0` (horas ordinarias) + `btn_fichar`.
4. **Verificar**: vuelve a leer el portal y comprueba que el contador de hoy subió en 1.

## Reintentos

Un corte de internet **no** tumba el programa: se registra como fallo y se
reintenta dentro de la ventana.

| | Intentos | Cada cuánto |
|---|---|---|
| Entrada | 6 | 45 s |
| Salida | 4 | 15 s |

Nunca se reintenta fuera de la ventana.

## Arranque automático

Termux:Boot ejecuta `~/.termux/boot/sigma.sh` al encender el móvil:

```bash
#!/data/data/com.termux/files/usr/bin/bash
cd $HOME
for i in 1 2 3 4 5 6; do termux-wake-lock && break; sleep 10; done
exec python sigma_punch.py --forever >> fichaje_boot.log 2>&1
```

- El bucle `--forever` ficha entrada y salida cada día hasta el 25/10.
- `termux-wake-lock` evita que Android suspenda el proceso. Es lo que permite
  que el fichaje salga a su hora con la pantalla apagada.
- `fichaje.lock` impide que haya dos copias corriendo a la vez.

## Permisos que necesita en el móvil

En **Termux** y en **Termux:Boot**:

| Ajuste | Valor |
|---|---|
| Batería | Sin restricciones |
| Ejecución en 2º plano | Permitir |
| Inicio automático | Permitir |
| Notificaciones | activadas |

## Credenciales

Van solo en `config.json` **en el móvil**. Nunca en este repositorio.
Si un día hay que volver a fijarlas, mira el paso 3 de la página de
instrucciones.

## Ficheros

```
sigma_punch.py            el programa (esto es lo único que se ejecuta)
instrucciones.html        la página con los pasos, se abre en el móvil
INSTRUCCIONES.txt         los mismos pasos en texto plano
skip_dates.txt            días que no se ficha (uno por línea, dd/mm/aaaa)
.github/workflows/pages.yml   publica la página de instrucciones
```

## Notas

- El fichero de fichaje es la fuente de verdad: `fichaje.log` en el móvil.
- La comprobación automática contra el portal (`--check`) no es fiable: tras el
  login el portal a veces no se deja leer. El control real es la app de Sigma.
- No hay cron ni GitHub Actions: el histórico de acciones automáticas se
  eliminó porque usaban un horario viejo (9:30) y guardaban las credenciales
  del hotel como secretos del repositorio.