# 🚀 QUICK START GUIDE - RUN YOUR PIPELINE NOW

## Option 1: Run Pipeline in Terminal (No Jupyter Needed)

```bash
# Activate environment
source venv/bin/activate

# Run the complete pipeline
python -c "
from src.pipeline import BatchReconstructionPipeline

print('🚀 Starting Point Cloud Reconstruction Pipeline...')
print('=' * 70)

# Initialize pipeline
pipeline = BatchReconstructionPipeline(
    dataset_root='.',
    output_root='outputs',
    max_frames=50,
    log_file='pipeline.log'
)

# Process all parts (1_single configuration)
print('Processing dataset...')
batch_results = pipeline.batch_process(
    part_codes=None,  # All parts
    complexity_level='1_single'
)

# Save report
print('Saving batch report...')
pipeline.save_batch_report(batch_results, 'outputs/batch_report.json')

print('=' * 70)
print('✅ Pipeline complete!')
print('Check outputs/ directory for results')
"
```

---

## Option 2: Run Custom Pipeline with Specific Parts

```bash
source venv/bin/activate

python -c "
from src.pipeline import BatchReconstructionPipeline

pipeline = BatchReconstructionPipeline('.', 'outputs', max_frames=50)

# Process specific parts
parts_to_process = [
    'G-MS-I-HI-4',
    'G-LS-I-LO-33',
    'R-MS-I-HI-8'
]

for part_code in parts_to_process:
    print(f'Processing: {part_code}')
    result = pipeline.process_part(part_code, '1_single')
    print(f'  Status: {result[\"status\"]}')
"
```

---

## Option 3: Process Single Video Step-by-Step

```bash
source venv/bin/activate

python << 'EOF'
import sys
sys.path.insert(0, '.')

from src.core.data_loader import DataLoader
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor
import open3d as o3d

# Load dataset
loader = DataLoader('.')
part_data = loader.get_part_data('G-MS-I-HI-4', '1_single')

# Get paths
video_path = list(part_data['orientations'].values())[0]['video']
gt_path = list(part_data['orientations'].values())[0]['ground_truth']

print(f"Processing: {video_path}")

# Step 1: Extract frames
vp = VideoProcessor(sampling_rate=3)
frames, metadata = vp.extract_frames(video_path, max_frames=50)
print(f"✓ Extracted {len(frames)} frames")

# Step 2: Detect features
keypoints = vp.detect_keypoints(frames)
print(f"✓ Detected SIFT keypoints")

# Step 3: Match features
matches = vp.match_features(keypoints)
total_matches = sum(len(m) for m in matches)
print(f"✓ Found {total_matches} feature matches")

# Step 4: Reconstruct 3D
K = vp.estimate_camera_intrinsics(metadata['width'], metadata['height'])
reconstructor = PointCloudReconstructor(K=K)
points_3d, colors = reconstructor.sift_based_reconstruction(frames, keypoints, matches)
print(f"✓ Generated {len(points_3d):,} 3D points")

# Step 5: Create and filter point cloud
pcd = reconstructor.create_point_cloud(points_3d, colors)
pcd, _ = pcd.remove_statistical_outliers(nb_neighbors=20, std_ratio=2.0)
pcd_down = reconstructor.downsample(pcd, voxel_size=0.01)
print(f"✓ Filtered to {len(pcd_down.points):,} points")

# Step 6: Align with ground truth
gt_pcd = o3d.io.read_point_cloud(gt_path)
gt_down = reconstructor.downsample(gt_pcd, voxel_size=0.01)
reg_result = reconstructor.register_to_ground_truth(pcd_down, gt_down)
pcd_aligned = pcd_down.transform(reg_result.transformation)
print(f"✓ Aligned to ground truth")

# Step 7: Evaluate
from src.core.evaluator import PointCloudEvaluator
metrics = PointCloudEvaluator.point_cloud_metrics(pcd_aligned, gt_down)
print(f"✓ Computed metrics: F-Score = {metrics.get('f_score', 'N/A'):.4f}")

print("\n✅ Pipeline complete!")
EOF
```

---

## Option 4: Run Interactive Notebook (After Jupyter Installs)

Once Jupyter installation completes, run:

```bash
source venv/bin/activate
jupyter notebook notebooks/01_Complete_Pipeline.ipynb
```

Then the notebook will open in your browser with all the pipeline code cells ready to run.

---

## View Results

After any pipeline run:

```bash
# Show point clouds generated
ls -lh outputs/point_clouds/*.ply

# Show evaluation metrics
ls -lh outputs/evaluations/*.json

# Show visualizations
ls -lh outputs/visualizations/*.png

# View batch report
cat outputs/batch_report.json | head -50
```

---

## Installation Status

Jupyter is being installed in the background. You can:
- ✅ Run pipeline immediately using Option 1-3 above
- ⏳ Wait for Jupyter to complete (5-10 minutes)
- 🔄 Check status: `pip list | grep -i jupyter`

---

**RECOMMENDATION:** Start with Option 1 (terminal command) to process your dataset now! 🚀
