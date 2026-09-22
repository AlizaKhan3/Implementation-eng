"""Human-readable rendering of a report dict produced by report.build_report."""
from __future__ import annotations

import json


def render_text(report: dict) -> str:
    lines: list[str] = []
    lines.append(f"Transaction reference: {report['queried_ref']}")
    lines.append(f"Generated at:          {report['generated_at']}")
    lines.append(f"Matches found:         {report['match_count']}")
    if "duplicate_reference_warning" in report:
        lines.append(f"\n⚠ {report['duplicate_reference_warning']}")

    for i, m in enumerate(report["matches"], start=1):
        lines.append(f"\n--- Match {i} (internal id {m['id']}) ---")
        lines.append(f"Customer:     {m['customer_ref']} ({m['customer_name']})")
        lines.append(f"Amount:       {m['amount']}")
        lines.append(f"Status:       {m['status']}")
        lines.append(f"Created:      {m['created_at']}")
        lines.append(f"Completed:    {m['completed_at']}")
        lines.append(f"Failure code: {m['failure_code']}")
        if m["callbacks"]:
            lines.append("Callbacks:")
            for cb in m["callbacks"]:
                lines.append(
                    f"  attempt {cb['attempt_no']}: {cb['callback_status']} "
                    f"(http {cb['http_status']}) at {cb['attempted_at']}"
                )
        else:
            lines.append("Callbacks:    none recorded")
        if m["anomalies"]:
            lines.append("Anomalies detected:")
            for a in m["anomalies"]:
                lines.append(f"  - {a}")
        else:
            lines.append("Anomalies detected: none")
        lines.append(f"Recommended action: {m['recommendation']}")
    return "\n".join(lines)


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2)
