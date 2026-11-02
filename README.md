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

Consulta [la explicación de las funciones](docs/funciones.md) para ver los
detalles de los módulos, comandos y configuración.