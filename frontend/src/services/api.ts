import axios, { AxiosProgressEvent } from 'axios';
import { AIProvider, CalibrationPoint, TrackingMode, Video, TrackingResult, FieldCalibration, PlayArea, DetectedPlay } from '../types';
import { useSettingsStore } from '../stores/settingsStore';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Video endpoints
export async function uploadVideo(
  file: File,
  onProgress?: (progress: number) => void
): Promise<Video> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post('/video/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return response.data;
}

export async function getVideo(id: string): Promise<Video> {
  const response = await apiClient.get(`/video/${id}`);
  return response.data;
}

export async function startProcessing(
  videoId: string,
  config: {
    mode: TrackingMode;
    calibration?: FieldCalibration;
    target_player_ids?: string[];
    play_area?: PlayArea;
    player_selections?: { x: number; y: number; width: number; height: number }[];
  }
): Promise<{ session_id: string }> {
  const { yoloModel, enablePose, teamAColor, teamBColor } = useSettingsStore.getState();
  const response = await apiClient.post(`/video/${videoId}/process`, {
    ...config,
    yolo_model: yoloModel,
    enable_pose: enablePose,
    team_a_color: teamAColor ?? undefined,
    team_b_color: teamBColor ?? undefined,
  });
  return response.data;
}

export async function getResults(videoId: string): Promise<TrackingResult> {
  const response = await apiClient.get(`/video/${videoId}/results`);
  return response.data;
}

export async function deleteVideo(videoId: string): Promise<void> {
  await apiClient.delete(`/video/${videoId}`);
}

// Analysis status polling endpoint
export async function getAnalysisStatus(
  sessionId: string
): Promise<{ session_id: string; status: string; progress: number; current_frame: number; total_frames: number }> {
  const response = await apiClient.get(`/analysis/${sessionId}/status`);
  return response.data;
}

// Analysis results endpoint (fetches full results when status is completed)
export async function getAnalysisResults(
  sessionId: string
): Promise<{ session_id: string; video_id: string; mode: string; status: string; results: Record<string, unknown> | null }> {
  const response = await apiClient.get(`/analysis/${sessionId}/results`);
  return response.data;
}

// Analysis export endpoint (returns full JSON for download)
export async function getAnalysisExport(
  sessionId: string
): Promise<Record<string, unknown>> {
  const response = await apiClient.get(`/analysis/${sessionId}/export`);
  return response.data;
}

// AI endpoints
export async function listProviders(): Promise<{ providers: AIProvider[] }> {
  const response = await apiClient.get('/ai/providers');
  return response.data;
}

export async function switchProvider(provider: AIProvider): Promise<void> {
  await apiClient.put('/ai/provider', { provider });
}

export async function updateAIConfig(keys: Record<string, string>): Promise<void> {
  await apiClient.put('/ai/config', { keys });
}

export async function analyzeWithAI(prompt: string, context?: string): Promise<{ response: string }> {
  const response = await apiClient.post('/ai/analyze', { prompt, context });
  return response.data;
}

// Calibration endpoints
export async function autoCalibrate(frameBlob: Blob): Promise<FieldCalibration> {
  const formData = new FormData();
  formData.append('frame', frameBlob);

  const response = await apiClient.post('/calibration/auto', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function manualCalibrate(points: CalibrationPoint[]): Promise<FieldCalibration> {
  const response = await apiClient.post('/calibration/manual', { points });
  return response.data;
}

// Health check
export async function getHealth(): Promise<{ status: string }> {
  const response = await apiClient.get('/health');
  return response.data;
}

// Play detection endpoints
export async function detectPlays(sessionId: string): Promise<DetectedPlay[]> {
  const response = await apiClient.post(`/analysis/${sessionId}/detect-plays`);
  return response.data.plays || response.data;
}

export async function getPlays(sessionId: string): Promise<DetectedPlay[]> {
  const response = await apiClient.get(`/analysis/${sessionId}/plays`);
  return response.data.plays || response.data;
}

// PDF report download
export async function downloadPDFReport(sessionId: string): Promise<void> {
  const response = await apiClient.get(`/analysis/${sessionId}/report/pdf`, {
    responseType: 'blob',
  });
  const blob = new Blob([response.data], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `rugby_report_${sessionId}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default apiClient;
