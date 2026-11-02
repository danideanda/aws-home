# Funciones de `aws-home`

Este documento describe lo que hace el código implementado actualmente. La API
es de solo lectura: no ejecuta comandos del sistema ni accede a rutas indicadas
por quien hace la petición.

## Inicio de la aplicación

El archivo [`main.py`](../main.py) es el punto de entrada:

- Importa la aplicación FastAPI desde `danideanda_api.api`.
- Configura el registro de mensajes (`logging`). El nivel puede cambiarse con
  `LOG_LEVEL`; por defecto es `INFO`.
- `main()` obtiene `API_HOST` y `API_PORT` del entorno. Los valores
  predeterminados son `127.0.0.1` y `8000`.
- Inicia Uvicorn para servir la API. Al escuchar en `127.0.0.1`, se puede
  colocar un proxy HTTPS delante. Para escuchar en otra interfaz, hay que
  configurar `API_HOST` conscientemente y proteger el servicio con HTTPS y
  controles de red.

## API (`danideanda_api/api.py`)

### `app`

Instancia FastAPI de la aplicación. La documentación interactiva y el esquema
OpenAPI están desactivados (`/docs`, `/redoc` y `/openapi.json`) para no
publicar esos endpoints.

### `CommandRequest`

Valida el cuerpo de las peticiones. Solo admite un campo `command` con uno de
estos valores exactos:

- `estado`
- `hora`
- `version`

Los demás comandos no pasan la validación.

### `_read_api_key()`

Lee y recorta la clave del archivo
`/etc/aws-home/secrets/api.key`. Si el archivo no existe, no se puede leer o
está vacío, registra un aviso y responde `404 Recurso no encontrado`. No
devuelve el contenido de la clave en la respuesta.

El archivo debe ser accesible para el usuario que ejecuta el servicio y tener
permisos restrictivos, por ejemplo modo `600`.

### `_authorize(api_key)`

Compara la cabecera recibida con la clave leída mediante una comparación
constante (`hmac.compare_digest`). Si falta la cabecera o no coincide, devuelve
`404`, igual que cuando el archivo de clave no está disponible.

### `run_read_only_command()`

Maneja `POST /api`. Primero autentica la petición; después valida el JSON y
responde según el comando:

| Comando | Respuesta |
|---|---|
| `estado` | Estado `ok` y tiempo de actividad del proceso en segundos. |
| `hora` | Fecha y hora UTC en formato ISO 8601. |
| `version` | Versión de Python que ejecuta el servicio. |

Si el cuerpo no es JSON válido o no contiene un comando permitido, responde
`422 Solicitud no válida`. La función no invoca una shell, no recibe rutas de
archivos y no ofrece comandos arbitrarios.

## Uso

Instala las dependencias de [`requirements.txt`](../requirements.txt), crea el
archivo de clave y arranca el servicio:

```sh
python3 -m pip install -r requirements.txt
python3 main.py
```

Ejemplo de petición:

```sh
curl -X POST http://127.0.0.1:8000/api \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: TU_CLAVE' \
  -d '{"command":"estado"}'
```

## Funciones todavía no implementadas

- No hay copia automática de `home` cada 12 horas. Está desactivada hasta
  determinar directorios concretos y un destino privado; no se deben incluir
  secretos ni datos personales.
- No se ha integrado `aws-whatsapp-system` ni el descifrado de sus archivos.
- La API no expone la clave de WhatsApp, archivos locales ni información de
  directorios sensibles.
