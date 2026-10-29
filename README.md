# negobazar-canal

Publicaciones automáticas del canal de WhatsApp **NEGOBAZAR**.

- El repositorio privado `distriecono-automatico` arma cada madrugada la agenda del día (placas de productos, mensajes, encuesta y estados) y la sube a la rama `dia` de este repo.
- `.github/workflows/canal.yml` publica cada ítem en su horario, de 7 a 17, usando Whapi.Cloud (`publicador.py`).
- El token de Whapi está guardado como secreto (`WHAPI_TOKEN`); no está en el código.
