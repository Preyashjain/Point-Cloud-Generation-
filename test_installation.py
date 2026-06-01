#!/usr/bin/env python3
"""Quick start test script to verify the installation"""

import sys
from pathlib import Path
from src.config import DATASET_ROOT, OUTPUT_ROOT

# Add src to path
sys.path.insert(0, f"{DATASET_ROOT}/src")

print("=" * 60)
print("Point Cloud Generation Pipeline - Installation Test")
print("=" * 60)

# Test imports
print("\n1. Testing imports...")
try:
    from core.data_loader import DataLoader

    print("   ✓ DataLoader imported")

    from core.video_processor import VideoProcessor

    print("   ✓ VideoProcessor imported")

    from core.reconstructor import PointCloudReconstructor

    print("   ✓ PointCloudReconstructor imported")

    from core.evaluator import PointCloudEvaluator

    print("   ✓ PointCloudEvaluator imported")

    from utils.helpers import create_output_dirs

    print("   ✓ Helpers imported")

    from visualization.visualizer import PointCloudVisualizer

    print("   ✓ Visualizer imported")

except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test dataset access
print("\n2. Testing dataset access...")
try:
    dataset_root = DATASET_ROOT
    loader = DataLoader(dataset_root)
    parts = loader.list_parts()
    print(f"   ✓ Dataset loaded with {len(parts)} parts")

    if len(parts) > 0:
        test_part = parts[0]
        part_data = loader.get_part_data(test_part, "1_single")
        print(f"   ✓ Sample part loaded: {test_part}")

        orientations = list(part_data["orientations"].keys())
        print(f"   ✓ Orientations available: {orientations}")

except Exception as e:
    print(f"   ✗ Dataset access failed: {e}")
    sys.exit(1)

# Test video processing
print("\n3. Testing video processing...")
try:
    vp = VideoProcessor(sampling_rate=10)  # Extract every 10th frame
    print("   ✓ VideoProcessor initialized")

    # Don't actually load video to save time, just verify class
    print("   ✓ Video processing module ready")

except Exception as e:
    print(f"   ✗ Video processing test failed: {e}")
    sys.exit(1)

# Test point cloud utilities
print("\n4. Testing point cloud utilities...")
try:
    import numpy as np
    import open3d as o3d

    # Create dummy point cloud
    points = np.random.rand(100, 3)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    reconstructor = PointCloudReconstructor()
    filtered = reconstructor.filter_outliers(pcd)
    print(f"   ✓ Point cloud filtering works")

    # Test evaluation
    pred = np.random.rand(50, 3)
    gt = np.random.rand(60, 3)

    chamfer, _, _ = PointCloudEvaluator.chamfer_distance(pred, gt)
    print(f"   ✓ Evaluation metrics work (Chamfer: {chamfer:.4f})")

except Exception as e:
    print(f"   ✗ Point cloud utilities test failed: {e}")
    sys.exit(1)

# Test output directories
print("\n5. Testing output structure...")
try:
    output_base = OUTPUT_ROOT
    output_dirs = create_output_dirs(output_base)
    print(f"   ✓ Output directories created")
    for name, path in output_dirs.items():
        print(f"      - {name}: {path.name}")

except Exception as e:
    print(f"   ✗ Output structure test failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED - Installation is ready!")
print("=" * 60)

print("\nNext steps:")
print("1. Try the interactive notebook:")
print("   jupyter notebook notebooks/01_Complete_Pipeline.ipynb")
print("\n2. Or use batch processing:")
print("   python src/pipeline.py --limit 3 --complexity 1_single")
print("\n3. Check the README for more information:")
print("   cat README_PROJECT.md")
print("=" * 60)
