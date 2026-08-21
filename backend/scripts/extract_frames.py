#!/usr/bin/env python3
"""
Script para extraer frames de videos de rugby para crear datasets de entrenamiento.

Extrae frames a intervalos regulares desde un video, guardándolos como archivos
PNG listos para ser etiquetados en herramientas como Roboflow o CVAT.

Uso:
    python extract_frames.py --video partido.mp4 --output frames/ --interval 1.0
    python extract_frames.py --video partido.mp4 --interval 0.5 --max-frames 1000 --resize 640
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
    """Parse command-line arguments for frame extraction."""
    parser = argparse.ArgumentParser(
        description="Extraer frames de videos de rugby para crear datasets de entrenamiento.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Extraer un frame cada segundo
  python extract_frames.py --video partido.mp4 --output frames/

  # Extraer frames cada 0.5 segundos, máximo 1000
  python extract_frames.py --video partido.mp4 --interval 0.5 --max-frames 1000

  # Extraer frames redimensionados a 640px de ancho
  python extract_frames.py --video partido.mp4 --resize 640

  # Extraer frames de múltiples videos
  for video in videos/*.mp4; do
    python extract_frames.py --video "$video" --output "frames/$(basename $video .mp4)/"
  done

Tips:
  - Usa --interval 0.5 para escenas con mucha acción (tries, tackles)
  - Usa --interval 2.0 para escenas más lentas (formaciones, pausas)
  - Selecciona clips variados: diferentes ángulos, jugadas, condiciones de luz
""",
    )

    parser.add_argument(
        "--video",
        type=str,
        required=True,
        help="Ruta al archivo de video de entrada (mp4, avi, mkv, etc.)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="frames/",
        help="Directorio de salida para los frames extraídos (default: frames/)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Intervalo en segundos entre frames extraídos (default: 1.0)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=500,
        help="Número máximo de frames a extraer (default: 500)",
    )
    parser.add_argument(
        "--resize",
        type=int,
        default=None,
        help="Redimensionar frames al ancho especificado en píxeles "
        "(mantiene proporción). Si no se especifica, se mantiene el tamaño original.",
    )
    parser.add_argument(
        "--start-time",
        type=float,
        default=0.0,
        help="Tiempo de inicio en segundos para comenzar la extracción (default: 0.0)",
    )
    parser.add_argument(
        "--end-time",
        type=float,
        default=None,
        help="Tiempo de fin en segundos (default: hasta el final del video)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["png", "jpg"],
        default="png",
        help="Formato de imagen de salida (default: png)",
    )

    return parser.parse_args()


def validate_video(video_path: str) -> Path:
    """Validate that the video file exists and return its Path."""
    path = Path(video_path)
    if not path.exists():
        logger.error(f"No se encontró el archivo de video: {video_path}")
        sys.exit(1)
    if not path.is_file():
        logger.error(f"La ruta especificada no es un archivo: {video_path}")
        sys.exit(1)
    return path


def extract_frames(args: argparse.Namespace) -> int:
    """Extract frames from video at specified intervals.

    Returns:
        Number of frames extracted.
    """
    try:
        import cv2
    except ImportError:
        logger.error(
            "opencv-python no está instalado. Ejecuta: pip install opencv-python-headless>=4.8.0"
        )
        sys.exit(1)

    video_path = validate_video(args.video)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("EXTRACCIÓN DE FRAMES PARA DATASET DE RUGBY")
    logger.info("=" * 60)
    logger.info(f"Video: {video_path}")
    logger.info(f"Salida: {output_dir.resolve()}")
    logger.info(f"Intervalo: {args.interval}s")
    logger.info(f"Max frames: {args.max_frames}")
    if args.resize:
        logger.info(f"Redimensionar a: {args.resize}px de ancho")
    logger.info("=" * 60)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"No se pudo abrir el video: {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    logger.info(f"FPS del video: {fps:.2f}")
    logger.info(f"Frames totales: {total_frames}")
    logger.info(f"Duración: {duration:.1f}s ({duration/60:.1f} min)")

    # Calculate frame interval
    frame_interval = int(fps * args.interval)
    if frame_interval < 1:
        frame_interval = 1

    # Calculate start and end frame
    start_frame = int(args.start_time * fps)
    end_frame = int(args.end_time * fps) if args.end_time else total_frames

    # Set starting position
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        logger.info(f"Iniciando desde: {args.start_time}s (frame {start_frame})")

    extracted_count = 0
    current_frame = start_frame

    while current_frame < end_frame and extracted_count < args.max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()

        if not ret:
            logger.warning(f"No se pudo leer el frame {current_frame}, finalizando.")
            break

        # Resize if specified
        if args.resize is not None:
            height, width = frame.shape[:2]
            new_width = args.resize
            new_height = int(height * (new_width / width))
            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

        # Save frame with sequential naming
        extracted_count += 1
        filename = f"frame_{extracted_count:06d}.{args.format}"
        filepath = output_dir / filename

        if args.format == "png":
            cv2.imwrite(str(filepath), frame)
        else:
            cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        if extracted_count % 50 == 0:
            progress = (current_frame - start_frame) / max(end_frame - start_frame, 1) * 100
            logger.info(
                f"Extraídos: {extracted_count} frames ({progress:.1f}% del video procesado)"
            )

        current_frame += frame_interval

    cap.release()

    logger.info("=" * 60)
    logger.info("EXTRACCIÓN COMPLETADA")
    logger.info("=" * 60)
    logger.info(f"Frames extraídos: {extracted_count}")
    logger.info(f"Guardados en: {output_dir.resolve()}")
    logger.info("")
    logger.info("Siguiente paso: Etiquetar las imágenes con Roboflow o CVAT")
    logger.info("Ver docs/FINE-TUNING.md para instrucciones detalladas")

    return extracted_count


def main() -> None:
    """Main entry point for frame extraction."""
    args = parse_args()
    extract_frames(args)


if __name__ == "__main__":
    main()
