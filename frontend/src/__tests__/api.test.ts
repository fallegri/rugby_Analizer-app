import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AIProvider, TrackingMode, VideoStatus } from '../types';

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPut = vi.fn();
const mockDelete = vi.fn();

vi.mock('axios', () => {
  return {
    default: {
      create: () => ({
        get: mockGet,
        post: mockPost,
        put: mockPut,
        delete: mockDelete,
      }),
    },
  };
});

describe('API Service', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  it('should upload a video', async () => {
    const { uploadVideo } = await import('../services/api');
    const mockVideo = {
      id: 'v1',
      filename: 'test.mp4',
      file_path: '/uploads/test.mp4',
      duration: 60,
      width: 1920,
      height: 1080,
      fps: 30,
      status: VideoStatus.UPLOADED,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    };
    mockPost.mockResolvedValueOnce({ data: mockVideo });

    const file = new File(['video content'], 'test.mp4', { type: 'video/mp4' });
    const result = await uploadVideo(file);

    expect(mockPost).toHaveBeenCalledWith(
      '/video/upload',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } })
    );
    expect(result).toEqual(mockVideo);
  });

  it('should get video by id', async () => {
    const { getVideo } = await import('../services/api');
    const mockVideo = { id: 'v1', filename: 'test.mp4', status: VideoStatus.UPLOADED };
    mockGet.mockResolvedValueOnce({ data: mockVideo });

    const result = await getVideo('v1');
    expect(mockGet).toHaveBeenCalledWith('/video/v1');
    expect(result).toEqual(mockVideo);
  });

  it('should start processing', async () => {
    const { startProcessing } = await import('../services/api');
    mockPost.mockResolvedValueOnce({ data: { session_id: 'sess-1' } });

    const result = await startProcessing('v1', { mode: TrackingMode.SINGLE_PLAYER });
    expect(mockPost).toHaveBeenCalledWith('/video/v1/process', { mode: TrackingMode.SINGLE_PLAYER });
    expect(result).toEqual({ session_id: 'sess-1' });
  });

  it('should get results', async () => {
    const { getResults } = await import('../services/api');
    const mockResults = { session_id: 'sess-1', players: [] };
    mockGet.mockResolvedValueOnce({ data: mockResults });

    const result = await getResults('v1');
    expect(mockGet).toHaveBeenCalledWith('/video/v1/results');
    expect(result).toEqual(mockResults);
  });

  it('should list providers', async () => {
    const { listProviders } = await import('../services/api');
    mockGet.mockResolvedValueOnce({ data: { providers: [AIProvider.NVIDIA, AIProvider.OPENAI] } });

    const result = await listProviders();
    expect(mockGet).toHaveBeenCalledWith('/ai/providers');
    expect(result.providers).toContain(AIProvider.NVIDIA);
  });

  it('should switch provider', async () => {
    const { switchProvider } = await import('../services/api');
    mockPut.mockResolvedValueOnce({ data: {} });

    await switchProvider(AIProvider.CLAUDE);
    expect(mockPut).toHaveBeenCalledWith('/ai/provider', { provider: AIProvider.CLAUDE });
  });

  it('should update AI config', async () => {
    const { updateAIConfig } = await import('../services/api');
    mockPut.mockResolvedValueOnce({ data: {} });

    await updateAIConfig({ NVIDIA: 'key123' });
    expect(mockPut).toHaveBeenCalledWith('/ai/config', { keys: { NVIDIA: 'key123' } });
  });
});
