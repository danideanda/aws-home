# aws-home

## API de solo lectura

La API se inicia con `python3 main.py` y, de forma predeterminada, escucha
solo en `127.0.0.1:8000` para poder ponerse detrás de un proxy HTTPS. Requiere
las dependencias de `requirements.txt` y una clave no vacía en
`/etc/aws-home/secrets/api.key`. El directorio debe ser accesible solo por el
usuario del servicio y la clave debe pertenecer a ese usuario con modo `600`.
Si la clave falta, está vacía o la petición no está autorizada, la API responde
`404`.

`POST /api` acepta `{"command":"estado"}`, `{"command":"hora"}` o
`{"command":"version"}` y requiere el encabezado `X-API-Key`. No ejecuta shell,
no permite leer rutas arbitrarias ni devuelve archivos o claves. La copia
periódica de `home` está desactivada hasta definir directorios explícitos y un
destino privado; no se deben subir secretos ni datos personales a este repo.

Consulta [la explicación de las funciones](danideanda-docs/docs/funciones.md)
para ver los detalles de los módulos, comandos y configuración.

## Sitio de documentación

El mismo servicio también atiende el host `docs.danidenada.dev`. La ruta `/`
lista los archivos Markdown de `danideanda-docs/docs`; una ruta como
`/funciones.md` entrega el contenido original en `text/markdown`. Configura el
DNS y el proxy HTTPS para que ese dominio llegue al servicio y conserve el
encabezado `Host`. El sitio solo busca documentos Markdown directamente dentro
de esa carpeta.

## Actualizaciones automáticas

Al arrancar, el proceso comprueba `origin/main` cada 300 segundos por defecto
(`UPDATE_CHECK_INTERVAL_SECONDS`, mínimo 60). Solo actualiza el repositorio
oficial si está en `main`, la copia local está limpia y el cambio es un avance
directo; después reinicia el proceso. Las actualizaciones ejecutan el código
publicado en `main`, así que publica allí solo cambios confiables. No se
instalan dependencias automáticamente. Más detalles en
[la documentación de funciones](danideanda-docs/docs/funciones.md).