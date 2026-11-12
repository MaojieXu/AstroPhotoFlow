from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.packages import PendingSoftwareAction, SoftwarePackageDetails
from astrophotoflow.contracts.software import (
    SoftwareCommand,
    SoftwareInstallRequest,
    SoftwarePackage,
    SoftwarePreparation,
    SoftwareReleaseListing,
    SoftwareUninstallRequest,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("Packages")

    @mcp.tool(name="list", description="List local scientific software package states. 软件 软件包 安装 状态 列表")
    @service_errors
    def list_packages(*, client: AssetClient = Depends(service_client)) -> list[SoftwarePackage]:
        return client.list_software_packages()

    @mcp.tool(name="get", description="Inspect a package and its existing action without replaying writes. 软件 软件包 读取 详情 回执")
    @service_errors
    def get_package(
        package_id: str, operation_id: UuidInput | None = None, *, client: AssetClient = Depends(service_client)
    ) -> SoftwarePackageDetails:
        return client.get_software_package(package_id, operation_id=operation_id)

    @mcp.tool(
        name="releases", description="Read official releases and exact release tokens before requesting a version. 软件 版本 官方 发布 选择"
    )
    @service_errors
    def releases(package_id: str, *, client: AssetClient = Depends(service_client)) -> SoftwareReleaseListing:
        return client.list_software_releases(package_id)

    @mcp.tool(
        name="commands",
        description="Read command reference for an exact software version; this does not execute commands. 软件 命令 参考 文档 版本",
    )
    @service_errors
    def commands(package_id: str, version: str, *, client: AssetClient = Depends(service_client)) -> list[SoftwareCommand]:
        return client.list_software_commands(package_id, version)

    @mcp.tool(
        name="install",
        description="Request the exact user-selected package version; native confirmation is still required. 软件 安装 更新 版本 确认",
    )
    @service_errors
    def install(package_id: str, body: SoftwareInstallRequest, *, client: AssetClient = Depends(service_client)) -> PendingSoftwareAction:
        return client.install_software(package_id, body)

    @mcp.tool(
        name="uninstall",
        description="Request removal of a user-selected software package; native confirmation is still required. 软件 卸载 确认",
    )
    @service_errors
    def uninstall(
        package_id: str, body: SoftwareUninstallRequest, *, client: AssetClient = Depends(service_client)
    ) -> PendingSoftwareAction:
        return client.uninstall_software(package_id, body)

    @mcp.tool(name="prepare", description="Prepare dependencies for an installed local package. 软件 依赖 准备 环境")
    @service_errors
    def prepare(package_id: str, *, client: AssetClient = Depends(service_client)) -> SoftwarePreparation:
        return client.prepare_software(package_id)

    return mcp
