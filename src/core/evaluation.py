"""
Point-cloud evaluation: compare a sparse/dense reconstruction to the
laser-scanner ground truth provided in the dataset.

Metrics
-------
Chamfer Distance (symmetric mean NN distance)
Hausdorff Distance (worst-case NN distance)
F-score at 1 %, 2 %, 5 % of the GT bounding-box diagonal
  (scale-independent thresholds so results are comparable across objects)

Alignment
---------
1. Translate both centroids to the origin.
2. Scale the prediction so its bounding-box diagonal matches the GT's.
3. Optional ICP refinement (requires open3d; skipped if not installed).

The GT PLY may be in any unit (mm or m) — centroid + scale alignment
handles the offset and unit difference automatically.
"""

import json
import struct
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# PLY loading
# ---------------------------------------------------------------------------


def load_ply_points(path: Path) -> np.ndarray:
    """Return [N, 3] float64 xyz array from a PLY file."""
    try:
        import open3d as o3d

        pcd = o3d.io.read_point_cloud(str(path))
        pts = np.asarray(pcd.points, dtype=np.float64)
        if len(pts) > 0:
            return pts
    except ImportError:
        pass
    return _parse_ply(path)


def _parse_ply(path: Path) -> np.ndarray:
    """Dependency-free PLY reader (ASCII + binary little/big-endian)."""
    _SIZE = {
        "float": 4,
        "float32": 4,
        "double": 8,
        "float64": 8,
        "int": 4,
        "int32": 4,
        "uint": 4,
        "uint32": 4,
        "short": 2,
        "int16": 2,
        "ushort": 2,
        "uint16": 2,
        "char": 1,
        "int8": 1,
        "uchar": 1,
        "uint8": 1,
    }
    _FMT = {
        "float": "f",
        "float32": "f",
        "double": "d",
        "float64": "d",
        "int": "i",
        "int32": "i",
        "uint": "I",
        "uint32": "I",
        "short": "h",
        "int16": "h",
        "ushort": "H",
        "uint16": "H",
        "char": "b",
        "int8": "b",
        "uchar": "B",
        "uint8": "B",
    }

    with open(path, "rb") as fh:
        n_verts = 0
        fmt = "ascii"
        props: list[tuple[str, str]] = []
        in_vert = False

        while True:
            line = fh.readline().decode("ascii", errors="replace").strip()
            if line == "end_header":
                break
            toks = line.split()
            if not toks:
                continue
            if toks[0] == "format":
                fmt = toks[1]
            elif toks[0] == "element":
                in_vert = toks[1] == "vertex"
                if in_vert:
                    n_verts = int(toks[2])
            elif toks[0] == "property" and in_vert:
                props.append((toks[-1], toks[1]))

        xyz_idx = [i for i, (name, _) in enumerate(props) if name in ("x", "y", "z")]
        if len(xyz_idx) != 3:
            raise ValueError(
                f"{path}: expected 'x y z' properties, found {[n for n, _ in props]}"
            )

        if fmt == "ascii":
            rows = []
            for _ in range(n_verts):
                vals = list(map(float, fh.readline().decode().split()))
                rows.append([vals[i] for i in xyz_idx])
            return np.array(rows, dtype=np.float64)

        endian = "<" if "little" in fmt else ">"
        row_fmt = endian + "".join(_FMT.get(t, "f") for _, t in props)
        row_size = struct.calcsize(row_fmt)
        rows = []
        for _ in range(n_verts):
            vals = struct.unpack(row_fmt, fh.read(row_size))
            rows.append([vals[i] for i in xyz_idx])
        return np.array(rows, dtype=np.float64)


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


