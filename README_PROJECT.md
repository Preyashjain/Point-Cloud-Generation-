# Point Cloud Generation from Video Data - INNO-GRIP Dataset

A complete computer vision pipeline for reconstructing 3D point clouds from stereo video sequences and quantitatively evaluating reconstruction accuracy against ground truth laser-scanned data.

## Project Overview

This project implements:
1. **Video Processing**: Frame extraction, feature detection (SIFT), and feature matching
2. **3D Reconstruction**: Structure-from-Motion (SfM) using triangulation
3. **Point Cloud Processing**: Filtering, downsampling, and alignment
4. **Quantitative Evaluation**: Chamfer distance, Hausdorff distance, completeness, accuracy, F-score

## Dataset Structure

```
dataset/
├── G-LS-I-LO-33/          # Part identifier: Surface-Size-Shape-Complexity-Number
│   ├── 1_single/          # Single object (simplest)
│   │   ├── orientation_a/
│   │   │   ├── video.MP4
│   │   │   └── ground_truth.ply
│   │   └── orientation_b/
│   ├── 2_multiple/        # Multiple objects (medium)
│   │   └── ...
│   └── 3_stacked/         # Stacked objects (complex)
│       └── ...
└── ... (26 parts total)
```

### Part Code Legend
- **Surface**: R (Rough), G (Glossy), M (Metallic), T (Transparent)
- **Size**: TS (Tiny), MS (Medium), LS (Large)
- **Shape**: O (Oblate), I (Isotropic), P (Prolate)
- **Complexity**: HI (High), LO (Low)
- **Number**: Unique identifier (1-36)

## Project Structure

```
src/
├── core/
│   ├── data_loader.py         # Dataset loading and management
│   ├── video_processor.py     # Video processing and feature detection
│   ├── reconstructor.py       # 3D reconstruction algorithms
│   └── evaluator.py           # Evaluation metrics
├── utils/
│   └── helpers.py             # Utility functions
├── visualization/
│   └── visualizer.py          # Visualization tools
└── pipeline.py                # Batch processing pipeline

notebooks/
├── 01_Complete_Pipeline.ipynb # Step-by-step tutorial

outputs/
├── point_clouds/              # Reconstructed PLY files
├── evaluations/               # Metrics JSON files
├── visualizations/            # Generated images
└── logs/                       # Processing logs
```

## Installation & Setup

### 1. Create Virtual Environment
```bash
cd /Users/preyashjain/Downloads/Use_Case_2_Point_Cloud_Generation_dataset
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

## Quick Start

### Option 1: Interactive Notebook (Recommended for beginners)

```bash
jupyter notebook notebooks/01_Complete_Pipeline.ipynb
```

This notebook guides you through:
- Data exploration and statistics
- Video frame extraction
- Feature detection and matching
- Point cloud reconstruction
- Ground truth comparison
- Metrics evaluation

### Option 2: Batch Processing via Command Line

Process a single part with single level complexity:
```bash
python src/pipeline.py \
  --dataset /path/to/dataset \
  --output ./outputs \
  --max-frames 50 \
  --complexity 1_single \
  --parts G-LS-I-LO-33
```

Process multiple parts:
```bash
python src/pipeline.py \
  --dataset /path/to/dataset \
  --output ./outputs \
  --max-frames 50 \
  --complexity 1_single \
  --parts G-LS-I-LO-33 R-LS-I-HI-36 M-MS-P-HI-35 \
  --limit 3
```

Process all parts (start with a few):
```bash
python src/pipeline.py \
  --dataset /path/to/dataset \
  --output ./outputs \
  --max-frames 50 \
  --complexity 1_single \
  --limit 5
```

### Option 3: Python API

```python
from src.core.data_loader import DataLoader
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor
from src.core.evaluator import PointCloudEvaluator
from src.visualization.visualizer import PointCloudVisualizer

# Load dataset
loader = DataLoader('/path/to/dataset')
part_data = loader.get_part_data('G-LS-I-LO-33', '1_single')

# Process video
vp = VideoProcessor(sampling_rate=5)
frames, metadata = vp.extract_frames(part_data['video_path'])
keypoints = vp.detect_keypoints(frames)
matches = vp.match_features(keypoints)

# Reconstruct 3D
K = vp.estimate_camera_intrinsics(metadata['width'], metadata['height'])
reconstructor = PointCloudReconstructor(K=K)
points_3d, colors = reconstructor.sift_based_reconstruction(frames, keypoints, matches)

# Process point cloud
pcd = reconstructor.create_point_cloud(points_3d, colors)
pcd = reconstructor.filter_outliers(pcd)
pcd = reconstructor.downsample(pcd)

