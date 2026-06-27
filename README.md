## Licencia y uso

Copyright © 2026 Álvaro Rodríguez Villarin. Todos los derechos reservados.

Este software ha sido desarrollado como parte de un Trabajo de Fin de Grado
en la Universidad Alfonso X el Sabio. El código fuente, la arquitectura y la documentación
asociada son propiedad exclusiva del autor.

Se autoriza su consulta y ejecución únicamente con fines de evaluación
académica del TFG. Queda expresamente prohibida la reproducción total o
parcial, la distribución, la modificación y cualquier uso comercial o
académico derivado sin consentimiento escrito del autor.


# BECCA - MDAO v1.0

Herramienta de diseño conceptual multidisciplinar (MDAO) para un UCAV Affordable Mass
tipo CCA tier-2 (Loyal Wingman). Integra aerodinámica, propulsión, misión, pesos,
estabilidad y coste en un único bucle de optimización (OpenMDAO + SciPy SLSQP) con
interfaz gráfica PySide6.

Repositorio: [github.com/alvaroRodvil/BECCA-MDAO](https://github.com/alvaroRodvil/BECCA-MDAO)

---

## Instalación desde cero

### 1. Requisitos previos del sistema

| Dependencia | Versión mínima | Cómo obtenerla |
|---|---|---|
| **Python** | 3.11 | [python.org/downloads](https://www.python.org/downloads/) |
| **Git** | cualquiera | [git-scm.com/downloads](https://git-scm.com/downloads) |
| **LaTeX** | cualquiera (opcional) | ver sección siguiente |

> El resto de dependencias Python (OpenMDAO, PySide6, matplotlib…) se instalan
> automáticamente con `pip` en el paso 3.

#### LaTeX (opcional, mejora el render de las gráficas)

Las gráficas usan el estilo `science` de SciencePlots con renderizado mathtext
(Computer Modern). LaTeX completo no es necesario gracias al modo `no-latex`
(fallback automático), pero si quieres el render más limpio:

- **Windows** → instala [MiKTeX](https://miktex.org/download) (recomendado,
  instala todo lo necesario).
- **macOS** → instala [MacTeX](https://www.tug.org/mactex/) (~4 GB) o
  [BasicTeX](https://www.tug.org/mactex/morepackages.html) (~100 MB, suficiente):
  ```bash
  brew install --cask basictex
  sudo tlmgr update --self
  sudo tlmgr install dvipng type1cm
  ```
- **Linux (Debian/Ubuntu)** →
  ```bash
  sudo apt install texlive-latex-extra dvipng cm-super
  ```

Si LaTeX no está disponible, la GUI cae automáticamente al modo mathtext
(misma fuente, sin subproceso LaTeX) a través de `gui/plot_style.warmup_latex()`:
las gráficas se ven bien igualmente.

---

### 2. Descargar el proyecto

**Opción A — clonando el repositorio (recomendado):**
```bash
git clone https://github.com/alvaroRodvil/BECCA-MDAO.git
cd BECCA-MDAO
```

**Opción B — desde un ZIP:**
Descarga el ZIP desde GitHub (botón *Code → Download ZIP*), descomprímelo y
abre un terminal en la carpeta resultante.

---

### 3. Crear y activar el entorno virtual

```bash
# Crear el entorno (solo la primera vez)
python3.11 -m venv venv

# Activar — Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Activar — Windows (cmd)
venv\Scripts\activate.bat

# Activar — macOS / Linux
source venv/bin/activate
```

El prompt debe cambiar a `(venv) ...` para confirmar que está activo.

---

### 4. Instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

La instalación tarda 1–3 minutos. PySide6 es el paquete más pesado (~120 MB).

Dependencias directas (`requirements.txt`): `numpy`, `openmdao`, `PySide6`,
`matplotlib`, `SciencePlots`. Las transitivas (scipy, networkx, requests…) se
resuelven automáticamente.

---

### 5. Verificar la instalación

```bash
python -c "import openmdao; import PySide6; import matplotlib; print('OK')"
```

Debe imprimir `OK` sin errores.

---

### 6. Ejecutar la aplicación

```bash
python -m gui.app
```

Se abre la ventana principal de BECCA con cuatro pestañas navegables desde la
cabecera superior: `Configuración` → `Ejecución` → `Resultados` → `Gráficas`.

---

## Uso de la aplicación

### Pestaña Configuración

Asistente en 3 pasos para definir el problema de optimización:

1. **Misión** — perfil de la misión (altitudes/Mach de crucero y combate,
   factor de carga en combate, alcance, payload, tiempo de loiter) y un
   selector de **preset de aeronave de referencia**:
   - `Nominal (CCA tier-2)` — configuración por defecto del proyecto.
   - `XQ-58A Valkyrie` (Kratos Defense).
   - `MQ-28A Ghost Bat` (Boeing).
   - `YFQ-44A Fury` (Anduril).

   Cada preset rellena automáticamente parámetros de aeronave, variables de
   diseño y restricciones con valores de referencia de esa plataforma.

2. **Variables de diseño** — tabla editable con los *bounds* (límite inferior/
   superior) y valor de referencia de cada variable de diseño del MDAO
   (envergadura, superficie alar, empuje a nivel del mar, etc.).

3. **Restricciones** — tabla editable de restricciones del optimizador
   (margen estático, velocidad de pérdida, distancia de despegue, *rate of
   climb*, energía específica de combate, factor de carga en giro…), cada una
   activable/desactivable individualmente.

### Pestaña Ejecución

Lanza la optimización (`core/runner.run_mdao`) en un hilo aparte
(`gui/worker.py`, `QThread`) para no bloquear la interfaz. Muestra en
tiempo real:

- Log de iteraciones del optimizador SciPy SLSQP.
- Diagrama **N2** generado por OpenMDAO (acoplamiento entre disciplinas).
- Diagrama **XDSM** del MDAO (`docs/xdsm_ucav.pdf`).

Desde aquí también se lanzan los **estudios adicionales** (`core/studies.py`,
ejecutados en `gui/study_worker.py`):

- **Análisis tornado** — sensibilidad local del objetivo a perturbaciones
  (±10 %) de las entradas clave de la misión.
- **Frontera de Pareto** — barrido de un requisito de misión (p. ej. alcance),
  reoptimizando el diseño completo en cada punto del barrido.

### Pestaña Resultados

Tabla con todos los *outputs* relevantes del problema OpenMDAO tras converger:
geometría, pesos, prestaciones, estabilidad y coste, junto con una barra de
margen visual (`gui/widgets/margin_bar.py`) para cada restricción activa.

### Pestaña Gráficas

Árbol de navegación + lienzo matplotlib con más de 20 gráficas agrupadas por
disciplina (pesos, aerodinámica, estabilidad, propulsión, prestaciones,
misión, geometría), cada una con sus ecuaciones y notas técnicas mostradas
debajo (`gui/plots.py` → `CHART_INFO`). Incluye, entre otras: desglose de
pesos, polar de resistencia, L/D vs Mach, diagrama V-n, viraje sostenido,
envolvente de energía específica (P_s), diagrama de restricciones,
payload-range/radius y planform de la aeronave.

---

## Estructura del proyecto

```
BECCA-MDAO/
│
├── modules/                    # Componentes OpenMDAO (física del MDAO)
│   ├── aerodynamics.py         # Polar de resistencia, Korn-Mason, Oswald
│   ├── geometry.py             # Geometría alar, MAC, empenaje en V, tanques
│   ├── propulsion.py           # Lapse de empuje Mattingly, TSFC, peso motor
│   ├── mission.py              # Breguet crucero/loiter, combate explícito
│   ├── weights.py              # CER Fighter/Attack Raymer, subsistemas
│   ├── stability.py            # NP (Polhamus+DATCOM+Multhopp), SM, Cn_β
│   ├── performance.py          # Despegue, aterrizaje, P_s, giro, RoC
│   └── cost.py                 # Modelo DAPCA IV (RAND), factor Affordable Mass
│
├── core/                       # Orquestación del MDAO (capa Model del MVC)
│   ├── config.py               # FullConfig, MissionConfig, DesignVar, AircraftParams,
│   │                           #   restricciones, presets de aeronaves (PRESETS)
│   ├── model.py                # Grupo OpenMDAO UCAVModel + build_problem()
│   ├── runner.py                # run_mdao(): ejecuta optimización, genera N2
│   ├── diagrams.py             # Física de las gráficas (datos para plots.py)
│   ├── results.py               # ResultsDTO: extrae outputs del Problem
│   └── studies.py               # Análisis tornado y frontera de Pareto
│
├── gui/                        # Interfaz gráfica PySide6 (MVC: View + Controller)
│   ├── app.py                  # Punto de entrada: QApplication + MainWindow
│   ├── style.py                # Paleta de colores y estilos Qt globales
│   ├── plot_style.py           # Tema matplotlib (SciencePlots + paleta BECCA)
│   ├── plots.py                # ← GRÁFICAS: funciones de dibujo + CHART_INFO
│   │                           #   (ecuaciones y observaciones bajo cada gráfica)
│   ├── worker.py                # QThread para ejecutar run_mdao() en segundo plano
│   ├── study_worker.py         # QThread para estudios tornado / Pareto
│   ├── views/
│   │   ├── main_window.py      # Ventana principal y barra de navegación
│   │   ├── setup_view.py       # Pestaña "Configuración" (wizard: misión, DVs, constraints)
│   │   ├── run_view.py         # Pestaña "Ejecución" (log, N2, diagrama XDSM, estudios)
│   │   ├── results_view.py     # Pestaña "Resultados" (tabla de outputs)
│   │   └── plots_view.py       # Pestaña "Gráficas" (árbol + lienzo matplotlib)
│   ├── controllers/
│   │   └── main_controller.py  # Conecta señales View ↔ lógica Model
│   ├── widgets/
│   │   ├── mpl_canvas.py       # Canvas matplotlib reutilizable en Qt
│   │   └── margin_bar.py       # Barra de margen de restricciones
│   └── assets/
│
├── docs/                       # Documentación y diagramas
│   ├── xdsm_ucav.pdf            # Diagrama XDSM del MDAO (se muestra en la GUI)
│   ├── xdsm_ucav.py             # Script pyXDSM para regenerar el diagrama
│   ├── xdsm_ucav.tex            # Fuente LaTeX generada por pyXDSM
│   └── xdsm_ucav.tikz           # TikZ generado por pyXDSM
│
├── requirements.txt            # Dependencias Python del proyecto
└── README.md                   # Esta guía
```

---

## Referencia rápida — dónde está cada cosa

| Quiero modificar… | Archivo |
|---|---|
| Requisitos de misión (alcance, Mach, payload…) | `core/config.py` → `MissionConfig` |
| Parámetros fijos del avión (t/c, flecha, fuselaje…) | `core/config.py` → `AircraftParams` |
| Variables de diseño y sus bounds | `core/config.py` → `_default_design_vars()` |
| Restricciones del optimizador | `core/config.py` → `_default_constraints()` |
| Presets de aeronaves (XQ-58A, MQ-28A, YFQ-44A…) | `core/config.py` → `PRESETS` |
| La física de cualquier módulo OpenMDAO | `modules/<nombre>.py` |
| Los datos que alimentan una gráfica | `core/diagrams.py` |
| El dibujo matplotlib de una gráfica | `gui/plots.py` → función `plot_<nombre>()` |
| Las ecuaciones bajo cada gráfica | `gui/plots.py` → `CHART_INFO` |
| El estilo visual de las gráficas (fuentes, colores…) | `gui/plot_style.py` |
| Colores y estilos de la interfaz Qt | `gui/style.py` |
| El análisis tornado / frontera de Pareto | `core/studies.py` |
| Regenerar el diagrama XDSM | `python docs/xdsm_ucav.py` |

---

## Solución de problemas

| Síntoma | Causa probable / solución |
|---|---|
| `ModuleNotFoundError` al ejecutar `python -m gui.app` | El entorno virtual no está activado, o falta `pip install -r requirements.txt`. |
| Las gráficas se ven con tipografía distinta a la esperada | No hay LaTeX instalado; la GUI usa el fallback `no-latex` automáticamente (no es un error). |
| La optimización no converge | Revisa los *bounds* de las variables de diseño y las restricciones activas en la pestaña Configuración; un rango demasiado estrecho o contradictorio impide la convergencia de SLSQP. |
| La ventana no se abre en Linux (error de plataforma Qt) | Instala las librerías de sistema de Qt (`libxcb`, `libxkbcommon-x11-0` u equivalentes de tu distribución). |
