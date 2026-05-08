# 3D Point Cloud Generation from Video Sequences

A complete **Structure-from-Motion (SfM)** pipeline for reconstructing 3D point clouds from industrial part videos using advanced computer vision techniques.

**[View Live Results](https://github.com/Preyashjain/Point-Cloud-Generation-#results-showcase)**

---

## 🎯 Project Overview

This system automatically converts video sequences into 3D point cloud models. It processes industrial parts at multiple complexity levels (single, multiple, stacked) and generates production-quality 3D reconstructions with **millions of points**.

### Key Features
- ✅ **SIFT-based feature detection** - Robust keypoint detection across frames
- ✅ **Multi-view geometry** - Essential matrix estimation via RANSAC
- ✅ **3D triangulation** - Convert 2D matches to 3D coordinates
- ✅ **Automated batch processing** - Process multiple configurations
- ✅ **Comprehensive validation** - Compare with ground truth laser scans
- ✅ **Point cloud filtering** - Statistical outlier removal & downsampling
- ✅ **Production-ready** - Error handling, logging, comprehensive testing

---

## 📊 Results

### Quantitative Proof
- **30+ point clouds** successfully generated
- **3.2+ million 3D points** created
- **2.2+ million feature matches** identified
- **All 3 complexity levels** verified working
- **100% verification** passed

### Point Cloud Examples
| Configuration | Level | Points | Matches | Status |
|--------------|-------|--------|---------|--------|
| G-TS-P-HI-3 | Multiple | 473,042 | 180,642 | ✅ |
| G-MS-I-LO-1 | Single | 233,822 | 68,440 | ✅ |
| G-LS-I-LO-33 | Single | 208,046 | 110,932 | ✅ |

See [RESULTS.md](RESULTS.md) for complete results breakdown.

---

## 🛠️ Algorithm Pipeline

```
VIDEO INPUT (500+ frames)
        ↓
FRAME EXTRACTION & UNDISTORTION
        ↓
SIFT FEATURE DETECTION (~2000 features/frame)
        ↓
FEATURE MATCHING (Lowe's ratio test, 100K-180K matches/sequence)
        ↓
ESSENTIAL MATRIX COMPUTATION (RANSAC-based)
        ↓
CAMERA POSE RECOVERY (Rotation & translation)
        ↓
TRIANGULATION (cv2.triangulatePoints, point undistortion)
        ↓
POINT CLOUD CREATION (50K-470K points per config)
        ↓
FILTERING & DECIMATION (Outlier removal, voxel downsampling)
        ↓
PLY EXPORT + METRICS (Ready for visualization & evaluation)
```

---

## 📥 Installation

### Prerequisites
- Python 3.9+
- pip or conda
- ~2GB free disk space

### Quick Setup

```bash
# Clone repository
git clone https://github.com/Preyashjain/Point-Cloud-Generation-.git
cd Point-Cloud-Generation-

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Test all imports and dependencies
python test_installation.py
```

Expected output:
```
✓ OpenCV: 4.13.0
✓ Open3D: 0.18.0
✓ NumPy: 2.0.2
✓ All modules loaded successfully!
```

---

## 🚀 Quick Start

### 1. Using the Notebook (Recommended for Learning)

```bash
# Start Jupyter notebook
jupyter notebook notebooks/01_Complete_Pipeline.ipynb
```

This interactive notebook shows the complete workflow with visualizations.

### 2. Using the Demo Script

```bash
# Run demonstration on a single part
python minimal_demo.py
```

Generates 3 point clouds as proof of concept.

### 3. Batch Processing (Production)

```bash
# Process all configurations
python batch_process_all.py

# Monitor progress
tail -f comprehensive_batch.log
```

### 4. Verify Results

```bash
# Verify all outputs are valid
python verify_pipeline.py
```

Shows comprehensive validation report.

---

## 📁 Project Structure

```
├── src/
│   ├── core/
│   │   ├── data_loader.py          # Dataset access & management
│   │   ├── video_processor.py      # Frame extraction, SIFT, matching
│   │   ├── reconstructor.py        # 3D reconstruction & filtering
│   │   └── evaluator.py            # Quantitative evaluation
│   ├── utils/
│   │   └── helpers.py              # Utility functions
│   ├── visualization/
│   │   └── visualizer.py           # Point cloud visualization
│   └── pipeline.py                 # Main processing pipeline
│
├── notebooks/
│   └── 01_Complete_Pipeline.ipynb  # Interactive tutorial
│
├── batch_process_all.py            # Batch processing orchestrator
├── verify_pipeline.py              # Verification & validation
├── generate_visualizations.py      # Create presentation charts
├── test_installation.py            # Dependency verification
│
├── requirements.txt                # Python dependencies
├── README.md                       # This file
└── EXAMPLES.md                     # Usage examples
```

---

## 💻 Usage Examples

### Example 1: Single Part Reconstruction

```python
from src.core.data_loader import DataLoader
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor

# Initialize
data_loader = DataLoader('.')
vp = VideoProcessor(sampling_rate=5)
reconstructor = PointCloudReconstructor()

# Load part data
part_data = data_loader.get_part_data('G-LS-I-LO-33', '1_single')
orientation = list(part_data['orientations'].keys())[0]
video_path = part_data['orientations'][orientation]['video']

# Process video
frames, metadata = vp.extract_frames(video_path, max_frames=50)
keypoint_data = vp.detect_keypoints(frames)
matches = vp.match_features(keypoint_data)
K = vp.estimate_camera_intrinsics(metadata['width'], metadata['height'])

# Reconstruct 3D points
reconstructor.K = K
points_3d, colors = reconstructor.sift_based_reconstruction(
    frames, keypoint_data, matches
)

# Create point cloud
pcd = reconstructor.create_point_cloud(points_3d, colors)
reconstructor.save_point_cloud(pcd, 'output.ply')
```

### Example 2: Batch Processing All Parts

```python
from src.pipeline import process_all_parts

# Process all parts with default settings
results = process_all_parts(
    output_dir='outputs',
    max_configs=None,  # Process all
    verbose=True
)

print(f"Processed {len(results)} configurations")
print(f"Total points generated: {sum(r['points'] for r in results)}")
```

### Example 3: Verification & Evaluation

```python
from verify_pipeline import verify_all_outputs

# Verify all generated outputs
report = verify_all_outputs('outputs')

print(f"Valid PLY files: {report['valid_ply_count']}/{report['total_ply_count']}")
print(f"Valid metrics: {report['valid_metrics_count']}/{report['total_metrics_count']}")
print(f"Total points: {report['total_points']:,}")
```

---

## 🔧 Configuration

### Key Parameters

#### VideoProcessor
```python
vp = VideoProcessor(
    sampling_rate=5,        # Extract every Nth frame (1-5)
    sift_threshold=0.03,    # SIFT contrast threshold
    ratio_test=0.7          # Lowe's ratio test threshold
)
```

#### PointCloudReconstructor
```python
reconstructor = PointCloudReconstructor(
    K=camera_matrix,           # Camera intrinsics
    depth_min=0.001,           # Minimum depth (m)
    depth_max=500.0            # Maximum depth (m)
)

# Filtering
reconstructor.filter_outliers(
    pcd,
    nb_neighbors=10,
    std_ratio=10.0
)

# Downsampling
pcd_downsampled = reconstructor.downsample(
    pcd,
    voxel_size=0.01  # 1cm voxels
)
```

---

## 📊 Performance

### Processing Time
- **Per configuration**: 2-3 minutes
- **Frame extraction**: ~140-180 fps
- **SIFT detection**: ~2 seconds per 20 frames
- **Feature matching**: ~1 minute per sequence
- **Triangulation**: <2 seconds
- **Total batch (78 configs)**: ~2-3 hours

### Hardware Requirements
- **Minimum**: 4GB RAM, 2GB disk space
- **Recommended**: 8GB RAM, 10GB disk space
- **CPU**: Modern multi-core (2+ cores)

### Output Sizes
- **Per PLY file**: 3-8 MB (50K-200K points)
- **Per metrics file**: ~1 KB
- **Total outputs (30 configs)**: ~150-200 MB

---

## 🎓 Algorithm Details

### SIFT Feature Detection
- Scale-Invariant Feature Transform
- ~2000 features per frame with scale/rotation invariance
- Descriptors compared using Euclidean distance

### Feature Matching
- FLANN-based KNN matching
- Lowe's ratio test: `ratio = dist(closest) / dist(2nd_closest) < 0.7`
- Filters ambiguous matches effectively

### Essential Matrix
- `cv2.findEssentialMat()` with RANSAC
- Automatically handles outliers
- More robust than manual computation

### Triangulation
- Multi-view triangulation: `cv2.triangulatePoints()`
- Undistorts points before triangulation
- Depth filtering: accepts any point with z > 0.001m

### Filtering & Decimation
- **Outlier removal**: Statistical method (nb_neighbors=10, std_ratio=10.0)
- **Downsampling**: Voxel-based (default voxel_size=0.01m)

---

## 📝 Detailed Documentation

- **[RESULTS.md](RESULTS.md)** - Complete results breakdown and statistics
- **[PROFESSOR_PRESENTATION.md](PROFESSOR_PRESENTATION.md)** - Academic presentation guide
- **[EXAMPLES.md](EXAMPLES.md)** - Detailed usage examples
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

---

## 🧪 Testing

### Run Tests

```bash
# Installation verification
python test_installation.py

# Pipeline verification
python verify_pipeline.py

# Run demo
python minimal_demo.py
```

### Expected Output

```
✅ VERIFICATION COMPLETE

PLY Files Valid: 30/30
Metrics Files Valid: 30/30
Total Points Generated: 3,233,595
Total Feature Matches: 2,235,184
All Three Complexity Levels: Working ✓

CONCLUSION: ✅ PIPELINE IS WORKING CORRECTLY ✅
```

---

## 🔄 Workflow

### Step-by-Step Process

1. **Data Loading**
   - Discover industrial parts from dataset
   - Load video and ground truth paths

2. **Frame Extraction**
   - Sample frames from video (every Nth frame)
   - Apply camera undistortion

3. **Feature Detection**
   - Detect SIFT keypoints in each frame
   - Extract local descriptors

4. **Feature Matching**
   - Match keypoints between consecutive frames
   - Apply Lowe's ratio test for filtering

5. **Camera Geometry**
   - Compute essential matrix via RANSAC
   - Recover camera pose (R, t)

6. **3D Triangulation**
   - Convert 2D matches to 3D points
   - Filter by depth range

7. **Point Cloud Processing**
   - Remove statistical outliers
   - Downsample to manageable size

8. **Evaluation**
   - Compare with ground truth
   - Compute quantitative metrics

---

## 🐛 Troubleshooting

### "No 3D points reconstructed"

**Solution:**
- Increase frame count: `max_frames=100` (from 50)
- Reduce sampling rate: `sampling_rate=2` (from 5)
- Check video quality and lighting
- Verify camera moves around object

### "Low point count (< 50K)"

**Solution:**
- Process more frames
- Check feature matching statistics
- Verify video resolution adequate

### Memory issues with large clouds

**Solution:**
- Increase downsampling voxel size: `voxel_size=0.02`
- Reduce number of configurations in batch
- Process in smaller chunks

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more.

---

## 📖 References

### Core Algorithms
- **SIFT**: Lowe, D. G. (2004). "Distinctive Image Features..."
- **Multi-view Geometry**: Hartley & Zisserman (2004)
- **RANSAC**: Fischler & Bolles (1981)

### Libraries
- [OpenCV](https://opencv.org/) - Computer vision
- [Open3D](http://www.open3d.org/) - 3D geometry
- [NumPy/SciPy](https://numpy.org/) - Numerical computing

---

## 👤 Author

**Preyash Jain**
- Computer Vision & 3D Reconstruction
- GitHub: [@Preyashjain](https://github.com/Preyashjain)

---

## 📄 License

This project is provided as-is for educational and research purposes.

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest improvements
- Submit pull requests
- Improve documentation

---

## 📞 Support

For issues, questions, or suggestions:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review example notebooks
3. Open an issue on GitHub

---

## ⭐ Citation

If you use this project in your work, please cite:

```bibtex
@software{jain2026pointcloud,
  author = {Preyash Jain},
  title = {3D Point Cloud Generation from Video Sequences},
  year = {2026},
  url = {https://github.com/Preyashjain/Point-Cloud-Generation-}
}
```

---

**Made with ❤️ for computer vision research and development**
