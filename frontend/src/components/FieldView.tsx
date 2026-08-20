import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { ZoomIn, ZoomOut, Maximize2, Play, Pause, SkipBack } from 'lucide-react';
import { PlayerMetrics, RoutePoint } from '../types';

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

const PLAYBACK_SPEEDS = [0.5, 1, 2, 4];

/**
 * Interpolates the player position at a given time from the route array.
 * Returns { x, y } in field coordinates, or null if no valid data.
 */
function interpolatePosition(route: RoutePoint[], time: number): { x: number; y: number } | null {
  if (!route || route.length === 0) return null;

  // Before the first point
  if (time <= route[0].timestamp) {
    return { x: route[0].x, y: route[0].y };
  }

  // After the last point
  if (time >= route[route.length - 1].timestamp) {
    return { x: route[route.length - 1].x, y: route[route.length - 1].y };
  }

  // Find the two surrounding points and lerp
  for (let i = 0; i < route.length - 1; i++) {
    const p0 = route[i];
    const p1 = route[i + 1];
    if (time >= p0.timestamp && time <= p1.timestamp) {
      const dt = p1.timestamp - p0.timestamp;
      if (dt === 0) return { x: p0.x, y: p0.y };
      const t = (time - p0.timestamp) / dt;
      return {
        x: p0.x + (p1.x - p0.x) * t,
        y: p0.y + (p1.y - p0.y) * t,
      };
    }
  }

  return { x: route[route.length - 1].x, y: route[route.length - 1].y };
}

/**
 * Returns the trail points (route points up to and including the current time).
 * The last point is the interpolated current position.
 */
