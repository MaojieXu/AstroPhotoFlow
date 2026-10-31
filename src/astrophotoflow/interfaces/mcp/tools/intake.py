from typing import Annotated
from pydantic import Field

from astrophotoflow.contracts.import_batches import ImportBatchProjectRetry, ImportBatchSubmit, ImportBatchWait, SourceInspection

NAMES = {'inspect_sources': 'imports.inspect', 'get_inspection': 'imports.get_inspection',
         'inspection_entries': 'imports.entries', 'submit_batch': 'imports.submit',
         'batch_status': 'import_tasks.status', 'wait_batch': 'import_tasks.wait',
         'retry_batch_project_links': 'projects.retry_import_links'}


def register(server, call, locale='en'):
    @server.tool(description='只读检查文件／递归目录，返回分组建议、疑义与清单ID。确认前不入库。' if locale == 'zh' else 'Inspect local files/recursive folders without ingestion. Return a manifest ID, suggested groups and issues for user confirmation.')
    def inspect_sources(body: SourceInspection) -> dict:
        return call(lambda client: client.inspect_import_sources(body))

    @server.tool(description='读取扫描摘要，不重新扫描。' if locale == 'zh' else 'Read an existing inspection summary without rescanning.')
    def get_inspection(scan_id: str) -> dict:
        return call(lambda client: client.get_import_inspection(scan_id))

    @server.tool(description='按需分页读取扫描文件、分组、排除项或来源错误；可按组筛选。' if locale == 'zh' else 'Page files, groups, excluded entries or source issues; optionally filter by group_id. Do not load every file into model context routinely.')
    def inspection_entries(scan_id: str, kind: str = 'files', group_id: str | None = None,
                           limit: Annotated[int, Field(ge=1, le=200)] = 50,
                           offset: Annotated[int, Field(ge=0)] = 0) -> dict:
        return call(lambda client: client.list_inspection_entries(scan_id, kind, group_id, limit, offset))

    @server.tool(description='用户确认后一次提交所有分组；request_id防重复受理，来源变化则拒绝。组用group_id或member_ids；人工options必须是确认内容。项目需project_revision。' if locale == 'zh' else 'Submit all user-confirmed groups once. Reuse request_id to query/recover the same acceptance; different content conflicts. Groups select group_id or member_ids. options are explicit manual values, not unconfirmed filename guesses. Optional project requires project_revision.')
    def submit_batch(body: ImportBatchSubmit) -> dict:
        return call(lambda client: client.submit_import_batch(body))

    @server.tool(description='一次查询整批任务、各阶段和项目关联状态；不重跑。' if locale == 'zh' else 'Read aggregate batch tasks, independent stage readiness and project links without re-executing anything.')
    def batch_status(request_id: str) -> dict:
        return call(lambda client: client.get_import_batch(request_id))

    @server.tool(description='整批聚合等待最多20秒；超时返回进度与建议查询间隔，不进行模型端秒级轮询。' if locale == 'zh' else 'Wait up to 20 seconds for the whole batch. Timeout returns progress and next_poll_seconds; avoid model-side rapid polling. Interrupted/failed tasks require explicit action.')
    def wait_batch(body: ImportBatchWait) -> dict:
        return call(lambda client: client.wait_import_batch(body))

    @server.tool(description='读取并协调项目当前revision后，显式重试导入后的项目关联；不重新导入。' if locale == 'zh' else 'Explicitly retry only batch project links after reading/reconciling the current project revision; never re-import files.')
    def retry_batch_project_links(request_id: str, body: ImportBatchProjectRetry) -> dict:
        return call(lambda client: client.retry_batch_project_links(request_id, body))
