"""Reproducible MCP tool-discovery benchmarks over the real FastMCP catalog.

Measures the context cost of `tools/list`, the ranking quality of the production
BM25 search transform, and query latency. No workspace, service or image data is
required: only the static tool catalog is exercised.
"""

import argparse
import asyncio
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from fastmcp.server.transforms.search import BM25SearchTransform

from astrophotoflow.interfaces.mcp.server import build_tool_catalog, create_server

# (language, natural-language query, expected tool name)
QUERIES: list[tuple[str, str, str]] = [
    ("en", "find light frames of M31 captured last week", "data_assets_search"),
    ("en", "read this image's current facts and equipment", "data_assets_get"),
    ("en", "list the fixed original versions of this frame", "data_assets_list_versions"),
    ("en", "change the gain and offset on this image", "data_assets_update"),
    ("en", "batch update metadata for the selected images", "data_assets_update_metadata_batch"),
    ("en", "read the FITS header keywords of this original", "data_assets_read_header"),
    ("en", "which source frames were used for this master", "data_assets_get_master_provenance"),
    ("en", "hash the original file to check whether it changed", "data_assets_observe_content"),
    ("en", "list datasets with their calibration status", "data_library_search"),
    ("en", "what filter names and ranges can I filter by", "data_library_filters"),
    ("en", "search image groups by target and equipment", "data_datasets_search"),
    ("en", "create a new group from these fixed image versions", "data_datasets_create"),
    ("en", "append these frames to the group and keep the order", "data_datasets_edit_members"),
    ("en", "inspect this folder before importing anything", "data_imports_inspect"),
    ("en", "import this single confirmed file as one frame", "data_imports_import_asset"),
    ("en", "import these ordered files as a new named group", "data_imports_import_dataset"),
    ("en", "import more files into the existing group", "data_imports_append_dataset"),
    ("en", "retry publishing the failed import group", "data_imports_retry_publication"),
    ("en", "upload one photo from my computer", "data_imports_upload_one"),
    ("en", "which local import roots are configured", "data_imports_roots"),
    ("en", "list the import tasks", "data_tasks_list"),
    ("en", "read progress and failed members of this task", "data_tasks_get"),
    ("en", "wait for the whole import batch to finish", "data_tasks_wait"),
    ("en", "cancel this import task", "data_tasks_cancel"),
    ("en", "retry the failed items of this task", "data_tasks_retry"),
    ("en", "save these images to a local destination folder", "data_exports_submit"),
    ("en", "read the export receipt and member outcomes", "data_exports_status"),
    ("en", "read the full resolution result members of this node", "data_results_get"),
    ("en", "move these images to the trash", "data_trash_remove"),
    ("en", "restore the trashed images", "data_trash_restore"),
    ("en", "preview permanent deletion of these trashed files", "data_trash_preview_delete"),
    ("en", "find master dark frames compatible with these lights", "data_calibration_search"),
    ("en", "check whether this calibration binding conflicts", "data_calibration_check"),
    ("en", "set the group's default calibration frames", "data_calibration_update_defaults"),
    ("en", "register a new camera in my equipment library", "data_equipment_register_camera"),
    ("en", "find my telescope by model name", "data_equipment_search"),
    ("en", "create an imaging rig with a camera and telescope", "data_setups_create"),
    ("en", "preview deleting this equipment and its dependencies", "data_equipment_management_preview_delete"),
    ("en", "create a new project for this target", "data_projects_create"),
    ("en", "pin this image to the project", "data_projects_add_asset"),
    ("en", "generate library thumbnails", "data_media_thumbnails_generate"),
    ("en", "show me the cached preview image", "data_media_read"),
    ("en", "list installed software packages", "software_packages_list"),
    ("en", "install Siril version 1.4.4", "software_packages_install"),
    ("en", "read Siril's command reference", "software_packages_commands"),
    ("en", "list available Siril releases", "software_packages_releases"),
    ("en", "show the software calls made for this prompt", "software_calls_list_calls"),
    ("en", "check whether this software call finished", "software_calls_get_call"),
    ("en", "render a sample preview of this node", "software_previews_render"),
    ("en", "search nodes for auto stretch", "graph_nodes_search"),
    ("en", "read the full definition of this node", "graph_nodes_get"),
    ("en", "list the open canvas pages", "graph_canvas_pages"),
    ("en", "connect these two nodes on the canvas", "graph_canvas_edit"),
    ("en", "add this image to the canvas", "graph_canvas_add_data"),
    ("zh", "把这张图加入画布", "graph_canvas_add_data"),
    ("zh", "搜索自动拉伸节点", "graph_nodes_search"),
    ("zh", "导入这个文件夹里的文件", "data_imports_inspect"),
    ("zh", "查询我的相机设备", "data_equipment_search"),
    ("zh", "列出已安装的软件包", "software_packages_list"),
    ("zh", "生成素材库缩略图", "data_media_thumbnails_generate"),
    ("zh", "把这些图移到回收站", "data_trash_remove"),
    ("zh", "查看这个任务的进度", "data_tasks_get"),
    ("zh", "给这个图像组绑定暗场", "data_calibration_update_defaults"),
    ("zh", "等待导入批次完成", "data_tasks_wait"),
    ("zh", "删除这个设备组合", "data_equipment_management_preview_delete"),
    ("zh", "读取节点的完整定义", "graph_nodes_get"),
]


def estimate_tokens(text: str) -> float:
    """Rough token estimate: 4 chars per token for ASCII, 1.5 for CJK."""
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    return (len(text) - non_ascii) / 4 + non_ascii / 1.5


