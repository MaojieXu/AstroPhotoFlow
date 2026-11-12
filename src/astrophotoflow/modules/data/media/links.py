"""Data-owned relative media references."""


def asset_media_base(asset_id: str) -> str:
    return f"/astrophotoflow/api/v1/library/assets/{asset_id}/previews"


def project_asset_media_base(project_id: str, reference_id: str) -> str:
    return f"/astrophotoflow/api/v1/projects/{project_id}/asset-references/{reference_id}/previews"
