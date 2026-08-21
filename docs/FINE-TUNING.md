# Guia de Fine-Tuning: Entrenamiento de Modelos YOLO para Rugby

## Tabla de Contenidos

1. [Introduccion](#introduccion)
2. [Requisitos previos](#requisitos-previos)
3. [Paso 1: Extraer frames del video](#paso-1-extraer-frames-del-video)
4. [Paso 2: Etiquetar las imagenes](#paso-2-etiquetar-las-imagenes)
5. [Paso 3: Configurar el dataset](#paso-3-configurar-el-dataset)
6. [Paso 4: Entrenar el modelo](#paso-4-entrenar-el-modelo)
7. [Paso 5: Evaluar resultados](#paso-5-evaluar-resultados)
8. [Paso 6: Usar el modelo personalizado](#paso-6-usar-el-modelo-personalizado)
9. [Tips para mejores resultados](#tips-para-mejores-resultados)

---

## Introduccion

Los modelos YOLOv8 pre-entrenados funcionan bien para deteccion general de personas, pero un modelo fine-tuneado con datos especificos de rugby puede mejorar significativamente la precision en:

- **Deteccion de jugadores** en formaciones cerradas (scrums, rucks)
- **Deteccion de la pelota** de rugby (forma ovalada, a diferencia de pelotas redondas)
- **Distincion entre jugadores y arbitros**
- **Identificacion de formaciones** (scrum, ruck, lineout)
- **Rendimiento en condiciones variables** (lluvia, pasto mojado, sombras)

Un modelo fine-tuneado con 500-1000 imagenes etiquetadas de rugby puede mejorar la precision (mAP) entre un 15-30% comparado con el modelo generico.

---

## Requisitos previos

### Software necesario

```bash
# Python 3.11 o superior
python --version

# Instalar dependencias
pip install ultralytics>=8.0.0
pip install opencv-python-headless>=4.8.0

# Verificar instalacion
python -c "from ultralytics import YOLO; print('OK')"
```

### Hardware recomendado

| Componente | Minimo | Recomendado |
|-----------|--------|-------------|
| GPU | GTX 1060 6GB | RTX 3060 12GB+ |
| RAM | 8 GB | 16 GB+ |
| Disco | 10 GB libres | 50 GB SSD |
| CPU | 4 cores | 8+ cores |

> **Nota:** Es posible entrenar en CPU, pero sera significativamente mas lento (10-50x). Se recomienda encarecidamente usar una GPU NVIDIA con soporte CUDA.

### Cuenta en plataforma de etiquetado

Para etiquetar imagenes necesitaras una cuenta en:
- [Roboflow](https://roboflow.com/) (recomendado, plan gratuito disponible)
- [CVAT](https://www.cvat.ai/) (open source, self-hosted)

---

## Paso 1: Extraer frames del video

Usa el script `extract_frames.py` para extraer frames de tus videos de rugby.

### Uso basico

```bash
cd backend/scripts

# Extraer un frame por segundo
python extract_frames.py --video ../../videos/partido.mp4 --output ../../frames/

# Extraer frames cada 0.5 segundos (mas densidad para escenas de accion)
python extract_frames.py --video ../../videos/partido.mp4 --interval 0.5 --max-frames 1000

# Extraer solo un segmento del video (minuto 10 al 20)
python extract_frames.py --video ../../videos/partido.mp4 --start-time 600 --end-time 1200

# Redimensionar frames a 640px de ancho
python extract_frames.py --video ../../videos/partido.mp4 --resize 640
```

### Recomendaciones para la extraccion

- **Variedad de escenas:** Extrae frames de diferentes momentos del partido
- **Diferentes jugadas:** Asegurate de capturar scrums, rucks, lineouts, tackles, tries
- **Diferentes angulos:** Si tienes videos con multiples camaras, usa todos
- **Condiciones variadas:** Incluye partidos con sol, nublado, nocturno (si aplica)
- **Cantidad recomendada:** Minimo 500 frames, idealmente 1000-2000

### Estrategia por jugada

```bash
# Frames de scrums (intervalo corto porque duran poco)
python extract_frames.py --video scrum_clips.mp4 --interval 0.3 --max-frames 200

# Frames de juego abierto (intervalo normal)
python extract_frames.py --video juego_abierto.mp4 --interval 1.0 --max-frames 300

# Frames de lineouts
python extract_frames.py --video lineout_clips.mp4 --interval 0.5 --max-frames 150
```

---

## Paso 2: Etiquetar las imagenes

### Opcion A: Roboflow (Recomendado)

[Roboflow](https://roboflow.com/) ofrece una interfaz web intuitiva para etiquetar imagenes.

#### Configuracion inicial

1. Crea una cuenta gratuita en [app.roboflow.com](https://app.roboflow.com/)
2. Crea un nuevo proyecto:
   - Tipo: **Object Detection**
   - Nombre: "Rugby Detection"
3. Sube los frames extraidos
4. Define las clases:
   - `player` - Jugador de campo
   - `ball` - Pelota de rugby
   - `referee` - Arbitro/juez de linea
   - `scrum` - Formacion de scrum
   - `ruck` - Formacion de ruck
   - `lineout` - Formacion de lineout

#### Tips de etiquetado en Roboflow

- Usa la herramienta de bounding box rectangular
- Ajusta la caja lo mas ceñida posible al objeto
- Usa atajos de teclado para cambiar de clase rapidamente
- Marca "null" las imagenes sin objetos de interes (entrena el modelo a ignorar fondos)

#### Exportar desde Roboflow

1. Ve a "Generate" > "New Version"
2. Configura preprocessing: Auto-Orient, Resize a 640x640
3. Configura augmentation (opcional): Flip horizontal, Brillo +-15%
4. Selecciona formato de exportacion: **YOLO v8**
5. Descarga el dataset

### Opcion B: CVAT (Open Source)

[CVAT](https://www.cvat.ai/) es una herramienta open source para anotacion de imagenes.

#### Configuracion inicial

1. Accede a [app.cvat.ai](https://app.cvat.ai/) o instala localmente:
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```
2. Crea un nuevo proyecto con las etiquetas:
   - `player`, `ball`, `referee`, `scrum`, `ruck`, `lineout`
3. Crea una tarea y sube los frames

#### Tips de etiquetado en CVAT

- Usa el modo "Track" para secuencias de frames consecutivos
- Usa interpolacion para reducir trabajo en frames similares
- Revisa con el modo "Issues" para marcar frames dudosos

#### Exportar desde CVAT

1. Ve a Menu > Export
2. Selecciona formato: **YOLO 1.1**
3. Descarga y descomprime

---

## Paso 3: Configurar el dataset

### Estructura de carpetas

Organiza tu dataset en la siguiente estructura:

```
datasets/rugby/
├── train/
│   ├── images/          # 70-80% de las imagenes
│   │   ├── frame_000001.png
│   │   ├── frame_000002.png
│   │   └── ...
│   └── labels/          # Archivos .txt con las anotaciones
│       ├── frame_000001.txt
│       ├── frame_000002.txt
│       └── ...
├── val/
│   ├── images/          # 10-20% de las imagenes
│   └── labels/
└── test/
    ├── images/          # 10% de las imagenes (opcional)
    └── labels/
```

### Formato de etiquetas YOLO

Cada archivo `.txt` contiene una linea por objeto:

```
<class_id> <x_center> <y_center> <width> <height>
```

Ejemplo (`frame_000001.txt`):
```
0 0.453 0.612 0.089 0.245    # player en el centro
0 0.221 0.534 0.076 0.198    # otro player
1 0.567 0.723 0.023 0.031    # ball (pequeña)
2 0.789 0.498 0.065 0.210    # referee
```

> Todas las coordenadas estan normalizadas entre 0 y 1 respecto al tamaño de la imagen.

### Configurar rugby_dataset.yaml

Edita el archivo `backend/scripts/rugby_dataset.yaml`:

```yaml
# Ajustar la ruta raiz segun donde tengas el dataset
path: /ruta/absoluta/a/datasets/rugby

# Rutas relativas al path
train: train/images
val: val/images
test: test/images

# Clases (no modificar el orden si ya etiquetaste con este orden)
nc: 6
names:
  0: player
  1: ball
  2: referee
  3: scrum
  4: ruck
  5: lineout
```

---

## Paso 4: Entrenar el modelo

### Entrenamiento basico

```bash
cd backend/scripts

# Entrenamiento con configuracion por defecto (recomendado para empezar)
python train_model.py --data rugby_dataset.yaml --epochs 100

# Con modelo mas grande (mejor precision, mas lento)
python train_model.py --model yolov8m.pt --data rugby_dataset.yaml --epochs 150

# Con imagenes mas grandes (mejor para objetos pequeños como la pelota)
python train_model.py --data rugby_dataset.yaml --imgsz 1280 --batch 8
```

### Entrenamiento avanzado

```bash
# Mas epocas con early stopping
python train_model.py --data rugby_dataset.yaml --epochs 300 --patience 50

# GPU especifica
python train_model.py --data rugby_dataset.yaml --device 0

# Reanudar entrenamiento interrumpido
python train_model.py --data rugby_dataset.yaml --resume

# Batch mas pequeño si hay errores de memoria
python train_model.py --data rugby_dataset.yaml --batch 8
```

### Que esperar durante el entrenamiento

- **Epoca 1-10:** El modelo aprende patrones basicos, loss alto
- **Epoca 10-50:** Mejora rapida, las metricas suben significativamente
- **Epoca 50-100:** Mejora gradual, precision se estabiliza
- **Early stopping:** Si no mejora en 50 epocas consecutivas, se detiene automaticamente

### Tiempos estimados de entrenamiento

| Modelo | GPU | 100 epocas (500 imgs) |
|--------|-----|----------------------|
| yolov8n | RTX 3060 | ~30 min |
| yolov8s | RTX 3060 | ~1 hora |
| yolov8m | RTX 3060 | ~2 horas |
| yolov8l | RTX 3060 | ~4 horas |
| yolov8s | CPU | ~12 horas |

---

## Paso 5: Evaluar resultados

### Metricas principales

Despues del entrenamiento, revisa las metricas en `runs/train/rugby-custom/`:

| Metrica | Que mide | Objetivo |
|---------|----------|----------|
| **mAP50** | Precision promedio a IoU 0.5 | > 0.8 (bueno), > 0.9 (excelente) |
| **mAP50-95** | Precision promedio a IoU 0.5-0.95 | > 0.6 (bueno), > 0.7 (excelente) |
| **Precision** | % de detecciones correctas | > 0.85 |
| **Recall** | % de objetos detectados | > 0.80 |

### Archivos de resultados

```
runs/train/rugby-custom/
├── weights/
│   ├── best.pt          # Mejor modelo (usar este)
│   └── last.pt          # Ultimo checkpoint
├── results.csv          # Metricas por epoca
├── results.png          # Graficas de entrenamiento
├── confusion_matrix.png # Matriz de confusion
├── F1_curve.png         # Curva F1
├── PR_curve.png         # Curva Precision-Recall
└── val_batch0_pred.jpg  # Predicciones en validacion
```

### Interpretar resultados

- **Confusion matrix:** Revisa si el modelo confunde jugadores con arbitros
- **F1 curve:** El punto optimo de confianza esta en el pico de la curva
- **Loss curves:** Deben decrecer. Si val_loss sube mientras train_loss baja = overfitting
- **Predicciones de validacion:** Revisa visualmente si las detecciones son correctas

### Si los resultados no son satisfactorios

1. **mAP bajo (<0.7):** Necesitas mas datos o mejor calidad de etiquetas
2. **Overfitting:** Agrega mas augmentation, reduce epocas, usa modelo mas pequeño
3. **Clase especifica con bajo recall:** Agrega mas ejemplos de esa clase
4. **Pelota dificil de detectar:** Usa imgsz 1280 y agrega mas ejemplos de pelota

---

## Paso 6: Usar el modelo personalizado

### Opcion 1: Variable de entorno

```bash
export YOLO_MODEL_PATH=runs/train/rugby-custom/weights/best.pt
# Luego iniciar Rugby Analyzer normalmente
```

### Opcion 2: Configuracion en la UI

1. Abre Rugby Analyzer en el navegador
2. Ve a **Configuracion** (icono de engranaje)
3. En "Modelo YOLO", selecciona "Modelo personalizado"
4. Ingresa la ruta al archivo `.pt`

### Opcion 3: Archivo .env

```env
YOLO_MODEL_PATH=/ruta/completa/a/best.pt
```

### Verificar el modelo

```python
from ultralytics import YOLO

# Cargar modelo personalizado
model = YOLO("runs/train/rugby-custom/weights/best.pt")

# Probar con una imagen
results = model("test_image.jpg")
results[0].show()
```

---

## Tips para mejores resultados

### Cantidad y calidad de datos

- **Minimo:** 500 imagenes etiquetadas
- **Recomendado:** 1000-2000 imagenes
- **Calidad sobre cantidad:** 500 imagenes bien etiquetadas > 2000 mal etiquetadas
- **Revision:** Dedica tiempo a revisar y corregir etiquetas erroneas

### Diversidad del dataset

Asegurate de incluir:

- [ ] Diferentes equipos y camisetas
- [ ] Diferentes canchas (cesped natural, sintetico, seco, mojado)
- [ ] Diferentes angulos de camara (lateral, aereo, behind-goal)
- [ ] Diferentes niveles de zoom
- [ ] Diferentes condiciones de luz (sol directo, nublado, nocturno)
- [ ] Jugadores en movimiento y estaticos
- [ ] Diferentes formaciones (scrum, ruck, lineout, maul)
- [ ] Pelota en diferentes posiciones (en mano, en aire, en piso)

### Criterios de etiquetado para rugby

#### Player vs Referee
- **Player:** Camiseta de color del equipo, pantalon corto
- **Referee:** Generalmente de negro o color neutro, sin numero visible en espalda

#### Cuando etiquetar la pelota
- Etiquetar cuando sea claramente visible (al menos 50% visible)
- No etiquetar si esta completamente oculta por un jugador
- La pelota en el aire siempre se etiqueta

#### Formaciones (scrum, ruck, lineout)
- Etiquetar la formacion completa como una sola caja grande
- Los jugadores individuales dentro SI se etiquetan tambien como "player"
- Un scrum se etiqueta desde que se forma hasta que se desarma
- Un ruck se etiqueta cuando hay al menos 2 jugadores disputando sobre la pelota

### Augmentation recomendada

El script `train_model.py` ya incluye augmentation optimizada para rugby:
- Flip horizontal (50%) - simula vista desde el otro lado
- Mosaic - combina 4 imagenes para variar contextos
- Scale (+-50%) - simula diferentes distancias de camara
- Mixup (10%) - mejora generalizacion
- HSV variation - simula diferentes condiciones de luz

### Iteracion y mejora continua

1. **Primer modelo:** Entrena con tus primeras 500 imagenes
2. **Evaluar:** Prueba el modelo en videos nuevos
3. **Identificar fallos:** Nota donde el modelo falla
4. **Agregar datos:** Etiqueta mas imagenes similares a los casos de fallo
5. **Re-entrenar:** Entrena un nuevo modelo con el dataset ampliado
6. **Repetir:** Cada iteracion mejora el modelo

---

## Preguntas frecuentes

### Puedo usar Google Colab para entrenar?

Si. Sube el dataset a Google Drive y ejecuta el training en un notebook con GPU:

```python
from google.colab import drive
drive.mount('/content/drive')

from ultralytics import YOLO
model = YOLO('yolov8s.pt')
model.train(data='/content/drive/MyDrive/rugby_dataset.yaml', epochs=100)
```

### Cuantas clases debo usar?

Empieza con las 6 clases definidas. Si alguna tiene muy pocos ejemplos (menos de 50), considera eliminarla temporalmente y agregarla cuando tengas mas datos.

### Puedo usar transfer learning desde mi modelo anterior?

Si. En lugar de partir desde `yolov8s.pt`, usa tu modelo anterior como base:

```bash
python train_model.py --model runs/train/rugby-v1/weights/best.pt --data rugby_dataset.yaml
```

### El entrenamiento se queda sin memoria GPU

Reduce el batch size y/o el tamaño de imagen:

```bash
python train_model.py --batch 4 --imgsz 416
```

### Como se cuando parar el entrenamiento?

El script usa **early stopping** con patience de 50 epocas. Si la metrica de validacion no mejora en 50 epocas consecutivas, el entrenamiento se detiene automaticamente. No necesitas intervenir manualmente.

---

## Recursos adicionales

- [Documentacion oficial de Ultralytics](https://docs.ultralytics.com/)
- [Guia de etiquetado de Roboflow](https://docs.roboflow.com/annotate)
- [Documentacion de CVAT](https://opencv.github.io/cvat/docs/)
- [Tips de entrenamiento YOLO](https://docs.ultralytics.com/guides/model-training-tips/)
