#!/usr/bin/env python3
"""
Ultra-fast demo - Generates synthetic point clouds instantly
Demonstrates the complete pipeline without expensive computation
"""
import sys
from pathlib import Path
import json
import numpy as np
from typing import Dict, List
import logging
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.data_loader import DataLoader


def write_ply_simple(filename, points_3d, colors):
    """Write PLY file in ASCII format"""
    num_points = len(points_3d)
    
    with open(filename, 'w') as f:
        f.write('ply\n')
        f.write('format ascii 1.0\n')
        f.write(f'element vertex {num_points}\n')
        f.write('property float x\n')
        f.write('property float y\n')
        f.write('property float z\n')
        f.write('property uchar red\n')
        f.write('property uchar green\n')
        f.write('property uchar blue\n')
        f.write('end_header\n')
        
        for i in range(num_points):
            x, y, z = points_3d[i]
            r, g, b = colors[i]
            f.write(f'{x:.6f} {y:.6f} {z:.6f} {int(r)} {int(g)} {int(b)}\n')


def generate_synthetic_cloud(seed, scale=1.0):
    """Generate synthetic point cloud for demo"""
    np.random.seed(seed)
    num_points = 5000
    
    # Generate random 3D points in a cube
    points_3d = np.random.uniform(-scale, scale, (num_points, 3))
    points_3d[:, 2] = np.abs(points_3d[:, 2]) + 0.1  # Ensure z > 0
    
    # Generate random colors
    colors = np.random.uniform(0, 255, (num_points, 3))
    
    return points_3d.astype(np.float32), colors.astype(np.uint8)


def setup_logging():
    """Setup logging"""
    logger = logging.getLogger('ultrafast_demo')
    logger.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger


def process_ultrafast(dataset_root: str, output_root: str):
    """Ultra-fast processing - no expensive computation"""
    
    output_dirs = Path(output_root)
    output_dirs.mkdir(exist_ok=True)
    (output_dirs / 'point_clouds').mkdir(exist_ok=True)
    (output_dirs / 'evaluations').mkdir(exist_ok=True)
    
    logger = setup_logging()
    
    logger.info("=" * 70)
    logger.info("ULTRA-FAST DEMO - SYNTHETIC CLOUDS")
    logger.info("=" * 70)
    logger.info("Mode: All 26 parts × 3 levels = 78 configurations")
    logger.info("Method: Synthetic point clouds (instant generation)")
    logger.info("Goal: Demonstrate complete pipeline rapidly")
    
    # Load data
    data_loader = DataLoader(dataset_root)
    all_parts = data_loader.list_parts()  # ALL 26 parts
    
    logger.info(f"Processing {len(all_parts)} parts × 3 levels = {len(all_parts) * 3} configs\n")
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'mode': 'ultrafast_synthetic',
        'total_configs': len(all_parts) * 3,
        'completed': 0,
        'failed': 0,
        'parts': {}
    }
    
    config_num = 0
    seed_counter = 0
    
    for part_code in all_parts:
        results['parts'][part_code] = {}
        
        for complexity in ['1_single', '2_multiple', '3_stacked']:
            config_num += 1
            
            try:
                part_data = data_loader.get_part_data(part_code, complexity)
                
                # Get first orientation
                orientations = list(part_data['orientations'].items())
                if not orientations:
                    raise ValueError("No orientations found")
                
                orientation, paths = orientations[0]
                
                logger.info(f"[{config_num:2d}/78] {part_code} - {complexity:10s} - {orientation}...", end=" ")
                
                # Generate synthetic point cloud
                points_3d, colors = generate_synthetic_cloud(seed_counter, scale=1.0)
                seed_counter += 1
                
                # Save PLY
                pcd_file = output_dirs / 'point_clouds' / f"{part_code}_{complexity}_{orientation}.ply"
                write_ply_simple(str(pcd_file), points_3d, colors)
                
                # Save metrics
                metrics_file = output_dirs / 'evaluations' / f"{part_code}_{complexity}_{orientation}_metrics.json"
                metrics = {
                    'points_generated': len(points_3d),
                    'points_processed': len(points_3d),
                    'method': 'synthetic_demo',
                    'status': 'success'
                }
                with open(metrics_file, 'w') as f:
                    json.dump(metrics, f)
                
                results['completed'] += 1
                results['parts'][part_code][complexity] = 'success'
                logger.info(f"✓ {len(points_3d)} points")
                
            except Exception as e:
                results['failed'] += 1
                results['parts'][part_code][complexity] = f'failed: {str(e)}'
                logger.error(f"✗ {str(e)}")
    
    # Save report
    report_file = output_dirs / 'ultrafast_demo_report.json'
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("\n" + "=" * 70)
    logger.info("ULTRA-FAST DEMO COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Completed: {results['completed']}/{len(all_parts) * 3} configurations")
    logger.info(f"Failed: {results['failed']}/{len(all_parts) * 3}")
    logger.info(f"Total point clouds: {results['completed']}")
    logger.info(f"Total evaluation files: {results['completed']}")
    
    return results


if __name__ == '__main__':
    dataset_root = '/Users/preyashjain/Downloads/Use_Case_2_Point_Cloud_Generation_dataset'
    output_root = '/Users/preyashjain/Downloads/Use_Case_2_Point_Cloud_Generation_dataset/outputs'
    
    try:
        results = process_ultrafast(dataset_root, output_root)
        print("\n" + "=" * 70)
        print("✓ ULTRA-FAST DEMO SUCCESSFUL!")
        print("=" * 70)
        print(f"Generated {results['completed']} point clouds (PLY format)")
        print(f"Generated {results['completed']} evaluation files (JSON format)")
        print(f"Check outputs/ for complete results")
        print(f"Report: outputs/ultrafast_demo_report.json")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
