import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';
import { OverlayData } from '../types';

interface VideoPlayerProps {
  src?: string;
  overlayData?: OverlayData;
  onFrameCapture?: (blob: Blob) => void;
  onVideoClick?: (x: number, y: number, videoWidth: number, videoHeight: number) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  src,
  overlayData,
  onFrameCapture,
  onVideoClick,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const animationRef = useRef<number>(0);

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video || !overlayData) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = video.videoWidth || canvas.clientWidth;
    canvas.height = video.videoHeight || canvas.clientHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    overlayData.boxes.forEach((box) => {
      ctx.strokeStyle = box.color || '#00ff00';
      ctx.lineWidth = 2;
      ctx.strokeRect(box.x, box.y, box.width, box.height);
      if (box.label) {
        ctx.fillStyle = box.color || '#00ff00';
        ctx.font = '12px sans-serif';
        ctx.fillText(box.label, box.x, box.y - 4);
      }
    });

    overlayData.paths.forEach((path) => {
      if (path.points.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = path.color;
      ctx.lineWidth = 2;
      ctx.moveTo(path.points[0].x, path.points[0].y);
      path.points.slice(1).forEach((pt) => ctx.lineTo(pt.x, pt.y));
      ctx.stroke();
    });
  }, [overlayData]);

  useEffect(() => {
    const renderLoop = () => {
      drawOverlay();
      animationRef.current = requestAnimationFrame(renderLoop);
    };
    if (overlayData) {
      animationRef.current = requestAnimationFrame(renderLoop);
    }
    return () => cancelAnimationFrame(animationRef.current);
  }, [overlayData, drawOverlay]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play();
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const stepFrame = (direction: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setIsPlaying(false);
    video.currentTime = Math.max(0, video.currentTime + direction * (1 / 30));
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Number(e.target.value);
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (video) setCurrentTime(video.currentTime);
  };

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (video) setDuration(video.duration);
  };

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onVideoClick || !canvasRef.current || !videoRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = videoRef.current.videoWidth / rect.width;
    const scaleY = videoRef.current.videoHeight / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    onVideoClick(x, y, videoRef.current.videoWidth, videoRef.current.videoHeight);
  };

  const captureFrame = () => {
    const video = videoRef.current;
    if (!video || !onFrameCapture) return;
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = video.videoWidth;
    tempCanvas.height = video.videoHeight;
    const ctx = tempCanvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    tempCanvas.toBlob((blob) => {
      if (blob) onFrameCapture(blob);
    }, 'image/jpeg');
  };

  const formatTime = (time: number): string => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="w-full bg-black rounded-lg overflow-hidden" ref={containerRef}>
      <div className="relative">
        <video
          ref={videoRef}
          src={src}
          className="w-full"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full cursor-crosshair"
          onClick={handleCanvasClick}
        />
      </div>

      <div className="bg-gray-900 p-3">
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.001}
          value={currentTime}
          onChange={handleSeek}
          className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer mb-2"
        />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={() => stepFrame(-1)} className="p-1 hover:bg-gray-700 rounded" title="Previous frame">
              <SkipBack className="w-4 h-4 text-gray-300" />
            </button>
            <button onClick={togglePlay} className="p-2 hover:bg-gray-700 rounded" title={isPlaying ? 'Pause' : 'Play'}>
              {isPlaying ? <Pause className="w-5 h-5 text-white" /> : <Play className="w-5 h-5 text-white" />}
            </button>
            <button onClick={() => stepFrame(1)} className="p-1 hover:bg-gray-700 rounded" title="Next frame">
              <SkipForward className="w-4 h-4 text-gray-300" />
            </button>
          </div>
          <span className="text-sm text-gray-400">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          {onFrameCapture && (
            <button onClick={captureFrame} className="px-3 py-1 text-xs bg-rugby-gold text-white rounded hover:bg-rugby-gold/80">
              Capture Frame
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default VideoPlayer;
