import React, { useState } from 'react';
import { Stage, Layer, Circle, Text, Line } from 'react-konva';
import { Crosshair, Wand2, Loader2 } from 'lucide-react';
import { CalibrationPoint, FieldCalibration as FieldCalibrationData } from '../types';
import { autoCalibrate, manualCalibrate } from '../services/api';
import { useAnalysisStore } from '../stores/analysisStore';

interface FieldCalibrationProps {
  frameBlob?: Blob | null;
  videoWidth: number;
  videoHeight: number;
  containerWidth: number;
  containerHeight: number;
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

export const FieldCalibration: React.FC<FieldCalibrationProps> = ({
  frameBlob,
  videoWidth,
  videoHeight,
  containerWidth,
  containerHeight,
}) => {
  const { setCalibration } = useAnalysisStore();
  const [activeTab, setActiveTab] = useState<'auto' | 'manual'>('auto');
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [points, setPoints] = useState<(CalibrationPoint & { id: number })[]>([]);
  const [selectedFieldCoord, setSelectedFieldCoord] = useState(FIELD_COORDS_OPTIONS[0]);
  const [error, setError] = useState<string | null>(null);
  const [calibResult, setCalibResult] = useState<FieldCalibrationData | null>(null);

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

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-3">Field Calibration</h3>

      <div className="flex gap-2 mb-4">
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

      {activeTab === 'auto' ? (
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
          Calibration complete! Confidence: {Math.round((calibResult.confidence || 0) * 100)}%
        </div>
      )}
    </div>
  );
};

export default FieldCalibration;
