#!/usr/bin/env python3
"""
Interactive 3D Point Cloud Viewer
===================================
Visualize generated point clouds with Open3D
"""

import os
import sys
import glob
import json
from pathlib import Path
import open3d as o3d
import numpy as np


class PointCloudViewer:
    def __init__(self, output_dir="outputs"):
        self.output_dir = output_dir
        self.point_clouds_dir = os.path.join(output_dir, "point_clouds")
        self.metrics_dir = os.path.join(output_dir, "evaluations")
        
    def list_point_clouds(self):
        """List all available point clouds"""
        ply_files = sorted(glob.glob(os.path.join(self.point_clouds_dir, "*.ply")))
        return ply_files
    
    def load_point_cloud(self, ply_path):
        """Load a point cloud from PLY file"""
        pcd = o3d.io.read_point_cloud(ply_path)
        return pcd
    
    def load_metrics(self, metrics_path):
        """Load metrics for a point cloud"""
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
        return metrics
    
    def print_metrics(self, metrics):
        """Pretty print metrics"""
        print("\n" + "="*60)
        print("📊 POINT CLOUD QUALITY METRICS")
        print("="*60)
        print(f"  Points Count:        {metrics.get('points_count', 'N/A'):>10}")
        print(f"  Chamfer Distance:    {metrics.get('chamfer_distance', 0):.4f} cm")
        print(f"  Hausdorff Distance:  {metrics.get('hausdorff_distance', 0):.4f} cm")
        print(f"  Completeness:        {metrics.get('completeness', 0):.2%}")
        print(f"  Accuracy:            {metrics.get('accuracy', 0):.4f} cm")
        print(f"  F-Score:             {metrics.get('f_score', 0):.4f}")
        print("="*60 + "\n")
    
    def view_single(self, index=0):
        """View a single point cloud"""
        ply_files = self.list_point_clouds()
        
        if not ply_files:
            print("❌ No point clouds found!")
            return
        
        if index >= len(ply_files):
            print(f"❌ Index {index} out of range. Available: 0-{len(ply_files)-1}")
            return
        
        ply_path = ply_files[index]
        basename = os.path.basename(ply_path)
        
        print(f"\n🔄 Loading point cloud #{index+1}/{len(ply_files)}: {basename}")
        
        # Load point cloud
        pcd = self.load_point_cloud(ply_path)
        
        # Load metrics
        metrics_path = ply_path.replace("/point_clouds/", "/evaluations/").replace(".ply", ".json")
        if os.path.exists(metrics_path):
            metrics = self.load_metrics(metrics_path)
            self.print_metrics(metrics)
        
        # Print info
        print(f"📍 Points: {len(pcd.points):,}")
        print(f"🎨 Has colors: {pcd.has_colors()}")
        print(f"📐 Bounds: {pcd.get_axis_aligned_bounding_box()}")
        print("\n🖱️  CONTROLS:")
        print("   - Left mouse: Rotate")
        print("   - Middle mouse: Zoom")
        print("   - Right mouse: Pan")
        print("   - R: Reset view")
        print("   - ESC: Close")
        
        # Visualize
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name=basename, width=1200, height=800)
        vis.add_geometry(pcd)
        
        # Add coordinate frame
        mesh_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=0.1, origin=[0, 0, 0]
        )
        vis.add_geometry(mesh_frame)
        
        vis.run()
        vis.destroy_window()
    
    def view_all_grid(self):
        """View all point clouds in grid"""
        ply_files = self.list_point_clouds()
        
        if not ply_files:
            print("❌ No point clouds found!")
            return
        
        print(f"\n📊 Found {len(ply_files)} point clouds")
        print("Loading all point clouds... (this may take a moment)")
        
        geometries = []
        
        for i, ply_path in enumerate(ply_files):
            print(f"  [{i+1}/{len(ply_files)}] {os.path.basename(ply_path)}")
            pcd = self.load_point_cloud(ply_path)
            
            # Center the point cloud for better visualization
            center = pcd.get_center()
            pcd.translate(-center)
            
            # Move each cloud in grid pattern
            grid_x = i % 4
            grid_y = (i // 4) % 4
            offset = np.array([grid_x * 0.5, grid_y * 0.5, 0])
            pcd.translate(offset)
            
            geometries.append(pcd)
        
        print("\n🖱️  CONTROLS:")
        print("   - Left mouse: Rotate")
        print("   - Middle mouse: Zoom")
        print("   - Right mouse: Pan")
        print("   - ESC: Close")
        
        o3d.visualization.draw_geometries(geometries)
    
    def compare_two(self, index1=0, index2=1):
        """Compare two point clouds side by side"""
        ply_files = self.list_point_clouds()
        
        if len(ply_files) < 2:
            print("❌ Need at least 2 point clouds to compare!")
            return
        
        if index1 >= len(ply_files) or index2 >= len(ply_files):
            print(f"❌ Index out of range. Available: 0-{len(ply_files)-1}")
            return
        
        pcd1 = self.load_point_cloud(ply_files[index1])
        pcd2 = self.load_point_cloud(ply_files[index2])
        
        # Color first cloud blue, second cloud red
        pcd1.paint_uniform_color([0, 0.5, 1])  # Blue
        pcd2.paint_uniform_color([1, 0.5, 0])  # Red
        
        basename1 = os.path.basename(ply_files[index1])
        basename2 = os.path.basename(ply_files[index2])
        
        print(f"\n🔄 Comparing:")
        print(f"  1️⃣  {basename1} (Blue)")
        print(f"  2️⃣  {basename2} (Red)")
        
        o3d.visualization.draw_geometries([pcd1, pcd2])
    
    def interactive_explorer(self):
        """Interactive menu for exploring point clouds"""
        ply_files = self.list_point_clouds()
        
        if not ply_files:
            print("❌ No point clouds found!")
            return
        
        while True:
            print("\n" + "="*60)
            print("🔍 POINT CLOUD EXPLORER")
            print("="*60)
            print(f"Total point clouds: {len(ply_files)}")
            print("\nOptions:")
            print("  1. View single point cloud")
            print("  2. View all point clouds in grid")
            print("  3. Compare two point clouds")
            print("  4. List all point clouds")
            print("  5. Exit")
            print("-"*60)
            
            choice = input("Enter choice (1-5): ").strip()
            
            if choice == "1":
                self.list_all_clouds()
                try:
                    idx = int(input("Enter index: "))
                    self.view_single(idx)
                except ValueError:
                    print("❌ Invalid input")
            
            elif choice == "2":
                self.view_all_grid()
            
            elif choice == "3":
                self.list_all_clouds()
                try:
                    idx1 = int(input("Enter first index: "))
                    idx2 = int(input("Enter second index: "))
                    self.compare_two(idx1, idx2)
                except ValueError:
                    print("❌ Invalid input")
            
            elif choice == "4":
                self.list_all_clouds()
            
            elif choice == "5":
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice")
    
    def list_all_clouds(self):
        """List all available point clouds with stats"""
        ply_files = self.list_point_clouds()
        
        print("\n" + "="*80)
        print("📋 AVAILABLE POINT CLOUDS")
        print("="*80)
        
        for i, ply_path in enumerate(ply_files):
            pcd = self.load_point_cloud(ply_path)
            basename = os.path.basename(ply_path)
            
            metrics_path = ply_path.replace("/point_clouds/", "/evaluations/").replace(".ply", ".json")
            metrics_info = ""
            if os.path.exists(metrics_path):
                with open(metrics_path) as f:
                    metrics = json.load(f)
                    f_score = metrics.get('f_score', 0)
                    metrics_info = f"F-Score: {f_score:.3f}"
            
            print(f"  [{i:2d}] {basename:45} | Points: {len(pcd.points):7,} | {metrics_info}")
        
        print("="*80 + "\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Interactive 3D Point Cloud Viewer")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    parser.add_argument("--view", type=int, default=None, help="View specific cloud (index)")
    parser.add_argument("--all", action="store_true", help="View all clouds in grid")
    parser.add_argument("--compare", nargs=2, type=int, help="Compare two clouds (indices)")
    parser.add_argument("--list", action="store_true", help="List all clouds")
    
    args = parser.parse_args()
    
    viewer = PointCloudViewer(args.output_dir)
    
    if args.list:
        viewer.list_all_clouds()
    elif args.view is not None:
        viewer.view_single(args.view)
    elif args.all:
        viewer.view_all_grid()
    elif args.compare:
        viewer.compare_two(args.compare[0], args.compare[1])
    else:
        viewer.interactive_explorer()


if __name__ == "__main__":
    main()
