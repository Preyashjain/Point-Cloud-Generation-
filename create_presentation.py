"""
Generate PowerPoint Presentation 2: Implementation & Intermediate Results
For 3D Point Cloud Reconstruction Project
UPDATED WITH ACTUAL PROJECT SPECIFICATIONS
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

def add_title_slide(prs, title, subtitle):
    """Add a title slide"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(25, 51, 102)  # Dark blue
    
    # Title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(9), Inches(1.5))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    p = title_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(60)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.alignment = PP_ALIGN.CENTER
    
    # Subtitle
    subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(9), Inches(1.5))
    subtitle_frame = subtitle_box.text_frame
    subtitle_frame.word_wrap = True
    p = subtitle_frame.paragraphs[0]
    p.text = subtitle
    p.font.size = Pt(32)
    p.font.color.rgb = RGBColor(100, 181, 246)
    p.alignment = PP_ALIGN.CENTER
    
    return slide

def add_content_slide(prs, title, content_items):
    """Add a content slide with bullet points"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    # Title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    # Add blue underline
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    # Content
    content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8.4), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    for i, item in enumerate(content_items):
        if i == 0:
            p = text_frame.paragraphs[0]
        else:
            p = text_frame.add_paragraph()
        
        p.text = item
        p.font.size = Pt(18)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(6)
        p.space_after = Pt(6)
        p.level = 0
    
    return slide

def create_presentation():
    """Create the complete presentation"""
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    
    # SLIDE 1: Title Slide
    add_title_slide(prs, 
                    "3D Point Cloud Reconstruction",
                    "Progress Update: Implementation & Intermediate Results")
    
    # SLIDE 2: Where We Left Off
    add_content_slide(prs,
                      "Where We Left Off",
                      [
                          "• Problem: Automatic 3D reconstruction of industrial parts from monocular video requires robust feature matching and multi-view geometry",
                          "",
                          "• Dataset: 78 configurations across 3 complexity levels (single, multiple, stacked parts) with laser ground truth for evaluation",
                          "",
                          "• Planned Approach: Feature Matching → Essential Matrix → Camera Pose → Triangulation → Point Cloud refinement"
                      ])
    
    # SLIDE 3: Pipeline Implementation Status
    add_content_slide(prs,
                      "Pipeline Implementation Status",
                      [
                          "✅ Frame Extraction & Undistortion [100%]",
                          "✅ SuperPoint Feature Detection (~300 features/frame) [100%]",
                          "✅ LightGlue Feature Matching [100%]",
                          "✅ Essential Matrix Computation (RANSAC) [100%]",
                          "✅ Camera Pose Recovery [100%]",
                          "✅ Triangulation & Point Cloud Creation [100%]",
                          "✅ Statistical Outlier Filtering [100%]",
                          "",
                          "🔄 Quantitative Evaluation (all 78 configs) [50%]",
                          "🔄 Refinement & Optimization [40%]",
                          "⏳ Final Results Compilation & Analysis [0%]"
                      ])
    
    # SLIDE 4: Algorithm Improvements
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = "Feature Detection & Matching Strategy"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    content = [
        "✅ SELECTED: SuperPoint + LightGlue",
        "  • SuperPoint: Modern deep learning-based detector",
        "  • Extracts ~300 features per frame (precise, repeatable)",
        "  • LightGlue: Efficient, learned feature matcher",
        "  • Why: Balance of speed, accuracy, and reliability",
        "",
        "❌ NOT USED: Classical SIFT",
        "  • Too slow for real-time processing",
        "  • Requires additional descriptor matching (kNN + Lowe's ratio test)",
        "",
        "❌ NOT USED: LoFTR",
        "  • Slower than LightGlue for our use case",
        "  • Overkill for fixed-camera scenarios"
    ]
    
    for i, item in enumerate(content):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        p.text = item
        p.font.size = Pt(16)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(3)
        p.space_after = Pt(3)
    
    # SLIDE 5: Reconstruction Approach
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = "3D Reconstruction Pipeline"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    pipeline = [
        "1. Feature Detection (SuperPoint)",
        "   Extracts keypoints and descriptors from each frame",
        "",
        "2. Feature Matching (LightGlue)",
        "   Matches features across consecutive frames",
        "",
        "3. Essential Matrix Estimation",
        "   RANSAC-based computation with calibrated camera K",
        "",
        "4. Camera Pose Recovery",
        "   Extracts rotation (R) and translation (t) from E matrix",
        "",
        "5. Triangulation",
        "   Converts 2D feature matches to 3D points in world coordinates",
        "",
        "6. Point Cloud Filtering & Export",
        "   Statistical outlier removal + PLY format output"
    ]
    
    for i, item in enumerate(pipeline):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        p.text = item
        p.font.size = Pt(15)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(2)
        p.space_after = Pt(2)
    
    # SLIDE 6: Why Certain Approaches Were Rejected
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = "Approaches Evaluated & Rejected"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    rejected = [
        "❌ Depth Anything v2",
        "   Reason: Computationally too expensive",
        "   Would require GPU cluster for batch processing",
        "",
        "❌ Multi-View Stereo (MVS) Networks",
        "   Reason: Results were horrible in early testing",
        "   Dense reconstruction added more noise than value",
        "",
        "❌ Direct Regression (DuSt3R / MASt3R)",
        "   Reason: High computational overhead",
        "   Classical triangulation + SuperPoint is more stable",
        "",
        "✅ Classical Triangulation",
        "   Reason: Reliable, interpretable, good baseline"
    ]
    
    for i, item in enumerate(rejected):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        p.text = item
        p.font.size = Pt(15)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(2)
        p.space_after = Pt(2)
    
    # SLIDE 7: Bugs & Challenges
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = "Challenges Faced"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    challenges = [
        "Challenge 1: Multi-Object Degradation ⚠️",
        "  Problem: Quality drops significantly with 2+ parts",
        "  Impact: Objects overlap in point cloud, merged geometry",
        "  Status: Under investigation - needs object segmentation",
        "",
        "Challenge 2: Fingerprint Noise (Clay Capacitor) ⚠️",
        "  Problem: Surface imperfections picked up as 3D points",
        "  Current Solution: Statistical outlier filtering (80% effective)",
        "  Remaining: 20% of noise persists in final cloud",
        "",
        "Challenge 3: Low Feature Density",
        "  Problem: Only ~300 features per frame is sparse",
        "  Impact: Fewer 3D points than classical SIFT (2000 features)",
        "  Trade-off: Accuracy over quantity (SuperPoint is more robust)"
    ]
    
    for i, item in enumerate(challenges):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        p.text = item
        p.font.size = Pt(15)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(2)
        p.space_after = Pt(2)
    
    # SLIDE 8: Demo
    add_content_slide(prs,
                      "Pipeline in Action",
                      [
                          "Input: 500+ frames extracted from 4K industrial video",
                          "",
                          "Processing Steps:",
                          "  1. SuperPoint Detection: ~300 features per frame",
                          "  2. LightGlue Matching: Hundreds of feature pairs across frames",
                          "  3. Essential Matrix: RANSAC-based pose estimation",
                          "  4. Triangulation: 2D matches → 3D world coordinates",
                          "",
                          "Output: Point cloud with statistical filtering applied",
                          "",
                          "Processing Time: 2-3 minutes end-to-end per configuration"
                      ])
    
    # SLIDE 9: Intermediate Results
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = "Current Results & Evaluation Metrics"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    results = [
        "Status: Evaluating across 78 configurations",
        "Current Progress: ~50% of full dataset processed",
        "",
        "Best Case Performance (Level 1 - Single Objects):",
        "  • Completeness: ~40% vs ground truth laser scan",
        "    (Coverage of actual object surface points)",
        "",
        "  • Accuracy: 3-7mm average error",
        "    (Distance of reconstructed points to true surface)",
        "",
        "  • Point Cloud Density: Varies by object (10K - 100K+ points)",
        "",
        "⚠️ Multi-object & stacked configs show 20-30% lower completeness",
        "⚠️ Full quantitative comparison still running"
    ]
    
    for i, item in enumerate(results):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        p.text = item
        p.font.size = Pt(15)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(2)
        p.space_after = Pt(2)
    
    # SLIDE 10: What's Still Pending
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    title_frame = title_box.text_frame
    p = title_frame.paragraphs[0]
    p.text = "Remaining Work for Presentation 3"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(25, 51, 102)
    
    line = slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(9), Inches(0))
    line.line.color.rgb = RGBColor(100, 181, 246)
    line.line.width = Pt(3)
    
    content_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.8), Inches(8.8), Inches(5.5))
    text_frame = content_box.text_frame
    text_frame.word_wrap = True
    
    pending = [
        "🔴 CRITICAL:",
        "  1. Complete evaluation on all 78 configurations",
        "  2. Resolve multi-object degradation (need segmentation masks)",
        "  3. Reduce fingerprint noise to < 5%",
        "",
        "🟡 IMPORTANT:",
        "  1. Optimize filtering parameters per object type",
        "  2. Improve feature matching robustness",
        "  3. Benchmark performance metrics comprehensively",
        "",
        "🟢 NICE-TO-HAVE:",
        "  1. Real-time processing pipeline",
        "  2. GPU acceleration for SuperPoint + LightGlue",
        "  3. Interactive 3D visualization tool",
        "",
        "Timeline: ~4 weeks for Presentation 3"
    ]
    
    for i, item in enumerate(pending):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        p.text = item
        p.font.size = Pt(14)
        p.font.color.rgb = RGBColor(50, 50, 50)
        p.space_before = Pt(1)
        p.space_after = Pt(1)
    
    # Save presentation
    output_file = "Presentation_2_Implementation_and_Intermediate_Results.pptx"
    prs.save(output_file)
    print(f"✅ Presentation created successfully: {output_file}")
    print(f"📊 Total slides: {len(prs.slides)}")
    print(f"🎨 Theme: Dark blue + light gray professional design")
    print(f"📝 Content: SuperPoint + LightGlue, 40% completeness, challenges & next steps")

if __name__ == "__main__":
    create_presentation()
