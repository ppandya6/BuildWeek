# ruff: noqa: E501
"""Standalone HTML report rendering for SlideLineage audits."""

from collections import Counter, deque

from jinja2 import Environment, select_autoescape

from slidelineage.errors import ReportTemplateError
from slidelineage.models import AuditReport

_TEMPLATE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>SlideLineage audit</title>
<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.4}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #ccc;padding:.35rem;text-align:left;vertical-align:top}.notice{border:2px solid #555;padding:1rem;background:#f7f7f7}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:.5rem}.card{border:1px solid #ccc;padding:.75rem}code{white-space:pre-wrap}</style>
<script>function filterFindings(){const q=document.getElementById('filter').value.toLowerCase();document.querySelectorAll('[data-finding]').forEach(r=>{r.style.display=r.innerText.toLowerCase().includes(q)?'':'none'});}</script>
</head><body>
<header><h1>SlideLineage</h1><p>Status: {{ report.status }}</p><p>Policy: {{ report.policy.name }}</p><p>Generated: {{ report.run.completed_at or report.run.started_at }}</p><p>Schema: {{ report.schema_version }}</p></header>
<section class="notice"><h2>Scope notice</h2><ul><li>Findings concern dataset relationships and evaluation design.</li><li>Image similarity does not establish patient identity.</li><li>Repair output is a proposal requiring researcher review.</li><li>No clinical interpretation is performed.</li></ul></section>
<section><h2>Overview</h2><div class="cards"><div class="card">Records: {{ report.inputs.total_records }}</div><div class="card">Confirmed relationships: {{ confirmed_relationships }}</div><div class="card">Policy violations: {{ report.policy_evaluation.violations }}</div><div class="card">Review items: {{ report.policy_evaluation.review_items }}</div><div class="card">Image failures: {{ report.summary.metrics.get('image_input_quality_findings', 0) }}</div><div class="card">Repair moved records: {{ report.summary.metrics.get('moved_records', 0) }}</div></div></section>
<section><h2>Input provenance</h2><table><tr><th>Manifest</th><th>Path</th><th>SHA-256</th><th>Rows</th></tr>{% for m in report.inputs.manifests %}<tr><td>{{ m.manifest_id }}</td><td>{{ m.path }}</td><td>{{ m.sha256 }}</td><td>{{ m.row_count }}</td></tr>{% endfor %}</table></section>
<section><h2>Schema mapping</h2><code>{{ schema_mappings }}</code></section>
<section><h2>Findings</h2><input id="filter" oninput="filterFindings()" placeholder="Filter findings"><table><tr><th>Type</th><th>Confirmation</th><th>Policy outcome</th><th>Records</th><th>Evidence summary</th><th>Reason</th></tr>{% for f in report.evaluated_findings %}<tr data-finding><td>{{ f.finding_type }}</td><td>{{ f.confirmation_level }}</td><td>{{ f.policy_outcome }}</td><td>{{ f.record_ids|join(';') }}</td><td>{{ f.evidence|length }} evidence records</td><td>{{ f.policy_reason }}</td></tr>{% endfor %}</table></section>
<section><h2>Image evidence</h2><p>Text-only image evidence is included in this milestone; thumbnails are deferred to avoid embedding unsafe or unsupported images.</p><table><tr><th>Finding</th><th>Metrics</th></tr>{% for f in image_findings %}<tr><td>{{ f.finding_id }}</td><td>{{ f.metrics }}</td></tr>{% endfor %}</table></section>
<section><h2>Relationship graph summary</h2><p>Nodes: {{ report.relationship_graph.nodes|length }}. Edges: {{ report.relationship_graph.edges|length }}. Largest connected component size: {{ largest_component }}.</p><code>{{ edge_counts }}</code></section>
<section><h2>Repair</h2>{% if report.repair_proposal %}<p>{{ report.repair_proposal.statement }}</p><p>Target fraction: {{ report.repair_proposal.metrics.get('target_train_fraction') }}. Proposed fraction: {{ report.repair_proposal.metrics.get('proposed_train_fraction') }}. Moved records: {{ report.repair_proposal.metrics.get('records_moved') }}. Components: {{ report.repair_proposal.metrics.get('component_count') }}.</p><ul>{% for t in report.repair_proposal.tradeoffs %}<li>{{ t }}</li>{% endfor %}</ul><table><tr><th>Component</th><th>Partition</th><th>Moved records</th></tr>{% for d in report.repair_proposal.decisions %}<tr><td>{{ d.component_id }}</td><td>{{ d.proposed_partition }}</td><td>{{ d.moved_record_ids|join(';') }}</td></tr>{% endfor %}</table>{% else %}<p>No repair proposal was requested.</p>{% endif %}</section>
<section><h2>Reproducibility</h2><p>Package: {{ report.reproducibility.slidelineage_version }}. Python: {{ report.reproducibility.python_version }}. Config digest: {{ report.reproducibility.config_digest }}.</p><code>{{ report.reproducibility.model_dump(mode='json') }}</code></section>
<section><h2>Warnings</h2><ul>{% for warning in report.warnings %}<li>{{ warning }}</li>{% endfor %}</ul></section>
</body></html>
"""


def render_html_report(report: AuditReport) -> str:
    """Render a standalone autoescaped HTML report."""

    try:
        env = Environment(autoescape=select_autoescape(default=True))
        template = env.from_string(_TEMPLATE)
        return (
            template.render(
                report=report,
                schema_mappings=report.schema_mappings or {},
                confirmed_relationships=sum(
                    1
                    for f in report.evaluated_findings
                    if f.confirmation_level == "confirmed"
                ),
                image_findings=tuple(
                    f
                    for f in report.evaluated_findings
                    if "image" in f.finding_type.value
                    or "content" in f.finding_type.value
                ),
                edge_counts=dict(
                    sorted(
                        Counter(
                            e.relationship_type.value
                            for e in report.relationship_graph.edges
                        ).items()
                    )
                ),
                largest_component=_largest_component_size(report),
            )
            + "\n"
        )
    except Exception as exc:  # pragma: no cover - defensive template boundary
        raise ReportTemplateError("HTML report rendering failed") from exc


def _largest_component_size(report: AuditReport) -> int:
    graph: dict[str, set[str]] = {
        node.record_id: set() for node in report.relationship_graph.nodes
    }
    for edge in report.relationship_graph.edges:
        graph.setdefault(edge.source_record_id, set()).add(edge.target_record_id)
        graph.setdefault(edge.target_record_id, set()).add(edge.source_record_id)
    seen: set[str] = set()
    largest = 0
    for start in sorted(graph):
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        size = 0
        while queue:
            node = queue.popleft()
            size += 1
            for nxt in sorted(graph[node]):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        largest = max(largest, size)
    return largest
