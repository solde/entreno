# homelab-training — Entrenamiento y Nutrición (portal.solde.cat/entreno)

Sección **Entrenamiento** del portal de administración: gestión de rutinas, base de ejercicios con imágenes/vídeos, entrenamiento guiado con
cronómetros de ejercicio y descanso, panel de progreso, asistente de IA con acceso a los datos (lee y edita rutinas, y puede evaluar el
desempeño y ajustar las rutinas automáticamente) y copia de seguridad (exportar/importar).

```
navegador ──► portal.solde.cat/entreno (Flask + SQLite, ns training; sesión y cookie del portal)
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
- **Asistente** (chat) y **evaluación automática**: lee ejercicios, rutinas, entrenamientos, estadísticas y perfil, y crea/edita rutinas (cada edición guarda la versión anterior).
  «Evaluar y ajustar con IA» (por rutina o global), o automático **después de cada entrenamiento** o **una vez por semana** (Ajustes). Progresión por doble criterio (reps/RPE), descansos,
  sustitución de ejercicios con molestias; estilo conservador/normal/agresivo.
- **Ajustes**: perfil (objetivo, experiencia, días, material, lesiones), unidades, sonido/vibración/pantalla, ajuste automático, y **exportar/importar** (JSON completo, con o sin imágenes
  propias; CSV de entrenamientos; importación combinar/reemplazar con validación).

## Nutrición (menú diario)

Grupo **Nutrición** del portal (misma app, vistas `menu`, `foods`, `shopping`; el portal lo incrusta con su propio iframe sobre `/entreno/`):

- **Menú en calendario** con vistas **día / semana / mes**: por día seis momentos (desayuno, media mañana, comida, merienda, cena, otros) con alimentos (gramos), recetas (raciones) o entradas libres con
  macros; totales del día frente a tus objetivos (calorías, proteína, hidratos, grasa), marcar como hecho, copiar día o semana, vaciar y **historial con deshacer**. La semana muestra una cuadrícula
  momento × día y el mes un calendario con kcal y puntos de comidas, coloreado según el objetivo (verde ±10 %, ámbar por debajo, rojo por encima).
- **Alimentos y recetas**: 108 alimentos habituales con valores **orientativos** por 100 g (`data/foods.json`, generado por `tools/make_foods.py`), propios ilimitados, favoritos/archivo; recetas con
  ingredientes en gramos y macros por ración.
- **Lista de la compra** de cualquier rango (ingredientes sumados, recetas desglosadas; marcas guardadas en el navegador; copiar al portapapeles).
- **Asistente conectado**: el mismo agente que las rutinas (MCP `training`) lee el perfil nutricional, alimentos, recetas, menú y entrenos, y edita el menú con `plan_set_days` (motivo obligatorio, estado
  anterior guardado → «Deshacer» en el calendario). «**Planificar con IA**» (día/semana/rango + indicaciones) encola un trabajo (`plan_jobs`, prompt `plan_prompt.md`): respeta los días que ya tienen menú tuyo,
  usa tus objetivos/dieta/alergias/gustos/entrenos y verifica los totales. Estimador de objetivos en Ajustes (Mifflin-St Jeor × actividad ± objetivo) para empezar.
- **Datos**: se exportan e importan con el resto (JSON: alimentos propios, recetas y menú; CSV del menú). No sustituye a un dietista; con patologías, embarazo o trastornos alimentarios, consulta a un profesional.

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
`homelab-infra/training/` (y el acceso de `traefik-private` al namespace), instala `training-agent.service` y publica el portal v19 con los grupos «Entrenamiento» y «Nutrición».
Después commitea el cambio de tag en `homelab-infra`.

## Piezas

| Ruta | Qué es |
|---|---|
| `app.py`, `core.py`, `db.py` | API Flask: ejercicios y medios, rutinas con versiones, entrenamientos, estadísticas, exportar/importar, chat y API del agente |
| `data/exercises.json`, `static/ex/` | Base de ejercicios (generada por `tools/build_exercises.py`; las imágenes no van a git) |
| `static/`, `templates/` | Frontend (Liquid Glass): panel, rutinas, entrenar, ejercicios, asistente, ajustes |
| `nutri.py`, `data/foods.json` | Nutrición: alimentos, recetas, menú por días, compra, historial, trabajos del asistente, exportar/importar |
| `host-agent/worker.py`, `training_mcp.py`, `prompt/` | Worker (chat, evaluaciones y planes de comidas), servidor MCP y prompts (`system_prompt.md`, `eval_prompt.md`, `plan_prompt.md`) |
| `host-agent/install.sh`, `set-token.sh` | Instalación del servicio y token compartido |
| `tests/` | pytest (`pytest -q tests --ignore=tests/ui_smoke.py`) y prueba de interfaz con Playwright (`tests/ui_smoke.py <carpeta>`) |

Variables de la app: `DB_PATH`, `MEDIA_DIR`, `URL_PREFIX` (/entreno), `SECRET_KEY`, `AGENT_TOKEN`, `COOKIE_SECURE`, `TRAINING_TZ` (Europe/Madrid). Del worker (`/etc/training-agent/env`):
`TRAINING_URL`, `TRAINING_MODEL`, `TRAINING_EFFORT`, `TRAINING_TURN_TIMEOUT`, `TRAINING_EVAL_TIMEOUT`, `TRAINING_MAX_BUDGET_USD`.

## Límites conocidos

- Los nombres de los ejercicios de la biblioteca están en inglés (los de cardio propios, en español); puedes poner un «nombre en español» a cualquiera y se conserva al exportar.
- La unidad (kg/lb) solo cambia la etiqueta; no convierte valores guardados.
- Tras cambiar `host-agent/`, hay que reinstalar el agente (`sudo host-agent/install.sh && sudo systemctl restart training-agent`): el servicio ejecuta la copia de `/opt/training-agent`.
- No sustituye a un entrenador ni a un médico.
