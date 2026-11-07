# negobazar-canal

Publicaciones automáticas del canal de WhatsApp **NEGOBAZAR**.

- El repositorio privado `distriecono-automatico` arma cada madrugada la agenda del día (placas de productos, mensajes, encuesta y estados) y la sube a la rama `dia` de este repo.
- `.github/workflows/canal.yml` publica cada ítem en su horario, de 7 a 17, usando Whapi.Cloud (`publicador.py`).
- El token de Whapi está guardado como secreto (`WHAPI_TOKEN`); no está en el código.

## Canal de Sitronik

- `.github/workflows/sitronik_canal.yml` arma cada mañana (09:15) las placas del día leyendo `tiendasitronik.com.ar` (más vendidos y lo nuevo) y las publica en el canal de Sitronik en los horarios de `sitronik/canal/config.json`.
- Publica con el Whapi de Negobazar (`WHAPI_TOKEN`), que es administrador del canal de Sitronik; lo encuentra por el nombre. Si algún día Sitronik tiene su propio Whapi, se carga `WHAPI_TOKEN_SITRONIK` y usa ese.
- Para ver las placas sin publicar: Actions > "Sitronik - canal de WhatsApp" > Run workflow > `solo_placas`, y bajarlas de Artifacts.
- Combos Hudson: además de las 6 placas, publica 6 combos Hudson de la categoría Combos, solo los que tienen foto con ambiente (detecta y descarta los de fondo blanco). Horarios en `combos.horarios`.
- Instagram: si están los secretos `META_TOKEN_SITRONIK` (token de la página de Facebook de Sitronik) y `SITRONIK_IG_USER_ID`, comparte en el canal los posteos de @sitronik.home de las últimas 24 h (horario en `horarios_ig`), con su texto y el link al posteo.
