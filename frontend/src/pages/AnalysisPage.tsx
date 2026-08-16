import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Play, Loader2 } from 'lucide-react';
import { VideoPlayer } from '../components/VideoPlayer';
import { PlayerSelector } from '../components/PlayerSelector';
import { FieldCalibration } from '../components/FieldCalibration';
import { FieldView } from '../components/FieldView';
import { AnalyticsDashboard } from '../components/AnalyticsDashboard';
import { AIChat } from '../components/AIChat';
import { TrackingModeSelector } from '../components/TrackingModeSelector';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { useAnalysisStore } from '../stores/analysisStore';
import { getVideo, startProcessing, getAnalysisStatus } from '../services/api';
import { wsService } from '../services/websocket';
import { AnalysisStatus, TrackingMode, TrackingResult, PlayerMetrics, PlayArea } from '../types';

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
  // The backend now sends a 'players' array in PlayerMetrics format
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
    setVideo,
    updateProgress,
    updateProcessingDetails,
    setProcessingStatus,
    setResults,
    setSessionId,
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
        // Update progress from polling data
        if (statusData.progress !== undefined) {
          updateProgress(statusData.progress);
        }
        if (statusData.current_frame && statusData.total_frames) {
          updateProcessingDetails({
            currentFrame: statusData.current_frame,
            totalFrames: statusData.total_frames,
          });
        }
        // Check terminal states
        if (statusData.status === 'completed') {
          setProcessingStatus(AnalysisStatus.COMPLETED);
          stopPolling();
        } else if (statusData.status === 'failed') {
          setProcessingStatus(AnalysisStatus.FAILED);
          setError('Processing failed on backend');
          stopPolling();
        }
      } catch {
        // Polling errors are non-fatal, WebSocket may still work
      }
    }, 2000);
  }, [updateProgress, updateProcessingDetails, setProcessingStatus]);

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
          // progress is at top level of the message
          if (msg.progress !== undefined) {
            updateProgress(msg.progress);
          }
          // Rich processing details are in msg.data
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
            // Transform and set results from the completed progress message
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
            // Fallback: transform raw results
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

      // Build player selection bounding boxes for target acquisition
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
        // Pass play_area for linear field transform
        play_area: playArea || undefined,
        // Pass player selection bounding boxes for IoU-based target acquisition
        player_selections:
          (trackingMode === TrackingMode.SINGLE_PLAYER || trackingMode === TrackingMode.GROUP_TRACKING)
            ? playerSelections
            : undefined,
      };

      // 1. First, call the API to start processing and get a session_id
      const response = await startProcessing(videoId, config);
      const sessionId = response.session_id;
      setSessionId(sessionId);
      sessionIdRef.current = sessionId;
      setProcessingStatus(AnalysisStatus.PROCESSING);

      // 2. Subscribe to WebSocket messages BEFORE connecting
      if (wsUnsubRef.current) {
        wsUnsubRef.current();
      }
      wsUnsubRef.current = handleWebSocket();

      // 3. Connect WebSocket to receive progress updates
      wsService.connect(sessionId);

      // 4. Start polling fallback immediately (catches messages lost during WS setup)
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

  const handleFrameCapture = (blob: Blob) => {
    setFrameBlob(blob);
  };

  const videoSrc = currentVideo
    ? `${import.meta.env.VITE_API_URL || '/api'}/video/${currentVideo.id}/stream`
    : undefined;

  const showPlayerSelector =
    trackingMode === TrackingMode.SINGLE_PLAYER || trackingMode === TrackingMode.GROUP_TRACKING;

  const isProcessing = processingStatus === AnalysisStatus.PROCESSING;

  return (
    <div className="min-h-screen grid grid-rows-[auto_1fr_auto] gap-4 p-4">
      {/* Top bar - Mode selector + controls */}
      <div className="bg-gray-800/50 rounded-xl p-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <TrackingModeSelector />
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
        </div>
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      </div>

      {/* Processing status bar - shown during processing */}
      {isProcessing && (
        <ProcessingStatus onRetry={handleRetry} />
      )}

      {/* Main content area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        {/* Left panel - Video + Player selector */}
        <div className="flex flex-col gap-4 overflow-y-auto">
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
        </div>

        {/* Right panel - Field view + Analytics */}
        <div className="flex flex-col gap-4 overflow-y-auto">
          <FieldView players={results?.players || []} />
          <AnalyticsDashboard players={results?.players || []} />
        </div>
      </div>

      {/* Bottom panel - AI Chat */}
      <div className="h-80">
        <AIChat />
      </div>
    </div>
  );
};

export default AnalysisPage;
