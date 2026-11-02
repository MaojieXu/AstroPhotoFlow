from astrophotoflow.interfaces.mcp.composition import tool_namespace

"Typed local tool composition; the searchable Agent view shares the full catalog."
from fastmcp import FastMCP
from fastmcp.server.transforms.search import BM25SearchTransform

from astrophotoflow.interfaces.mcp.data import (
    assets,
    calibration,
    datasets,
    equipment,
    exports,
    imports,
    library,
    media,
    presets,
    projects,
    results,
    setups,
    tasks,
    trash,
)
from astrophotoflow.interfaces.mcp.errors import ServiceErrors
from astrophotoflow.interfaces.mcp.graph import canvas, nodes, receipts
from astrophotoflow.interfaces.mcp.lifespan import service_lifespan
from astrophotoflow.interfaces.mcp.software import calls, packages, previews

INSTRUCTIONS = "Operate the selected local AstroPhotoFlow workspace through typed data/software/graph tools.\nKnown exact names are directly callable. search_tools returns at most ten complete definitions; BM25 is keyword retrieval, not a semantic model.\nImports: inspect sources, show groups/issues for user confirmation, submit once, then query/wait using the original request_id.\nCanvas edits require the exact page/workflow/graph IDs and current content_token. Stop on target/content changes; query the original operation_id for an unknown result, never replay blindly. Editing does not execute the graph. ComfyUI owns files, queue, history, progress and cancellation entry.\nKeep fixed asset versions, member order and original-file protection. Preview bytes are not scientific inputs. Permanent cleanup needs a current fingerprint and explicit user authorization. Software install/uninstall retains native confirmation. Cancellation acceptance, observed process stop and unknown results are distinct.\n中文：素材 设备 集合 导入 软件 节点 画布。先检索陌生能力，已知工具直接调用。科学输入固定版本和成员顺序；原件不覆盖。切图或内容过期停止修改；未知结果查询原回执，不自动重发。软件安装需原生确认，永久清理需用户明确授权。\n"


def build_tool_catalog() -> FastMCP:
    root = FastMCP(
        "AstroPhotoFlow", instructions=INSTRUCTIONS, lifespan=service_lifespan, middleware=[ServiceErrors()], mask_error_details=True
    )
    data = tool_namespace("Data")
    data.mount(assets.build_server(), namespace="assets")
    data.mount(library.build_server(), namespace="library")
    data.mount(datasets.build_server(), namespace="datasets")
    data.mount(equipment.build_server(), namespace="equipment")
    data.mount(setups.build_server(), namespace="setups")
    data.mount(presets.build_server(), namespace="presets")
    data.mount(projects.build_server(), namespace="projects")
    data.mount(imports.build_server(), namespace="imports")
    data.mount(tasks.build_server(), namespace="tasks")
    data.mount(exports.build_server(), namespace="exports")
    data.mount(results.build_server(), namespace="results")
    data.mount(trash.build_server(), namespace="trash")
    data.mount(calibration.build_server(), namespace="calibration")
    data.mount(media.build_server(), namespace="media")
    graph = tool_namespace("Graph")
    graph.mount(nodes.build_server(), namespace="nodes")
    graph.mount(canvas.build_server(), namespace="canvas")
    graph.mount(receipts.build_server(), namespace="receipts")
    software = tool_namespace("Software")
    software.mount(calls.build_server(), namespace="calls")
    software.mount(packages.build_server(), namespace="packages")
    software.mount(previews.build_server(), namespace="previews")
    root.mount(data, namespace="data")
    root.mount(software, namespace="software")
    root.mount(graph, namespace="graph")
    return root


def create_server() -> FastMCP:
    root = build_tool_catalog()
    root.add_transform(BM25SearchTransform(max_results=10))
    return root


def run() -> None:
    server.run()


server = create_server()
if __name__ == "__main__":
    run()
