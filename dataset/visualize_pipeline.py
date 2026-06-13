#!/usr/bin/env python3
"""
Pipeline Processing Visualizer
=================================
Shows each stage of the processing pipeline with visual output
"""

import os
import sys
import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


class PipelineVisualizer:
    def __init__(self, dataset_dir=".", part_code=None):
        self.dataset_dir = dataset_dir
        self.part_code = part_code
        
    def find_video_files(self):
        """Find all video files in dataset"""
        videos = []
        for root, dirs, files in os.walk(self.dataset_dir):
            for file in files:
                if file.endswith('.mp4'):
                    videos.append(os.path.join(root, file))
        return sorted(videos)[:5]  # Limit to first 5 for demo
    
    def extract_frames(self, video_path, num_frames=6):
        """Extract sample frames from video"""
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        frames = []
        for i in range(num_frames):
            frame_idx = int(i * total_frames / num_frames)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Resize for display
                frame = cv2.resize(frame, (400, 225))
                frames.append(frame)
        
        cap.release()
        return frames
    
    def detect_sift(self, frame):
        """Detect SIFT keypoints and descriptors"""
        sift = cv2.SIFT_create()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        keypoints, descriptors = sift.detectAndCompute(gray, None)
        return keypoints, descriptors, gray
    
    def draw_keypoints(self, frame, keypoints):
        """Draw keypoints on frame"""
        output = frame.copy()
        for kp in keypoints[:100]:  # Limit to 100 for visibility
            x, y = int(kp.pt[0]), int(kp.pt[1])
            cv2.circle(output, (x, y), 3, (0, 255, 0), 2)
        return output
    
    def match_features(self, frame1, frame2):
        """Detect and match features between two frames"""
        sift = cv2.SIFT_create()
        
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2GRAY)
        
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)
        
        # BFMatcher
        bf = cv2.BFMatcher()
        matches = bf.knnMatch(des1, des2, k=2)
        
        # Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)
        
        return kp1, kp2, good_matches
    
    def draw_matches(self, frame1, frame2, kp1, kp2, matches):
        """Draw matching features"""
        h, w = frame1.shape[:2]
        output = np.zeros((h, w*2, 3), dtype=np.uint8)
        output[:h, :w] = frame1
        output[:h, w:] = frame2
        
        for match in matches[:50]:  # Limit to 50 for visibility
            x1, y1 = map(int, kp1[match.queryIdx].pt)
            x2, y2 = map(int, kp2[match.trainIdx].pt)
            
            cv2.circle(output, (x1, y1), 3, (0, 255, 0), 2)
            cv2.circle(output, (w + x2, y2), 3, (0, 255, 0), 2)
            cv2.line(output, (x1, y1), (w + x2, y2), (255, 0, 0), 1)
        
        return output
    
    def visualize_frame_extraction(self):
        """Visualize frame extraction stage"""
        videos = self.find_video_files()
        
        if not videos:
            print("❌ No video files found!")
            return
        
        print(f"\n📹 STAGE 1: FRAME EXTRACTION")
        print(f"{'='*60}")
        print(f"Processing: {os.path.basename(videos[0])}")
        
        frames = self.extract_frames(videos[0], num_frames=6)
        
        fig = plt.figure(figsize=(14, 8))
        fig.suptitle('Stage 1: Frame Extraction from Video', fontsize=16, fontweight='bold')
        
        for i, frame in enumerate(frames):
            ax = fig.add_subplot(2, 3, i+1)
            ax.imshow(frame)
            ax.set_title(f'Frame {i+1}')
            ax.axis('off')
        
        plt.tight_layout()
        plt.show()
        
        print(f"✅ Extracted {len(frames)} sample frames")
    
    def visualize_sift_detection(self):
        """Visualize SIFT keypoint detection"""
        videos = self.find_video_files()
        
        if not videos:
            print("❌ No video files found!")
            return
        
        print(f"\n🔍 STAGE 2: SIFT FEATURE DETECTION")
        print(f"{'='*60}")
        
        frames = self.extract_frames(videos[0], num_frames=3)
        
        fig = plt.figure(figsize=(15, 10))
        fig.suptitle('Stage 2: SIFT Keypoint Detection', fontsize=16, fontweight='bold')
        
        for i, frame in enumerate(frames):
            # Original frame
            ax1 = fig.add_subplot(3, 2, i*2+1)
            ax1.imshow(frame)
            ax1.set_title(f'Original Frame {i+1}')
            ax1.axis('off')
            
            # Keypoints
            kp, des, gray = self.detect_sift(frame)
            frame_kp = self.draw_keypoints(frame, kp)
            
            ax2 = fig.add_subplot(3, 2, i*2+2)
            ax2.imshow(frame_kp)
            ax2.set_title(f'Keypoints: {len(kp)} detected')
            ax2.axis('off')
        
        plt.tight_layout()
        plt.show()
        
        print(f"✅ SIFT successfully detected keypoints in frames")
    
    def visualize_feature_matching(self):
        """Visualize feature matching between frames"""
        videos = self.find_video_files()
        
        if not videos:
            print("❌ No video files found!")
            return
        
        print(f"\n🔗 STAGE 3: FEATURE MATCHING")
        print(f"{'='*60}")
        
        frames = self.extract_frames(videos[0], num_frames=4)
        
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle('Stage 3: Feature Matching Between Consecutive Frames', fontsize=16, fontweight='bold')
        
        for i in range(len(frames)-1):
            kp1, kp2, matches = self.match_features(frames[i], frames[i+1])
            
            match_img = self.draw_matches(frames[i], frames[i+1], kp1, kp2, matches)
            
            ax = fig.add_subplot(2, 2, i+1)
            ax.imshow(match_img)
            ax.set_title(f'Frame {i+1} → {i+2}: {len(matches)} matches')
            ax.axis('off')
        
        plt.tight_layout()
        plt.show()
        
        print(f"✅ Feature matching completed")
    
    def visualize_pipeline_flow(self):
        """Interactive pipeline visualization menu"""
        while True:
            print("\n" + "="*60)
            print("🎬 PROCESSING PIPELINE VISUALIZER")
            print("="*60)
            print("\nVisualization Stages:")
            print("  1. Frame Extraction")
            print("  2. SIFT Feature Detection")
            print("  3. Feature Matching")
            print("  4. All Stages (Sequential)")
            print("  5. Exit")
            print("-"*60)
            
            choice = input("Enter choice (1-5): ").strip()
            
            if choice == "1":
                self.visualize_frame_extraction()
            elif choice == "2":
                self.visualize_sift_detection()
            elif choice == "3":
                self.visualize_feature_matching()
            elif choice == "4":
                self.visualize_frame_extraction()
                self.visualize_sift_detection()
                self.visualize_feature_matching()
            elif choice == "5":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline Processing Visualizer")
    parser.add_argument("--dataset-dir", default=".", help="Dataset directory")
    parser.add_argument("--frames", action="store_true", help="Show frame extraction")
    parser.add_argument("--sift", action="store_true", help="Show SIFT detection")
    parser.add_argument("--matching", action="store_true", help="Show feature matching")
    
    args = parser.parse_args()
    
    viz = PipelineVisualizer(args.dataset_dir)
    
    if args.frames:
        viz.visualize_frame_extraction()
    elif args.sift:
        viz.visualize_sift_detection()
    elif args.matching:
        viz.visualize_feature_matching()
    else:
        viz.visualize_pipeline_flow()


if __name__ == "__main__":
    main()
