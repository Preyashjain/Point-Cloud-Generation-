#!/usr/bin/env python3
"""
Real-time progress monitoring for batch processing
"""
import json
import os
from pathlib import Path
from datetime import datetime

def monitor_progress():
    """Monitor and display batch processing progress"""
    
    output_dir = Path("outputs")
    
    stats = {
        "timestamp": datetime.now().isoformat(),
        "point_clouds_count": len(list(output_dir.glob("point_clouds/*.ply"))),
        "metrics_count": len(list(output_dir.glob("evaluations/*.json"))),
        "batch_report": None
    }
    
    # Try to read batch report if it exists
    batch_report_path = output_dir / "logs" / "batch_report.json"
    if batch_report_path.exists():
        try:
            with open(batch_report_path) as f:
                stats["batch_report"] = json.load(f)
        except:
            pass
    
    # Read last lines of log
    log_path = Path("all_parts_processing.log")
    if log_path.exists():
        with open(log_path) as f:
            lines = f.readlines()
            stats["last_log_lines"] = lines[-10:] if len(lines) > 10 else lines
    
    return stats

if __name__ == "__main__":
    stats = monitor_progress()
    
    print("\n" + "="*70)
    print("BATCH PROCESSING - REAL-TIME PROGRESS")
    print("="*70)
    print(f"Timestamp: {stats['timestamp']}")
    print(f"Point Clouds Generated: {stats['point_clouds_count']}/78")
    print(f"Metrics Files Generated: {stats['metrics_count']}/78")
    
    if stats['batch_report']:
        report = stats['batch_report']
        print(f"\nBatch Report Status:")
        print(f"  Total Parts: {report.get('total_parts', 'N/A')}")
        print(f"  Complexity Levels: {report.get('complexity_levels', 'N/A')}")
    
    print("\nRecent Log Output:")
    print("-" * 70)
    if stats.get('last_log_lines'):
        for line in stats['last_log_lines']:
            print(line.rstrip())
    
    print("\n" + "="*70)
