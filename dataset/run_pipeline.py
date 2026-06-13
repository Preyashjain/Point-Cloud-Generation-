#!/usr/bin/env python3
"""
Simple pipeline runner script
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.pipeline import BatchReconstructionPipeline
    
    print("=" * 70)
    print("🚀 POINT CLOUD RECONSTRUCTION PIPELINE")
    print("=" * 70)
    
    # Initialize pipeline
    print("\n📂 Initializing pipeline...")
    pipeline = BatchReconstructionPipeline(
        dataset_root='.',
        output_root='outputs',
        max_frames=50
    )
    print("✅ Pipeline initialized")
    
    # Run batch processing
    print("\n🔄 Processing dataset...")
    batch_results = pipeline.batch_process(complexity_level='1_single')
    
    # Save report
    print("\n💾 Saving batch report...")
    pipeline.save_batch_report(batch_results, 'outputs/batch_report.json')
    
    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETE!")
    print("=" * 70)
    print(f"\n📊 Results:")
    print(f"   Point clouds: outputs/point_clouds/")
    print(f"   Metrics: outputs/evaluations/")
    print(f"   Report: outputs/batch_report.json")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
