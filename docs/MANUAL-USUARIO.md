# Manual de Usuario - Rugby Analyzer

## Indice

1. [Descripcion General del Sistema](#descripcion-general-del-sistema)
2. [Requisitos de Hardware](#requisitos-de-hardware)
3. [Requisitos del Video](#requisitos-del-video)
4. [Modos de Tracking](#modos-de-tracking)
5. [Guia de Uso Paso a Paso](#guia-de-uso-paso-a-paso)
6. [Tips para Mejores Resultados](#tips-para-mejores-resultados)
7. [Limitaciones Conocidas](#limitaciones-conocidas)
8. [Resolucion de Problemas](#resolucion-de-problemas)

---

## Descripcion General del Sistema

Rugby Analyzer es una aplicacion de analisis de video para rugby que utiliza vision por computadora e inteligencia artificial para rastrear jugadores y la pelota, generar metricas de rendimiento y proporcionar analisis tacticos automatizados.

### Tecnologias Principales

- **Deteccion de objetos:** YOLOv8n (version nano, optimizada para velocidad)
- **Tracking multi-objeto:** ByteTrack (asociacion basada en IoU)
- **Backend:** Python 3.11 con FastAPI
- **Frontend:** React con TypeScript
- **IA conversacional:** Soporte para OpenAI, Anthropic y Gemini

### Que Puede Hacer el Sistema

- Rastrear jugadores individuales o grupos a lo largo del video
- Calcular distancias recorridas, velocidades maximas y promedio
- Generar mapas de calor por jugador
- Visualizar rutas de desplazamiento sobre un diagrama 2D de la cancha
- Detectar automaticamente jugadas (tackles, scrums, rucks, line-outs, trys)
- Detectar sprints repetidos (RSA - Repeated Sprint Ability)
- Comparar rendimiento entre jugadores
- Generar reportes PDF con metricas y graficos
- Proporcionar analisis tactico via chat con IA

---

## Requisitos de Hardware

### Minimo (con GPU)

| Componente | Requisito |
|---|---|
| GPU | NVIDIA GTX 1060 6GB VRAM o superior |
| RAM | 16 GB |
| CPU | Intel i5 / AMD Ryzen 5 o equivalente |
| Almacenamiento | 10 GB libres (videos + modelos) |

### Recomendado

| Componente | Requisito |
|---|---|
| GPU | NVIDIA RTX 2060 8GB VRAM o superior |
| RAM | 32 GB |
| CPU | Intel i7 / AMD Ryzen 7 o equivalente |
| Almacenamiento | SSD con 50 GB libres |

### Modo CPU (sin GPU)

El sistema puede funcionar sin GPU dedicada, pero el procesamiento sera significativamente mas lento (5-10x). Recomendado unicamente para videos cortos (menos de 2 minutos) o pruebas.

| Componente | Requisito |
|---|---|
| RAM | 16 GB minimo |
| CPU | Intel i7 / AMD Ryzen 7 (8+ nucleos recomendado) |

---

## Requisitos del Video

### Formatos Soportados

| Formato | Extension | Notas |
|---|---|---|
| MP4 | `.mp4` | Recomendado. Mejor compatibilidad |
| AVI | `.avi` | Soportado |
| MOV | `.mov` | Soportado (formato Apple) |
| MKV | `.mkv` | Soportado |

### Resolucion

| Resolucion | Calidad de Tracking | Velocidad |
|---|---|---|
| 720p (1280x720) | Buena | Rapida |
| 1080p (1920x1080) | Muy buena | Media |
| 4K (3840x2160) | Excelente | Lenta |

**Recomendacion:** 1080p ofrece el mejor balance entre calidad de deteccion y velocidad de procesamiento.

### Angulo de Camara

Para obtener los mejores resultados:

- **Ideal:** Camara elevada (tribuna, torre de filmacion) con vista lateral completa de la cancha
- **Aceptable:** Camara en angulo diagonal que cubra al menos la mitad de la cancha
- **No recomendado:** Camara a nivel de cancha o con angulo muy cerrado

La camara debe estar **fija** (sin movimiento) o con movimiento minimo (paneo suave). Los videos con camara en mano producen resultados inferiores.

### Iluminacion

- **Ideal:** Luz natural diurna uniforme o iluminacion artificial de cancha profesional
- **Aceptable:** Iluminacion mixta sin sombras fuertes
- **Problematico:** Contraluz, sombras marcadas, iluminacion insuficiente, reflejos fuertes

### Duracion Recomendada

| Duracion | Uso Recomendado |
|---|---|
| 30s - 2min | Analisis de jugadas especificas. Ideal para pruebas |
| 2min - 10min | Analisis de secuencias de juego |
| 10min - 40min | Medio tiempo completo |
| 40min+ | Partido completo (requiere hardware potente) |

**Nota:** A mayor duracion, mayor sera el tiempo de procesamiento y el uso de memoria RAM.

### Otras Recomendaciones para el Video

- Los jugadores deben ser visibles (no tapados por graficos de TV)
- Evitar videos con superposiciones de publicidad que cubran jugadores
- El framerate ideal es 25-30 fps (mas fps = mas precision pero mas procesamiento)
- Evitar videos comprimidos en exceso (bitrate muy bajo genera artefactos)

---

## Modos de Tracking

El sistema ofrece cuatro modos de rastreo:

### 1. Jugador Individual (Single Player)

Rastrea a un unico jugador seleccionado por el usuario. Ideal para analisis de rendimiento individual detallado.

**Como funciona:** El usuario selecciona al jugador dibujando un recuadro sobre el en el video. El sistema identifica al jugador por IoU (Intersection over Union) y lo sigue durante todo el video.

**Metricas generadas:**
- Distancia total recorrida
- Velocidad maxima y promedio
- Cantidad de sprints
- Mapa de calor individual
- Ruta de desplazamiento

### 2. Portador de Pelota (Ball Carrier)

Rastrea automaticamente al jugador que lleva la pelota en cada momento.

**Como funciona:** El sistema detecta la pelota y determina cual jugador esta mas cerca de ella, cambiando el tracking cuando la pelota cambia de manos.

### 3. Solo Pelota (Ball Only)

Rastrea unicamente la pelota a lo largo del video.

**Metricas generadas:**
- Distancia de pases
- Velocidad de la pelota
- Patrones de circulacion

### 4. Grupo (Group Tracking)

Rastrea a multiples jugadores seleccionados simultaneamente. Ideal para analisis de lineas (forwards, backs) o equipos completos.

**Metricas generadas:**
- Distancia individual de cada jugador
- Comparativa de velocidades
- Distribucion espacial del grupo
- Tabla comparativa

---

## Guia de Uso Paso a Paso

La interfaz se organiza en pestanas laterales. A continuacion se detalla como utilizar cada una.

### Pestana: Video

Esta es la pestana inicial donde se carga y configura el video.

#### Paso 1: Cargar el Video

1. Hacer clic en el area de carga o arrastrar un archivo de video
2. Los formatos aceptados son: MP4, AVI, MOV, MKV
3. Esperar a que se complete la subida (se muestra barra de progreso)
4. Una vez cargado, se muestra la vista previa del primer frame

#### Paso 2: Seleccionar Modo de Tracking

1. Seleccionar uno de los cuatro modos disponibles en el selector superior:
   - Jugador Individual
   - Portador de Pelota
   - Solo Pelota
   - Grupo
2. Si se elige "Jugador Individual" o "Grupo", se debe seleccionar al jugador o jugadores dibujando un recuadro sobre ellos en el frame del video

#### Paso 3: Calibrar la Cancha

La calibracion permite al sistema convertir las coordenadas de pixeles del video a metros reales sobre la cancha. Hay tres opciones:

**Opcion A - Zona de Juego (recomendada):**
1. En la pestana "Zona de Juego" del panel de calibracion, se muestra un diagrama 2D de la cancha
2. Dibujar un rectangulo sobre el diagrama indicando que porcion de la cancha es visible en el video
3. Hacer clic y arrastrar desde una esquina hasta la esquina opuesta
4. El rectangulo debe tener un minimo de 10m x 10m
5. Presionar "Aplicar Zona de Juego"

**Opcion B - Automatica:**
1. Capturar un frame claro donde se vean las lineas de la cancha
2. Presionar "Auto Calibrate"
3. El sistema detecta automaticamente las lineas y calcula la transformacion
4. Verificar que la deteccion sea correcta

**Opcion C - Manual (puntos):**
1. Seleccionar la pestana "Manual"
2. Identificar al menos 4 puntos conocidos en el video (intersecciones de lineas)
3. Para cada punto: seleccionar la coordenada de cancha correspondiente del dropdown y hacer clic en el video donde se ve ese punto
4. Repetir para al menos 4 puntos (mas puntos = mayor precision)
5. Presionar "Calibrate"

#### Paso 4: Iniciar Procesamiento

1. Presionar el boton "Procesar Video"
2. El sistema comenzara a analizar frame por frame
3. Se muestra el progreso en tiempo real via WebSocket

---

### Pestana: Analisis

En esta pestana se visualizan los resultados del tracking sobre la cancha 2D.

#### Visualizacion de Rutas

- Las rutas de los jugadores se dibujan como lineas de colores sobre el diagrama de cancha
- Cada jugador tiene un color asignado
- Se puede activar/desactivar la visualizacion por jugador

#### Mapa de Calor

- Seleccionar un jugador para ver su mapa de calor individual
- Las zonas mas calientes (rojo) indican donde paso mas tiempo
- Las zonas frias (azul) indican zonas poco transitadas

#### Controles

- Zoom y paneo sobre la cancha 2D
- Filtrar por rango de tiempo
- Alternar entre vista de rutas y mapa de calor

---

### Pestana: Metricas

Muestra las estadisticas numericas y graficos del analisis.

#### Metricas Disponibles por Jugador

| Metrica | Descripcion |
|---|---|
| Distancia Total | Metros recorridos durante el video |
| Velocidad Maxima | Pico de velocidad alcanzado (km/h) |
| Velocidad Promedio | Velocidad media durante el video (km/h) |
| Sprints | Cantidad de aceleraciones por encima de umbral |
| RSA | Deteccion de sprints repetidos |

#### Graficos

- **Velocidad vs Tiempo:** Muestra la evolucion de la velocidad a lo largo del video
- **Comparativa de Jugadores:** Tabla con metricas lado a lado
- **Analisis por Zonas:** Tiempo en cada tercio de la cancha

#### Analisis RSA (Repeated Sprint Ability)

El sistema detecta automaticamente secuencias de sprints repetidos (esfuerzos de alta intensidad con recuperacion corta). Esto es util para evaluar la capacidad fisica de un jugador.

#### Exportar Reporte PDF

1. Presionar el boton "Exportar PDF" en la pestana de Metricas
2. El reporte incluye:
   - Metricas de todos los jugadores rastreados
   - Diagrama de cancha con rutas
   - Graficos de velocidad
   - Resumen de jugadas detectadas

---

### Pestana: Jugadas

Detecta automaticamente eventos/jugadas del partido.

#### Tipos de Jugadas Detectadas

| Jugada | Descripcion |
|---|---|
| Tackle | Contacto entre jugadores con cambio brusco de movimiento |
| Scrum | Formacion de 8 jugadores en posicion agrupada |
| Ruck | Agrupacion de jugadores sobre la pelota en el piso |
| Line-out | Formacion lateral para saque desde la linea de touch |
| Try | Apoyo de la pelota en el in-goal |

#### Como Usar

1. Una vez procesado el video, las jugadas detectadas aparecen en una linea de tiempo
2. Hacer clic en una jugada para ir al momento exacto del video
3. Cada jugada tiene una confianza asociada (porcentaje)
4. El sistema de IA puede confirmar o explicar la jugada detectada

---

### Pestana: IA Chat

Interfaz de chat para interactuar con un asistente de IA sobre el analisis.

#### Proveedores de IA Soportados

- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)

#### Configuracion

1. Ir a Configuracion (icono de engranaje)
2. Ingresar la API key del proveedor deseado
3. Seleccionar el proveedor activo

#### Ejemplos de Consultas

- "Analiza el posicionamiento del jugador 9 durante los primeros 5 minutos"
- "Que jugador cubrio mas distancia?"
- "Identifica patrones de ataque del equipo"
- "Compara la actividad de los forwards vs los backs"
- "Cuantos sprints repetidos tuvo el jugador seleccionado?"

#### Como Funciona

El chat envia el contexto del analisis actual (metricas, jugadas detectadas, rutas) junto con la consulta del usuario al proveedor de IA, que genera una respuesta contextualizada.

---

## Tips para Mejores Resultados

### Preparacion del Video

1. **Usar video de la mejor calidad posible** - Evitar comprimir el video antes de subirlo
2. **Preferir angulo elevado** - Una camara en la tribuna o en torre produce mucho mejor tracking que una camara a nivel de cancha
3. **Evitar videos con graficos superpuestos** - Scoreboards y publicidades pueden confundir al detector
4. **Recortar el video** antes de subirlo si solo interesa una jugada especifica

### Calibracion

1. **Zona de Juego es la opcion mas simple y efectiva** para la mayoria de los casos
2. Para calibracion manual, usar **intersecciones de lineas claramente visibles** como puntos de referencia
3. **Cuantos mas puntos** en calibracion manual, mejor sera la precision (minimo 4, recomendado 6+)
4. Si la camara se mueve durante el video, la calibracion puede perder precision

### Seleccion de Jugador

1. **Dibujar el recuadro ajustado** al jugador (sin mucho espacio extra)
2. Seleccionar al jugador en un frame donde este **claramente visible y separado** de otros
3. Evitar seleccionar cuando hay jugadores superpuestos

### Analisis con IA

1. **Ser especifico** en las preguntas al chat
2. Hacer preguntas sobre datos que el sistema ya calculo (distancias, velocidades, jugadas)
3. El chat funciona mejor cuando el video ya fue procesado completamente

---

## Limitaciones Conocidas

### Deteccion y Tracking

- **Oclusion:** Cuando los jugadores se superponen (scrums, rucks), el tracking puede perder identidades
- **Cambio de ID:** En situaciones de contacto intenso, ByteTrack puede asignar un nuevo ID al mismo jugador
- **Pelota pequena:** La deteccion de la pelota es menos confiable a distancias grandes o con baja resolucion
- **Jugadores similares:** Sin distincion de colores de camiseta, el sistema puede confundir jugadores del mismo equipo

### Calibracion

- La calibracion asume una cancha plana (no compensa por terrenos irregulares)
- La calibracion es estatica: si la camara se mueve, los calculos de distancia pierden precision
- La auto-calibracion requiere que las lineas de la cancha sean claramente visibles

### Metricas

- Las velocidades son aproximaciones basadas en el framerate del video
- Con baja tasa de frames (< 15 fps), las velocidades instantaneas pueden ser imprecisas
- Las distancias se calculan frame a frame, por lo que movimientos muy rapidos entre frames pueden subestimarse

### Hardware y Rendimiento

- Sin GPU, el procesamiento de un video de 10 minutos puede tardar 30+ minutos
- Videos en 4K requieren significativamente mas RAM y tiempo
- El modelo YOLOv8n prioriza velocidad sobre precision (existen versiones mas precisas pero mas lentas)

### IA Chat

- Requiere una API key valida del proveedor seleccionado
- Las respuestas dependen de la calidad del modelo de IA utilizado
- El contexto enviado al chat tiene un limite de tokens

---

## Resolucion de Problemas

### El video no se carga

- Verificar que el formato sea MP4, AVI, MOV o MKV
- Verificar que el archivo no este corrupto
- Verificar que el tamano no exceda el limite del servidor

### El procesamiento es muy lento

- Verificar que la GPU esta siendo utilizada (revisar logs del backend)
- Reducir la resolucion del video a 720p
- Procesar segmentos mas cortos del video

### El tracking pierde al jugador

- Verificar que el jugador sea visible durante todo el clip
- Intentar con un frame de seleccion diferente
- Usar un video con mejor resolucion o angulo

### Las distancias no son realistas

- Verificar la calibracion: la zona de juego debe coincidir con lo que se ve en el video
- Si se usa calibracion manual, verificar que los puntos esten correctamente mapeados
- Asegurarse de que la camara no se mueva durante el clip analizado

### El chat de IA no responde

- Verificar que la API key este configurada correctamente en Configuracion
- Verificar la conexion a internet
- Intentar con un proveedor diferente

### Error al generar reporte PDF

- Asegurarse de que el analisis este completo antes de exportar
- Verificar que haya metricas calculadas (al menos un jugador rastreado)

---

## Contacto y Soporte

Para reportar bugs o solicitar mejoras, utilizar el repositorio del proyecto en GitHub.
