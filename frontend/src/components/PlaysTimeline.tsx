import React, { useState } from 'react';
import { Shield, Users, Circle, AlignLeft, Trophy, Loader2, Crosshair } from 'lucide-react';
import { useAnalysisStore } from '../stores/analysisStore';
import { detectPlays } from '../services/api';
import { PlayType, DetectedPlay } from '../types';

const playTypeConfig: Record<PlayType, { color: string; bgColor: string; icon: React.ElementType; label: string }> = {
  [PlayType.TACKLE]: { color: 'text-red-400', bgColor: 'bg-red-900/40', icon: Shield, label: 'Tackle' },
  [PlayType.SCRUM]: { color: 'text-blue-400', bgColor: 'bg-blue-900/40', icon: Users, label: 'Scrum' },
  [PlayType.RUCK]: { color: 'text-orange-400', bgColor: 'bg-orange-900/40', icon: Circle, label: 'Ruck' },
  [PlayType.LINEOUT]: { color: 'text-green-400', bgColor: 'bg-green-900/40', icon: AlignLeft, label: 'Line-out' },
  [PlayType.TRY]: { color: 'text-yellow-400', bgColor: 'bg-yellow-900/40', icon: Trophy, label: 'Try' },
};

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

interface PlayCardProps {
  play: DetectedPlay;
}

const PlayCard: React.FC<PlayCardProps> = ({ play }) => {
  const [expanded, setExpanded] = useState(false);
  const config = playTypeConfig[play.play_type] || playTypeConfig[PlayType.TACKLE];
  const Icon = config.icon;

  return (
    <div
      className={`${config.bgColor} border border-gray-700 rounded-lg p-3 cursor-pointer transition-all hover:border-gray-500`}
      onClick={() => setExpanded(!expanded)}
      data-testid="play-card"
    >
      <div className="flex items-center gap-3">
        <div className={`${config.color} flex-shrink-0`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-semibold ${config.color}`}>{config.label}</span>
            <span className="text-xs text-gray-400">
              {formatTime(play.start_time)} - {formatTime(play.end_time)}
            </span>
          </div>
          <p className="text-xs text-gray-300 truncate mt-0.5">{play.description}</p>
        </div>
        <div className="flex-shrink-0 text-right">
          <span className="text-xs font-medium text-gray-300">{Math.round(play.confidence * 100)}%</span>
        </div>
      </div>

      {play.players_involved.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {play.players_involved.map((player, idx) => (
            <span key={idx} className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
              {player}
            </span>
          ))}
        </div>
      )}

      {expanded && play.ai_explanation && (
        <div className="mt-3 pt-3 border-t border-gray-600" data-testid="ai-explanation">
          <p className="text-xs text-gray-300 leading-relaxed">{play.ai_explanation}</p>
        </div>
      )}
    </div>
  );
};

export const PlaysTimeline: React.FC = () => {
  const { detectedPlays, isDetectingPlays, sessionId, setDetectedPlays, setIsDetectingPlays } = useAnalysisStore();
  const [error, setError] = useState<string | null>(null);

  const handleDetectPlays = async () => {
    if (!sessionId) return;
    setError(null);
    setIsDetectingPlays(true);
    try {
      const plays = await detectPlays(sessionId);
      setDetectedPlays(plays);
    } catch {
      setError('Failed to detect plays. Ensure analysis is completed first.');
    } finally {
      setIsDetectingPlays(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Crosshair className="w-5 h-5 text-rugby-gold" />
          Jugadas Detectadas
        </h2>
        <button
          onClick={handleDetectPlays}
          disabled={isDetectingPlays || !sessionId}
          className="flex items-center gap-2 px-3 py-1.5 bg-rugby-gold text-gray-900 font-medium text-sm rounded-lg hover:bg-rugby-gold/80 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isDetectingPlays ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Crosshair className="w-4 h-4" />
          )}
          {isDetectingPlays ? 'Detecting...' : 'Detectar Jugadas'}
        </button>
      </div>

      {error && <p className="px-4 pt-2 text-sm text-red-400">{error}</p>}

      <div className="flex-1 overflow-y-auto p-4">
        {detectedPlays.length === 0 && !isDetectingPlays ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400" data-testid="empty-state">
            <Crosshair className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm">No plays detected yet</p>
            <p className="text-xs mt-1">Run play detection after completing an analysis</p>
          </div>
        ) : isDetectingPlays ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin mb-3" />
            <p className="text-sm">Detecting plays...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {detectedPlays.map((play, index) => (
              <PlayCard key={index} play={play} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PlaysTimeline;
