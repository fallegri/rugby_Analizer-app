import React, { useState, useRef, useCallback } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { PlayerMetrics } from '../types';

interface FieldViewProps {
  players?: PlayerMetrics[];
  showHeatMap?: boolean;
}

// Rugby field dimensions: 100m x 70m
const FIELD_WIDTH = 100;
const FIELD_HEIGHT = 70;
const SVG_WIDTH = 700;
const SVG_HEIGHT = 490;
const SCALE_X = SVG_WIDTH / FIELD_WIDTH;
const SCALE_Y = SVG_HEIGHT / FIELD_HEIGHT;

const PLAYER_COLORS = [
  '#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

export const FieldView: React.FC<FieldViewProps> = ({ players = [], showHeatMap = false }) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.5));
  const handleReset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
  }, [isPanning, panStart]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const renderFieldLines = () => (
    <g>
      {/* Field background */}
      <rect x={0} y={0} width={SVG_WIDTH} height={SVG_HEIGHT} fill="#1a5c2e" />
      {/* Touchlines */}
      <rect x={0} y={0} width={SVG_WIDTH} height={SVG_HEIGHT} fill="none" stroke="white" strokeWidth={2} />
      {/* Try lines */}
      <line x1={0} y1={0} x2={0} y2={SVG_HEIGHT} stroke="white" strokeWidth={3} />
      <line x1={SVG_WIDTH} y1={0} x2={SVG_WIDTH} y2={SVG_HEIGHT} stroke="white" strokeWidth={3} />
      {/* 22m lines */}
      <line x1={22 * SCALE_X} y1={0} x2={22 * SCALE_X} y2={SVG_HEIGHT} stroke="white" strokeWidth={1.5} />
      <line x1={78 * SCALE_X} y1={0} x2={78 * SCALE_X} y2={SVG_HEIGHT} stroke="white" strokeWidth={1.5} />
      {/* 10m lines (dashed) */}
      <line x1={40 * SCALE_X} y1={0} x2={40 * SCALE_X} y2={SVG_HEIGHT} stroke="white" strokeWidth={1.5} strokeDasharray="8,4" />
      <line x1={60 * SCALE_X} y1={0} x2={60 * SCALE_X} y2={SVG_HEIGHT} stroke="white" strokeWidth={1.5} strokeDasharray="8,4" />
      {/* Halfway line */}
      <line x1={50 * SCALE_X} y1={0} x2={50 * SCALE_X} y2={SVG_HEIGHT} stroke="white" strokeWidth={2} />
      {/* 5m dashed lines */}
      <line x1={0} y1={5 * SCALE_Y} x2={SVG_WIDTH} y2={5 * SCALE_Y} stroke="white" strokeWidth={0.75} strokeDasharray="4,6" />
      <line x1={0} y1={65 * SCALE_Y} x2={SVG_WIDTH} y2={65 * SCALE_Y} stroke="white" strokeWidth={0.75} strokeDasharray="4,6" />
      {/* 15m dashed lines */}
      <line x1={0} y1={15 * SCALE_Y} x2={SVG_WIDTH} y2={15 * SCALE_Y} stroke="white" strokeWidth={0.75} strokeDasharray="4,6" />
      <line x1={0} y1={55 * SCALE_Y} x2={SVG_WIDTH} y2={55 * SCALE_Y} stroke="white" strokeWidth={0.75} strokeDasharray="4,6" />
      {/* Center mark */}
      <circle cx={50 * SCALE_X} cy={35 * SCALE_Y} r={3} fill="white" />
      {/* Distance labels */}
      <text x={50 * SCALE_X} y={SVG_HEIGHT + 16} textAnchor="middle" fill="#aaa" fontSize={10}>50m</text>
      <text x={22 * SCALE_X} y={SVG_HEIGHT + 16} textAnchor="middle" fill="#aaa" fontSize={10}>22m</text>
      <text x={78 * SCALE_X} y={SVG_HEIGHT + 16} textAnchor="middle" fill="#aaa" fontSize={10}>22m</text>
    </g>
  );

  const renderPlayerRoutes = () => (
    <g>
      {players.map((player, idx) => {
        const color = PLAYER_COLORS[idx % PLAYER_COLORS.length];
        if (!player.route || player.route.length < 2) return null;
        const pathPoints = player.route.map((pt) => `${pt.x * SCALE_X},${pt.y * SCALE_Y}`).join(' ');
        const lastPoint = player.route[player.route.length - 1];
        return (
          <g key={player.player_id}>
            <polyline points={pathPoints} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" opacity={0.8} />
            <circle cx={lastPoint.x * SCALE_X} cy={lastPoint.y * SCALE_Y} r={6} fill={color} stroke="white" strokeWidth={1.5} />
            <text x={lastPoint.x * SCALE_X} y={lastPoint.y * SCALE_Y - 10} textAnchor="middle" fill="white" fontSize={9} fontWeight="bold">{player.player_id}</text>
          </g>
        );
      })}
    </g>
  );

  const renderHeatMap = () => {
    if (!showHeatMap || players.length === 0) return null;
    return (
      <g opacity={0.4}>
        {players.flatMap((player) =>
          (player.route || []).map((pt, i) => (
            <circle key={`heat-${player.player_id}-${i}`} cx={pt.x * SCALE_X} cy={pt.y * SCALE_Y} r={8} fill="red" opacity={0.1} />
          ))
        )}
      </g>
    );
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold">Field View</h3>
        <div className="flex items-center gap-1">
          <button onClick={handleZoomOut} className="p-1 hover:bg-gray-700 rounded" title="Zoom out">
            <ZoomOut className="w-4 h-4 text-gray-300" />
          </button>
          <span className="text-xs text-gray-400 w-12 text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={handleZoomIn} className="p-1 hover:bg-gray-700 rounded" title="Zoom in">
            <ZoomIn className="w-4 h-4 text-gray-300" />
          </button>
          <button onClick={handleReset} className="p-1 hover:bg-gray-700 rounded ml-1" title="Reset view">
            <Maximize2 className="w-4 h-4 text-gray-300" />
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="overflow-hidden border border-gray-700 rounded-lg cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          width="100%"
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT + 24}`}
          style={{ transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`, transformOrigin: 'center center' }}
        >
          {renderFieldLines()}
          {renderHeatMap()}
          {renderPlayerRoutes()}
        </svg>
      </div>
      {players.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {players.map((player, idx) => (
            <div key={player.player_id} className="flex items-center gap-1 text-xs">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PLAYER_COLORS[idx % PLAYER_COLORS.length] }} />
              <span className="text-gray-300">{player.player_id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FieldView;