function getTrailPoints(route: RoutePoint[], time: number): { x: number; y: number }[] {
  if (!route || route.length === 0) return [];

  const trail: { x: number; y: number }[] = [];

  for (const pt of route) {
    if (pt.timestamp <= time) {
      trail.push({ x: pt.x, y: pt.y });
    } else {
      break;
    }
  }

  // Add interpolated current position at end
  const currentPos = interpolatePosition(route, time);
  if (currentPos) {
    // Avoid duplicate if last trail point is at exactly current time
    const last = trail[trail.length - 1];
    if (!last || Math.abs(last.x - currentPos.x) > 0.001 || Math.abs(last.y - currentPos.y) > 0.001) {
      trail.push(currentPos);
    }
  }

  return trail;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export const FieldView: React.FC<FieldViewProps> = ({ players = [] }) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedHeatMapPlayers, setSelectedHeatMapPlayers] = useState<string[]>([]);

  // Animation state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const animationRef = useRef<number | null>(null);
  const lastFrameTimeRef = useRef<number | null>(null);

  // Compute the time range from all players' routes
  const { minTime, maxTime } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    for (const player of players) {
      if (player.route && player.route.length > 0) {
        const first = player.route[0].timestamp;
        const last = player.route[player.route.length - 1].timestamp;
        if (first < min) min = first;
        if (last > max) max = last;
      }
    }
    if (min === Infinity) return { minTime: 0, maxTime: 0 };
    return { minTime: min, maxTime: max };
  }, [players]);

  const duration = maxTime - minTime;
  const hasRouteData = duration > 0;

  // Animation loop
  useEffect(() => {
    if (!isPlaying || !hasRouteData) return;

    const animate = (timestamp: number) => {
      if (lastFrameTimeRef.current === null) {
        lastFrameTimeRef.current = timestamp;
      }

      const deltaMs = timestamp - lastFrameTimeRef.current;
      lastFrameTimeRef.current = timestamp;

      setCurrentTime((prev) => {
        const next = prev + (deltaMs / 1000) * playbackSpeed;
        if (next >= maxTime) {
          setIsPlaying(false);
          return maxTime;
        }
        return next;
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      lastFrameTimeRef.current = null;
    };
  }, [isPlaying, playbackSpeed, maxTime, hasRouteData]);

  // Reset currentTime when players change
  useEffect(() => {
    setCurrentTime(minTime);
    setIsPlaying(false);
  }, [minTime]);

  const handlePlayPause = () => {
    if (!hasRouteData) return;
    if (currentTime >= maxTime) {
      // Restart from beginning
      setCurrentTime(minTime);
    }
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentTime(minTime);
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    setCurrentTime(value);
    setIsPlaying(false);
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
  };

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.5));
  const handleResetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

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

  const renderAnimatedPlayers = () => (
    <g>
      {players.map((player, idx) => {
        const color = PLAYER_COLORS[idx % PLAYER_COLORS.length];
        if (!player.route || player.route.length < 2) return null;

        // Get trail up to current time
        const trail = getTrailPoints(player.route, currentTime);
        if (trail.length === 0) return null;

        const trailPathPoints = trail.map((pt) => `${pt.x * SCALE_X},${pt.y * SCALE_Y}`).join(' ');
        const currentPos = trail[trail.length - 1];

        return (
          <g key={player.player_id}>
            {/* Trail / estela */}
            {trail.length >= 2 && (
              <polyline
                points={trailPathPoints}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={0.6}
              />
            )}
            {/* Current position */}
            <circle
              cx={currentPos.x * SCALE_X}
              cy={currentPos.y * SCALE_Y}
              r={6}
              fill={color}
              stroke="white"
              strokeWidth={1.5}
            />
            {/* Player label */}
            <text
              x={currentPos.x * SCALE_X}
              y={currentPos.y * SCALE_Y - 10}
              textAnchor="middle"
              fill="white"
              fontSize={9}
              fontWeight="bold"
            >
              {player.player_id}
            </text>
          </g>
        );
      })}
    </g>
  );

  const renderHeatMap = () => {
    if (selectedHeatMapPlayers.length === 0) return null;

    const GRID_COLS = 10;
    const GRID_ROWS = 7;
    const cellWidth = SVG_WIDTH / GRID_COLS;
    const cellHeight = SVG_HEIGHT / GRID_ROWS;

    return (
      <g>
        {players
          .filter((player) => selectedHeatMapPlayers.includes(player.player_id))
          .map((player, _playerIdx) => {
            const color = PLAYER_COLORS[players.indexOf(player) % PLAYER_COLORS.length];

            // Build grid density
            const grid: number[][] = Array.from({ length: GRID_ROWS }, () =>
              Array(GRID_COLS).fill(0)
            );

            const relevantPoints = (player.route || []).filter(
              (pt) => pt.timestamp <= currentTime
            );

            for (const pt of relevantPoints) {
              const col = Math.min(Math.floor((pt.x / FIELD_WIDTH) * GRID_COLS), GRID_COLS - 1);
              const row = Math.min(Math.floor((pt.y / FIELD_HEIGHT) * GRID_ROWS), GRID_ROWS - 1);
              if (col >= 0 && row >= 0) {
                grid[row][col]++;
              }
            }

            // Find max density for normalization
            let maxDensity = 0;
            for (let r = 0; r < GRID_ROWS; r++) {
              for (let c = 0; c < GRID_COLS; c++) {
                if (grid[r][c] > maxDensity) maxDensity = grid[r][c];
              }
            }

            if (maxDensity === 0) return null;

            return (
              <g key={`heatmap-${player.player_id}`}>
                {grid.map((row, rowIdx) =>
                  row.map((count, colIdx) => {
                    if (count === 0) return null;
                    const opacity = (count / maxDensity) * 0.6;
                    return (
                      <rect
                        key={`heat-${player.player_id}-${rowIdx}-${colIdx}`}
                        x={colIdx * cellWidth}
                        y={rowIdx * cellHeight}
                        width={cellWidth}
                        height={cellHeight}
                        fill={color}
                        opacity={opacity}
                        rx={2}
                      />
                    );
                  })
                )}
              </g>
            );
          })}
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
          <button onClick={handleResetView} className="p-1 hover:bg-gray-700 rounded ml-1" title="Reset view">
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
          {renderAnimatedPlayers()}
        </svg>
      </div>

      {/* Animation Controls */}
      {hasRouteData && (
        <div className="mt-3 space-y-2">
          {/* Time slider */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400 w-10 text-right">{formatTime(currentTime - minTime)}</span>
            <input
              type="range"
              min={minTime}
              max={maxTime}
              step={0.1}
              value={currentTime}
              onChange={handleSliderChange}
              className="flex-1 h-1.5 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
              aria-label="Time slider"
            />
            <span className="text-xs text-gray-400 w-10">{formatTime(duration)}</span>
          </div>

          {/* Playback controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={handleReset}
                className="p-1.5 hover:bg-gray-700 rounded text-gray-300 hover:text-white transition-colors"
                title="Reset"
                aria-label="Reset"
              >
                <SkipBack className="w-4 h-4" />
              </button>
              <button
                onClick={handlePlayPause}
                className="p-1.5 bg-blue-600 hover:bg-blue-500 rounded text-white transition-colors"
                title={isPlaying ? 'Pause' : 'Play'}
                aria-label={isPlaying ? 'Pause' : 'Play'}
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
            </div>

            {/* Speed controls */}
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-500 mr-1">Speed:</span>
              {PLAYBACK_SPEEDS.map((speed) => (
                <button
                  key={speed}
                  onClick={() => handleSpeedChange(speed)}
                  className={`px-2 py-0.5 text-xs rounded transition-colors ${
                    playbackSpeed === speed
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-gray-200'
                  }`}
                  aria-label={`${speed}x speed`}
                >
                  {speed}x
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Player legend with heatmap toggles */}
      {players.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {players.map((player, idx) => {
            const isHeatMapActive = selectedHeatMapPlayers.includes(player.player_id);
            return (
              <button
                key={player.player_id}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${
                  isHeatMapActive
                    ? 'bg-gray-600 ring-1 ring-white/30'
                    : 'bg-gray-700/50 hover:bg-gray-700'
                }`}
                onClick={() => {
                  setSelectedHeatMapPlayers((prev) =>
                    prev.includes(player.player_id)
                      ? prev.filter((id) => id !== player.player_id)
                      : [...prev, player.player_id]
                  );
                }}
                title={`Toggle heatmap for ${player.player_id}`}
                data-testid={`heatmap-toggle-${player.player_id}`}
              >
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PLAYER_COLORS[idx % PLAYER_COLORS.length] }} />
                <span className="text-gray-300">{player.player_id}</span>
                {isHeatMapActive && <span className="text-[10px] text-green-400 ml-1">&#9632;</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default FieldView;
