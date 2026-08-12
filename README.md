# 🦴 PostureGuard

Aplicación desktop nativa para Windows que monitorea tu postura en tiempo real usando tu webcam y genera alertas cuando detecta mala postura. **100% local y orientada a privacidad** — ningún dato sale de tu computadora.

---

## Características

### Detección de postura
- Basada en **MediaPipe Pose Landmarker** (Tasks API) — modelo `pose_landmarker_lite`
- **Modo upper-body**: funciona con solo cabeza + hombros visibles (sin necesitar caderas), ideal para cámaras de escritorio
- **4 tipos de mala postura detectados:**
  - 🔴 Cabeza adelantada (*forward head posture*) — la nariz se acerca a la línea de hombros
  - 🔴 Hombros caídos / encorvamiento (*slouch*) — el ancho de hombros se reduce respecto a la calibración
  - 🔴 Inclinación lateral — asimetría en el ángulo de la línea de hombros
  - 🔴 **Hombros fuera de cuadro** — si los hombros desaparecen del encuadre se detecta automáticamente como encorvamiento
- **Histéresis por indicador**: evita falsos positivos — una vez que un problema se limpia, requiere una recuperación del 15% por encima del umbral antes de volver a marcarse
- **Smoothing adaptativo** (ventana de 10 frames) — reduce el jitter de los landmarks

### Sistema de alertas escalonado
| Nivel | Trigger | Acción |
|---|---|---|
| Warning | N seg. de mala postura | Estado interno — sin notificación |
| Alerta L1 | Warning + N seg. adicionales | Toast nativa de Windows + Beep |
| Alerta L2 | L1 + N seg. adicionales | Ventana emergente con cámara en vivo + Beep doble |
| Modo gaming | Pantalla completa detectada | Solo Beep (sin ventanas emergentes) |

> Los tiempos son configurables desde la pantalla de configuración.

### Control de presencia y pausa
- **Pausa manual persistente**: al hacer click en "Pausar monitoreo", el sistema apaga la cámara, libera el dispositivo de hardware (luz LED apaga) y suspende la evaluación hasta que el usuario decida reanudarla.
- **Auto-pausa / Reposo por ausencia (`ABSENT`)**: si te levantás de tu silla o no hay nadie frente a la cámara, PostureGuard entra automáticamente en modo en espera (ícono gris), detiene el conteo de mala postura y reduce el consumo de CPU. Al regresar, retoma limpiamente en estado `GOOD`.

### 🚶 Recordatorios de Pausa Activa (Tiempo Sentado)
- 💡 **Cada 30 minutos (Ideal):** Notificación de **Micropausa (1 a 2 minutos)** para ponerse de pie, estirar las piernas y activar el retorno venoso.
- 🚶 **Cada 50-60 minutos (Máximo):** Notificación de **Descanso Activo (5 a 10 minutos)** para aliviar la carga sobre la columna lumbar y cervical antes de sufrir rigidez.
- **Reset automático:** El temporizador continuo de estar sentado se reinicia automáticamente si te levantás del escritorio por más de 45 segundos.
- Configurable (on/off e intervalos) desde la ventana de **Configuración**.

### UI & Tray
- **System tray siempre activo** con ícono de color según estado (verde/amarillo/rojo/gris)
- Click izquierdo → abre/cierra el **feed de cámara en vivo** (con overlay del esqueleto y métricas)
- Doble click → abre **Estadísticas**
- Click derecho → Menú contextual: Ver cámara, Pausar, Recalibrar, Estadísticas, Configuración, Salir

### Estadísticas
- Dashboard con gráficos matplotlib (diario / semanal / mensual)
- Muestra solo las horas con datos (no 23 barras vacías)
- Navegación con ◀ ▶ entre períodos
- Cards de resumen: % postura correcta, tiempo total, alertas, racha de días

### Configuración
- **Tab Alertas**: tipos de notificación (toast / beep / ventana), tiempos de escalada
- **Tab Sensibilidad**: sliders para cada umbral con tooltips explicativos
- **Tab General**: auto-inicio con Windows, selección de cámara

---

## 📦 Instalación

### Requisitos

- **Python 3.10+**
- **Windows 10 / 11**
- **Webcam** (USB o integrada)

### Pasos

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/posture-guard.git
cd posture-guard

