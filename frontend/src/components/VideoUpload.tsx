import React, { useState, useCallback, useRef } from 'react';
import { Upload, FileVideo, X, CheckCircle } from 'lucide-react';
import { uploadVideo } from '../services/api';
import { Video } from '../types';

interface VideoUploadProps {
  onUploadComplete?: (video: Video) => void;
}

const ACCEPTED_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv'];

export const VideoUpload: React.FC<VideoUploadProps> = ({ onUploadComplete }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadComplete, setUploadComplete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (f: File): boolean => {
    const extension = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setError(`Invalid file format. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      return false;
    }
    setError(null);
    return true;
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && validateFile(droppedFile)) {
      setFile(droppedFile);
      setUploadComplete(false);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && validateFile(selectedFile)) {
      setFile(selectedFile);
      setUploadComplete(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const video = await uploadVideo(file, (progress) => {
        setUploadProgress(progress);
      });
      setUploadComplete(true);
      onUploadComplete?.(video);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    setUploadProgress(0);
    setUploadComplete(false);
    setError(null);
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="w-full">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !file && inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
          transition-all duration-200
          ${isDragging ? 'border-rugby-gold bg-rugby-gold/10' : 'border-gray-600 hover:border-gray-400'}
          ${file ? 'cursor-default' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          onChange={handleFileSelect}
          className="hidden"
        />

        {!file ? (
          <div className="flex flex-col items-center gap-3">
            <Upload className="w-12 h-12 text-gray-400" />
            <p className="text-lg text-gray-300">
              Drag and drop your video here, or click to browse
            </p>
            <p className="text-sm text-gray-500">
              Supports: {ACCEPTED_EXTENSIONS.join(', ')}
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <FileVideo className="w-10 h-10 text-rugby-gold flex-shrink-0" />
            <div className="flex-1 text-left">
              <p className="text-white font-medium truncate">{file.name}</p>
              <p className="text-sm text-gray-400">{formatSize(file.size)}</p>
            </div>
            {!isUploading && !uploadComplete && (
              <button
                onClick={(e) => { e.stopPropagation(); handleRemoveFile(); }}
                className="p-1 hover:bg-gray-700 rounded"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            )}
            {uploadComplete && (
              <CheckCircle className="w-6 h-6 text-green-500 flex-shrink-0" />
            )}
          </div>
        )}

        {isUploading && (
          <div className="mt-4">
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-rugby-gold rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-gray-400 mt-1">{uploadProgress}% uploaded</p>
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      {file && !isUploading && !uploadComplete && (
        <button
          onClick={handleUpload}
          className="mt-4 w-full py-3 bg-rugby-gold text-white font-semibold rounded-lg hover:bg-rugby-gold/90 transition-colors"
        >
          Upload Video
        </button>
      )}
    </div>
  );
};

export default VideoUpload;
