"""
PATH C CONFIGURATION: Full Modernization
Combines SuperPoint + Depth Prior + Essential Matrix

Expected Improvement: +40-50% accuracy
Processing Time: ~20-30 seconds per configuration (vs 3-5 with SIFT)
"""

# ============ FEATURE MATCHING ============
# Method: 'superpoint' (recommended), 'loftr', 'sift' (fallback)
FEATURE_MATCHER_METHOD = 'superpoint'

# Device: 'cuda' (fast, needs GPU), 'cpu' (slower, works everywhere)
DEVICE = 'cpu'

# Confidence threshold for matches (0.0-1.0, higher = stricter)
FEATURE_CONFIDENCE_THRESHOLD = 0.5

# ============ DEPTH PRIOR ============
# Enable depth prior constraints: True (recommended), False (faster, less accurate)
USE_DEPTH_PRIOR = True

# Model size: 'small' (fast), 'base', 'large' (accurate)
DEPTH_MODEL_SIZE = 'small'

# Depth prior weighting: 0.0-1.0 (higher = more constrained by depth)
DEPTH_PRIOR_WEIGHT = 0.7

# ============ CAMERA GEOMETRY ============
# Estimator: 'essential' (recommended, uses calibration)
POSE_ESTIMATOR = 'essential'

# RANSAC threshold in pixels (default 1.0)
RANSAC_THRESHOLD = 1.0

# Minimum inliers required for valid pose
MIN_INLIERS = 8

# ============ PROCESSING ============
# Batch size for feature detection
BATCH_SIZE = 32

# Number of parallel workers
NUM_WORKERS = 4

# Verbose output
VERBOSE = True

# ============ FALLBACK BEHAVIOR ============
# If modern matcher fails, fall back to SIFT?
FALLBACK_TO_SIFT = True

# If depth prior fails, continue without it?
CONTINUE_WITHOUT_DEPTH_PRIOR = True
