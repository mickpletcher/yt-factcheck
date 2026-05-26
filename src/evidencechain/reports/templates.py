HTML_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - EvidenceChain Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --text: #1d2433;
      --muted: #5b6475;
      --line: #d9e0ea;
      --accent: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    header, section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 18px;
    }}
    h1, h2, h3 {{
      margin: 0 0 12px;
      line-height: 1.2;
    }}
    h1 {{
      font-size: 32px;
    }}
    h2 {{
      font-size: 22px;
    }}
    h3 {{
      font-size: 18px;
    }}
    a {{
      color: #075985;
    }}
    .meta, .summary-grid, .claim-meta {{
      display: grid;
      gap: 10px;
    }}
    .meta {{
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      color: var(--muted);
    }}
    .summary-grid {{
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }}
    .bucket {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }}
    .bar {{
      height: 8px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
      margin-top: 8px;
    }}
    .fill {{
      height: 100%;
      background: var(--accent);
    }}
    .claim {{
      border-top: 1px solid var(--line);
      padding-top: 18px;
      margin-top: 18px;
    }}
    .claim:first-child {{
      border-top: 0;
      padding-top: 0;
      margin-top: 0;
    }}
    .claim-meta {{
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 12px;
    }}
    .badge {{
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 10px;
      font-size: 13px;
      color: var(--muted);
      background: #f8fafc;
    }}
    .evidence {{
      padding-left: 20px;
    }}
    .evidence li {{
      margin-bottom: 12px;
    }}
    .snippet {{
      color: var(--muted);
      margin: 4px 0 0;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <div class="meta">
        <div><strong>Video ID:</strong> {video_id}</div>
        <div><strong>Channel:</strong> {channel}</div>
        <div><strong>Generated:</strong> {generated_at}</div>
        <div><strong>Source:</strong> <a href="{youtube_url}">{youtube_url}</a></div>
      </div>
    </header>
    <section>
      <h2>Verdict Summary</h2>
      <p>{total_claims} claims checked. Average verdict confidence: {average_confidence}</p>
      <div class="summary-grid">
        {verdict_buckets}
      </div>
    </section>
    <section>
      <h2>Claims</h2>
      {claims}
    </section>
  </main>
</body>
</html>
"""

MARKDOWN_REPORT_TEMPLATE = """# {title}

Generated: {generated_at}

Video ID: `{video_id}`

Channel: {channel}

Source: {youtube_url}

## Verdict Summary

Claims checked: {total_claims}

Average verdict confidence: {average_confidence}

{verdict_buckets}

## Claims

{claims}
"""