def align(pred: np.ndarray, gt: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Align *pred* to *gt* without correspondence:
      1. Subtract each cloud's centroid.
      2. Scale pred so its bounding-box diagonal = GT's diagonal.

    Returns (pred_aligned [N,3], scale_factor).
    """
    pred_c = pred.mean(axis=0)
    gt_c = gt.mean(axis=0)

    def diag(pts: np.ndarray) -> float:
        return float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))

    scale = diag(gt) / max(diag(pred), 1e-9)
    return (pred - pred_c) * scale + gt_c, scale


def icp_refine(
    pred: np.ndarray,
    gt: np.ndarray,
    max_correspondence_dist: float | None = None,
) -> np.ndarray:
    """
    Optional ICP refinement (requires open3d).
    Falls back to returning pred unchanged if open3d is not available.
    """
    try:
        import open3d as o3d
    except ImportError:
        return pred

    def _pcd(pts):
        p = o3d.geometry.PointCloud()
        p.points = o3d.utility.Vector3dVector(pts.astype(np.float64))
        return p

    if max_correspondence_dist is None:
        max_correspondence_dist = (
            float(np.linalg.norm(gt.max(axis=0) - gt.min(axis=0))) * 0.05
        )

    result = o3d.pipelines.registration.registration_icp(
        _pcd(pred),
        _pcd(gt),
        max_correspondence_distance=max_correspondence_dist,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
    )
    T = np.asarray(result.transformation)
    pred_h = np.hstack([pred, np.ones((len(pred), 1))])
    return (T @ pred_h.T).T[:, :3]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _nn_dists(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    from scipy.spatial import cKDTree

    dists, _ = cKDTree(dst).query(src, k=1)
    return dists.astype(np.float64)


def evaluate(
    pred_pts: np.ndarray,
    gt_pts: np.ndarray,
    use_icp: bool = True,
    fscore_pcts: tuple[float, ...] = (0.01, 0.02, 0.05),
) -> dict:
    """
    Evaluate pred_pts against gt_pts.

    Parameters
    ----------
    pred_pts      [N, 3] reconstructed points
    gt_pts        [M, 3] ground-truth points
    use_icp       attempt ICP refinement after centroid+scale alignment
    fscore_pcts   F-score thresholds as fraction of GT bounding-box diagonal
                  (0.01 = 1 %, 0.02 = 2 %, 0.05 = 5 %)

    Returns a flat dict of metric values.
    """
    if len(pred_pts) == 0:
        return {"error": "empty prediction"}

    pred_a, scale = align(pred_pts, gt_pts)

    alignment = "centroid+scale"
    if use_icp:
        pred_icp = icp_refine(pred_a, gt_pts)
        if not np.allclose(pred_icp, pred_a):
            pred_a = pred_icp
            alignment += "+ICP"

    d_p2g = _nn_dists(pred_a, gt_pts)
    d_g2p = _nn_dists(gt_pts, pred_a)

    gt_diag = float(np.linalg.norm(gt_pts.max(axis=0) - gt_pts.min(axis=0)))

    results: dict = {
        "alignment": alignment,
        "scale_factor": round(scale, 6),
        "num_pred": int(len(pred_pts)),
        "num_gt": int(len(gt_pts)),
        "gt_diagonal": round(gt_diag, 4),
        "chamfer_pred_to_gt": round(float(d_p2g.mean()), 4),
        "chamfer_gt_to_pred": round(float(d_g2p.mean()), 4),
        "chamfer_symmetric": round(float((d_p2g.mean() + d_g2p.mean()) / 2), 4),
        "hausdorff": round(float(max(d_p2g.max(), d_g2p.max())), 4),
    }

    for pct in fscore_pcts:
        tau = pct * gt_diag
        prec = float((d_p2g <= tau).mean())
        recall = float((d_g2p <= tau).mean())
        denom = prec + recall
        f = (2 * prec * recall / denom) if denom > 0 else 0.0
        label = f"{pct * 100:.0f}%"
        results[f"precision@{label}"] = round(prec, 4)
        results[f"recall@{label}"] = round(recall, 4)
        results[f"fscore@{label}"] = round(f, 4)

    return results


def print_results(results: dict, title: str = "Evaluation") -> None:
    """
    Print evaluation results in a box whose width is computed from the
    actual content — the right border is never misaligned.
    """
    INDENT = "  "
    LABEL_W = 26  # fixed label column width

    # ------------------------------------------------------------------
    # 1. Build all content strings FIRST (no printing yet)
    # ------------------------------------------------------------------
    # Each entry is ("sep", None) or ("line", text).
    items: list[tuple[str, str | None]] = []

    def _row(label: str, value: str) -> tuple[str, str]:
        return ("line", f"{label:<{LABEL_W}}{value}")

    items.append(("line", title))
    items.append(("sep", None))

    if "error" in results:
        items.append(("line", f"ERROR: {results['error']}"))
    else:
        gt_diag = results["gt_diagonal"]

        items.append(("line", "Setup"))
        items.append(
            _row(
                "Alignment",
                f"{results['alignment']}  " f"(scale = {results['scale_factor']:.4f})",
            )
        )
        items.append(
            _row(
                "Points  (pred / GT)",
                f"{results['num_pred']:,}  /  {results['num_gt']:,}",
            )
        )
        items.append(_row("GT bounding-box diagonal", f"{gt_diag:.4f} units"))

        items.append(("sep", None))
        items.append(("line", "Distance metrics  (GT units after alignment)"))
        items.append(_row("Chamfer symmetric", f"{results['chamfer_symmetric']:.6f}"))
        items.append(_row("Chamfer  pred → GT", f"{results['chamfer_pred_to_gt']:.6f}"))
        items.append(_row("Chamfer  GT → pred", f"{results['chamfer_gt_to_pred']:.6f}"))
        items.append(_row("Hausdorff", f"{results['hausdorff']:.6f}"))

        fscore_keys = sorted(
            [k for k in results if k.startswith("fscore@")],
            key=lambda k: float(k.split("@")[1].rstrip("%")),
        )
        if fscore_keys:
            items.append(("sep", None))
            items.append(("line", "F-score  (threshold = % of GT diagonal)"))
            for key in fscore_keys:
                pct_str = key[len("fscore@") :]
                pct_val = float(pct_str.rstrip("%")) / 100.0
                tau = pct_val * gt_diag
                f = results[key]
                p = results.get(f"precision@{pct_str}", 0.0)
                r = results.get(f"recall@{pct_str}", 0.0)
                label = f"@ {pct_str}  (τ = {tau:.4f})"
                value = f"F = {f:.4f}   P = {p:.4f}   R = {r:.4f}"
                items.append(_row(label, value))

    # ------------------------------------------------------------------
    # 2. Measure — box width = longest content line + 2 spaces padding
    # ------------------------------------------------------------------
    W = max(len(text) for kind, text in items if kind == "line") + 2

    # ------------------------------------------------------------------
    # 3. Render — every content line is padded to exactly W characters
    # ------------------------------------------------------------------
    top = f"{INDENT}┌{'─' * (W + 2)}┐"
    sep = f"{INDENT}├{'─' * (W + 2)}┤"
    bot = f"{INDENT}└{'─' * (W + 2)}┘"

    print(top)
    for kind, text in items:
        if kind == "sep":
            print(sep)
        else:
            print(f"{INDENT}│ {text:<{W}} │")
    print(bot)


def print_results_compact(results: dict, title: str = "Evaluation") -> None:
    """
    Print evaluation results as plain ASCII key=value lines.

    Designed to be pasted directly into an LLM prompt:
      - no Unicode box-drawing characters
      - one metric per line with a fixed label column
      - a single SUMMARY line with the headline numbers
      - delimited by --- so the block is easy to locate
    """
    L = 14  # label column width

    print(f"--- {title} ---")

    if "error" in results:
        print(f"ERROR: {results['error']}")
        print("---")
        return

    gt_diag = results["gt_diagonal"]

    print(f"{'alignment:':{L}} {results['alignment']}  scale={results['scale_factor']:.4f}")
    print(f"{'points:':{L}} pred={results['num_pred']:,}  gt={results['num_gt']:,}")
    print(f"{'gt_diagonal:':{L}} {gt_diag:.4f} units")
    print(f"{'chamfer_sym:':{L}} {results['chamfer_symmetric']:.6f}")
    print(f"{'chamfer_p2g:':{L}} {results['chamfer_pred_to_gt']:.6f}")
    print(f"{'chamfer_g2p:':{L}} {results['chamfer_gt_to_pred']:.6f}")
    print(f"{'hausdorff:':{L}} {results['hausdorff']:.6f}")

    fscore_keys = sorted(
        [k for k in results if k.startswith("fscore@")],
        key=lambda k: float(k.split("@")[1].rstrip("%")),
    )
    summary_parts: list[str] = []
    for key in fscore_keys:
        pct_str = key[len("fscore@"):]
        pct_val = float(pct_str.rstrip("%")) / 100.0
        tau = pct_val * gt_diag
        f = results[key]
        p = results.get(f"precision@{pct_str}", 0.0)
        r = results.get(f"recall@{pct_str}", 0.0)
        label = f"fscore@{pct_str}:"
        print(f"{label:{L}} F={f:.4f}  P={p:.4f}  R={r:.4f}  tau={tau:.4f}")
        summary_parts.append(f"F@{pct_str}={f:.4f}")

    summary_parts.append(f"chamfer={results['chamfer_symmetric']:.4f}")
    summary_parts.append(f"pts={results['num_pred']:,}")
    print(f"SUMMARY: {' '.join(summary_parts)}")
    print("---")


def save_results(results: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
