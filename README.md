# homelab-training — Entrenamiento y Nutrición (entreno.solde.cat / nutricion.solde.cat, públicos con login)

Sección **Entrenamiento** del portal de administración: gestión de rutinas, base de ejercicios con imágenes/vídeos, entrenamiento guiado con
cronómetros de ejercicio y descanso, panel de progreso, asistente de IA con acceso a los datos (lee y edita rutinas, y puede evaluar el
desempeño y ajustar las rutinas automáticamente) y copia de seguridad (exportar/importar).

```
navegador ──► entreno.solde.cat / nutricion.solde.cat (Traefik público → Flask + SQLite, ns training; login `auth`, cookie `solde_session`)
                  ▲  pull (X-Agent-Token, solo por ClusterIP)
        training-agent.service (host) ── claude -p SIN herramientas propias + MCP "training" (lee datos / edita rutinas con historial)
```

## Qué incluye

- **Ejercicios** (917): ~876 de [free-exercise-db](https://github.com/yuhonas/free-exercise-db) (dominio público, Unlicense) con descripción en inglés y 2 imágenes
  (inicio/fin, animadas) más 41 de cardio propios (carrera, ciclismo, remo, natación, comba, HIIT, boxeo…) con nombre y descripción en español y **sin imagen**.
  Filtros por categoría, músculo, material y nivel; favoritos; búsqueda por nombre en español o inglés.
  **Imágenes y vídeos propios**: cualquier ejercicio (de la biblioteca o propio) admite JPG/PNG/WebP/GIF (8 MB) y MP4/WebM (30 MB), hasta 8; los tuyos sustituyen a los de la
  biblioteca y se pueden quitar para volver a ellos. Además, enlace opcional a un vídeo (https) y botón «Buscar vídeo» (YouTube). Ejercicios propios con todos sus campos.
- **Rutinas**: ejercicios ordenables con series, repeticiones (rango), peso, duración/distancia (cardio y por tiempo), **descanso entre series y al acabar el ejercicio**, notas y días de la semana.
  Historial de versiones con «volver a esta»; duplicar y archivar.
- **Entrenar**: sesión guiada (desde una rutina o libre) con cronómetro de serie/ejercicio, **cuenta atrás de descanso** (±15 s, saltar), pitidos y vibración, pantalla siempre encendida,
  registro de reps/peso/duración/distancia/RPE, plan editable al vuelo, «última vez», valoración y notas. El estado sobrevive a recargas y se ve un banner mientras hay un entrenamiento en curso.
- **Panel**: sesiones, tiempo, volumen y cardio por semana (12 semanas), constancia frente al objetivo, racha, músculos trabajados, récords (1RM estimado), entrenamientos recientes y
  ajustes del asistente.
- **Asistente** (chat) y **evaluación automática**: lee ejercicios, rutinas, entrenamientos, estadísticas y perfil, y crea/edita rutinas (cada edición guarda la versión anterior) y, si se lo pides, corrige entrenamientos ya registrados (`session_update`: notas, valoración, editar/borrar/añadir series; devuelve los valores anteriores).
  «Evaluar y ajustar con IA» (por rutina o global), o automático **después de cada entrenamiento** o **una vez por semana** (Ajustes). Progresión por doble criterio (reps/RPE), descansos,
  sustitución de ejercicios con molestias; estilo conservador/normal/agresivo.
- **Ajustes**: perfil (objetivo, experiencia, días, material, lesiones), unidades, sonido/vibración/pantalla, ajuste automático, y **exportar/importar** (JSON completo, con o sin imágenes
  propias; CSV de entrenamientos; importación combinar/reemplazar con validación).

## Temporada y producto local

- Cada alimento puede llevar `months` (meses de temporada; vacío = todo el año) y `origin` (`cat` | `es`). **`peak`** = «de temporada este mes». Los filtros «De temporada ahora», «Cataluña» y «España» están en Alimentos y en Recetas, y el selector de recetas del menú pone primero las de la época.
- **Biblioteca de 59 recetas tradicionales** (`data/recipes.json`, de `tools/make_recipes.py`; `source='lib'`, uid `lib_*`) con época ideal, origen, tipo y minutos. Se siembran al arrancar y no se pisan si las editas; el export solo incluye las editadas o archivadas.
- Estación por fechas (invierno 21-dic…20-mar, primavera hasta 20-jun, verano hasta 22-sep, otoño). `GET /api/season` y `GET /agent/season`. El asistente recibe en el prompt (`{{SEASON}}`: menú, cocina y chat) los frescos de temporada, el tipo de cocina de la época y las recetas de la biblioteca de ese mes; `food_search`/`recipe_list` aceptan `season=true` y `origin`.
- Tras regenerar datos: `python tools/make_foods.py && python tools/make_recipes.py` (el segundo falla si un ingrediente no existe). Los ids `f_001…f_108` no cambian.

## Nutrición (menú diario)

Grupo **Nutrición** del portal (misma app, vistas `menu`, `foods`, `cook`, `shopping`; el portal lo incrusta con su propio iframe sobre `/entreno/`):

- **Menú en calendario** con vistas **día / semana / mes**: por día seis momentos (desayuno, media mañana, comida, merienda, cena, otros) con alimentos (gramos), recetas (raciones) o entradas libres con
  macros; totales del día frente a tus objetivos (calorías, proteína, hidratos, grasa), marcar como hecho, copiar día o semana, vaciar y **historial con deshacer**. La semana muestra una cuadrícula
  momento × día y el mes un calendario con kcal y puntos de comidas, coloreado según el objetivo (verde ±10 %, ámbar por debajo, rojo por encima).
- **Alimentos y recetas**: 258 alimentos (108 habituales + 150 productos locales de España y Cataluña con su calendario de temporada) con valores **orientativos** por 100 g (`data/foods.json`, generado por `tools/make_foods.py` + `tools/local_foods.py`), propios ilimitados, favoritos/archivo; recetas con
  ingredientes en gramos y macros por ración.
- **Lista de la compra** de cualquier rango (ingredientes sumados, recetas desglosadas; marcas guardadas en el navegador; copiar al portapapeles).
- **Asistente conectado**: el mismo agente que las rutinas (MCP `training`) lee el perfil nutricional, alimentos, recetas, menú y entrenos, y edita el menú con `plan_set_days` (motivo obligatorio, estado
  anterior guardado → «Deshacer» en el calendario). «**Planificar con IA**» (día/semana/rango + indicaciones) encola un trabajo (`plan_jobs`, prompt `plan_prompt.md`): respeta los días que ya tienen menú tuyo,
  usa tus objetivos/dieta/alergias/gustos/entrenos y verifica los totales. Estimador de objetivos en Ajustes (Mifflin-St Jeor × actividad ± objetivo) para empezar.
- **Personas** (`static/js/people.js`): control «Personas» en Menú (vista día), Compra, receta (lista «Escalar ingredientes») y Cocinar; multiplica las cantidades (gramos/raciones/lista de la compra) por N, se recuerda en el navegador (`localStorage people`). Las calorías y macros del menú siguen siendo por persona; solo visual, no cambia los datos guardados.
- **Cocinar** (vista `cook`): elige un día, lista sus alimentos (recetas desglosadas) y «Sugerir recetas» encola `cook_jobs` (prompt `cook_prompt.md`, herramienta `cook_ideas_set`): el asistente propone 1–3 recetas con esos alimentos (+ básicos de despensa), guardadas como `recipe_ideas` (macros por ración calculados, no son recetas aún). «Guardar en mis recetas» las convierte en receta real (solo ingredientes con alimento de la base); una nueva tanda sustituye las no guardadas. No toca el menú.
- **Datos**: se exportan e importan con el resto (JSON: alimentos propios, recetas y menú; CSV del menú). No sustituye a un dietista; con patologías, embarazo o trastornos alimentarios, consulta a un profesional.

## Datos por persona (cada usuario ve solo lo suyo)

Cada usuario del login (`auth`, cookie `solde_session` con `user`) tiene **su propia base SQLite** (`/data/users/<usuario>.db`: rutinas, entrenos, perfil y ajustes, chat, menús, alimentos, recetas…) y su carpeta de media (`/data/media/u/<usuario>/`), sembradas con la biblioteca común al entrar por primera vez.
`db.use(usuario)` (contextvar) fija la base de cada petición (`gate()`), y `db.q/one/run/tx` van siempre a ella: ninguna consulta puede mezclar personas (probado en `tests/test_isolation.py`: rutinas, ejercicios y alimentos propios, media, chat, ajustes, y el asistente).
- **Asistente**: el worker (`training-agent.service`) pide `/agent/next` (recorre las bases de todas las personas) y el trabajo trae `user`; desde ahí **todas** las llamadas del trabajo (worker y MCP, variable `TRAINING_USER`) llevan `X-Agent-User` y la app solo sirve datos de esa persona. Sin cabecera o con un usuario desconocido → 400.
- **Migración**: la base anterior a las cuentas (`/data/training.db` y `/data/media/*`) pasa, la primera vez que entra, al usuario de `LEGACY_OWNER` (manifest: `dsoldevila`); nadie más la ve. Una cookie sin `user` (anterior a las cuentas) pide volver a entrar.
- Tras actualizar `host-agent/`: `sudo -E host-agent/install.sh` y reiniciar `training-agent`.

## Casas (Nutrición compartida)

Una **casa** es un espacio compartido de Nutrición: sus **alimentos propios, recetas, menú, compra y trabajos del asistente** viven en `/data/casas/<slug>.db` (mismo esquema que la base personal, sembrada con la biblioteca) y los ven todas las personas asignadas. Una persona puede estar en **una o varias casas** y elige cuál usa (botón de la barra superior, `static/js/casas.js`); sin casa activa trabaja con su menú personal de siempre.
- **Lo personal no se comparte**: perfil y objetivos de macros (`nutri.targets()` y `/agent/nutrition/profile` leen siempre la base personal con `db.personal()`), entrenos, rutinas, chat y ajustes. El «Personas» del menú sigue siendo local del navegador (la primera vez se pone al número de personas de la casa).
- **Registro** (`casas.py`, `/data/casas/_registro.db`): `casas`, `members(casa, user, role owner|member)` y `active(user → casa)`. Cualquier persona con sesión crea casas (queda como `owner`; opción de **copiar** su menú, recetas y alimentos propios actuales con `nutri.export_part/import_part`); quien administra asigna/quita personas (nombre de usuario válido; no hace falta que ya haya entrado), renombra y elimina; cualquiera puede salirse. La casa no se queda sin administración mientras haya más gente ni sin personas. **Eliminar** aparta la base en `/data/casas/_eliminadas/` (no se borra).
- **Aislamiento**: `db.use_casa(slug)` (contextvar `_space`) hace que `db.q/one/run/tx` vayan a la base de la casa; lo activa el `before_request` del blueprint de nutrición (`casas.select_casa`) **solo si la persona es miembro**; el resto de rutas siguen en la base personal. Probado en `tests/test_casas.py` (compartir, varias casas, no miembros, solo administra quien es `owner`, trabajos, asistente) y `tests/ui_casas.py` (Playwright, escritorio y móvil).
- **Asistente**: los trabajos de plan y Cocinar de una casa se encolan en la base de la casa con `requested_by`; `/agent/next` también recorre las casas y el trabajo trae `user` (quien lo pidió: de él salen los objetivos; si ya no es miembro, el trabajo falla) y `casa`. El worker manda `X-Agent-Casa` (y el MCP `TRAINING_CASA`); un trabajo de chat lleva la casa activa en ese momento. Sin cabecera, la casa activa de la persona; con una casa de la que no es miembro → 400. `nutrition_profile` devuelve `casa {name, members}` y los prompts piden respetar lo de las demás personas.
- **Límites**: la exportación JSON completa (Ajustes) sigue siendo la personal (el CSV del menú sí es el de la casa activa); no hay roles más finos que administra/miembro; el chat del asistente es personal.
- Tras actualizar: `deploy.sh vNN` (instala también el worker; cambió `worker.py`, `training_mcp.py` y los prompts).

## Seguridad

- Sesión del portal (cookie `homelab_session`, misma `SECRET_KEY` copiada a `training-auth`), CSRF, mismo origen; `/agent/*` solo por ClusterIP y con token (404 bajo el prefijo).
- El modelo corre con `--restricted --tools ""`, solo con el MCP `training`; sin Vault, kubeconfig ni Bash. Los textos de la app son datos no fiables.
- Ediciones del asistente con motivo obligatorio y versión previa guardada (deshacer en un clic). No puede borrar entrenamientos ni ejercicios de la biblioteca; archivar rutinas solo si se lo pides.
- Subidas: se validan los primeros bytes (solo imágenes/vídeos conocidos), se sirven con su tipo real y `CSP: sandbox`, nombres aleatorios; NetworkPolicy: el pod solo sale a DNS.

## Despliegue (un solo comando)

```bash
sudo -E /home/claude/homelab-training/deploy.sh [vNN]
```

Descarga la base de ejercicios (una vez, necesita internet y crea un venv temporal con Pillow), crea ns/secretos/token, construye la imagen, aplica los manifiestos de
`homelab-infra/training/` (y el acceso de `traefik-private` al namespace), instala `training-agent.service` y publica el portal v20 con los grupos «Entrenamiento» y «Nutrición».
Después commitea el cambio de tag en `homelab-infra`.

## Piezas

| Ruta | Qué es |
|---|---|
| `app.py`, `core.py`, `db.py` | API Flask: ejercicios y medios, rutinas con versiones, entrenamientos, estadísticas, exportar/importar, chat y API del agente |
| `data/exercises.json`, `static/ex/` | Base de ejercicios (generada por `tools/build_exercises.py`; las imágenes no van a git) |
| `static/`, `templates/` | Frontend (Liquid Glass): panel, rutinas, entrenar, ejercicios, asistente, ajustes |
| `casas.py`, `static/js/casas.js` | Casas: registro de casas/miembros/casa activa, API y gestor de la barra superior |
| `nutri.py`, `data/foods.json` | Nutrición: alimentos, recetas, menú por días, compra, historial, trabajos del asistente, exportar/importar |
| `host-agent/worker.py`, `training_mcp.py`, `prompt/` | Worker (chat, evaluaciones y planes de comidas), servidor MCP y prompts (`system_prompt.md`, `eval_prompt.md`, `plan_prompt.md`, `cook_prompt.md`) |
| `host-agent/install.sh`, `set-token.sh` | Instalación del servicio y token compartido |
| `tests/` | pytest (`pytest -q tests --ignore=tests/ui_smoke.py`) y prueba de interfaz con Playwright (`tests/ui_smoke.py <carpeta>`) |

Variables de la app: `DB_PATH`, `MEDIA_DIR`, `URL_PREFIX` (vacío), `SECRET_KEY`, `AGENT_TOKEN`, `COOKIE_SECURE`, `TRAINING_TZ` (Europe/Madrid). Del worker (`/etc/training-agent/env`):
`TRAINING_URL`, `TRAINING_MODEL`, `TRAINING_EFFORT`, `TRAINING_TURN_TIMEOUT`, `TRAINING_EVAL_TIMEOUT`, `TRAINING_MAX_BUDGET_USD`.

## Límites conocidos

- Los nombres de los ejercicios de la biblioteca están en inglés (los de cardio propios, en español); puedes poner un «nombre en español» a cualquiera y se conserva al exportar.
- La unidad (kg/lb) solo cambia la etiqueta; no convierte valores guardados.
- Tras cambiar `host-agent/`, hay que reinstalar el agente (`sudo host-agent/install.sh && sudo systemctl restart training-agent`): el servicio ejecuta la copia de `/opt/training-agent`.
- No sustituye a un entrenador ni a un médico.
