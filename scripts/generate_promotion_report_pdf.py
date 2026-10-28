"""
Generates a professional PDF report for:
SHM-AI — Promoting YOLOv8 Crack Detection from Preview to Production
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = PROJECT_ROOT.parent

HTML_OUT_PATH = PROJECT_ROOT / "reports" / "SHM_AI_YOLOv8_Production_Promotion_Report.html"
PDF_OUT_PROJECT = PROJECT_ROOT / "reports" / "SHM_AI_YOLOv8_Production_Promotion_Report.pdf"
PDF_OUT_PARENT = PARENT_DIR / "SHM_AI_YOLOv8_Production_Promotion_Report.pdf"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SHM-AI — Promoting YOLOv8 Crack Detection to Production</title>
<style>
  @page {
    size: A4;
    margin: 18mm 15mm 18mm 15mm;
    @bottom-right {
      content: counter(page);
    }
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background-color: #ffffff;
    line-height: 1.5;
    font-size: 10.5pt;
    margin: 0;
    padding: 0;
  }

  .header {
    border-bottom: 2px solid #0284c7;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }

  .header-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .brand {
    font-size: 18pt;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.5px;
    margin: 0;
  }

  .brand span {
    color: #0284c7;
  }

  .doc-tag {
    background: #e0f2fe;
    color: #0369a1;
    font-size: 8pt;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .title {
    font-size: 15pt;
    font-weight: 700;
    color: #0f172a;
    margin: 8px 0 4px 0;
  }

  .subtitle {
    font-size: 9.5pt;
    color: #64748b;
    margin: 0;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 16px 0 24px 0;
    font-size: 8.5pt;
  }

  .meta-item strong {
    display: block;
    color: #64748b;
    font-size: 7.5pt;
    text-transform: uppercase;
    margin-bottom: 2px;
  }

  h2 {
    font-size: 12pt;
    font-weight: 700;
    color: #0f172a;
    border-left: 3.5px solid #0284c7;
    padding-left: 8px;
    margin: 22px 0 10px 0;
    page-break-after: avoid;
  }

  h3 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #334155;
    margin: 14px 0 6px 0;
    page-break-after: avoid;
  }

  p {
    margin: 0 0 10px 0;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 18px 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
  }

  th {
    background-color: #f1f5f9;
    color: #334155;
    text-align: left;
    font-weight: 700;
    padding: 8px 10px;
    border: 1px solid #cbd5e1;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  td {
    padding: 7px 10px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
  }

  tr:nth-child(even) td {
    background-color: #f8fafc;
  }

  .badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 7.5pt;
  }

  .badge-success { background: #dcfce7; color: #15803d; }
  .badge-warning { background: #fef3c7; color: #b45309; }
  .badge-info { background: #e0f2fe; color: #0369a1; }
  .badge-neutral { background: #f1f5f9; color: #475569; }

  .callout {
    border-left: 3px solid;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    margin: 14px 0;
    font-size: 9pt;
    page-break-inside: avoid;
  }

  .callout-info {
    border-color: #0284c7;
    background-color: #f0f9ff;
    color: #0c4a6e;
  }

  .callout-warning {
    border-color: #d97706;
    background-color: #fffbeb;
    color: #78350f;
  }

  .callout-success {
    border-color: #16a34a;
    background-color: #f0fdf4;
    color: #14532d;
  }

  .callout strong {
    display: block;
    margin-bottom: 3px;
    font-size: 9pt;
  }

  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 8pt;
    background: #f1f5f9;
    padding: 2px 4px;
    border-radius: 3px;
    color: #0f172a;
    border: 1px solid #e2e8f0;
  }

  ul, ol {
    margin: 0 0 12px 0;
    padding-left: 20px;
  }

  li {
    margin-bottom: 4px;
  }

  .step-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 10px;
    page-break-inside: avoid;
  }

  .step-title {
    font-weight: 700;
    color: #0f172a;
    font-size: 9.5pt;
    margin-bottom: 4px;
  }

  .flow-box {
    background: #f8fafc;
    border: 1px dashed #94a3b8;
    border-radius: 6px;
    padding: 10px;
    text-align: center;
    font-family: ui-monospace, Consolas, monospace;
    font-size: 8pt;
    color: #334155;
    margin: 12px 0;
  }

  .page-break {
    page-break-before: always;
  }
</style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    <div class="header-top">
      <div class="brand">SHM<span>-AI</span></div>
      <div class="doc-tag">Promotion Technical Audit</div>
    </div>
    <div class="title">Engineering Report: Promoting YOLOv8 Crack Detection to Production</div>
    <div class="subtitle">Architectural Comparison, Safety Verification, Downstream Impact, and Promotion Plan</div>
  </div>

  <!-- Metadata Grid -->
  <div class="meta-grid">
    <div class="meta-item">
      <strong>Target Model</strong>
      YOLOv8 Nano (best.pt)
    </div>
    <div class="meta-item">
      <strong>Promotion Scope</strong>
      Preview &rarr; Production
    </div>
    <div class="meta-item">
      <strong>Active Git Commit</strong>
      <code>5a1a30a</code> (main)
    </div>
    <div class="meta-item">
      <strong>Report Date</strong>
      October 27, 2026
    </div>
  </div>

  <!-- Section 1 -->
  <h2>1. Executive Summary & Configuration Comparison</h2>
  <p>
    The SHM-AI Preview backend (<code>https://shm-ai-preview.onrender.com</code>) successfully runs a domain-specific YOLOv8 crack-detection model that detects structural cracks with ~53.4% confidence (59.9 ms CPU inference), replacing the unvalidated baseline YOLO11 COCO model which suffered from domain blindness and caused a false 100% health score.
  </p>
  <p>
    An audit of the codebase confirms that <strong>both Preview and Production run the exact same Git commit</strong> (<code>5a1a30a</code> on <code>main</code>). All code necessary to support YOLOv8 detection-only mode is already present and verified in Production. The only difference is the <strong>environment variable configuration on Render</strong>.
  </p>

  <table>
    <thead>
      <tr>
        <th>Attribute</th>
        <th>Preview Backend (shm-ai-preview)</th>
        <th>Production Backend (infralytiq)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Active Model</strong></td>
        <td><code>best.pt</code> <span class="badge badge-success">YOLOv8 Nano</span></td>
        <td><code>yolo11n-seg.pt</code> <span class="badge badge-warning">COCO Base</span></td>
      </tr>
      <tr>
        <td><strong>Model Task</strong></td>
        <td><code>detect</code> (Bounding Boxes + Confidence)</td>
        <td><code>segment</code> (Bounding Boxes + Masks)</td>
      </tr>
      <tr>
        <td><strong>Trained Classes</strong></td>
        <td><code>{0: 'crack'}</code> (Domain-Specific)</td>
        <td>80 General COCO Classes (No Defects)</td>
      </tr>
      <tr>
        <td><strong>Weights Source</strong></td>
        <td>Hugging Face (<code>cazzz307/yolov8-crack-detection</code>)</td>
        <td>Ultralytics Official Release Assets</td>
      </tr>
      <tr>
        <td><strong>Render Env Vars</strong></td>
        <td><code>DEFAULT_MODEL_NAME=best.pt</code><br><code>HF_TOKEN=&lt;secret&gt;</code></td>
        <td><em>Not configured</em> (Defaults to <code>yolo11n-seg.pt</code> in code)</td>
      </tr>
      <tr>
        <td><strong>Crack Detection</strong></td>
        <td><strong>Detected</strong> (~53.4% confidence)</td>
        <td><strong>Missed</strong> (0 detections)</td>
      </tr>
      <tr>
        <td><strong>Health Assessment</strong></td>
        <td><span class="badge badge-warning">UNVERIFIED</span> (Detection-only disclosures)</td>
        <td><span class="badge badge-warning">UNVERIFIED</span> (Model blindness safeguard)</td>
      </tr>
      <tr>
        <td><strong>Crack Width/Length</strong></td>
        <td><code>null</code> (Rendered as <code>&mdash;</code> in UI)</td>
        <td><code>null</code> (No detections)</td>
      </tr>
      <tr>
        <td><strong>CPU Latency</strong></td>
        <td>~59.9 ms</td>
        <td>~75&ndash;95 ms</td>
      </tr>
    </tbody>
  </table>

  <!-- Section 2 -->
  <h2>2. Runtime Loading & Inference Flow in Preview</h2>
  <div class="flow-box">
    Render Build (scripts/render_build.sh) &rarr; scripts/download_weights.py --yes &rarr; Hugging Face (best.pt)<br>
    &darr;<br>
    YOLO11Detector loads best.pt (Task: detect) &rarr; CVInferencePipeline (mask: None) &rarr; StructuralAssessmentService (UNVERIFIED)
  </div>
  <ul>
    <li><strong>Weight Download:</strong> <code>scripts/download_weights.py</code> detects <code>DEFAULT_MODEL_NAME=best.pt</code> and fetches the 6.25 MB weight file using the <code>HF_TOKEN</code> secret. The custom <code>SafeAuthRedirectHandler</code> strips auth credentials upon CDN redirect.</li>
    <li><strong>Task Assertion:</strong> Ultralytics validates that <code>best.pt</code> has <code>task == 'detect'</code> and saves it to <code>weights/best.pt</code>.</li>
    <li><strong>Graceful Bounding-Box Mode:</strong> <code>CVInferencePipeline</code> notices <code>raw.mask is None</code> and computes bounding-box area envelope, setting length and width to <code>None</code> without fabricating measurements.</li>
    <li><strong>Assessment Safeguard:</strong> <code>StructuralAssessmentService</code> checks <code>supports_segmentation</code>. Because it is <code>False</code>, it authoritatively returns <code>status = "unverified"</code> and <code>health_score = None</code>, preventing misleading 100/100 scores.</li>
  </ul>

  <div class="page-break"></div>

  <!-- Section 3 -->
  <h2>3. Production Compatibility & Exact Promotion Changes</h2>
  <div class="callout callout-success">
    <strong>Zero Code Changes Required in Git</strong>
    Because commits <code>4897a9d</code>, <code>f47e7c4</code>, and <code>5a1a30a</code> are already merged to <code>main</code>, Production code is 100% ready for YOLOv8. Promotion is achieved strictly through Render environment variables.
  </div>

  <h3>Recommended Promotion Path (Render Dashboard Switch)</h3>
  <div class="step-card">
    <div class="step-title">Step 1: Set Production Environment Variables on Render</div>
    <p>Navigate to <strong>Render Dashboard &rarr; Service: infralytiq &rarr; Environment</strong> and add:</p>
    <ul>
      <li><code>DEFAULT_MODEL_NAME</code> = <code>best.pt</code></li>
      <li><code>HF_TOKEN</code> = <code>&lt;your_huggingface_read_token&gt;</code></li>
    </ul>
  </div>

  <div class="step-card">
    <div class="step-title">Step 2: Deploy Production Service</div>
    <p>Click <strong>Manual Deploy &rarr; Clear build cache &amp; deploy</strong>. The build script will automatically download and verify <code>best.pt</code>.</p>
  </div>

  <div class="step-card">
    <div class="step-title">Step 3: Post-Deployment Smoke Verification</div>
    <p>Upload the crack inspection image at <code>https://shm-ai.vercel.app</code> and verify that crack bounding boxes and ~53.4% confidence appear.</p>
  </div>

  <!-- Section 4 -->
  <h2>4. Impact on Segmentation-Dependent Features</h2>
  <table>
    <thead>
      <tr>
        <th>Feature</th>
        <th>Behavior with YOLOv8 Detection</th>
        <th>Safety &amp; Integrity Analysis</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Defect Localization</strong></td>
        <td>Bounding box displayed over image</td>
        <td><span class="badge badge-success">Working</span> Crack is accurately localized.</td>
      </tr>
      <tr>
        <td><strong>Crack Length &amp; Width</strong></td>
        <td>Displays as <code>&mdash;</code> in inventory table</td>
        <td><span class="badge badge-info">Honest Limitation</span> 2D bounding boxes cannot quantify crack aperture.</td>
      </tr>
      <tr>
        <td><strong>Health Score</strong></td>
        <td>Displays as <code>Unverified</code></td>
        <td><span class="badge badge-success">Safeguard Intact</span> Prevents misleading 100/100 score.</td>
      </tr>
      <tr>
        <td><strong>PDF Report Generation</strong></td>
        <td>HTTP 422 Unprocessable Entity</td>
        <td><span class="badge badge-warning">Integrity Guard</span> Blocked at <code>reports.py:143</code> because health score is unverified.</td>
      </tr>
    </tbody>
  </table>

  <!-- Section 5 -->
  <h2>5. Storage, Licensing, and Resource Footprint</h2>
  <ul>
    <li><strong>Model Size &amp; Memory:</strong> <code>best.pt</code> is 6.25 MB. Memory consumption is ~80 MB RAM, easily fitting inside Render's 512 MB free/starter tier.</li>
    <li><strong>Licensing:</strong> The weights repository (<code>cazzz307/yolov8-crack-detection</code>) is under <strong>MIT License</strong>. Underlying Ultralytics code is <strong>AGPL-3.0</strong>. Model weights are stored outside Git.</li>
  </ul>

  <!-- Section 6 -->
  <h2>6. Instant Rollback Procedure (&lt; 3 Minutes)</h2>
  <div class="callout callout-warning">
    <strong>Instant Production Rollback</strong>
    If any issue is detected in Production after switching to YOLOv8:
    <ol style="margin-top: 6px; margin-bottom: 0;">
      <li>Go to Render Dashboard &rarr; <code>infralytiq</code> &rarr; Environment.</li>
      <li>Delete <code>DEFAULT_MODEL_NAME</code> (or set it to <code>yolo11n-seg.pt</code>).</li>
      <li>Click <strong>Deploy Latest Commit</strong>. Production immediately reverts to YOLO11 in under 3 minutes.</li>
    </ol>
  </div>

  <!-- Section 7 -->
  <h2>7. Sign-Off & Recommendation</h2>
  <p>
    <strong>Recommendation:</strong> Proceed with Option A (Render environment variable configuration). It activates the proven, working crack-detection capability in Production with zero risk of breaking Git history or local development environments, while preserving an instant rollback path.
  </p>

</body>
</html>
"""


def main():
    print(f"Writing report HTML to '{HTML_OUT_PATH}'...")
    HTML_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT_PATH.write_text(HTML_CONTENT, encoding="utf-8")

    print(f"Generating PDF via headless Google Chrome...")
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_OUT_PROJECT}",
        str(HTML_OUT_PATH),
    ]

    subprocess.check_call(cmd)

    # Also copy to parent directory for easy user access
    import shutil
    shutil.copy2(PDF_OUT_PROJECT, PDF_OUT_PARENT)

    print("=" * 70)
    print("PDF REPORT GENERATION SUCCESSFUL".center(70))
    print("=" * 70)
    print(f"Project Path: {PDF_OUT_PROJECT} ({PDF_OUT_PROJECT.stat().st_size:,} bytes)")
    print(f"Parent Path:  {PDF_OUT_PARENT} ({PDF_OUT_PARENT.stat().st_size:,} bytes)")
    print("=" * 70)


if __name__ == "__main__":
    main()