# Evaluate
gt_pcd = loader.load_ground_truth_pointcloud(part_data['ground_truth_path'])
metrics = PointCloudEvaluator.point_cloud_metrics(pcd, gt_pcd)
PointCloudEvaluator.print_metrics(metrics)
```

## Key Modules

### DataLoader
Manages dataset discovery, part metadata parsing, and file access.

```python
loader = DataLoader(dataset_root)
part_data = loader.get_part_data('G-LS-I-LO-33', '1_single')
stats = loader.get_statistics()
parts_by_complexity = loader.list_parts(filter_complexity='LO')
```

### VideoProcessor
Extracts frames, detects SIFT features, and matches features between frames.

```python
vp = VideoProcessor(sampling_rate=5)
frames, metadata = vp.extract_frames(video_path, max_frames=100)
keypoint_data = vp.detect_keypoints(frames)
matches = vp.match_features(keypoint_data)
K = vp.estimate_camera_intrinsics(width, height)
```

### PointCloudReconstructor
Reconstructs 3D point clouds using triangulation and manages filtering/downsampling.

```python
reconstructor = PointCloudReconstructor(K=K)
points_3d, colors = reconstructor.sift_based_reconstruction(frames, keypoints, matches)
pcd = reconstructor.create_point_cloud(points_3d, colors)
pcd = reconstructor.filter_outliers(pcd)
pcd = reconstructor.downsample(pcd, voxel_size=0.01)
```

### PointCloudEvaluator
Computes comprehensive evaluation metrics.

```python
metrics = PointCloudEvaluator.point_cloud_metrics(pred_pcd, gt_pcd)

# Available metrics:
# - Chamfer distance (symmetric point-to-surface)
# - Hausdorff distance (maximum distance)
# - Completeness @ multiple thresholds
# - Accuracy @ multiple thresholds
# - F-score (harmonic mean)
```

## Evaluation Metrics

### Distance Metrics
- **Chamfer Distance**: Average of closest point distances (symmetric)
- **Hausdorff Distance**: Maximum distance between any point pairs

### Accuracy Metrics (with adjustable threshold)
- **Completeness**: % of GT points within threshold of predicted points
- **Accuracy**: % of predicted points within threshold of GT points
- **F-score**: Harmonic mean of completeness and accuracy

## Output Files

After processing, outputs are saved as:

### Point Clouds (PLY format)
- `outputs/point_clouds/{part_code}_{orientation}_reconstructed.ply`

### Metrics (JSON format)
- `outputs/evaluations/{part_code}_{orientation}_metrics.json`

Example metrics file:
```json
{
  "pred_point_count": 15234,
  "gt_point_count": 28456,
  "chamfer_distance": 0.0245,
  "hausdorff_distance": 0.1234,
  "completeness_@0.1": 87.34,
  "accuracy_@0.1": 92.15,
  "f_score_@0.1": 89.65
}
```

## Workflow Recommendations

### Phase 1: Exploration (Simple Parts)
Start with simple single parts at low complexity:
```python
parts = ['G-LS-I-LO-33', 'G-LS-P-LO-34', 'R-LS-I-HI-36']
for part in parts:
    # Process and evaluate
```

### Phase 2: Scaling (Multiple Complexity Levels)
Test same parts at different complexity levels:
```python
part = 'G-LS-I-LO-33'
for level in ['1_single', '2_multiple', '3_stacked']:
    # Process and compare difficulty
```

### Phase 3: Full Batch Processing
Process all 26 parts systematically:
```python
pipeline = BatchReconstructionPipeline(dataset_root, output_root)
results = pipeline.batch_process(complexity_level='1_single')
```

## Performance Optimization Tips

1. **Sampling Rate**: Increase `sampling_rate` in VideoProcessor to skip more frames
2. **Max Frames**: Use `max_frames` parameter to limit processing
3. **Voxel Downsampling**: Adjust `voxel_size` for speed vs. detail tradeoff
4. **Feature Threshold**: Adjust SIFT ratio test threshold in `match_features()`

## Troubleshooting

### Few or no 3D points reconstructed
- Increase number of frames processed
- Lower feature matching threshold
- Check video quality and lighting
- Verify camera motion captures object from different angles

### Poor alignment with ground truth
- Increase `max_correspondence_distance` in ICP registration
- Try processing more frame pairs
- Verify coordinate system alignment

### Out of memory
- Reduce `max_frames`
- Increase `voxel_size` for more aggressive downsampling
- Process fewer parts in batch mode

## Advanced Features

### Custom Reconstruction Methods
Extend `PointCloudReconstructor` class for:
- Bundle adjustment optimization
- Multi-view stereo (MVS) approaches
- Dense reconstruction techniques
- Deep learning-based methods

### Evaluation Extensions
Add custom metrics in `PointCloudEvaluator`:
- Surface normal comparison
- Mesh quality metrics
- Semantic segmentation evaluation

## References

- OpenCV: https://docs.opencv.org/
- Open3D: http://www.open3d.org/docs/
- SIFT Features: Lowe, D. G. (2004). "Distinctive Image Features from Scale-Invariant Keypoints"
- Structure from Motion: Hartley & Zisserman (2003). "Multiple View Geometry in Computer Vision"

## Dataset Citation

INNO-GRIP: Small industrial part dataset for photogrammetry and 3D reconstruction
- Resolution: ~37 GB
- Parts: 26 industrial objects
- Data: High-res video + laser-scanned ground truth

## License & Usage

This implementation is provided for research and educational purposes. Ensure compliance with dataset terms of use.

## Contact & Support

For issues, questions, or contributions, refer to the project documentation and code comments.

---

**Last Updated**: April 2026  
**Python Version**: 3.9+  
**Key Dependencies**: OpenCV, Open3D, NumPy, SciPy
