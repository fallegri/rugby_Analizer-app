import React, { useState, useRef, useCallback } from 'react';
import { Stage, Layer, Circle, Text, Line } from 'react-konva';
import { Crosshair, Wand2, Loader2, Square } from 'lucide-react';
import { CalibrationPoint, FieldCalibration as FieldCalibrationData, PlayArea } from '../types';
import { autoCalibrate, manualCalibrate } from '../services/api';
import { useAnalysisStore } from '../stores/analysisStore';

interface FieldCalibrationProps {
  frameBlob?: Blob | null;
  videoWidth: number;
  videoHeight: number;
  containerWidth: number;
  containerHeight: number;
  onPlayAreaChange?: (playArea: PlayArea | null) => void;
}

const FIELD_COORDS_OPTIONS = [
  { label: 'Try Line Left (0m)', x: 0, y: 35 },
  { label: '22m Left', x: 22, y: 35 },
  { label: '10m Left', x: 40, y: 35 },
  { label: 'Halfway (50m)', x: 50, y: 35 },
  { label: '10m Right', x: 60, y: 35 },
  { label: '22m Right', x: 78, y: 35 },
  { label: 'Try Line Right (100m)', x: 100, y: 35 },
  { label: 'Top Touchline', x: 50, y: 0 },
  { label: 'Bottom Touchline', x: 50, y: 70 },
];

// Mini field SVG dimensions
const MINI_FIELD_W = 500;
const MINI_FIELD_H = 350;
const FIELD_LENGTH = 100; // meters
const FIELD_WIDTH = 70;  // meters
const MF_SCALE_X = MINI_FIELD_W / FIELD_LENGTH;
const MF_SCALE_Y = MINI_FIELD_H / FIELD_WIDTH;

