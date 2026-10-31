from astrophotoflow.contracts.data_nodes import ExportRequest

NAMES = {'get_data_result': 'exports.inspect', 'submit_export': 'exports.submit',
         'get_export': 'exports.status', 'cancel_export': 'exports.cancel'}


def register(server, call, locale='en'):
    @server.tool(description='读取Data节点实际运行结果及有序完整成员；不执行图。' if locale == 'zh' else 'Inspect an actual completed Data node and its ordered full-resolution members without executing the graph.')
    def get_data_result(run_id: str, execution_id: str) -> dict:
        return call(lambda client: client.get_data_result(run_id, execution_id))

    @server.tool(description='按用户明确选择保存Data完整结果到素材库或本机；格式与精度只影响副本，默认保留数值，request_id防重复；不执行上游。' if locale == 'zh' else 'Save explicitly selected Data members to the library or an absolute local destination. Format/precision affect copies only; preserve numeric values by default. Reuse request_id for unknown acceptance; never rerun upstream processing.')
    def submit_export(body: ExportRequest) -> dict:
        return call(lambda client: client.submit_export(body))

    @server.tool(description='查询导出回执与成员结果，包括登记任务ID；未知结果先查，不重放。' if locale == 'zh' else 'Read export receipts and member outcomes, including registration task IDs. Query unknown results rather than replaying writes.')
    def get_export(request_id: str) -> dict:
        return call(lambda client: client.get_export(request_id))

    @server.tool(description='请求取消尚未完成的导出；已完成的成员保留，查询回执确认实际停止。' if locale == 'zh' else 'Request export cancellation. Completed members remain; read the receipt to confirm actual stopping.')
    def cancel_export(request_id: str) -> dict:
        return call(lambda client: client.cancel_export(request_id))
