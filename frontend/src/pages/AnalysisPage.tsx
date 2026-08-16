import React, { useEffect, useState, useCallback } from 'react';
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
import { getVideo, startProcessing } from '../services/api';
import { wsService } from '../services/websocket';
import { AnalysisStatus, TrackingMode } from '../types';

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

  // Load video info
  useEffect(() => {
    if (!videoId) return;
    getVideo(videoId)
      .then(setVideo)
      .catch(() => setError('Failed to load video information'));
  }, [videoId, setVideo]);

  // WebSocket connection for progress
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
          }
          break;
        case 'error':
          setError(msg.data?.message || msg.error || 'Processing failed');
          setProcessingStatus(AnalysisStatus.FAILED);
          break;
      }
    });

    return unsubMessage;
  }, [updateProgress, updateProcessingDetails, setProcessingStatus, setResults]);

  const handleStartProcessing = async () => {
    if (!videoId) return;
    setIsStarting(true);
    setError(null);

    try {
      const playerIds = selectedPlayers.map((p) => p.id);
      const config = {
        mode: trackingMode,
        calibration: calibration || undefined,
        target_player_ids:
          trackingMode === TrackingMode.SINGLE_PLAYER || trackingMode === TrackingMode.GROUP_TRACKING
            ? playerIds
            : undefined,
      };

      const response = await startProcessing(videoId, config);
      setSessionId(response.session_id);
      setProcessingStatus(AnalysisStatus.PROCESSING);

      // Connect WebSocket for progress
      wsService.connect(response.session_id);
      const unsub = handleWebSocket();

      // Cleanup on unmount
      return () => {
        unsub();
        wsService.disconnect();
      };
    } catch {
      setError('Failed to start processing');
    } finally {
      setIsStarting(false);
    }
  };

  const handleRetry = () => {
    wsService.disconnect();
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
          <VideoPlayer
            src={videoSrc}
            onFrameCapture={handleFrameCapture}
            overlayData={undefined}
          />

          {showPlayerSelector && (
            <PlayerSelector
              videoWidth={currentVideo?.width || 1920}
              videoHeight={currentVideo?.height || 1080}
              containerWidth={640}
              containerHeight={360}
            />
          )}

          <FieldCalibration
            frameBlob={frameBlob}
            videoWidth={currentVideo?.width || 1920}
            videoHeight={currentVideo?.height || 1080}
            containerWidth={640}
            containerHeight={360}
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
