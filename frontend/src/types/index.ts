// Enums matching backend models
export enum TrackingMode {
  SINGLE_PLAYER = 'single_player',
  BALL_CARRIER = 'ball_carrier',
  BALL_ONLY = 'ball_only',
  GROUP_TRACKING = 'group_tracking',
}

export enum AIProvider {
  NVIDIA = 'nvidia',
  OPENAI = 'openai',
  CLAUDE = 'claude',
  GEMINI = 'gemini',
  OLLAMA = 'ollama',
}

export enum VideoStatus {
  UPLOADED = 'uploaded',
  CALIBRATING = 'calibrating',
  ANALYZING = 'analyzing',
  COMPLETED = 'completed',
}

export enum AnalysisStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

// Core interfaces
export interface Video {
  id: string;
  filename: string;
  file_path: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  status: VideoStatus;
  created_at: string;
  updated_at: string;
}

export interface RoutePoint {
  x: number;
  y: number;
  timestamp: number;
  speed: number;
}

export interface SprintSegment {
  start_time: number;
  end_time: number;
  max_speed: number;
  distance: number;
}

export interface PlayerMetrics {
  player_id: string;
  total_distance_km: number;
  max_speed_kmh: number;
  avg_speed_kmh: number;
  sprint_count: number;
  sprints: SprintSegment[];
  route: RoutePoint[];
}

export interface TrackingResult {
  session_id: string;
  video_id: string;
  mode: TrackingMode;
  status: AnalysisStatus;
  players: PlayerMetrics[];
  duration: number;
  processed_frames: number;
  total_frames: number;
}

export interface TrackingSession {
  id: string;
  video_id: string;
  mode: TrackingMode;
  status: AnalysisStatus;
  target_player_ids: string[];
  created_at: string;
}

export interface CalibrationPoint {
  pixel_x: number;
  pixel_y: number;
  field_x: number;
  field_y: number;
}

export interface FieldCalibration {
  id: string;
  video_id: string;
  points: CalibrationPoint[];
  homography_matrix: number[][] | null;
  is_auto: boolean;
  confidence: number;
}

export interface PlayerSelection {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
}

export interface AnalysisRequest {
  video_id: string;
  mode: TrackingMode;
  calibration?: FieldCalibration;
  target_player_ids?: string[];
}

export interface WebSocketMessage {
  // Top-level fields from backend broadcast_progress
  session_id?: string;
  progress?: number;
  status?: string;
  timestamp?: number;
  message?: string;
  error?: string;
  type: 'progress' | 'status' | 'result' | 'error' | 'connected' | 'pong' | 'ack' | 'subscribed';
  data?: {
    progress?: number;
    status?: AnalysisStatus;
    message?: string;
    result?: TrackingResult;
    stage?: string;
    current_frame?: number;
    total_frames?: number;
    fps?: number;
    elapsed_time?: number;
    eta?: number;
    results?: Record<string, unknown>;
  };
}

export interface AnalyticsData {
  session_id: string;
  players: PlayerMetrics[];
  summary: {
    total_players_tracked: number;
    total_duration: number;
    avg_team_speed: number;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface OverlayBox {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label?: string;
  color?: string;
}

export interface OverlayPath {
  id: string;
  points: { x: number; y: number }[];
  color: string;
}

export interface OverlayData {
  boxes: OverlayBox[];
  paths: OverlayPath[];
}
