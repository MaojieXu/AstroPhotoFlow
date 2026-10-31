from astrophotoflow.contracts.data_nodes import ExportRequest


class ExportOperations:
    def get_data_result(self, run_id: str, execution_id: str):
        return self.request('GET', f'/data-nodes/{run_id}/{execution_id}')

    def submit_export(self, body: ExportRequest):
        return self.request('POST', '/exports', json=body)

    def get_export(self, request_id: str):
        return self.request('GET', f'/exports/{request_id}')

    def cancel_export(self, request_id: str):
        return self.request('POST', f'/exports/{request_id}/cancel')