export const FieldCalibration: React.FC<FieldCalibrationProps> = ({
  frameBlob,
  videoWidth,
  videoHeight,
  containerWidth,
  containerHeight,
  onPlayAreaChange,
}) => {
  const { setCalibration } = useAnalysisStore();
  const [activeTab, setActiveTab] = useState<'auto' | 'manual' | 'play_area'>('play_area');
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [points, setPoints] = useState<(CalibrationPoint & { id: number })[]>([]);
  const [selectedFieldCoord, setSelectedFieldCoord] = useState(FIELD_COORDS_OPTIONS[0]);
  const [error, setError] = useState<string | null>(null);
  const [calibResult, setCalibResult] = useState<FieldCalibrationData | null>(null);

  // Play Area state - rectangle drawn on field diagram
  const [playArea, setPlayArea] = useState<PlayArea>({ x_min: 20, x_max: 80, y_min: 15, y_max: 55 });
  const [isDraggingArea, setIsDraggingArea] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ x: number; y: number } | null>(null);
  const fieldSvgRef = useRef<SVGSVGElement>(null);

  const scaleX = containerWidth / (videoWidth || 1);
  const scaleY = containerHeight / (videoHeight || 1);

  const handleAutoCalibrate = async () => {
    if (!frameBlob) {
      setError('Capture a frame first to auto-calibrate');
      return;
    }
    setIsCalibrating(true);
    setError(null);
    try {
      const result = await autoCalibrate(frameBlob);
      setCalibResult(result);
      setCalibration(result);
    } catch {
      setError('Auto-calibration failed. Try manual calibration.');
    } finally {
      setIsCalibrating(false);
    }
  };

  const handleStageClick = (e: { evt: { offsetX: number; offsetY: number } }) => {
    if (activeTab !== 'manual') return;
    const pixelX = e.evt.offsetX / scaleX;
    const pixelY = e.evt.offsetY / scaleY;

    const newPoint: CalibrationPoint & { id: number } = {
      id: Date.now(),
      pixel_x: pixelX,
      pixel_y: pixelY,
      field_x: selectedFieldCoord.x,
      field_y: selectedFieldCoord.y,
    };
    setPoints([...points, newPoint]);
  };

  const removePoint = (id: number) => {
    setPoints(points.filter((p) => p.id !== id));
  };

  const handleManualCalibrate = async () => {
    if (points.length < 4) {
      setError('At least 4 points are required for calibration');
      return;
    }
    setIsCalibrating(true);
    setError(null);
    try {
      const calibPoints = points.map(({ pixel_x, pixel_y, field_x, field_y }) => ({
        pixel_x, pixel_y, field_x, field_y,
      }));
      const result = await manualCalibrate(calibPoints);
      setCalibResult(result);
      setCalibration(result);
    } catch {
      setError('Manual calibration failed. Check your point placements.');
    } finally {
      setIsCalibrating(false);
    }
  };

  // Play Area drag handlers
  const getSvgFieldCoords = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const svg = fieldSvgRef.current;
    if (!svg) return { fx: 0, fy: 0 };
    const rect = svg.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const fx = (px / rect.width) * FIELD_LENGTH;
    const fy = (py / rect.height) * FIELD_WIDTH;
    return { fx: Math.max(0, Math.min(FIELD_LENGTH, fx)), fy: Math.max(0, Math.min(FIELD_WIDTH, fy)) };
  }, []);

  const handleFieldMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const { fx, fy } = getSvgFieldCoords(e);
    setIsDraggingArea(true);
    setDragStart({ x: fx, y: fy });
    setDragCurrent({ x: fx, y: fy });
  }, [getSvgFieldCoords]);

  const handleFieldMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDraggingArea) return;
    const { fx, fy } = getSvgFieldCoords(e);
    setDragCurrent({ x: fx, y: fy });
  }, [isDraggingArea, getSvgFieldCoords]);

  const handleFieldMouseUp = useCallback(() => {
    if (!isDraggingArea || !dragStart || !dragCurrent) {
      setIsDraggingArea(false);
      return;
    }

    const x_min = Math.min(dragStart.x, dragCurrent.x);
    const x_max = Math.max(dragStart.x, dragCurrent.x);
    const y_min = Math.min(dragStart.y, dragCurrent.y);
    const y_max = Math.max(dragStart.y, dragCurrent.y);

    // Minimum size check (at least 10m x 10m)
    if (x_max - x_min >= 10 && y_max - y_min >= 10) {
      const newArea: PlayArea = {
        x_min: Math.round(x_min),
        x_max: Math.round(x_max),
        y_min: Math.round(y_min),
        y_max: Math.round(y_max),
      };
      setPlayArea(newArea);
      if (onPlayAreaChange) {
        onPlayAreaChange(newArea);
      }
    }

    setIsDraggingArea(false);
    setDragStart(null);
    setDragCurrent(null);
  }, [isDraggingArea, dragStart, dragCurrent, onPlayAreaChange]);

  const renderMiniField = () => {
    // Calculate the play area rectangle position in SVG coordinates
    const areaX = playArea.x_min * MF_SCALE_X;
    const areaY = playArea.y_min * MF_SCALE_Y;
    const areaW = (playArea.x_max - playArea.x_min) * MF_SCALE_X;
    const areaH = (playArea.y_max - playArea.y_min) * MF_SCALE_Y;

    // Dragging preview rectangle
    let dragRect = null;
    if (isDraggingArea && dragStart && dragCurrent) {
      const dx = Math.min(dragStart.x, dragCurrent.x) * MF_SCALE_X;
      const dy = Math.min(dragStart.y, dragCurrent.y) * MF_SCALE_Y;
      const dw = Math.abs(dragCurrent.x - dragStart.x) * MF_SCALE_X;
      const dh = Math.abs(dragCurrent.y - dragStart.y) * MF_SCALE_Y;
      dragRect = (
        <rect x={dx} y={dy} width={dw} height={dh} fill="rgba(196, 168, 79, 0.3)" stroke="#c4a84f" strokeWidth={2} strokeDasharray="6,3" />
      );
    }

    return (
      <svg
        ref={fieldSvgRef}
        width="100%"
        viewBox={`0 0 ${MINI_FIELD_W} ${MINI_FIELD_H}`}
        className="cursor-crosshair border border-gray-600 rounded"
        onMouseDown={handleFieldMouseDown}
        onMouseMove={handleFieldMouseMove}
        onMouseUp={handleFieldMouseUp}
        onMouseLeave={handleFieldMouseUp}
      >
        {/* Field background */}
        <rect x={0} y={0} width={MINI_FIELD_W} height={MINI_FIELD_H} fill="#1a5c2e" />
        {/* Touchlines */}
        <rect x={0} y={0} width={MINI_FIELD_W} height={MINI_FIELD_H} fill="none" stroke="white" strokeWidth={2} />
        {/* Try lines */}
        <line x1={0} y1={0} x2={0} y2={MINI_FIELD_H} stroke="white" strokeWidth={2} />
        <line x1={MINI_FIELD_W} y1={0} x2={MINI_FIELD_W} y2={MINI_FIELD_H} stroke="white" strokeWidth={2} />
        {/* 22m lines */}
        <line x1={22 * MF_SCALE_X} y1={0} x2={22 * MF_SCALE_X} y2={MINI_FIELD_H} stroke="white" strokeWidth={1} />
        <line x1={78 * MF_SCALE_X} y1={0} x2={78 * MF_SCALE_X} y2={MINI_FIELD_H} stroke="white" strokeWidth={1} />
        {/* 10m lines (dashed) */}
        <line x1={40 * MF_SCALE_X} y1={0} x2={40 * MF_SCALE_X} y2={MINI_FIELD_H} stroke="white" strokeWidth={1} strokeDasharray="6,3" />
        <line x1={60 * MF_SCALE_X} y1={0} x2={60 * MF_SCALE_X} y2={MINI_FIELD_H} stroke="white" strokeWidth={1} strokeDasharray="6,3" />
        {/* Halfway line */}
        <line x1={50 * MF_SCALE_X} y1={0} x2={50 * MF_SCALE_X} y2={MINI_FIELD_H} stroke="white" strokeWidth={1.5} />
        {/* Center mark */}
        <circle cx={50 * MF_SCALE_X} cy={35 * MF_SCALE_Y} r={2} fill="white" />
        {/* Labels */}
        <text x={50 * MF_SCALE_X} y={MINI_FIELD_H - 4} textAnchor="middle" fill="#aaa" fontSize={9}>50m</text>
        <text x={22 * MF_SCALE_X} y={MINI_FIELD_H - 4} textAnchor="middle" fill="#aaa" fontSize={9}>22m</text>
        <text x={78 * MF_SCALE_X} y={MINI_FIELD_H - 4} textAnchor="middle" fill="#aaa" fontSize={9}>22m</text>
        <text x={0 + 8} y={MINI_FIELD_H - 4} fill="#aaa" fontSize={9}>0m</text>
        <text x={MINI_FIELD_W - 24} y={MINI_FIELD_H - 4} fill="#aaa" fontSize={9}>100m</text>

        {/* Current play area rectangle */}
        <rect
          x={areaX}
          y={areaY}
          width={areaW}
          height={areaH}
          fill="rgba(196, 168, 79, 0.25)"
          stroke="#c4a84f"
          strokeWidth={2}
        />

        {/* Dragging preview */}
        {dragRect}

        {/* Play area label */}
        <text x={areaX + areaW / 2} y={areaY + areaH / 2 + 4} textAnchor="middle" fill="white" fontSize={11} fontWeight="bold">
          Zona visible
        </text>
        <text x={areaX + areaW / 2} y={areaY + areaH / 2 + 18} textAnchor="middle" fill="#ddd" fontSize={9}>
          {Math.round(playArea.x_max - playArea.x_min)}m x {Math.round(playArea.y_max - playArea.y_min)}m
        </text>
      </svg>
    );
  };

  const handleApplyPlayArea = () => {
    if (onPlayAreaChange) {
      onPlayAreaChange(playArea);
    }
    setCalibResult({
      id: 'play-area',
      video_id: '',
      points: [],
      homography_matrix: null,
      is_auto: false,
      confidence: 0.9,
    });
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-3">Field Calibration</h3>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveTab('play_area')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'play_area' ? 'bg-rugby-gold text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <Square className="w-4 h-4" />
          Zona de Juego
        </button>
        <button
          onClick={() => setActiveTab('auto')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'auto' ? 'bg-rugby-gold text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <Wand2 className="w-4 h-4" />
          Auto
        </button>
        <button
          onClick={() => setActiveTab('manual')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'manual' ? 'bg-rugby-gold text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <Crosshair className="w-4 h-4" />
          Manual
        </button>
      </div>

      {activeTab === 'play_area' ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-400">
            Dibuja un rectangulo sobre la cancha indicando que zona se ve en el video.
            Esto permite convertir coordenadas de pixeles a metros reales.
          </p>

          {renderMiniField()}

          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>X: {Math.round(playArea.x_min)}m - {Math.round(playArea.x_max)}m</span>
            <span>Y: {Math.round(playArea.y_min)}m - {Math.round(playArea.y_max)}m</span>
            <span>Area: {Math.round(playArea.x_max - playArea.x_min)}m x {Math.round(playArea.y_max - playArea.y_min)}m</span>
          </div>

          <button
            onClick={handleApplyPlayArea}
            className="w-full py-2 bg-rugby-green text-white rounded-lg hover:bg-rugby-green/80 flex items-center justify-center gap-2"
          >
            <Square className="w-4 h-4" />
            Aplicar Zona de Juego
          </button>
        </div>
      ) : activeTab === 'auto' ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-400">
            Auto-detect field lines using computer vision. Capture a clear frame of the field first.
          </p>
          <button
            onClick={handleAutoCalibrate}
            disabled={isCalibrating || !frameBlob}
            className="w-full py-2 bg-rugby-green text-white rounded-lg hover:bg-rugby-green/80 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isCalibrating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
            {isCalibrating ? 'Detecting...' : 'Auto Calibrate'}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-gray-400">
            Click on the video frame to place calibration points. Select the field coordinate for each point.
          </p>

          <select
            value={`${selectedFieldCoord.x},${selectedFieldCoord.y}`}
            onChange={(e) => {
              const [x, y] = e.target.value.split(',').map(Number);
              const opt = FIELD_COORDS_OPTIONS.find((o) => o.x === x && o.y === y);
              if (opt) setSelectedFieldCoord(opt);
            }}
            className="w-full bg-gray-700 text-white text-sm rounded-lg px-3 py-2 border border-gray-600"
          >
            {FIELD_COORDS_OPTIONS.map((opt) => (
              <option key={`${opt.x}-${opt.y}`} value={`${opt.x},${opt.y}`}>
                {opt.label} ({opt.x}m, {opt.y}m)
              </option>
            ))}
          </select>

          <div className="border border-gray-600 rounded overflow-hidden">
            <Stage
              width={containerWidth}
              height={containerHeight}
              onClick={handleStageClick}
              className="cursor-crosshair"
            >
              <Layer>
                {points.map((point, i) => (
                  <React.Fragment key={point.id}>
                    <Circle x={point.pixel_x * scaleX} y={point.pixel_y * scaleY} radius={6} fill="#c4a84f" stroke="white" strokeWidth={2} />
                    <Text x={point.pixel_x * scaleX + 10} y={point.pixel_y * scaleY - 6} text={`${i + 1}`} fontSize={12} fill="white" />
                    {i > 0 && (
                      <Line
                        points={[points[i - 1].pixel_x * scaleX, points[i - 1].pixel_y * scaleY, point.pixel_x * scaleX, point.pixel_y * scaleY]}
                        stroke="#c4a84f" strokeWidth={1} dash={[4, 4]} opacity={0.5}
                      />
                    )}
                  </React.Fragment>
                ))}
              </Layer>
            </Stage>
          </div>

          {points.length > 0 && (
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {points.map((p, i) => (
                <div key={p.id} className="flex items-center justify-between text-xs bg-gray-700 px-2 py-1 rounded">
                  <span className="text-gray-300">
                    Point {i + 1}: pixel({Math.round(p.pixel_x)},{Math.round(p.pixel_y)}) → field({p.field_x}m,{p.field_y}m)
                  </span>
                  <button onClick={() => removePoint(p.id)} className="text-red-400 hover:text-red-300 ml-2">x</button>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={handleManualCalibrate}
            disabled={isCalibrating || points.length < 4}
            className="w-full py-2 bg-rugby-green text-white rounded-lg hover:bg-rugby-green/80 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isCalibrating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Crosshair className="w-4 h-4" />}
            {isCalibrating ? 'Calibrating...' : `Calibrate (${points.length}/4+ points)`}
          </button>
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      {calibResult && (
        <div className="mt-3 p-2 bg-green-900/30 border border-green-700 rounded text-sm text-green-300">
          Calibration complete! {calibResult.id === 'play-area' ? 'Play area configured.' : `Confidence: ${Math.round((calibResult.confidence || 0) * 100)}%`}
        </div>
      )}
    </div>
  );
};

export default FieldCalibration;
