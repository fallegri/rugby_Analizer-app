import React, { useEffect, useState, useRef } from 'react';
import {
  Loader2,
  AlertTriangle,
  XCircle,
  CheckCircle,
  Video,
  Users,
  Crosshair,
  Ruler,
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import { useAnalysisStore } from '../stores/analysisStore';

/** Stall thresholds in milliseconds */
const STALL_WARNING_MS = 10_000;
const STALL_ERROR_MS = 30_000;

type StallState = 'active' | 'warning' | 'error';

/** Map stage names to icons */
const stageIcons: Record<string, React.ReactNode> = {
  'Cargando video': <Video className="w-5 h-5" />,
  'Detectando jugadores': <Users className="w-5 h-5" />,
  Tracking: <Crosshair className="w-5 h-5" />,
  'Calibrando cancha': <Ruler className="w-5 h-5" />,
  'Calculando analiticas': <BarChart3 className="w-5 h-5" />,
  Completado: <CheckCircle className="w-5 h-5" />,
};

function formatTime(seconds: number): string {
  if (seconds <= 0) return '0s';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

interface ProcessingStatusProps {
  onRetry?: () => void;
}

export const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ onRetry }) => {
  const { processingProgress, processingDetails } = useAnalysisStore();
  const [stallState, setStallState] = useState<StallState>('active');
  const stallCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stall detection logic
  useEffect(() => {
    if (stallCheckRef.current) {
      clearInterval(stallCheckRef.current);
    }

    stallCheckRef.current = setInterval(() => {
      const { lastUpdateTimestamp } = processingDetails;
      if (lastUpdateTimestamp === 0) return;

      const elapsed = Date.now() - lastUpdateTimestamp;

      if (elapsed >= STALL_ERROR_MS) {
        setStallState('error');
      } else if (elapsed >= STALL_WARNING_MS) {
        setStallState('warning');
      } else {
        setStallState('active');
      }
    }, 1000);

    return () => {
      if (stallCheckRef.current) {
        clearInterval(stallCheckRef.current);
      }
    };
  }, [processingDetails]);

  // Reset stall state when we get new updates
  useEffect(() => {
    if (processingDetails.lastUpdateTimestamp > 0) {
      setStallState('active');
    }
  }, [processingDetails.lastUpdateTimestamp]);

  const { stage, currentFrame, totalFrames, fps, elapsedTime, eta } = processingDetails;

  const getProgressColor = (): string => {
    switch (stallState) {
      case 'error':
        return 'bg-red-500';
      case 'warning':
        return 'bg-yellow-500';
      default:
        return 'bg-emerald-500';
    }
  };

  const getBorderColor = (): string => {
    switch (stallState) {
      case 'error':
        return 'border-red-500/50';
      case 'warning':
        return 'border-yellow-500/50';
      default:
        return 'border-emerald-500/30';
    }
  };

  const getGlowColor = (): string => {
    switch (stallState) {
      case 'error':
        return 'shadow-red-500/20';
      case 'warning':
        return 'shadow-yellow-500/20';
      default:
        return 'shadow-emerald-500/20';
    }
  };

  const stageIcon = stageIcons[stage] || <Loader2 className="w-5 h-5 animate-spin" />;

  return (
    <div
      className={`rounded-xl border ${getBorderColor()} bg-gray-800/80 backdrop-blur-sm p-5 shadow-lg ${getGlowColor()}`}
      data-testid="processing-status"
    >
      {/* Header with stage */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-lg ${
              stallState === 'active'
                ? 'bg-emerald-500/20 text-emerald-400'
                : stallState === 'warning'
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-red-500/20 text-red-400'
            }`}
          >
            {stallState === 'active' ? stageIcon : stallState === 'warning' ? (
              <AlertTriangle className="w-5 h-5" />
            ) : (
              <XCircle className="w-5 h-5" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">
              {stallState === 'error'
                ? 'El proceso se detuvo'
                : stallState === 'warning'
                  ? 'El proceso puede estar bloqueado'
                  : stage || 'Iniciando...'}
            </h3>
            <p className="text-xs text-gray-400">
              {stallState === 'error'
                ? 'Sin respuesta por mas de 30 segundos'
                : stallState === 'warning'
                  ? 'Sin actualizacion por mas de 10 segundos'
                  : 'Procesando video'}
            </p>
          </div>
        </div>

        {stallState === 'error' && onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-red-500/20 text-red-300 border border-red-500/40 rounded-lg hover:bg-red-500/30 transition-colors"
            data-testid="retry-button"
          >
            <RefreshCw className="w-4 h-4" />
            Reintentar
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="relative w-full h-3 bg-gray-700 rounded-full overflow-hidden mb-4">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${getProgressColor()} ${
            stallState === 'active' ? 'animate-pulse-subtle' : ''
          }`}
          style={{ width: `${Math.min(processingProgress, 100)}%` }}
          data-testid="progress-bar"
        />
        {stallState === 'active' && processingProgress > 0 && processingProgress < 100 && (
          <div
            className="absolute top-0 left-0 h-full w-full"
            style={{
              background:
                'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%)',
              animation: 'shimmer 2s infinite',
            }}
          />
        )}
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-gray-700/50 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-400 mb-0.5">Progreso</p>
          <p className="text-lg font-bold text-white" data-testid="progress-percentage">
            {processingProgress.toFixed(1)}%
          </p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-400 mb-0.5">Frames</p>
          <p className="text-lg font-bold text-white" data-testid="frame-counter">
            {currentFrame}
            <span className="text-sm text-gray-400">/{totalFrames}</span>
          </p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-400 mb-0.5">Tiempo / ETA</p>
          <p className="text-lg font-bold text-white" data-testid="time-display">
            {formatTime(elapsedTime)}
            <span className="text-sm text-gray-400"> / {formatTime(eta)}</span>
          </p>
        </div>

        <div className="bg-gray-700/50 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-400 mb-0.5">Velocidad</p>
          <p className="text-lg font-bold text-white" data-testid="fps-display">
            {fps.toFixed(1)}
            <span className="text-sm text-gray-400"> fps</span>
          </p>
        </div>
      </div>

      {/* Stage indicators */}
      <div className="mt-4 flex items-center justify-between gap-1">
        {Object.entries(stageIcons)
          .filter(([key]) => key !== 'Completado')
          .map(([stageName, icon], idx, arr) => {
            const stageOrder = [
              'Cargando video',
              'Detectando jugadores',
              'Tracking',
              'Calibrando cancha',
              'Calculando analiticas',
            ];
            const currentIdx = stageOrder.indexOf(stage);
            const thisIdx = stageOrder.indexOf(stageName);
            const isComplete = thisIdx < currentIdx;
            const isCurrent = thisIdx === currentIdx;

            return (
              <React.Fragment key={stageName}>
                <div
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-colors ${
                    isCurrent
                      ? 'bg-emerald-500/20 text-emerald-400 font-medium'
                      : isComplete
                        ? 'bg-gray-600/50 text-gray-300'
                        : 'bg-gray-700/30 text-gray-500'
                  }`}
                  title={stageName}
                >
                  <span className="hidden sm:inline">{icon}</span>
                  <span className="hidden md:inline truncate max-w-[80px]">{stageName}</span>
                  {isComplete && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                </div>
                {idx < arr.length - 1 && (
                  <div
                    className={`flex-shrink-0 w-4 h-0.5 ${
                      thisIdx < currentIdx ? 'bg-emerald-500/60' : 'bg-gray-600'
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}
      </div>
    </div>
  );
};

export default ProcessingStatus;
