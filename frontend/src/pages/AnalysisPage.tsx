import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Play, Loader2, Download, Video, Activity, BarChart3, Crosshair, MessageSquare, FileText } from 'lucide-react';
import { VideoPlayer } from '../components/VideoPlayer';
import { PlayerSelector } from '../components/PlayerSelector';
import { FieldCalibration } from '../components/FieldCalibration';
import { FieldView } from '../components/FieldView';
import { AnalyticsDashboard } from '../components/AnalyticsDashboard';
import { AIChat } from '../components/AIChat';
import { TrackingModeSelector } from '../components/TrackingModeSelector';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { PlaysTimeline } from '../components/PlaysTimeline';
import { PlayerComparison } from '../components/PlayerComparison';
import { TimeZoneAnalysis } from '../components/TimeZoneAnalysis';
import { RSAAnalysis } from '../components/RSAAnalysis';
import { useAnalysisStore, TabId } from '../stores/analysisStore';
import { getVideo, startProcessing, getAnalysisStatus, getAnalysisResults, getAnalysisExport, downloadPDFReport } from '../services/api';
import { wsService } from '../services/websocket';
import { AnalysisStatus, TrackingMode, TrackingResult, PlayerMetrics, PlayArea } from '../types';

interface TabConfig {
  id: TabId;
  label: string;
  icon: React.ElementType;
}

const tabs: TabConfig[] = [
  { id: 'video', label: 'Video', icon: Video },
  { id: 'analisis', label: 'Analisis', icon: Activity },
  { id: 'metricas', label: 'Metricas', icon: BarChart3 },
  { id: 'jugadas', label: 'Jugadas', icon: Crosshair },
  { id: 'ia-chat', label: 'IA Chat', icon: MessageSquare },
];

/**
 * Transform raw backend results (from WebSocket/polling) into a TrackingResult
 * that AnalyticsDashboard and FieldView can consume.
 */
function transformBackendResults(
  raw: Record<string, unknown>,
  sessionId: string,
  videoId: string,
  mode: TrackingMode
): TrackingResult {
  const rawPlayers = (raw.players as Record<string, unknown>[] | undefined) || [];

  const players: PlayerMetrics[] = rawPlayers.map((p: Record<string, unknown>) => ({
    player_id: String(p.player_id || ''),
    total_distance_km: Number(p.total_distance_km || 0),
    max_speed_kmh: Number(p.max_speed_kmh || 0),
    avg_speed_kmh: Number(p.avg_speed_kmh || 0),
    sprint_count: Number(p.sprint_count || 0),
    sprints: ((p.sprints as Record<string, unknown>[]) || []).map((s) => ({
      start_time: Number(s.start_time || 0),
      end_time: Number(s.end_time || 0),
      max_speed: Number(s.max_speed || 0),
      distance: Number(s.distance || 0),
    })),
    route: ((p.route as Record<string, unknown>[]) || []).map((r) => ({
      x: Number(r.x || 0),
      y: Number(r.y || 0),
      timestamp: Number(r.timestamp || 0),
      speed: Number(r.speed || 0),
    })),
  }));

  return {
    session_id: sessionId,
    video_id: videoId,
    mode,
    status: AnalysisStatus.COMPLETED,
    players,
    duration: Number(raw.duration_s || 0),
    processed_frames: Number(raw.total_frames || 0),
    total_frames: Number(raw.total_frames || 0),
  };
}

