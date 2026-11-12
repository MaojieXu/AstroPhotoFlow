from pathlib import Path
from typing import TypedDict
from pydantic import TypeAdapter
from astrophotoflow.contracts.data_nodes import DataNodeResult, ExportReceipt, ExportRequest

class PreviewExportResult(TypedDict):
    path: str
    byte_size: int

class ExportOperations:

    def get_data_result(self, run_id: str, execution_id: str) -> DataNodeResult:
        return self.request('GET', f'/data-nodes/{run_id}/{execution_id}', adapter=TypeAdapter(DataNodeResult))

    def submit_export(self, body: ExportRequest) -> ExportReceipt:
        return self.request('POST', '/exports', json=body, adapter=TypeAdapter(ExportReceipt))

    def get_export(self, request_id: str) -> ExportReceipt:
        return self.request('GET', f'/exports/{request_id}', adapter=TypeAdapter(ExportReceipt))

    def cancel_export(self, request_id: str) -> ExportReceipt:
        return self.request('POST', f'/exports/{request_id}/cancel', adapter=TypeAdapter(ExportReceipt))

    def export_display_preview(self, asset_id: str, output: Path) -> PreviewExportResult:
        data = self.read_display_preview(asset_id)
        output = output.expanduser().resolve()
        with output.open('xb') as stream:
            stream.write(data)
        return {'path': str(output), 'byte_size': len(data)}
