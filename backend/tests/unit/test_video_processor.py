"""Unit tests for the video processor pipeline.

Mocks VideoCapture and YOLO model to test pipeline orchestration.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cv.analytics import AnalyticsEngine
from src.cv.detector import Detection, YOLODetector
from src.cv.tracker import MultiObjectTracker
from src.cv.tracking_modes import SinglePlayerStrategy
from src.cv.transform import HomographyTransform
from src.cv.video_processor import AnalysisResult, FrameResult, VideoProcessor


@pytest.fixture
def mock_detector():
    """Create a mocked YOLODetector."""
    detector = MagicMock(spec=YOLODetector)
    detector.detect_frame.return_value = [
        Detection(
            bbox=(100.0, 100.0, 200.0, 200.0),
            class_id=0,
            confidence=0.9,
            class_name="person",
        )
    ]
    return detector


@pytest.fixture
def tracker():
    """Create a real MultiObjectTracker."""
    return MultiObjectTracker(iou_threshold=0.3, max_age=30)


@pytest.fixture
def simple_transform():
    """Create a simple identity-like transform (scale 0.1x)."""
    matrix = np.array([
        [0.1, 0.0, 0.0],
        [0.0, 0.1, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    return HomographyTransform(matrix, validate_bounds=True)


@pytest.fixture
def analytics_engine():
    """Create an AnalyticsEngine for testing."""
    return AnalyticsEngine(fps=30.0)


class TestVideoProcessor:
    """Tests for VideoProcessor class."""

    def test_instantiation(self, mock_detector, tracker):
        """Test processor can be instantiated."""
        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
        )
        assert processor.detector is mock_detector
        assert processor.tracker is tracker

    @patch("cv2.VideoCapture")
    def test_process_video_basic(
        self, mock_cap_cls, mock_detector, tracker, analytics_engine
    ):
        """Test basic video processing pipeline."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            5: 30.0,
            7: 3,
        }.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, fake_frame),
            (True, fake_frame),
            (True, fake_frame),
            (False, None),
        ]

        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
            analytics_engine=analytics_engine,
        )

        result = processor.process_video("test_video.mp4")

        assert isinstance(result, AnalysisResult)
        assert result.total_frames == 3
        assert result.fps == 30.0
        assert mock_detector.detect_frame.call_count == 3
        mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    def test_process_video_file_not_found(self, mock_cap_cls, mock_detector, tracker):
        """Test error when video file cannot be opened."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = False

        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
        )

        with pytest.raises(FileNotFoundError, match="Cannot open video"):
            processor.process_video("nonexistent.mp4")

    @patch("cv2.VideoCapture")
    def test_process_video_with_transform(
        self, mock_cap_cls, mock_detector, tracker, simple_transform, analytics_engine
    ):
        """Test processing with coordinate transformation."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 7: 2}.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, fake_frame),
            (True, fake_frame),
            (False, None),
        ]

        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
            transform=simple_transform,
            analytics_engine=analytics_engine,
        )

        result = processor.process_video("test.mp4", store_frame_results=True)

        assert result.total_frames == 2
        assert len(result.frame_results) == 2
        for fr in result.frame_results:
            for track_id, fx, fy in fr.field_positions:
                assert 0.0 <= fx <= 100.0
                assert 0.0 <= fy <= 70.0

    @patch("cv2.VideoCapture")
    def test_process_video_with_tracking_strategy(
        self, mock_cap_cls, mock_detector, tracker
    ):
        """Test processing with a tracking strategy filter."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 7: 2}.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, fake_frame),
            (True, fake_frame),
            (False, None),
        ]

        strategy = SinglePlayerStrategy()
        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
            tracking_strategy=strategy,
        )

        result = processor.process_video(
            "test.mp4", target_ids=[1], store_frame_results=True
        )

        assert result.total_frames == 2
        for fr in result.frame_results:
            assert fr.filtered is not None

    @patch("cv2.VideoCapture")
    def test_progress_callback(self, mock_cap_cls, mock_detector, tracker):
        """Test that progress callback is called for each frame."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 7: 5}.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, fake_frame),
            (True, fake_frame),
            (True, fake_frame),
            (False, None),
        ]

        callback = MagicMock()
        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
        )

        processor.process_video("test.mp4", progress_callback=callback)

        assert callback.call_count == 3
        callback.assert_any_call(1, 5)
        callback.assert_any_call(2, 5)
        callback.assert_any_call(3, 5)

    @patch("cv2.VideoCapture")
    def test_process_realtime_stream(self, mock_cap_cls, mock_detector, tracker):
        """Test real-time stream processing."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 7: 0}.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, fake_frame),
            (True, fake_frame),
            (False, None),
        ]

        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
        )

        result = processor.process_realtime_stream("rtsp://test:8554/stream")

        assert result.total_frames == 2
        assert result.fps == 30.0

    @patch("cv2.VideoCapture")
    def test_process_realtime_stream_max_frames(
        self, mock_cap_cls, mock_detector, tracker
    ):
        """Test stream processing stops at max_frames."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 7: 0}.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)

        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
        )

        result = processor.process_realtime_stream(
            "rtsp://test:8554/stream", max_frames=2
        )

        assert result.total_frames == 2

    @patch("cv2.VideoCapture")
    def test_process_realtime_stream_connection_error(
        self, mock_cap_cls, mock_detector, tracker
    ):
        """Test error when stream cannot be connected."""
        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = False

        processor = VideoProcessor(
            detector=mock_detector,
            tracker=tracker,
        )

        with pytest.raises(ConnectionError, match="Cannot connect to stream"):
            processor.process_realtime_stream("rtsp://invalid:8554/stream")

    def test_frame_result_dataclass(self):
        """Test FrameResult dataclass."""
        fr = FrameResult(frame_num=5)
        assert fr.frame_num == 5
        assert fr.detections == []
        assert fr.tracks == []
        assert fr.filtered is None
        assert fr.field_positions == []

    def test_analysis_result_dataclass(self):
        """Test AnalysisResult dataclass."""
        ar = AnalysisResult(total_frames=100, fps=30.0, duration_s=3.33)
        assert ar.total_frames == 100
        assert ar.fps == 30.0
        assert ar.duration_s == 3.33
        assert ar.analytics == {}

    @patch("cv2.VideoCapture")
    def test_analytics_computed_for_tracks(
        self, mock_cap_cls, tracker, analytics_engine
    ):
        """Test that analytics are computed for all tracked entities."""
        detector = MagicMock(spec=YOLODetector)
        frame_num_counter = [0]

        def mock_detect(frame):
            n = frame_num_counter[0]
            frame_num_counter[0] += 1
            x = 100.0 + n * 10
            return [
                Detection(
                    bbox=(x, 100.0, x + 100, 200.0),
                    class_id=0,
                    confidence=0.9,
                    class_name="person",
                )
            ]

        detector.detect_frame.side_effect = mock_detect

        mock_cap = MagicMock()
        mock_cap_cls.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {5: 30.0, 7: 5}.get(prop, 0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, fake_frame),
            (True, fake_frame),
            (True, fake_frame),
            (True, fake_frame),
            (True, fake_frame),
            (False, None),
        ]

        processor = VideoProcessor(
            detector=detector,
            tracker=tracker,
            analytics_engine=analytics_engine,
        )

        result = processor.process_video("test.mp4")

        assert result.total_frames == 5
        assert len(result.analytics) >= 1
