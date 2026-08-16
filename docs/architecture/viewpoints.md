# Architecture Viewpoints

## Functional Viewpoint

### System Capabilities

1. **Video Ingestion**: Upload and stream rugby match videos
2. **Object Detection**: Detect players, ball, and field lines using YOLO
3. **Tracking**: Follow detected objects across frames using ByteTrack
4. **Field Calibration**: Map pixel coordinates to real-world field positions
5. **Analytics**: Calculate metrics (speed, distance, positioning)
6. **AI Analysis**: Generate natural language insights from tracking data
7. **Visualization**: Display results on interactive field canvas

## Information Viewpoint

### Data Entities

- **Video**: Source video file with metadata
- **Frame**: Individual video frame with timestamp
- **Detection**: Bounding box with class and confidence
- **Track**: Sequence of detections for a single entity
- **FieldCalibration**: Homography matrix for coordinate mapping
- **AnalyticsResult**: Computed metrics for a track
- **AIInsight**: Natural language analysis from AI provider

## Development Viewpoint

### Dependency Rules

- Core has NO external dependencies
- Ports define interfaces that adapters implement
- Adapters depend on ports (not on core directly)
- API layer depends on core and ports
- CV module is a specialized adapter

## Security Viewpoint

1. **API Authentication**: JWT-based token authentication
2. **Input Validation**: Pydantic models for all inputs
3. **File Upload**: Size limits, type validation
4. **WebSocket**: Origin validation, rate limiting
5. **CORS**: Strict origin policies