# Instalar dependencias
pip install -e .
```

O directamente con pip:

```bash
pip install -r requirements.txt
```

---

## 🚀 Uso

```bash
python -m posture_guard
```

### Primera vez — Calibración

La app detecta automáticamente que no hay calibración y abre el wizard:

1. **Sentate en tu posición normal de trabajo** con buena postura (hombros hacia atrás, cabeza recta mirando la pantalla)
2. La ventana mostrará tu imagen en vivo con el esqueleto de MediaPipe superpuesto
3. Esperá que el esqueleto sea estable (se ve bien definido en el encuadre)
4. Presioná **"Iniciar Calibración"** y mantenés la posición ~3 segundos
5. PostureGuard captura la referencia y comienza a monitorear

> ⚠️ **Importante:** La cámara debe capturar **cabeza + hombros completos** en el encuadre. No es necesario que se vean las caderas.

### Recalibración

Si cambiás de silla, escritorio o posición de la cámara, recalibrá desde el tray:
- Click derecho en el ícono → **"🎯 Recalibrar"**

---

## 🖥️ Controles

| Acción | Efecto |
|---|---|
| Click izquierdo en tray | Abre / cierra ventana de cámara en vivo |
| Doble click en tray | Abre Estadísticas |
| Click derecho en tray | Menú contextual |
| Tray → Pausar | Pausa el monitoreo (ícono gris) |
| Tray → Recalibrar | Lanza el wizard de calibración |
| Tray → Configuración | Abre el panel de ajustes |
| Cerrar ventana de cámara | Oculta la ventana (el monitoreo sigue) |
| Botón "Pausar" en ventana | Pausa el monitoreo |

---

## 🏗️ Arquitectura

```
posture-guard/
├── src/posture_guard/
│   ├── __main__.py              # Entry point: logging, mutex, High-DPI, env vars
│   ├── app.py                   # Coordinador central — conecta todo via Qt Signals
│   ├── core/
│   │   ├── camera.py            # OpenCV + CAP_DSHOW (rápido en Windows), grab/retrieve
│   │   ├── pose.py              # MediaPipe Tasks API → PoseResult wrapper
│   │   ├── analyzer.py          # 3 detectores upper-body con histéresis + smoothing
│   │   ├── calibration.py       # Captura N frames y promedia métricas de referencia
│   │   ├── state_machine.py     # ABSENT→GOOD→WARNING→ALERT_L1→ALERT_L2 con timers
│   │   └── engine.py            # QThread @ ~3 FPS (300ms), signals al hilo principal
│   ├── alerts/
│   │   ├── manager.py           # Orquesta toast/beep/ventana según estado y config
│   │   ├── toast.py             # Notificaciones nativas con winotify
│   │   ├── sound.py             # winsound.Beep (L1=single, L2=double pattern)
│   │   └── fullscreen_detector.py  # Shell API D3D + geometric check
│   ├── ui/
│   │   ├── styles.py            # Dark theme completo (paleta + QSS)
│   │   ├── tray.py              # System tray con ícono dinámico por color de estado
│   │   ├── feed_window.py       # Popup frameless stay-on-top, draggable, fade-in
│   │   ├── overlay_painter.py   # Dibuja esqueleto + métricas sobre el frame BGR
│   │   ├── calibration_dialog.py  # Wizard con preview en vivo
│   │   ├── settings_dialog.py   # 3 tabs: Alertas / Sensibilidad / General
│   │   └── stats_window.py      # Dashboard matplotlib con navegación temporal
│   ├── data/
│   │   ├── models.py            # Dataclasses: CalibrationProfile, UserConfig, etc.
│   │   ├── database.py          # SQLite: eventos, sesiones, alertas, queries agregadas
│   │   └── config.py            # JSON config con migración automática de campos
│   └── utils/
│       ├── constants.py         # Todas las constantes centralizadas
│       ├── angles.py            # Geometría + MetricsSmoother (moving average)
│       └── platform_win.py      # Registry auto-start + fullscreen helpers
└── tests/
    ├── test_analyzer.py         # 9 tests: detección, histéresis, hombros fuera de frame
    ├── test_state_machine.py    # 11 tests: transiciones, pause/resume, timings
    └── test_angles.py           # 24 tests: geometría, smoothing
```

**Patrón de concurrencia:** Single-process con un único QThread (`VisionEngine`) que procesa los frames. Toda comunicación con la UI es via Qt Signals/Slots (thread-safe). La DB usa una conexión nueva por llamada (thread-safe sin lock).

---

## 🔬 Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

```
44 passed in 0.27s
```

---

## ⚙️ Configuración Avanzada

El archivo de configuración se guarda en:
```
%APPDATA%\PostureGuard\config.json
```

La calibración se guarda en:
```
%APPDATA%\PostureGuard\calibration.json
```

Las estadísticas (SQLite) en:
```
%APPDATA%\PostureGuard\posture_guard.db
```

Para resetear todo:
```bash
Remove-Item "$env:APPDATA\PostureGuard" -Recurse -Force
```

---

## 🧩 Decisiones Técnicas

| Decisión | Rationale |
|---|---|
| **Modo upper-body (sin caderas)** | Las caderas suelen estar fuera del encuadre en cámaras de escritorio. Se usa `shoulder_width` como normalizador en lugar de `torso_height` |
| **Histéresis por indicador** | Evita parpadeo entre estados. Requiere recuperación del 15% más allá del umbral para limpiar un issue |
| **`CAP_DSHOW` en Windows** | Reduce el tiempo de inicialización de cámara de ~3s a ~200ms |
| **`grab()` + `retrieve()`** | Elimina el buffer de OpenCV (siempre el frame más reciente) |
| **MediaPipe Tasks API** | API moderna vs. la legacy `mp.solutions`. El campo `visibility` tiene semántica diferente (oclusión, no confianza) |
| **MetricsSmoother (window=10)** | Promedia los últimos N frames para suavizar jitter de landmarks. El ángulo de tilt (atan2) es el más ruidoso, beneficiado por la ventana mayor |
| **Beep siempre activo en L1/L2** | El modo gaming solo suprime ventanas visuales, no el sonido. El usuario lo desactiva explícitamente en Config |
| **Thread-safe DB** | Cada operación crea su propia conexión SQLite — sin locks ni pools necesarios |
| **Íconos programáticos** | Generados con `QPainter` en tiempo de ejecución — sin archivos de imagen externos |

---


