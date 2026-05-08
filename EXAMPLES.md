# Usage Examples

Complete examples showing how to use the Point Cloud Generation pipeline.

---

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Processing Single Part](#processing-single-part)
3. [Batch Processing](#batch-processing)
4. [Advanced Configuration](#advanced-configuration)
5. [Evaluation & Comparison](#evaluation--comparison)
6. [Visualization](#visualization)

---

## Basic Usage

### Example 1: Run Complete Pipeline

```python
from pathlib import Path
from src.core.data_loader import DataLoader
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor
from src.utils.helpers import save_metrics_json
import open3d as o3d

# Initialize components
data_loader = DataLoader('.')
vp = VideoProcessor(sampling_rate=5)
reconstructor = PointCloudReconstructor()

# Load a specific part
part_code = 'G-LS-I-LO-33'
part_data = data_loader.get_part_data(part_code, complexity_level='1_single')

# Get first orientation
orientation = list(part_data['orientations'].keys())[0]
video_path = part_data['orientations'][orientation]['video']

# Extract frames
print(f"Processing: {part_code}/{orientation}")
frames, metadata = vp.extract_frames(video_path, max_frames=50)
print(f"  Extracted {len(frames)} frames")

# Detect features
keypoint_data = vp.detect_keypoints(frames)
print(f"  Detected SIFT features")

# Match features
matches = vp.match_features(keypoint_data)
match_count = sum(len(m) for m in matches)
print(f"  Found {match_count} feature matches")

# Estimate camera intrinsics
K = vp.estimate_camera_intrinsics(metadata['width'], metadata['height'])
reconstructor.K = K

# Reconstruct 3D points
points_3d, colors = reconstructor.sift_based_reconstruction(
    frames, keypoint_data, matches
)
print(f"  Generated {len(points_3d)} 3D points")

# Create point cloud
if len(points_3d) > 0:
    pcd = reconstructor.create_point_cloud(points_3d, colors)
    
    # Filter outliers
    pcd_filtered = reconstructor.filter_outliers(
        pcd, nb_neighbors=20, std_ratio=2.0
    )
    print(f"  After filtering: {len(pcd_filtered.points)} points")
    
    # Downsample
    pcd_final = reconstructor.downsample(pcd_filtered, voxel_size=0.01)
    print(f"  After downsampling: {len(pcd_final.points)} points")
    
    # Save
    output_path = Path('outputs/point_clouds') / f"{part_code}_{orientation}.ply"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reconstructor.save_point_cloud(pcd_final, str(output_path))
    
    # Save metrics
    metrics = {
        'points_generated': len(points_3d),
        'points_after_filtering': len(pcd_filtered.points),
        'points_final': len(pcd_final.points),
        'feature_matches': match_count,
        'frames_processed': len(frames)
    }
    metrics_path = Path('outputs/evaluations') / f"{part_code}_{orientation}_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    save_metrics_json(metrics, str(metrics_path))
    
    print(f"✓ Saved to {output_path.name}")
else:
    print("  ⚠ No points generated")
```

---

## Processing Single Part

### Example 2: Process Specific Complexity Level

```python
from src.core.data_loader import DataLoader
from src.pipeline import process_single_part

# Process only "Single Parts" complexity level
part_code = 'G-MS-I-LO-1'

results = process_single_part(
    part_code=part_code,
    complexity_level='1_single',
    output_dir='outputs',
    max_frames=50,
    verbose=True
)

print(f"\nResults for {part_code}:")
print(f"  Points generated: {results['points_generated']:,}")
print(f"  Feature matches: {results['matches_found']:,}")
print(f"  Status: {results['status']}")
```

### Example 3: Try Different Sampling Rates

```python
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor
from src.core.data_loader import DataLoader

# Compare different sampling rates
sampling_rates = [2, 5, 10]
results = {}

data_loader = DataLoader('.')
part_data = data_loader.get_part_data('G-LS-I-LO-33', '1_single')
video_path = list(part_data['orientations'].values())[0]['video']

for sr in sampling_rates:
    print(f"\nTesting sampling_rate={sr}:")
    
    vp = VideoProcessor(sampling_rate=sr)
    frames, metadata = vp.extract_frames(video_path, max_frames=50)
    print(f"  Frames extracted: {len(frames)}")
    
    keypoint_data = vp.detect_keypoints(frames)
    matches = vp.match_features(keypoint_data)
    match_count = sum(len(m) for m in matches)
    print(f"  Feature matches: {match_count}")
    
    K = vp.estimate_camera_intrinsics(metadata['width'], metadata['height'])
    reconstructor = PointCloudReconstructor(K=K)
    
    points_3d, colors = reconstructor.sift_based_reconstruction(
        frames, keypoint_data, matches
    )
    print(f"  3D points: {len(points_3d)}")
    
    results[sr] = {
        'frames': len(frames),
        'matches': match_count,
        'points': len(points_3d)
    }

# Compare results
print("\nComparison:")
print(f"{'Sampling Rate':15} {'Frames':10} {'Matches':10} {'Points':10}")
print("-" * 45)
for sr, res in results.items():
    print(f"{sr:15} {res['frames']:10} {res['matches']:10} {res['points']:10}")
```

---

## Batch Processing

### Example 4: Batch Process Multiple Parts

```python
from src.pipeline import process_all_parts
import json

# Process all parts, all complexity levels
results = process_all_parts(
    output_dir='outputs',
    max_configs=None,  # Process all
    max_frames=50,
    verbose=True
)

# Print summary
print(f"\n{'='*60}")
print(f"Batch Processing Complete!")
print(f"{'='*60}")
print(f"Total configurations processed: {len(results)}")
print(f"Successful: {sum(1 for r in results if r['status'] == 'success')}")
print(f"Failed: {sum(1 for r in results if r['status'] != 'success')}")

total_points = sum(r['points_generated'] for r in results)
print(f"Total points generated: {total_points:,}")

total_matches = sum(r['matches_found'] for r in results)
print(f"Total feature matches: {total_matches:,}")

# Save summary
summary = {
    'total_configs': len(results),
    'successful': sum(1 for r in results if r['status'] == 'success'),
    'total_points': total_points,
    'total_matches': total_matches,
    'results': results
}

with open('outputs/batch_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\nSummary saved to outputs/batch_summary.json")
```

### Example 5: Process Specific Complexity Levels

```python
from src.core.data_loader import DataLoader
from src.pipeline import process_single_part

data_loader = DataLoader('.')
all_parts = data_loader.list_parts()

# Process only Level 1 (Single) for all parts
print("Processing Level 1 (Single) for all parts...\n")

for i, part_code in enumerate(all_parts[:5]):  # First 5 parts
    print(f"{i+1}. Processing {part_code}...")
    
    try:
        result = process_single_part(
            part_code=part_code,
            complexity_level='1_single',
            output_dir='outputs',
            max_frames=50,
            verbose=False
        )
        print(f"   ✓ {result['points_generated']:,} points")
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
```

---

## Advanced Configuration

### Example 6: Custom Parameter Tuning

```python
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor
from src.core.data_loader import DataLoader

# Initialize with custom parameters
vp = VideoProcessor(
    sampling_rate=3,        # More frames
    sift_threshold=0.03,    # SIFT sensitivity
    ratio_test=0.7          # Feature matching threshold
)

# Load part
data_loader = DataLoader('.')
part_data = data_loader.get_part_data('G-LS-I-LO-33', '1_single')
video_path = list(part_data['orientations'].values())[0]['video']

# Extract frames
frames, metadata = vp.extract_frames(video_path, max_frames=100)  # More frames
print(f"Extracted {len(frames)} frames")

# Detect and match
keypoint_data = vp.detect_keypoints(frames)
matches = vp.match_features(keypoint_data)

# Reconstruct
K = vp.estimate_camera_intrinsics(metadata['width'], metadata['height'])
reconstructor = PointCloudReconstructor(
    K=K,
    depth_min=0.1,          # Minimum depth 10cm
    depth_max=1000.0        # Maximum depth 1km
)

points_3d, colors = reconstructor.sift_based_reconstruction(
    frames, keypoint_data, matches
)

# Process with custom parameters
pcd = reconstructor.create_point_cloud(points_3d, colors)
pcd_filtered = reconstructor.filter_outliers(
    pcd,
    nb_neighbors=10,        # Fewer neighbors for outlier removal
    std_ratio=10.0          # More tolerant
)

pcd_final = reconstructor.downsample(
    pcd_filtered,
    voxel_size=0.005  # Smaller voxels = more detail
)

print(f"Final point count: {len(pcd_final.points):,}")
```

---

## Evaluation & Comparison

### Example 7: Compare with Ground Truth

```python
import open3d as o3d
import numpy as np
from src.core.reconstructor import PointCloudReconstructor
from src.core.evaluator import PointCloudEvaluator

# Load both point clouds
pred_path = 'outputs/point_clouds/G-LS-I-LO-33_1_single_orientation_a.ply'
gt_path = 'G-LS-I-LO-33/1_single/orientation_a/ground_truth.ply'

pred_pcd = o3d.io.read_point_cloud(pred_path)
gt_pcd = o3d.io.read_point_cloud(gt_path)

print(f"Predicted points: {len(pred_pcd.points):,}")
print(f"Ground truth points: {len(gt_pcd.points):,}")

# Downsample for comparison
reconstructor = PointCloudReconstructor()
pred_downsampled = reconstructor.downsample(pred_pcd, voxel_size=0.01)
gt_downsampled = reconstructor.downsample(gt_pcd, voxel_size=0.01)

print(f"\nAfter downsampling:")
print(f"Predicted: {len(pred_downsampled.points):,}")
print(f"Ground truth: {len(gt_downsampled.points):,}")

# Register and compute metrics
print("\nRegistering point clouds...")
reg_result = reconstructor.register_to_ground_truth(
    pred_downsampled, gt_downsampled,
    max_correspondence_distance=1.0
)

print(f"Registration fitness: {reg_result.fitness:.6f}")
print(f"Registration RMSE: {reg_result.inlier_rmse:.6f}")

# Align
pred_aligned = pred_downsampled.transform(reg_result.transformation)

# Compute detailed metrics
metrics = PointCloudEvaluator.point_cloud_metrics(
    pred_aligned, gt_downsampled
)

PointCloudEvaluator.print_metrics(metrics)
```

### Example 8: Evaluate Batch Results

```python
import json
from pathlib import Path
import numpy as np

# Load all metrics
metrics_dir = Path('outputs/evaluations')
all_metrics = []

for metrics_file in sorted(metrics_dir.glob('*_metrics.json')):
    with open(metrics_file) as f:
        metrics = json.load(f)
        metrics['file'] = metrics_file.name
        all_metrics.append(metrics)

print(f"Loaded metrics for {len(all_metrics)} configurations\n")

# Analyze by complexity level
levels = {}
for m in all_metrics:
    level = '1_single' if '1_single' in m['file'] else \
            '2_multiple' if '2_multiple' in m['file'] else \
            '3_stacked'
    
    if level not in levels:
        levels[level] = []
    levels[level].append(m['points_generated'])

# Print summary
print("Summary by Complexity Level:")
print(f"{'Level':<15} {'Count':<10} {'Avg Points':<15} {'Min':<10} {'Max':<10}")
print("-" * 60)

for level in sorted(levels.keys()):
    points = levels[level]
    print(f"{level:<15} {len(points):<10} {np.mean(points):>12,.0f} "
          f"{np.min(points):>9,.0f} {np.max(points):>9,.0f}")
```

---

## Visualization

### Example 9: Create Result Charts

```python
import matplotlib.pyplot as plt
import numpy as np
import json
from pathlib import Path

# Load metrics
metrics_dir = Path('outputs/evaluations')
all_points = []
all_matches = []

for metrics_file in metrics_dir.glob('*_metrics.json'):
    with open(metrics_file) as f:
        m = json.load(f)
        all_points.append(m['points_generated'])
        all_matches.append(m['matches_found'])

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Histogram of points
axes[0, 0].hist(all_points, bins=20, edgecolor='black', color='skyblue')
axes[0, 0].set_xlabel('Points Generated')
axes[0, 0].set_ylabel('Frequency')
axes[0, 0].set_title('Distribution of Point Counts')
axes[0, 0].grid(alpha=0.3)

# Histogram of matches
axes[0, 1].hist(all_matches, bins=20, edgecolor='black', color='lightcoral')
axes[0, 1].set_xlabel('Feature Matches')
axes[0, 1].set_ylabel('Frequency')
axes[0, 1].set_title('Distribution of Feature Matches')
axes[0, 1].grid(alpha=0.3)

# Box plot
axes[1, 0].boxplot(all_points)
axes[1, 0].set_ylabel('Points Generated')
axes[1, 0].set_title('Point Count Distribution')
axes[1, 0].grid(alpha=0.3, axis='y')

# Scatter plot
axes[1, 1].scatter(all_matches, all_points, alpha=0.6, s=100)
axes[1, 1].set_xlabel('Feature Matches')
axes[1, 1].set_ylabel('Points Generated')
axes[1, 1].set_title('Matches vs Points Correlation')
axes[1, 1].grid(alpha=0.3)

plt.tight_layout()
plt.savefig('outputs/results_analysis.png', dpi=300)
print("✓ Saved visualization to outputs/results_analysis.png")
plt.show()
```

### Example 10: Interactive 3D Visualization

```python
import open3d as o3d

# Load and visualize point cloud
pcd_path = 'outputs/point_clouds/G-TS-P-HI-3_2_multiple_default.ply'
pcd = o3d.io.read_point_cloud(pcd_path)

# Color by height (Z coordinate)
z_values = np.asarray(pcd.points)[:, 2]
z_normalized = (z_values - z_values.min()) / (z_values.max() - z_values.min())

# Create colormap
colors = plt.cm.viridis(z_normalized)[:, :3]
pcd.colors = o3d.utility.Vector3dVector(colors)

# Visualize
o3d.visualization.draw_geometries([pcd])
```

---

## Running Examples

### Execute Examples in Notebook

```bash
jupyter notebook
# Open cells and run examples
```

### Execute Examples as Scripts

```bash
# Create a script
cat > example_usage.py << 'EOF'
# [Paste Example 1 code here]
EOF

# Run it
python example_usage.py
```

### Execute in Interactive Python

```bash
python
>>> [Paste Example code here]
```

---

## More Examples

For additional examples, see:
- `notebooks/01_Complete_Pipeline.ipynb` - Interactive notebook
- `minimal_demo.py` - Simple working example
- `batch_process_all.py` - Production batch processing

---

## Need Help?

- Check [README.md](README.md) for overview
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- Review source code comments in `src/core/`
- Open an issue on GitHub
