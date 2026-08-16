import React, { useState } from 'react';
import { Stage, Layer, Rect, Text, Circle } from 'react-konva';
import { UserPlus, X } from 'lucide-react';
import { PlayerSelection, TrackingMode } from '../types';
import { useAnalysisStore } from '../stores/analysisStore';

interface PlayerSelectorProps {
  videoWidth: number;
  videoHeight: number;
  containerWidth: number;
  containerHeight: number;
}

export const PlayerSelector: React.FC<PlayerSelectorProps> = ({
  videoWidth,
  videoHeight,
  containerWidth,
  containerHeight,
}) => {
  const { trackingMode, selectedPlayers, addPlayer, removePlayer } = useAnalysisStore();
  const [isSelecting, setIsSelecting] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  const scaleX = containerWidth / (videoWidth || 1);
  const scaleY = containerHeight / (videoHeight || 1);

  const isSingleMode = trackingMode === TrackingMode.SINGLE_PLAYER;
  const canAddMore = !isSingleMode || selectedPlayers.length === 0;

  const handleMouseDown = (e: { evt: { offsetX: number; offsetY: number } }) => {
    if (!canAddMore) return;
    setIsSelecting(true);
    setStartPoint({ x: e.evt.offsetX, y: e.evt.offsetY });
    setCurrentRect(null);
  };

  const handleMouseMove = (e: { evt: { offsetX: number; offsetY: number } }) => {
    if (!isSelecting || !startPoint) return;
    const x = Math.min(startPoint.x, e.evt.offsetX);
    const y = Math.min(startPoint.y, e.evt.offsetY);
    const w = Math.abs(e.evt.offsetX - startPoint.x);
    const h = Math.abs(e.evt.offsetY - startPoint.y);
    setCurrentRect({ x, y, w, h });
  };

  const handleMouseUp = () => {
    if (!isSelecting || !currentRect || currentRect.w < 10 || currentRect.h < 10) {
      setIsSelecting(false);
      setStartPoint(null);
      setCurrentRect(null);
      return;
    }

    const player: PlayerSelection = {
      id: `player-${Date.now()}`,
      x: currentRect.x / scaleX,
      y: currentRect.y / scaleY,
      width: currentRect.w / scaleX,
      height: currentRect.h / scaleY,
      label: `P${selectedPlayers.length + 1}`,
    };

    if (isSingleMode) {
      selectedPlayers.forEach((p) => removePlayer(p.id));
    }
    addPlayer(player);

    setIsSelecting(false);
    setStartPoint(null);
    setCurrentRect(null);
  };

  return (
    <div className="relative">
      <Stage
        width={containerWidth}
        height={containerHeight}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="absolute inset-0"
      >
        <Layer>
          {selectedPlayers.map((player) => (
            <React.Fragment key={player.id}>
              <Rect
                x={player.x * scaleX}
                y={player.y * scaleY}
                width={player.width * scaleX}
                height={player.height * scaleY}
                stroke="#c4a84f"
                strokeWidth={2}
                dash={[4, 4]}
              />
              <Circle
                x={player.x * scaleX + (player.width * scaleX) / 2}
                y={player.y * scaleY - 12}
                radius={10}
                fill="#c4a84f"
              />
              <Text
                x={player.x * scaleX + (player.width * scaleX) / 2 - 6}
                y={player.y * scaleY - 18}
                text={player.label}
                fontSize={10}
                fill="white"
                fontStyle="bold"
              />
            </React.Fragment>
          ))}

          {currentRect && (
            <Rect
              x={currentRect.x}
              y={currentRect.y}
              width={currentRect.w}
              height={currentRect.h}
              stroke="#00ff00"
              strokeWidth={2}
              dash={[6, 3]}
            />
          )}
        </Layer>
      </Stage>

      {selectedPlayers.length > 0 && (
        <div className="absolute top-2 right-2 bg-gray-900/90 rounded-lg p-2 space-y-1">
          {selectedPlayers.map((player) => (
            <div key={player.id} className="flex items-center gap-2 text-xs">
              <UserPlus className="w-3 h-3 text-rugby-gold" />
              <span className="text-white">{player.label}</span>
              <button onClick={() => removePlayer(player.id)} className="hover:text-red-400">
                <X className="w-3 h-3 text-gray-400" />
              </button>
            </div>
          ))}
        </div>
      )}

      {canAddMore && (
        <div className="absolute bottom-2 left-2 bg-gray-900/80 rounded px-2 py-1">
          <p className="text-xs text-gray-300">Draw a box around the player to select</p>
        </div>
      )}
    </div>
  );
};

export default PlayerSelector;