def wire_payload(tools) -> str:
    payload = [tool.to_mcp_tool().model_dump(by_alias=True, exclude_none=True, mode="json") for tool in tools]
    return json.dumps(payload, ensure_ascii=False)


def name_only(tools):
    return [
        tool.model_copy(update={"description": None, "parameters": {"type": "object", "properties": {}}})
        for tool in tools
    ]


async def run_queries(transform, tools, queries, max_results):
    rows = []
    for language, query, expected in queries:
        start = perf_counter()
        results = await transform._search(tools, query)
        elapsed = perf_counter() - start
        names = [tool.name for tool in results]
        rank = names.index(expected) + 1 if expected in names else None
        rows.append(
            {
                "language": language,
                "query": query,
                "expected": expected,
                "rank": rank,
                "top": names[:max_results],
                "seconds": elapsed,
                "result_chars": len(wire_payload(results)),
                "result_tokens": round(estimate_tokens(wire_payload(results))),
            }
        )
    return rows


def summarize(rows):
    ranks = [row["rank"] for row in rows]
    found = [rank for rank in ranks if rank is not None]
    seconds = [row["seconds"] for row in rows]

    def recall_at(k):
        return sum(1 for rank in ranks if rank is not None and rank <= k) / len(rows)

    return {
        "queries": len(rows),
        "recall_at_1": recall_at(1),
        "recall_at_3": recall_at(3),
        "recall_at_10": recall_at(10),
        "mrr": sum(1 / rank for rank in found) / len(rows) if rows else 0.0,
        "misses": [row["expected"] for row in rows if row["rank"] is None],
        "mean_result_tokens": round(statistics.fmean(row["result_tokens"] for row in rows)),
        "latency_ms_p50": round(statistics.median(seconds) * 1000, 2),
        "latency_ms_p95": round(sorted(seconds)[min(len(seconds) - 1, int(len(seconds) * 0.95))] * 1000, 2),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if not output.is_relative_to(repository / ".artifacts"):
        parser.error("Use a fresh directory below this worktree's .artifacts")
    output.mkdir(parents=True, exist_ok=False)

    catalog = build_tool_catalog()
    tools = await catalog.list_tools()
    full_payload = wire_payload(tools)

    visible = await create_server().list_tools()
    visible_payload = wire_payload(visible)

    transform = BM25SearchTransform(max_results=args.max_results)
    name_transform = BM25SearchTransform(max_results=args.max_results)

    cold_start = perf_counter()
    await transform._search(tools, "warm up the index")
    index_seconds = perf_counter() - cold_start

    rows = await run_queries(transform, tools, QUERIES, args.max_results)
    baseline_rows = await run_queries(name_transform, name_only(tools), QUERIES, args.max_results)

    per_language = {
        language: summarize([row for row in rows if row["language"] == language])
        for language in sorted({row["language"] for row in rows})
    }
    report = {
        "kind": "static MCP tool catalog only; no workspace, service, agent or image data",
        "python": sys.version,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "max_results": args.max_results,
        "catalog": {
            "tools": len(tools),
            "full_payload_chars": len(full_payload),
            "full_payload_tokens_estimated": round(estimate_tokens(full_payload)),
            "visible_tools_with_transform": len(visible),
            "visible_tools": [tool.name for tool in visible],
            "visible_payload_chars": len(visible_payload),
            "visible_payload_tokens_estimated": round(estimate_tokens(visible_payload)),
            "index_build_ms": round(index_seconds * 1000, 2),
        },
        "full_text_bm25": summarize(rows),
        "name_only_bm25": summarize(baseline_rows),
        "per_language": per_language,
        "queries": rows,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# MCP tool discovery benchmark",
        "",
        f"- tools: {report['catalog']['tools']}",
        f"- full catalog payload: {report['catalog']['full_payload_chars']:,} chars, "
        f"~{report['catalog']['full_payload_tokens_estimated']:,} tokens",
        f"- visible after search transform: {report['catalog']['visible_tools']} "
        f"({report['catalog']['visible_payload_chars']:,} chars)",
        f"- index build: {report['catalog']['index_build_ms']} ms",
        "",
        "| retrieval | Recall@1 | Recall@3 | Recall@10 | MRR | mean result tokens | p50 ms | p95 ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| no retrieval (all {report['catalog']['tools']}) | 1.00 | 1.00 | 1.00 | 1.00 | "
        f"{report['catalog']['full_payload_tokens_estimated']:,} | - | - |",
    ]
    for label, summary in (("full-text BM25", report["full_text_bm25"]), ("name-only BM25", report["name_only_bm25"])):
        lines.append(
            f"| {label} | {summary['recall_at_1']:.2f} | {summary['recall_at_3']:.2f} | "
            f"{summary['recall_at_10']:.2f} | {summary['mrr']:.2f} | {summary['mean_result_tokens']:,} | "
            f"{summary['latency_ms_p50']} | {summary['latency_ms_p95']} |"
        )
    lines += ["", "| language | queries | Recall@10 | MRR |", "| --- | --- | --- | --- |"]
    for language, summary in per_language.items():
        lines.append(
            f"| {language} | {summary['queries']} | {summary['recall_at_10']:.2f} | {summary['mrr']:.2f} |"
        )
    misses = [row for row in rows if row["rank"] is None]
    if misses:
        lines += ["", "## Misses", ""]
        lines += [f"- `{row['query']}` → expected `{row['expected']}`, top: {', '.join(row['top'][:5])}" for row in misses]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
