# MOSS-VL MCP 👁️

**Dale visión a Claude Code, Codex y otros agentes compatibles con MCP.** Usa [MOSS-VL](https://github.com/OpenMOSS/MOSS-VL) para analizar capturas, comparar interfaces, revisar grabaciones de pruebas y observar cambios visuales en tiempo real.

Es un **servidor MCP no oficial** en Python. El agente razona, ejecuta pruebas y modifica el código; **MOSS-VL aporta las observaciones visuales**.

> **Estado: v0.1, experimental.** Las herramientas y pruebas unitarias están implementadas, pero la inferencia GPU completa no se ha verificado de extremo a extremo. El MCP no incluye pesos ni inicia automáticamente un backend GPU.

## ¿Para qué sirve? Un ejemplo concreto

Imagina que un test de Playwright termina sin errores, pero la pantalla final tiene un botón oculto por un modal. Sin visión, un agente solo conoce los logs y el DOM. Con este MCP puede **inspeccionar una captura**, **compararla con una versión anterior** y conectar lo observado con el código.

**Flujo:** guardar captura → llamar a **inspect_ui** → comprobar en el código el posible fallo → corregirlo → comparar capturas con **compare_ui_states**. Es un análisis basado en un modelo, no un diff píxel a píxel.

## Instalación rápida (Python 3.11+)

En la máquina donde se ejecutará Claude Code o Codex:

~~~bash
git clone https://github.com/edujbarrios/moss-vl-mcp.git
cd moss-vl-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
mkdir -p "$HOME/moss-vl-media"
~~~

En Windows, utiliza el ejecutable del entorno virtual situado en la carpeta .venv/Scripts. Los comandos siguientes son para Bash/macOS/Linux.

**Importante:** la instalación base permite registrar el MCP y comprobar la configuración, pero **todavía no realiza inferencia visual**.

### Conectar con Claude Code

Desde la carpeta del repositorio:

~~~bash
claude mcp add --scope user \
  --env MOSS_VL_MEDIA_ROOT="$HOME/moss-vl-media" \
  --transport stdio moss-vl -- "$PWD/.venv/bin/moss-vl-mcp"

claude mcp list
~~~

Abre una sesión nueva de Claude Code y usa **/mcp** para inspeccionar las herramientas.

### Conectar con Codex

~~~bash
codex mcp add moss-vl \
  --env MOSS_VL_MEDIA_ROOT="$HOME/moss-vl-media" \
  -- "$PWD/.venv/bin/moss-vl-mcp"

codex mcp list
~~~

Reinicia la sesión del agente tras registrarlo. Se usa el ejecutable del entorno local: **no se presupone que este paquete esté publicado en PyPI**.

## Demo 1: comprobar el MCP sin GPU

Escribe **en el chat del agente**, no en una terminal:

> Usa la herramienta **check_moss_vl_setup** de moss-vl. Explícame qué dependencias detectas, si existe la carpeta de medios y qué necesito para analizar una captura. No intentes cargar ningún modelo.

La herramienta indica si está disponible la carpeta de medios, detecta módulos opcionales y muestra si la captura está habilitada. **No comprueba** disponibilidad de GPU, compatibilidad del checkpoint, inferencia real ni conexión con el backend realtime. Detectar paquetes **no** implica que el modelo esté funcionando.

## Demo 2: inspeccionar una captura (requiere modelo offline)

**1. Prepara el backend.** Instala y configura MOSS-VL Instruct según la [guía oficial offline](https://github.com/OpenMOSS/MOSS-VL/tree/main/inference/offline) en un entorno GPU compatible. Instala además las dependencias opcionales de este MCP:

~~~bash
python -m pip install -e '.[offline]'
~~~

El checkpoint predeterminado es **OpenMOSS-Team/MOSS-VL-Instruct-0708**. Si necesitas otro, define **MOSS_VL_CHECKPOINT** en las variables de entorno del registro MCP. El modelo se carga en la primera petición de análisis.

**2. Copia la captura a la carpeta permitida.**

~~~bash
cp /ruta/a/tu/captura.png "$HOME/moss-vl-media/login.png"
~~~

**3. Pide al agente que la analice:**

> Usa **inspect_ui** de moss-vl sobre la imagen **login.png** de la carpeta de medios. Describe el diseño, posibles elementos solapados y mensajes de error. Separa hechos visibles de hipótesis y sugiere qué comprobar en el código.

**4. Comprueba un cambio visual.** Guarda dos capturas **antes.png** y **despues.png** en la misma carpeta y pregunta:

> Llama a **compare_ui_states** con **antes.png** y **despues.png**. Describe qué cambió, qué posibles regresiones aparecen y qué no puedes confirmar solo con las imágenes.

El MCP devuelve **observaciones**. El agente, los tests y la revisión humana deben confirmar cualquier defecto antes de darlo por solucionado.

## Demo 3: revisar un vídeo de una prueba

Guarda una grabación de Playwright en la carpeta permitida como **registro.mp4** y escribe:

> Usa **analyze_test_recording** de moss-vl sobre **registro.mp4**. Resume los pasos visibles por orden, identifica estados inesperados y relaciónalos con las partes del código que deberíamos revisar. No inventes eventos invisibles.

Para preguntas generales, usa **analyze_video**. Para describir imágenes sin la plantilla de QA, usa **analyze_image**. **Este MCP no ejecuta Playwright ni crea grabaciones por sí mismo**: los archivos tienen que existir antes de analizarlos.

## Demo 4: observar cambios visuales en tiempo real

Esta modalidad necesita un backend diferente: el [servidor de referencia MOSS-VL-Realtime](https://github.com/OpenMOSS/MOSS-VL/blob/main/inference/realtime/README.md), lanzado por separado en una GPU. Por ejemplo, desde el repositorio de OpenMOSS:

~~~bash
CUDA_VISIBLE_DEVICES=0 python inference/realtime/run_online_inference.py \
  --serve --host 127.0.0.1 --port 8000
~~~

Por defecto, el MCP conecta con **ws://127.0.0.1:8000/v1/realtime** (configurable mediante **MOSS_VL_REALTIME_URL**). **SGLang-Omni utiliza otro protocolo y no está soportado.**

La captura del escritorio **se realiza en el host que ejecuta el MCP**, no automáticamente en el ordenador remoto del usuario. Para habilitarla explícitamente:

~~~bash
python -m pip install -e '.[screen]'
~~~

Añade **--env MOSS_VL_ALLOW_SCREEN_CAPTURE=1** al comando de registro de Claude Code o Codex y reinicia el agente. La captura está desactivada por defecto porque puede incluir contenido sensible.

Mensaje de ejemplo para el agente:

> Abre una sesión con **start_visual_session**. Observa el monitor 1 mediante **start_screen_observation** a 1 FPS durante 30 segundos. Usa **ask_visual_session** para preguntar si aparecen cambios inesperados, consulta **get_visual_events** usando el cursor **next_seq** y cierra tanto la observación como la sesión.

Los resultados se consultan por **polling**, sin notificaciones push automáticas. La captura está limitada a **2 FPS y 5 minutos** por petición. El backend de referencia admite una sola sesión por proceso del modelo.

## Todas las herramientas

| Caso de uso | Herramientas MCP | Necesitas |
| --- | --- | --- |
| Diagnosticar la instalación | **check_moss_vl_setup** | Instalación base |
| Imágenes y vídeos | **analyze_image**, **analyze_video** | Modelo offline |
| QA visual | **inspect_ui**, **compare_ui_states**, **analyze_test_recording** | Modelo offline |
| Sesiones realtime | **start_visual_session**, **push_visual_frame**, **ask_visual_session**, **get_visual_events**, **stop_visual_session** | Backend realtime |
| Captura local | **start_screen_observation**, **get_screen_observation_status**, **stop_screen_observation** | Realtime + dependencia screen + consentimiento explícito |
| Reproducir vídeo en el backend | **replay_visual_video**, **stop_visual_video** | Realtime + ruta compartida + **MOSS_VL_ALLOW_SERVER_VIDEO=1** |

**MOSS_VL_MEDIA_ROOT** restringe los archivos locales accesibles por el MCP. Si habilitas replay remoto, **la misma ruta absoluta** de vídeo debe estar disponible tanto en el host MCP como en el del modelo.

## Solución de problemas

| Problema | Qué revisar |
| --- | --- |
| No aparecen las herramientas | Ejecuta **claude mcp list** o **codex mcp list**, comprueba la ruta del ejecutable y reinicia el agente. |
| Faltan dependencias | Ejecuta **check_moss_vl_setup**. El paquete base no incluye el backend offline ni la captura. |
| Falla el análisis de una imagen | Verifica el checkpoint y las dependencias de OpenMOSS en el entorno GPU. El diagnóstico no valida la inferencia. |
| Archivo fuera de la carpeta | Mueve el archivo dentro de **MOSS_VL_MEDIA_ROOT**. Se rechazan rutas y enlaces simbólicos que escapen de ella. |
| No inicia realtime | Comprueba que el servidor de referencia esté activo y la variable **MOSS_VL_REALTIME_URL**. |
| No aparecen eventos nuevos | Envía frames o inicia la captura, pregunta con **ask_visual_session** y consulta **get_visual_events** usando **next_seq**. |
| No hay captura de pantalla | Instala **.[screen]**, habilita la función y concede permisos de pantalla al proceso. |

**Privacidad:** usa una carpeta pequeña para los archivos compartidos y evita enviar capturas con contraseñas o datos sensibles. No expongas el WebSocket de referencia públicamente sin TLS, autenticación y restricciones de red.

## Desarrollo y créditos

~~~bash
python -m pip install -e '.[dev]'
ruff check src tests
pytest -q
~~~

Las pruebas emplean backends simulados: **la inferencia GPU extremo a extremo sigue pendiente**.

Documentación adicional: [guía de agentes en inglés](docs/AGENT_USAGE.md) · [variables de entorno](.env.example) · [proyecto OpenMOSS](https://github.com/OpenMOSS/MOSS-VL).

Creado y mantenido por [@edujbarrios](https://github.com/edujbarrios). Proyecto **independiente y no oficial**; no afiliado ni respaldado por OpenMOSS. Los modelos y el trabajo de investigación pertenecen a sus respectivos autores. Revisa las licencias upstream antes de desplegar.