export const AnalysisPage: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const {
    currentVideo,
    trackingMode,
    selectedPlayers,
    calibration,
    processingStatus,
    results,
    sessionId: storeSessionId,
    activeTab,
    setVideo,
    updateProgress,
    updateProcessingDetails,
    setProcessingStatus,
    setResults,
    setSessionId,
    setActiveTab,
  } = useAnalysisStore();

  const [frameBlob, setFrameBlob] = useState<Blob | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playArea, setPlayArea] = useState<PlayArea | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const wsUnsubRef = useRef<(() => void) | null>(null);

  // Load video info
  useEffect(() => {
    if (!videoId) return;
    getVideo(videoId)
      .then(setVideo)
      .catch(() => setError('Failed to load video information'));
  }, [videoId, setVideo]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling();
      wsService.disconnect();
      if (wsUnsubRef.current) {
        wsUnsubRef.current();
        wsUnsubRef.current = null;
      }
    };
  }, []);

  // Start polling fallback for analysis status
  const startPolling = useCallback((sessionId: string) => {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      try {
        const statusData = await getAnalysisStatus(sessionId);
        if (statusData.progress !== undefined) {
          updateProgress(statusData.progress);
        }
        if (statusData.current_frame && statusData.total_frames) {
          updateProcessingDetails({
            currentFrame: statusData.current_frame,
            totalFrames: statusData.total_frames,
          });
        }
        if (statusData.status === 'completed') {
          setProcessingStatus(AnalysisStatus.COMPLETED);
          stopPolling();
          try {
            const resultsData = await getAnalysisResults(sessionId);
            if (resultsData.results) {
              const transformed = transformBackendResults(
                resultsData.results as Record<string, unknown>,
                sessionId,
                videoId || '',
                trackingMode
              );
              setResults(transformed);
            }
          } catch {
            // Results fetch failed - results may have already been set via WebSocket
          }
        } else if (statusData.status === 'failed') {
          setProcessingStatus(AnalysisStatus.FAILED);
          setError('Processing failed on backend');
          stopPolling();
        }
      } catch {
        // Polling errors are non-fatal, WebSocket may still work
      }
    }, 2000);
  }, [updateProgress, updateProcessingDetails, setProcessingStatus, setResults, videoId, trackingMode]);

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  // WebSocket message handler setup
  const handleWebSocket = useCallback(() => {
    const unsubMessage = wsService.onMessage((msg) => {
      switch (msg.type) {
        case 'progress':
          if (msg.progress !== undefined) {
            updateProgress(msg.progress);
          }
          if (msg.data) {
            updateProcessingDetails({
              stage: msg.data.stage || '',
              currentFrame: msg.data.current_frame || 0,
              totalFrames: msg.data.total_frames || 0,
              fps: msg.data.fps || 0,
              elapsedTime: msg.data.elapsed_time || 0,
              eta: msg.data.eta || 0,
            });
          }
          if (msg.status === 'completed') {
            setProcessingStatus(AnalysisStatus.COMPLETED);
            stopPolling();
            if (msg.data?.results) {
              const transformed = transformBackendResults(
                msg.data.results as Record<string, unknown>,
                sessionIdRef.current || '',
                videoId || '',
                trackingMode
              );
              setResults(transformed);
            }
          }
          break;
        case 'status':
          if (msg.data?.status) {
            setProcessingStatus(msg.data.status);
          }
          break;
        case 'result':
          if (msg.data?.result) {
            setResults(msg.data.result);
            setProcessingStatus(AnalysisStatus.COMPLETED);
            stopPolling();
          } else if (msg.data?.results) {
            const transformed = transformBackendResults(
              msg.data.results as Record<string, unknown>,
              sessionIdRef.current || '',
              videoId || '',
              trackingMode
            );
            setResults(transformed);
            setProcessingStatus(AnalysisStatus.COMPLETED);
            stopPolling();
          }
          break;
        case 'error':
          setError(msg.data?.message || msg.error || 'Processing failed');
          setProcessingStatus(AnalysisStatus.FAILED);
          stopPolling();
          break;
      }
    });

    return unsubMessage;
  }, [updateProgress, updateProcessingDetails, setProcessingStatus, setResults, videoId, trackingMode]);

  const handleStartProcessing = async () => {
    if (!videoId) return;
    setIsStarting(true);
    setError(null);

    try {
      const playerIds = selectedPlayers.map((p) => p.id);

      const playerSelections = selectedPlayers.map((p) => ({
        x: p.x,
        y: p.y,
        width: p.width,
        height: p.height,
      }));

      const config = {
        mode: trackingMode,
        calibration: calibration || undefined,
        target_player_ids:
          trackingMode === TrackingMode.SINGLE_PLAYER || trackingMode === TrackingMode.GROUP_TRACKING
            ? playerIds
            : undefined,
        play_area: playArea || undefined,
        player_selections:
          (trackingMode === TrackingMode.SINGLE_PLAYER || trackingMode === TrackingMode.GROUP_TRACKING)
            ? playerSelections
            : undefined,
      };

      const response = await startProcessing(videoId, config);
      const sessionId = response.session_id;
      setSessionId(sessionId);
      sessionIdRef.current = sessionId;
      setProcessingStatus(AnalysisStatus.PROCESSING);

      if (wsUnsubRef.current) {
        wsUnsubRef.current();
      }
      wsUnsubRef.current = handleWebSocket();

      wsService.connect(sessionId);
      startPolling(sessionId);

    } catch {
      setError('Failed to start processing');
    } finally {
      setIsStarting(false);
    }
  };

  const handleRetry = () => {
    wsService.disconnect();
    stopPolling();
    handleStartProcessing();
  };

  const handleExport = async () => {
    const sid = storeSessionId || sessionIdRef.current;
    if (!sid) return;
    try {
      const exportData = await getAnalysisExport(sid);
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis_${sid}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setError('Failed to export analysis');
    }
  };

  const handleFrameCapture = (blob: Blob) => {
    setFrameBlob(blob);
  };

  const videoSrc = currentVideo
    ? `${import.meta.env.VITE_API_URL || '/api'}/video/${currentVideo.id}/stream`
    : undefined;

  const showPlayerSelector =
    trackingMode === TrackingMode.SINGLE_PLAYER || trackingMode === TrackingMode.GROUP_TRACKING;

  const isProcessing = processingStatus === AnalysisStatus.PROCESSING;

  const renderTabContent = () => {
    switch (activeTab) {
      case 'video':
        return (
          <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
            <TrackingModeSelector />
            <div className="relative">
              <VideoPlayer
                src={videoSrc}
                onFrameCapture={handleFrameCapture}
                overlayData={undefined}
              />
              {showPlayerSelector && (
                <div className="absolute top-0 left-0 right-0 bottom-[52px] z-10">
                  <PlayerSelector
                    videoWidth={currentVideo?.width || 1920}
                    videoHeight={currentVideo?.height || 1080}
                    containerWidth={0}
                    containerHeight={0}
                    fillContainer
                  />
                </div>
              )}
            </div>
            <FieldCalibration
              frameBlob={frameBlob}
              videoWidth={currentVideo?.width || 1920}
              videoHeight={currentVideo?.height || 1080}
              containerWidth={640}
              containerHeight={360}
              onPlayAreaChange={setPlayArea}
            />
            <div className="flex items-center gap-3">
              <button
                onClick={handleStartProcessing}
                disabled={isStarting || isProcessing}
                className="flex items-center gap-2 px-5 py-2 bg-rugby-green text-white font-medium rounded-lg hover:bg-rugby-green/80 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isStarting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {isStarting ? 'Starting...' : 'Start Analysis'}
              </button>
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
          </div>
        );
      case 'analisis':
        return (
          <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
            {isProcessing && <ProcessingStatus onRetry={handleRetry} />}
            <FieldView players={results?.players || []} />
          </div>
        );
      case 'metricas':
        return (
          <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
            <AnalyticsDashboard players={results?.players || []} />
            <PlayerComparison players={results?.players || []} />
            <TimeZoneAnalysis players={results?.players || []} />
            <RSAAnalysis players={results?.players || []} />
            {processingStatus === AnalysisStatus.COMPLETED && results && (
              <div className="flex justify-end gap-3">
                <button
                  onClick={async () => {
                    const sid = storeSessionId || sessionIdRef.current;
                    if (sid) {
                      try {
                        await downloadPDFReport(sid);
                      } catch {
                        setError('Failed to generate PDF report');
                      }
                    }
                  }}
                  className="flex items-center gap-2 px-5 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700"
                >
                  <FileText className="w-4 h-4" />
                  Generar Reporte PDF
                </button>
                <button
                  onClick={handleExport}
                  className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700"
                >
                  <Download className="w-4 h-4" />
                  Exportar Analisis
                </button>
              </div>
            )}
          </div>
        );
      case 'jugadas':
        return (
          <div className="h-full">
            <PlaysTimeline />
          </div>
        );
      case 'ia-chat':
        return (
          <div className="h-full">
            <AIChat />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Sidebar navigation */}
      <nav className="w-56 bg-gray-900 border-r border-gray-700 flex flex-col" data-testid="sidebar-nav">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-rugby-gold/20 text-rugby-gold border-r-2 border-rugby-gold'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
              data-testid={`tab-${tab.id}`}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Main content area */}
      <main className="flex-1 bg-gray-800 overflow-hidden">
        {renderTabContent()}
      </main>
    </div>
  );
};

export default AnalysisPage;
