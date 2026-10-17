"""Nexa-Trader Karar Kayıtlarını (decisions.log) Tablo Formatına Dönüştürücü.

Çıktılar:
  - reports/decisions_table.md   (Markdown formatında okunabilir tablo)
  - reports/decisions_table.csv  (Excel uyumlu UTF-8 CSV)
  - reports/decisions_dashboard.html (Tarayıcıda açılabilir interaktif görsel tablo)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def export_decisions(log_path: Path, output_dir: Path) -> dict[str, Path]:
    if not log_path.exists():
        print(f"[!] Log dosyasi bulunamadi: {log_path}")
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    records = []

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(data)
            except Exception as e:
                print(f"[!] Satir {line_num} parse edilemedi: {e}")

    if not records:
        print("[!] Log dosyasinda kayit bulunamadi.")
        return {}

    # Tablo satırlarını hazırla
    rows = []
    for r in records:
        ts = r.get("timestamp", "-")
        scenario = r.get("scenario") or "Canlı Tarama"
        action = r.get("action", "UNKNOWN")
        mkt = r.get("market") or {}
        price = f"{mkt.get('price'):.3f}" if mkt.get("price") is not None else "-"

        pillars = {p.get("name", ""): p for p in r.get("pillars", [])}

        # 4 Ayak durumları
        tech = _find_pillar(pillars, "Teknik")
        onchain = _find_pillar(pillars, "On-Chain")
        news = _find_pillar(pillars, "Haber")
        macro = _find_pillar(pillars, "Makro")

        tech_status = tech.get("status", "-")
        onchain_status = onchain.get("status", "-")
        news_status = news.get("status", "-")
        macro_status = macro.get("status", "-")

        news_score = ""
        if news and "metrics" in news and "score" in news["metrics"]:
            news_score = f" ({news['metrics']['score']:+.2f})"

        # Veto / Ret gerekçeleri veya Emir özeti
        reasons = r.get("reasons", [])
        plan = r.get("plan")
        exec_info = r.get("execution")

        detail = ""
        if action == "BUY" and plan:
            sz = plan.get("sz_base", "-")
            tp = plan.get("tp_px", "-")
            sl = plan.get("sl_px", "-")
            ord_id = exec_info.get("order_id", "DRY-RUN") if exec_info else "DRY-RUN"
            detail = f"ALIM: {sz} AVAX | TP: {tp} | SL: {sl} | EmirID: {ord_id}"
        elif reasons:
            clean_reasons = []
            for rs in reasons:
                # Kısalt
                rs_clean = rs.split("]")[-1].strip() if "]" in rs else rs
                clean_reasons.append(rs_clean)
            detail = " | ".join(clean_reasons)
        else:
            detail = "Nötr / Beklemede"

        rows.append({
            "timestamp": ts,
            "scenario": scenario,
            "action": action,
            "price": price,
            "tech": tech_status,
            "onchain": onchain_status,
            "news": f"{news_status}{news_score}",
            "macro": macro_status,
            "detail": detail,
        })

    # 1. MARKDOWN TABLOSU
    md_path = output_dir / "decisions_table.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# NEXA-TRADER (SENTINEL) — KARAR VE İŞLEM GEÇMİŞİ\n\n")
        f.write(f"> **Toplam Kayıt Sayısı:** {len(rows)}  \n")
        f.write(f"> **Kaynak Dosya:** `{log_path.name}`  \n\n")
        f.write("| Zaman (TRT) | Senaryo / Mod | Fiyat (USDT) | Karar | 1.Teknik | 2.OnChain | 3.Haber | 4.Makro | Veto Gerekçesi / Emir Özeti |\n")
        f.write("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|\n")
        for row in rows:
            act_badge = f"**{row['action']}**" if row["action"] == "BUY" else row["action"]
            f.write(f"| {row['timestamp']} | {row['scenario']} | {row['price']} | {act_badge} | {row['tech']} | {row['onchain']} | {row['news']} | {row['macro']} | {row['detail']} |\n")

    # 2. CSV TABLOSU (UTF-8 with BOM for Excel)
    csv_path = output_dir / "decisions_table.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Zaman (TRT)", "Senaryo/Mod", "Fiyat (USDT)", "Karar",
            "1.Teknik", "2.OnChain", "3.Haber", "4.Makro", "Veto Gerekcesi / Emir Ozeti"
        ])
        for row in rows:
            writer.writerow([
                row["timestamp"], row["scenario"], row["price"], row["action"],
                row["tech"], row["onchain"], row["news"], row["macro"], row["detail"]
            ])

    # 3. HTML DASHBOARD
    html_path = output_dir / "decisions_dashboard.html"
    _generate_html_dashboard(rows, html_path)

    print(f"[OK] Raporlar basariyla olusturuldu:")
    print(f"  -> Markdown : {md_path}")
    print(f"  -> CSV      : {csv_path}")
    print(f"  -> HTML     : {html_path}")

    return {"md": md_path, "csv": csv_path, "html": html_path}


def _find_pillar(pillars: dict, keyword: str) -> dict:
    for name, p in pillars.items():
        if keyword.lower() in name.lower():
            return p
    return {}


def _generate_html_dashboard(rows: list[dict], html_path: Path) -> None:
    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>Nexa-Trader | Karar Denetim Tablosu</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 1400px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px 0;
      color: #38bdf8;
      font-size: 26px;
    }}
    .subtitle {{
      color: #94a3b8;
      margin-bottom: 24px;
      font-size: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #1e293b;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }}
    th {{
      background: #334155;
      color: #f1f5f9;
      text-align: left;
      padding: 12px 14px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    td {{
      padding: 12px 14px;
      border-bottom: 1px solid #334155;
      font-size: 13px;
      vertical-align: middle;
    }}
    tr:hover {{
      background: #273549;
    }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-weight: 600;
      font-size: 11px;
    }}
    .badge-buy {{ background: #15803d; color: #dcfce7; border: 1px solid #22c55e; }}
    .badge-notrade {{ background: #475569; color: #cbd5e1; }}
    .badge-pass {{ background: #064e3b; color: #6ee7b7; }}
    .badge-fail {{ background: #7f1d1d; color: #fca5a5; }}
    .detail {{ color: #cbd5e1; line-height: 1.4; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Nexa-Trader (Sentinel) — Karar Denetim Tablosu</h1>
    <div class="subtitle">OKX Agent Trade Kit 4-Ayak Karar Motoru & Guardrail Denetim Raporu | Toplam Karar: {len(rows)}</div>
    <table>
      <thead>
        <tr>
          <th>Zaman (TRT)</th>
          <th>Senaryo / Mod</th>
          <th>Fiyat</th>
          <th>Karar</th>
          <th>1. Teknik</th>
          <th>2. On-Chain</th>
          <th>3. Haber</th>
          <th>4. Makro</th>
          <th>Veto Gerekçesi / Emir Detayı</th>
        </tr>
      </thead>
      <tbody>
"""
    for r in rows:
        act_cls = "badge-buy" if r["action"] == "BUY" else "badge-notrade"
        tech_cls = "badge-pass" if "PASS" in r["tech"] else "badge-fail"
        onchain_cls = "badge-pass" if "PASS" in r["onchain"] else "badge-fail"
        news_cls = "badge-pass" if "PASS" in r["news"] else "badge-fail"
        macro_cls = "badge-pass" if "PASS" in r["macro"] else "badge-fail"

        html_content += f"""        <tr>
          <td>{r['timestamp']}</td>
          <td><strong>{r['scenario']}</strong></td>
          <td>{r['price']}</td>
          <td><span class="badge {act_cls}">{r['action']}</span></td>
          <td><span class="badge {tech_cls}">{r['tech']}</span></td>
          <td><span class="badge {onchain_cls}">{r['onchain']}</span></td>
          <td><span class="badge {news_cls}">{r['news']}</span></td>
          <td><span class="badge {macro_cls}">{r['macro']}</span></td>
          <td class="detail">{r['detail']}</td>
        </tr>
"""

    html_content += """      </tbody>
    </table>
  </div>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    # Masaüstü veya yerel dizin
    log_file = base_dir / "decisions.log"
    out_dir = base_dir / "reports"

    # Eğer masaüstünde çalıştırılıyorsa oradaki log_file'ı al
    desktop_log = Path("C:/Users/Yusuf/Desktop/Nexa-Trader/decisions.log")
    if desktop_log.exists():
        log_file = desktop_log
        out_dir = Path("C:/Users/Yusuf/Desktop/Nexa-Trader/reports")

    export_decisions(log_file, out_dir)
