#!/usr/bin/env python3
"""
Script de entrenamiento para modelos YOLO personalizados de rugby.

Utiliza la API de ultralytics para entrenar un modelo YOLO con datos
específicos de rugby (jugadores, pelota, árbitro, scrum, ruck, lineout).

Uso:
    python train_model.py --data rugby_dataset.yaml --epochs 100
    python train_model.py --model yolov8m.pt --data rugby_dataset.yaml --epochs 200 --batch 8
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for training configuration."""
    parser = argparse.ArgumentParser(
        description="Entrenar un modelo YOLO personalizado para detección en rugby.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Entrenamiento básico con configuración por defecto
  python train_model.py --data rugby_dataset.yaml

  # Entrenamiento con modelo más grande y más épocas
  python train_model.py --model yolov8m.pt --data rugby_dataset.yaml --epochs 200

  # Entrenamiento con GPU específica
  python train_model.py --data rugby_dataset.yaml --device 0

  # Entrenamiento con imágenes más grandes para mejor precisión
  python train_model.py --data rugby_dataset.yaml --imgsz 1280 --batch 8
""",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="yolov8s.pt",
        help="Modelo base para fine-tuning (default: yolov8s.pt). "
        "Opciones: yolov8n.pt, yolov8s.pt, yolov8m.pt, yolov8l.pt, yolov8x.pt",
    )
    parser.add_argument(
        "--data",
        type=str,
        default="rugby_dataset.yaml",
        help="Ruta al archivo YAML de configuración del dataset (default: rugby_dataset.yaml)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Número de épocas de entrenamiento (default: 100)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Tamaño de imagen para entrenamiento en píxeles (default: 640)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="Tamaño del batch (default: 16). Reducir si hay errores de memoria GPU.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Dispositivo de entrenamiento: '' para auto, '0' para GPU 0, 'cpu' para CPU "
        "(default: auto)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="runs/train",
        help="Directorio de salida para resultados (default: runs/train)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="rugby-custom",
        help="Nombre del experimento (default: rugby-custom)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reanudar entrenamiento desde el último checkpoint",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=50,
        help="Épocas sin mejora antes de early stopping (default: 50)",
    )

    return parser.parse_args()


def validate_dataset(data_path: str) -> Path:
    """Validate that the dataset YAML file exists and return its absolute path."""
    path = Path(data_path)
    if not path.exists():
        logger.error(f"No se encontró el archivo de dataset: {data_path}")
        logger.error(
            "Asegúrate de que el archivo YAML existe y las rutas dentro son correctas."
        )
        sys.exit(1)

    logger.info(f"Dataset encontrado: {path.resolve()}")
    return path.resolve()


def train(args: argparse.Namespace) -> None:
    """Run YOLO training with the specified configuration."""
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error(
            "ultralytics no está instalado. Ejecuta: pip install ultralytics>=8.0.0"
        )
        sys.exit(1)

    data_path = validate_dataset(args.data)

    logger.info("=" * 60)
    logger.info("ENTRENAMIENTO DE MODELO YOLO PARA RUGBY")
    logger.info("=" * 60)
    logger.info(f"Modelo base: {args.model}")
    logger.info(f"Dataset: {data_path}")
    logger.info(f"Épocas: {args.epochs}")
    logger.info(f"Tamaño de imagen: {args.imgsz}")
    logger.info(f"Batch size: {args.batch}")
    logger.info(f"Dispositivo: {args.device or 'auto'}")
    logger.info(f"Proyecto: {args.project}")
    logger.info(f"Nombre: {args.name}")
    logger.info(f"Patience: {args.patience}")
    logger.info("=" * 60)

    # Load the base model
    logger.info(f"Cargando modelo base: {args.model}")
    model = YOLO(args.model)

    # Start training
    logger.info("Iniciando entrenamiento...")
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device if args.device else None,
        project=args.project,
        name=args.name,
        resume=args.resume,
        patience=args.patience,
        # Augmentation settings optimized for sports/rugby
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=0.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        # Save settings
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
    )

    logger.info("=" * 60)
    logger.info("ENTRENAMIENTO COMPLETADO")
    logger.info("=" * 60)
    logger.info(f"Resultados guardados en: {args.project}/{args.name}")
    logger.info(f"Mejor modelo: {args.project}/{args.name}/weights/best.pt")
    logger.info(f"Último modelo: {args.project}/{args.name}/weights/last.pt")
    logger.info("")
    logger.info("Para usar el modelo entrenado en Rugby Analyzer:")
    logger.info(f"  export YOLO_MODEL_PATH={args.project}/{args.name}/weights/best.pt")
    logger.info("  O selecciónalo en Configuración > Modelo YOLO de la aplicación.")

    return results


def main() -> None:
    """Main entry point for the training script."""
    args = parse_args()
    train(args)


if __name__ == "__main__":
    main()
