#!/usr/bin/env python3
"""
Reliable web viewer using Plotly.js
"""

import os
import glob
import json
from pathlib import Path
import struct


def convert_ply_to_json_ultra_simple(ply_path, max_points=10000):
    """Convert PLY file to JSON (ultra simple for web)"""
    points = []
    colors = []
    
    try:
        with open(ply_path, 'rb') as f:
            lines = []
            while True:
                line = f.readline().decode('utf-8').strip()
                lines.append(line)
                if line == 'end_header':
                    break
            
            vertex_count = 0
            has_color = False
            for line in lines:
                if line.startswith('element vertex'):
                    vertex_count = int(line.split()[-1])
                if 'red' in line:
                    has_color = True
            
            for i in range(min(vertex_count, max_points)):
                xyz = struct.unpack('fff', f.read(12))
                points.append(xyz)
                
                if has_color:
                    rgb = struct.unpack('BBB', f.read(3))
                    colors.append(f'rgb({rgb[0]},{rgb[1]},{rgb[2]})')
                else:
                    colors.append('rgb(100,150,200)')
        
        return points, colors
    except Exception as e:
        print(f"Error: {e}")
        return [], []


def generate_html_plotly(output_dir="outputs"):
    """Generate using Plotly (very reliable)"""
    point_clouds_dir = os.path.join(output_dir, "point_clouds")
    
    ply_files = sorted(glob.glob(os.path.join(point_clouds_dir, "*.ply")))
    
    if not ply_files:
        print("❌ No point clouds found!")
        return
    
    print(f"\n📦 Generating Plotly-based HTML viewer...")
    print(f"   Found {len(ply_files)} point clouds")
    
    # Convert all clouds
    clouds_data = {}
    for i, ply_path in enumerate(ply_files):
        basename = os.path.basename(ply_path).replace('.ply', '')
        print(f"   [{i+1}/{len(ply_files)}] Converting {basename[:40]}...")
        
        points, colors = convert_ply_to_json_ultra_simple(ply_path)
        
        if points:
            metrics_path = ply_path.replace("/point_clouds/", "/evaluations/").replace(".ply", ".json")
            metrics = {}
            if os.path.exists(metrics_path):
                with open(metrics_path) as f:
                    metrics = json.load(f)
            
            clouds_data[basename] = {
                'points': points,
                'colors': colors,
                'metrics': metrics
            }
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Point Cloud Viewer</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; background: #1a1a2e; }}
        .container {{ display: flex; height: 100vh; }}
        .sidebar {{
            width: 200px;
            background: #f8f9fa;
            padding: 15px;
            overflow-y: auto;
            border-right: 1px solid #ddd;
        }}
        .main {{ flex: 1; display: flex; flex-direction: column; }}
        h1 {{ padding: 20px; color: white; text-align: center; }}
        #plot {{ flex: 1; }}
        .cloud-btn {{
            width: 100%;
            padding: 10px;
            margin: 5px 0;
            background: white;
            border: 2px solid #ddd;
            border-radius: 5px;
            cursor: pointer;
            text-align: left;
            font-size: 12px;
            transition: all 0.2s;
        }}
        .cloud-btn:hover {{ background: #e8ecff; border-color: #667eea; }}
        .cloud-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
        .metrics {{
            padding: 15px;
            background: white;
            border-top: 1px solid #ddd;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
        }}
        .metric {{
            text-align: center;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .metric-label {{ font-size: 12px; color: #666; }}
        .metric-value {{ font-size: 18px; font-weight: bold; color: #667eea; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar" id="sidebar"></div>
        <div class="main">
            <h1>🔷 3D Point Cloud Viewer</h1>
            <div id="plot"></div>
            <div class="metrics" id="metrics"></div>
        </div>
    </div>

    <script>
        const cloudsData = {json.dumps(clouds_data)};
        const cloudNames = Object.keys(cloudsData);
        
        function loadCloud(name) {{
            const cloud = cloudsData[name];
            const points = cloud.points;
            const colors = cloud.colors;
            const metrics = cloud.metrics;
            
            if (!points || points.length === 0) {{
                alert('No points in this cloud');
                return;
            }}
            
            // Extract coordinates
            const x = points.map(p => p[0]);
            const y = points.map(p => p[1]);
            const z = points.map(p => p[2]);
            
            // Create scatter plot
            const trace = {{
                x: x,
                y: y,
                z: z,
                mode: 'markers',
                marker: {{
                    size: 2,
                    color: colors,
                    opacity: 0.8
                }},
                type: 'scatter3d'
            }};
            
            const layout = {{
                title: name,
                scene: {{
                    xaxis: {{ title: 'X' }},
                    yaxis: {{ title: 'Y' }},
                    zaxis: {{ title: 'Z' }},
                    aspectmode: 'data'
                }},
                margin: {{ l: 0, r: 0, t: 40, b: 0 }}
            }};
            
            Plotly.newPlot('plot', [trace], layout, {{responsive: true}});
            
            // Update metrics
            const metricsDiv = document.getElementById('metrics');
            metricsDiv.innerHTML = `
                <div class="metric">
                    <div class="metric-label">Points</div>
                    <div class="metric-value">${{points.length.toLocaleString()}}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Chamfer (cm)</div>
                    <div class="metric-value">${{(metrics.chamfer_distance || 0).toFixed(2)}}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">F-Score</div>
                    <div class="metric-value">${{(metrics.f_score || 0).toFixed(3)}}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Complete %</div>
                    <div class="metric-value">${{((metrics.completeness || 0)*100).toFixed(0)}}</div>
                </div>
            `;
            
            // Update buttons
            document.querySelectorAll('.cloud-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector('[data-name="' + name + '"]').classList.add('active');
        }}
        
        // Create sidebar buttons
        const sidebar = document.getElementById('sidebar');
        cloudNames.forEach(name => {{
            const btn = document.createElement('button');
            btn.className = 'cloud-btn' + (cloudNames.indexOf(name) === 0 ? ' active' : '');
            btn.textContent = name.substring(0, 22) + '...';
            btn.title = name;
            btn.dataset.name = name;
            btn.onclick = () => loadCloud(name);
            sidebar.appendChild(btn);
        }});
        
        // Load first cloud
        if (cloudNames.length > 0) {{
            loadCloud(cloudNames[0]);
        }}
    </script>
</body>
</html>
"""
    
    output_path = os.path.join(output_dir, "point_cloud_viewer_simple.html")
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"\n✅ Viewer generated: {output_path}")
    return output_path


if __name__ == "__main__":
    output_path = generate_html_plotly()
    if output_path:
        import webbrowser
        try:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")
            print("🌐 Opened in browser!")
        except:
            print(f"Open this file in your browser: {output_path}")
