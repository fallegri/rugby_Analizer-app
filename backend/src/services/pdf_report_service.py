"""PDF Report Generation Service.

Generates professional PDF reports with player metrics, field diagrams,
detected plays, and speed charts from analysis session data.
"""

import io
from datetime import datetime
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# Colors for player routes (up to 10 distinct colors)
PLAYER_COLORS = [
    colors.red,
    colors.blue,
    colors.yellow,
    colors.cyan,
    colors.magenta,
    colors.orange,
    colors.green,
    colors.purple,
    colors.pink,
    colors.brown,
]


class PDFReportService:
    """Service for generating PDF reports from analysis session data."""

    def generate_report(self, session_data: dict[str, Any]) -> bytes:
        """Generate a PDF report from session analysis data.

        Args:
            session_data: Dictionary containing session results with keys:
                - session_id, video_id, mode, status, results

        Returns:
            PDF file content as bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor("#1a5c1a"),
        )
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor("#2d2d2d"),
        )
        normal_style = styles["Normal"]

        elements: list[Any] = []

        # --- Page 1: Title and metadata ---
        elements.append(Paragraph("Rugby Analyzer - Reporte de Analisis", title_style))
        elements.append(Spacer(1, 10))

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        video_id = session_data.get("video_id", "N/A")
        mode = session_data.get("mode", "N/A")
        session_id = session_data.get("session_id", "N/A")

        results = session_data.get("results") or {}
        duration = results.get("duration_s", 0)
        fps = results.get("fps", 30)
        total_frames = results.get("total_frames", 0)

        # Metadata table
        meta_data = [
            ["Generado", timestamp],
            ["Session ID", str(session_id)],
            ["Video ID", str(video_id)],
            ["Modo", str(mode)],
            ["Duracion (s)", f"{duration:.1f}" if isinstance(duration, (int, float)) else str(duration)],
            ["FPS", str(fps)],
            ["Frames Totales", str(total_frames)],
        ]
        meta_table = Table(meta_data, colWidths=[4 * cm, 12 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f5e9")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 20))

        # --- Section: Player metrics table ---
        players = results.get("players", [])

        elements.append(Paragraph("Metricas por Jugador", heading_style))

        if players:
            table_data = [
                ["Jugador", "Distancia (km)", "Vel. Max (km/h)", "Vel. Prom (km/h)", "Sprints"]
            ]
            for player in players:
                player_id = player.get("player_id", "?")
                distance = player.get("total_distance_km", 0)
                max_speed = player.get("max_speed_kmh", 0)
                avg_speed = player.get("avg_speed_kmh", 0)
                sprint_count = player.get("sprint_count", 0)
                table_data.append([
                    str(player_id),
                    f"{distance:.3f}",
                    f"{max_speed:.1f}",
                    f"{avg_speed:.1f}",
                    str(sprint_count),
                ])

            player_table = Table(table_data, colWidths=[3 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm, 2.5 * cm])
            player_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5c1a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                    ]
                )
            )
            elements.append(player_table)
        else:
            elements.append(Paragraph("No hay datos de jugadores disponibles.", normal_style))

        elements.append(Spacer(1, 20))

        # --- Section: Field diagram with player routes ---
        elements.append(Paragraph("Diagrama de Cancha con Rutas", heading_style))

        field_drawing = self._create_field_diagram(players)
        elements.append(field_drawing)
        elements.append(Spacer(1, 20))

        # --- Section: Detected plays ---
        plays = results.get("plays", [])
        elements.append(Paragraph("Jugadas Detectadas", heading_style))

        if plays:
            plays_data = [["Tipo", "Tiempo (s)", "Descripcion"]]
            for play in plays:
                play_type = play.get("type", play.get("play_type", "N/A"))
                play_time = play.get("time", play.get("timestamp", 0))
                play_desc = play.get("description", play.get("label", ""))
                plays_data.append([
                    str(play_type),
                    f"{play_time:.1f}" if isinstance(play_time, (int, float)) else str(play_time),
                    str(play_desc)[:60],
                ])

            plays_table = Table(plays_data, colWidths=[3.5 * cm, 3 * cm, 10 * cm])
            plays_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5c1a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(plays_table)
        else:
            elements.append(Paragraph("No se detectaron jugadas.", normal_style))

        elements.append(Spacer(1, 20))

        # --- Section: Speed chart ---
        elements.append(Paragraph("Grafico de Velocidad por Jugador", heading_style))

        speed_chart = self._create_speed_chart(players)
        if speed_chart:
            elements.append(speed_chart)
        else:
            elements.append(Paragraph("No hay datos de velocidad disponibles.", normal_style))

        # Build document
        doc.build(elements)
        return buffer.getvalue()

    def _create_field_diagram(self, players: list[dict[str, Any]]) -> Drawing:
        """Create a field diagram with player routes.

        Args:
            players: List of player data dicts with route information.

        Returns:
            A reportlab Drawing representing the field with routes.
        """
        width = 500
        height = 350
        drawing = Drawing(width, height)

        # Green field background
        field = Rect(0, 0, width, height, fillColor=colors.HexColor("#2e7d32"), strokeColor=colors.white)
        drawing.add(field)

        # Field markings - outer boundary
        drawing.add(Rect(10, 10, width - 20, height - 20, fillColor=None, strokeColor=colors.white, strokeWidth=2))

        # Center line
        drawing.add(Line(width / 2, 10, width / 2, height - 10, strokeColor=colors.white, strokeWidth=1.5))

        # 22m lines (roughly at 22% from each end)
        x_22_left = 10 + (width - 20) * 0.22
        x_22_right = 10 + (width - 20) * 0.78
        drawing.add(Line(x_22_left, 10, x_22_left, height - 10, strokeColor=colors.white, strokeWidth=1, strokeDashArray=[4, 4]))
        drawing.add(Line(x_22_right, 10, x_22_right, height - 10, strokeColor=colors.white, strokeWidth=1, strokeDashArray=[4, 4]))

        # Try lines (at ~10% from each end)
        x_try_left = 10 + (width - 20) * 0.10
        x_try_right = 10 + (width - 20) * 0.90
        drawing.add(Line(x_try_left, 10, x_try_left, height - 10, strokeColor=colors.white, strokeWidth=2))
        drawing.add(Line(x_try_right, 10, x_try_right, height - 10, strokeColor=colors.white, strokeWidth=2))

        # Draw player routes
        for i, player in enumerate(players):
            route = player.get("route", [])
            if len(route) < 2:
                continue

            color = PLAYER_COLORS[i % len(PLAYER_COLORS)]

            # Normalize route points to field dimensions
            points = self._normalize_route_to_field(route, width, height)

            if len(points) >= 4:  # Need at least 2 points (x,y pairs)
                polyline = PolyLine(points, strokeColor=color, strokeWidth=1.5)
                drawing.add(polyline)

                # Add player label at the start position
                label_x = points[0]
                label_y = points[1]
                player_id = player.get("player_id", f"P{i+1}")
                label = String(label_x, label_y + 5, f"J{player_id}", fontSize=7, fillColor=color)
                drawing.add(label)

        return drawing

    def _normalize_route_to_field(
        self, route: list[dict[str, Any]], field_width: int, field_height: int
    ) -> list[float]:
        """Normalize route coordinates to fit within field drawing dimensions.

        Args:
            route: List of route points with x, y keys.
            field_width: Width of the field drawing.
            field_height: Height of the field drawing.

        Returns:
            Flat list of [x1, y1, x2, y2, ...] coordinates for PolyLine.
        """
        if not route:
            return []

        xs = [p.get("x", 0) for p in route]
        ys = [p.get("y", 0) for p in route]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        range_x = max_x - min_x if max_x != min_x else 1
        range_y = max_y - min_y if max_y != min_y else 1

        margin = 20
        usable_width = field_width - 2 * margin
        usable_height = field_height - 2 * margin

        points: list[float] = []
        for p in route:
            norm_x = margin + ((p.get("x", 0) - min_x) / range_x) * usable_width
            norm_y = margin + ((p.get("y", 0) - min_y) / range_y) * usable_height
            points.append(norm_x)
            points.append(norm_y)

        return points

    def _create_speed_chart(self, players: list[dict[str, Any]]) -> Drawing | None:
        """Create a speed over time line chart for players.

        Args:
            players: List of player data with route (containing speed and timestamp).

        Returns:
            A Drawing with the speed chart, or None if no data.
        """
        # Collect speed data from player routes
        chart_data: list[list[tuple[float, float]]] = []
        has_data = False

        for player in players:
            route = player.get("route", [])
            if not route:
                chart_data.append([(0, 0)])
                continue

            player_speeds: list[tuple[float, float]] = []
            for point in route:
                t = point.get("timestamp", 0)
                speed = point.get("speed", 0)
                player_speeds.append((float(t), float(speed)))

            if player_speeds:
                has_data = True
                # Sample to limit points for readability (max 50 points per player)
                if len(player_speeds) > 50:
                    step = len(player_speeds) // 50
                    player_speeds = player_speeds[::step]
                chart_data.append(player_speeds)
            else:
                chart_data.append([(0, 0)])

        if not has_data:
            return None

        width = 500
        height = 250
        drawing = Drawing(width, height)

        chart = LinePlot()
        chart.x = 50
        chart.y = 30
        chart.width = width - 80
        chart.height = height - 60

        chart.data = chart_data

        # Style lines per player
        for i in range(len(chart_data)):
            chart.lines[i].strokeColor = PLAYER_COLORS[i % len(PLAYER_COLORS)]
            chart.lines[i].strokeWidth = 1.5

        chart.xValueAxis.labelTextFormat = "%.1f"
        chart.yValueAxis.labelTextFormat = "%.0f"
        chart.xValueAxis.visibleGrid = True
        chart.yValueAxis.visibleGrid = True

        drawing.add(chart)

        # Axis labels
        drawing.add(String(width / 2, 5, "Tiempo (s)", fontSize=9, textAnchor="middle"))
        drawing.add(String(10, height / 2, "Vel (km/h)", fontSize=9, textAnchor="middle"))

        return drawing
