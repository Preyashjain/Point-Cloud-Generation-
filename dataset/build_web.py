#!/usr/bin/env python3
"""
Collect all evaluation_*.json files from the outputs/ directory and write a
self-contained HTML report with an embedded JavaScript data table.

Run after you have run `src/main.py` script.

Usage:
    python build_web.py
    python build_web.py --outputs outputs/ --out eval_report.html
"""

import argparse
import json
import sys
from pathlib import Path


def collect(outputs_dir: Path) -> list[dict]:
    rows = []
    for p in sorted(outputs_dir.rglob("evaluation_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        tag = p.stem[len("evaluation_") :]
        sample_id = "/".join(p.relative_to(outputs_dir).parent.parts)
        rows.append({"sample_id": sample_id, "tag": tag, **data})
    return rows


_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Eval Report</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Consolas,Menlo,monospace;font-size:12px;background:#0d1117;color:#c9d1d9;padding:20px}
h1{font-size:16px;color:#58a6ff;margin-bottom:3px}
.sub{color:#8b949e;margin-bottom:12px;font-size:11px}
.bar{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
input,select{background:#161b22;color:#c9d1d9;border:1px solid #30363d;
             padding:4px 7px;outline:none;font:inherit}
input:focus,select:focus{border-color:#58a6ff}
input{width:240px}
#count{color:#8b949e;font-size:11px}
table{border-collapse:collapse;width:100%}
th{background:#161b22;padding:5px 9px;text-align:left;
   border:1px solid #30363d;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{background:#1c2128}
th.asc::after{content:" ▲";color:#58a6ff}
th.desc::after{content:" ▼";color:#58a6ff}
td{padding:4px 9px;border:1px solid #21262d;white-space:nowrap}
tr:nth-child(even) td{background:#090d13}
tr:hover td{background:#1c2128!important}
.sp{color:#79c0ff}.de{color:#d2a8ff}
.g{color:#56d364}.y{color:#e3b341}.r{color:#f85149}.dim{color:#4a5568}
ol{padding-left:3em}
code{font-family:monospace;color:lightgray}
.leg{border-collapse:collapse;width:100%;margin-top:4px}
.leg th{background:#161b22;padding:5px 9px;border:1px solid #30363d;
        text-align:left;white-space:nowrap;font-weight:bold}
.leg td{padding:5px 9px;border:1px solid #21262d;vertical-align:top;line-height:1.5}
.leg tr:nth-child(even) td{background:#090d13}
.cn{color:#e3b341;white-space:nowrap;font-weight:bold}
</style>
</head>
<body>
<h1>Point Cloud Evaluation Report</h1>
<div class="sub" id="sub"></div>
<div class="bar">
  <input id="q" placeholder="filter sample…" oninput="render()">
  <select id="tag" onchange="render()">
    <option value="">all tags</option>
    <option value="sparse">sparse</option>
    <option value="dense">dense</option>
  </select>
  <span id="count"></span>
</div>
<table>
<thead><tr>
  <th onclick="sort('sample_id')">Sample</th>
  <th onclick="sort('tag')">Type</th>
  <th onclick="sort('scale_factor')">Scale</th>
  <th onclick="sort('num_pred')">Pred pts</th>
  <th onclick="sort('num_gt')">GT pts</th>
  <th onclick="sort('chamfer_symmetric')">Chamfer ↓</th>
  <th onclick="sort('hausdorff')">Hausdorff ↓</th>
  <th onclick="sort('f1')">F@1%</th>
  <th onclick="sort('f2')">F@2%</th>
  <th onclick="sort('f5')">F@5% ↑</th>
  <th onclick="sort('p5')">P@5%</th>
  <th onclick="sort('r5')">R@5%</th>
  <th onclick="sort('alignment')">Alignment</th>
</tr></thead>
<tbody id="tb"></tbody>
</table>
<br>
<h2 style="color:#58a6ff;font-size:14px;margin-bottom:8px">Column Reference</h2>
<table class="leg">
<thead><tr>
  <th>Column</th>
  <th>What it measures</th>
  <th>Unit / range</th>
  <th>Ideal value</th>
  <th>Color thresholds</th>
</tr></thead>
<tbody>
<tr>
  <td class="cn">Sample</td>
  <td>Dataset identifier: object / scenario / orientation</td>
  <td>—</td>
  <td>—</td>
  <td>—</td>
</tr>
<tr>
  <td class="cn">Type</td>
  <td><span class="sp">sparse</span> = SfM feature-point cloud only.
      <span class="de">dense</span> = depth-model densification added on top</td>
  <td>—</td>
  <td>dense preferred for full coverage</td>
  <td>—</td>
</tr>
<tr>
  <td class="cn">Scale</td>
  <td>GT bounding-box diagonal ÷ pred diagonal after centroid alignment.
      Reflects how well the focal length is calibrated. &lt;1 means pred is
      too large (focal too short); &gt;1 means pred is too small (focal too long).</td>
  <td>dimensionless</td>
  <td class="g">1.000</td>
  <td><span class="g">±10%</span> · <span class="y">±30%</span> · <span class="r">else</span></td>
</tr>
<tr>
  <td class="cn">Pred pts</td>
  <td>Number of predicted 3D points after all filters. More is generally
      better for coverage, but quality matters more than quantity.</td>
  <td>integer</td>
  <td>dense: 200K–1M; sparse: 5K–50K</td>
  <td>—</td>
</tr>
<tr>
  <td class="cn">GT pts</td>
  <td>Number of laser-scan ground-truth points. Fixed per sample.</td>
  <td>integer</td>
  <td>—</td>
  <td>—</td>
</tr>
<tr>
  <td class="cn">Chamfer ↓</td>
  <td>Symmetric mean nearest-neighbour distance: average over all pred→GT
      distances and all GT→pred distances, then averaged. The primary
      continuous quality metric — penalises both inaccurate points and
      missing surface coverage equally.</td>
  <td>mm (GT units)</td>
  <td class="g">&lt; 10 mm</td>
  <td><span class="g">&lt;10</span> · <span class="y">&lt;20</span> · <span class="r">≥20</span></td>
</tr>
<tr>
  <td class="cn">Hausdorff ↓</td>
  <td>Worst-case nearest-neighbour distance: the single largest gap between
      any GT point and its closest predicted point (or vice-versa). Very
      sensitive to outliers and unscanned regions.</td>
  <td>mm (GT units)</td>
  <td class="g">&lt; 40 mm</td>
  <td><span class="g">&lt;40</span> · <span class="y">&lt;80</span> · <span class="r">≥80</span></td>
</tr>
<tr>
  <td class="cn">F@1%</td>
  <td>F-score at τ = 1% of GT diagonal (≈2.3 mm for this dataset).
      A strict threshold — only sub-millimetre-accurate points count.
      Sparse clouds rarely exceed 0.10 here.</td>
  <td>0–1</td>
  <td class="g">≥ 0.50</td>
  <td><span class="g">≥0.50</span> · <span class="y">≥0.30</span> · <span class="r">&lt;0.30</span></td>
</tr>
<tr>
  <td class="cn">F@2%</td>
  <td>F-score at τ = 2% of GT diagonal (≈4.6 mm). Medium threshold,
      the main balance point between precision and recall.</td>
  <td>0–1</td>
  <td class="g">≥ 0.50</td>
  <td><span class="g">≥0.50</span> · <span class="y">≥0.30</span> · <span class="r">&lt;0.30</span></td>
</tr>
<tr>
  <td class="cn">F@5% ↑</td>
  <td>F-score at τ = 5% of GT diagonal (≈11.4 mm). The headline benchmark
      metric used to compare methods. Harmonic mean of P@5% and R@5%.
      Best single number for overall reconstruction quality.</td>
  <td>0–1</td>
  <td class="g">≥ 0.50 (dense)</td>
  <td><span class="g">≥0.50</span> · <span class="y">≥0.30</span> · <span class="r">&lt;0.30</span></td>
</tr>
<tr>
  <td class="cn">P@5%</td>
  <td>Precision at 5%: fraction of predicted points that land within τ of
      any GT point. High precision = few outlier/floating points.
      Low precision = the cloud is noisy or geometrically wrong.</td>
  <td>0–1</td>
  <td class="g">≥ 0.50</td>
  <td><span class="g">≥0.50</span> · <span class="y">≥0.30</span> · <span class="r">&lt;0.30</span></td>
</tr>
<tr>
  <td class="cn">R@5%</td>
  <td>Recall at 5%: fraction of GT points that have at least one predicted
      point within τ nearby. High recall = good surface coverage.
      Low recall = large parts of the object are missing.</td>
  <td>0–1</td>
  <td class="g">≥ 0.50</td>
  <td><span class="g">≥0.50</span> · <span class="y">≥0.30</span> · <span class="r">&lt;0.30</span></td>
</tr>
<tr>
  <td class="cn">Alignment</td>
  <td>Method used to align pred to GT before computing metrics.
      <em>centroid+scale</em>: translate to same centroid, then scale pred
      bounding box to match GT. <em>+ICP</em>: iterative closest point
      refinement applied afterward (requires open3d).</td>
  <td>—</td>
  <td>centroid+scale+ICP</td>
  <td>—</td>
</tr>
</tbody>
</table>

<br>
<h2 style="color:#58a6ff;font-size:14px;margin-bottom:8px">Reading the numbers at a glance</h2>
<table class="leg">
<thead><tr><th>Symptom</th><th>Likely cause</th><th>Fix</th></tr></thead>
<tbody>
<tr><td>Scale ≪ 1 (e.g. 0.4)</td><td>Focal length set too short → triangulated cloud is too large</td><td>Increase <code>focal_length_mm</code>; use scale-hint formula: f_new = f / √scale</td></tr>
<tr><td>Scale ≫ 1 (e.g. 1.5)</td><td>Focal length set too long → cloud is too small</td><td>Decrease <code>focal_length_mm</code></td></tr>
<tr><td>High P, low R</td><td>Cloud is precise but incomplete — missing surface area</td><td>Run with <code>--depth</code>; lower <code>frame_stride</code></td></tr>
<tr><td>Low P, high R</td><td>Many outlier/ghost points — cloud is noisy</td><td>Tighten SOR (<code>--outlier-std 2.0</code>); check focal length</td></tr>
<tr><td>High Hausdorff, ok Chamfer</td><td>One large unscanned region or a cluster of outliers far away</td><td>Density filter removes outliers; depth pass fills gaps</td></tr>
<tr><td>sparse ≈ dense quality</td><td>Depth model not improving coverage — likely bad depth scale reference</td><td>Inspect sparse P: if &lt; 0.3 the sparse is too noisy to guide depth</td></tr>
</tbody>
</table>

<br>
<h2 style="color:#58a6ff;font-size:14px;margin-bottom:6px">How it works</h2>
<p>The pipeline is implemented the following way:</p>
<ol>
  <li>Video Frame extraction (Size: 3840x2160, Stride: 5)</li>
  <li>Feature extraction using SuperPoint</li>
  <li>Feature matching using LightGlue</li>
  <li>Camera matrix reconstruction using the following info from the dataset README.txt "The videos were captured
    using an orbit rig with a Nikon D780 camera at 41 cm height, 45° inclination, 40 cm horizontal distance to the
    platform center axis.". We always assume an orbital video uniformly covering the object</li>
  <li>Triangulation with Hierarchical Localization (HLoc), such that keypoints are shared across multiple frames</li>
  <li>Apply statistical outlier removal (SOR) algorithm to remove points too far away from standard deviation times
    some factor plus its mean</li>
  <li>All points too far away from world center are also discarded</li>
  <li>Lastly points are filtered by density. All outliers are filtered out, while correctly captured points are kept
  </li>
  <li>Then an output is created for those sparsely collected and filtered points</li>
  <li>Additionally, with the <code>--depth</code> flag set, the points are then given to the Depth Anything v2 model
    to densify the points. The points are then downsampled using voxels of 2mm</li>
</ol>
<script>
const DATA = __RESULTS_JSON__;

DATA.forEach(r => {
  r.f1 = r['fscore@1%']    ?? null;
  r.f2 = r['fscore@2%']    ?? null;
  r.f5 = r['fscore@5%']    ?? null;
  r.p5 = r['precision@5%'] ?? null;
  r.r5 = r['recall@5%']    ?? null;
});

const samples = new Set(DATA.map(r => r.sample_id)).size;
document.getElementById('sub').textContent =
  DATA.length + ' result(s) across ' + samples + ' sample(s)';

let sk = 'sample_id', sd = 1;

function sort(k) {
  if (sk === k) sd *= -1; else { sk = k; sd = 1; }
  document.querySelectorAll('th').forEach(th => th.className = '');
  const keys = ['sample_id','tag','scale_factor','num_pred','num_gt',
                 'chamfer_symmetric','hausdorff','f1','f2','f5','p5','r5','alignment'];
  const th = document.querySelectorAll('th')[keys.indexOf(k)];
  if (th) th.className = sd === 1 ? 'asc' : 'desc';
  render();
}

const fF = v => {
  if (v == null) return '<span class="dim">—</span>';
  const c = v >= 0.5 ? 'g' : v >= 0.3 ? 'y' : 'r';
  return '<span class="' + c + '">' + v.toFixed(3) + '</span>';
};
const fC = v => {
  if (v == null) return '<span class="dim">—</span>';
  const c = v < 10 ? 'g' : v < 20 ? 'y' : 'r';
  return '<span class="' + c + '">' + v.toFixed(2) + '</span>';
};
const fH = v => {
  if (v == null) return '<span class="dim">—</span>';
  const c = v < 40 ? 'g' : v < 80 ? 'y' : 'r';
  return '<span class="' + c + '">' + v.toFixed(1) + '</span>';
};
const fS = v => {
  if (v == null) return '<span class="dim">—</span>';
  const d = Math.abs(v - 1);
  const c = d < 0.1 ? 'g' : d < 0.3 ? 'y' : 'r';
  return '<span class="' + c + '">' + v.toFixed(3) + '</span>';
};
const fN = v => {
  if (v == null) return '<span class="dim">—</span>';
  if (v >= 1e6) return (v/1e6).toFixed(2)+'M';
  if (v >= 1e3) return (v/1e3).toFixed(1)+'K';
  return String(v);
};

function render() {
  const q   = document.getElementById('q').value.toLowerCase();
  const tag = document.getElementById('tag').value;
  let rows  = DATA.filter(r =>
    r.sample_id.toLowerCase().includes(q) &&
    (tag === '' || r.tag === tag)
  );
  rows.sort((a, b) => {
    let va = a[sk] ?? '', vb = b[sk] ?? '';
    return typeof va === 'string' ? sd * va.localeCompare(vb) : sd * (va - vb);
  });
  document.getElementById('count').textContent = rows.length + ' shown';
  document.getElementById('tb').innerHTML = rows.map(r => {
    const tc = r.tag === 'sparse' ? 'sp' : 'de';
    return '<tr><td>' + r.sample_id +
      '</td><td class="' + tc + '">' + r.tag +
      '</td><td>' + fS(r.scale_factor) +
      '</td><td>' + fN(r.num_pred) +
      '</td><td>' + fN(r.num_gt) +
      '</td><td>' + fC(r.chamfer_symmetric) +
      '</td><td>' + fH(r.hausdorff) +
      '</td><td>' + fF(r.f1) +
      '</td><td>' + fF(r.f2) +
      '</td><td>' + fF(r.f5) +
      '</td><td>' + fF(r.p5) +
      '</td><td>' + fF(r.r5) +
      '</td><td class="dim">' + (r.alignment || '—') + '</td></tr>';
  }).join('');
}

render();
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build a self-contained HTML evaluation report"
    )
    ap.add_argument(
        "--outputs",
        default="outputs",
        metavar="DIR",
        help="root directory to scan for evaluation JSON files (default: outputs)",
    )
    ap.add_argument(
        "--out",
        default="eval_report.html",
        metavar="FILE",
        help="output HTML path (default: eval_report.html)",
    )
    args = ap.parse_args()

    outputs_dir = Path(args.outputs)
    if not outputs_dir.exists():
        print(f"error: '{outputs_dir}' not found", file=sys.stderr)
        sys.exit(1)

    rows = collect(outputs_dir)
    if not rows:
        print("no evaluation_*.json files found under", outputs_dir)
        sys.exit(0)

    html = _HTML.replace(
        "__RESULTS_JSON__",
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
    )

    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {len(rows)} result(s) → {out}")


if __name__ == "__main__":
    main()
