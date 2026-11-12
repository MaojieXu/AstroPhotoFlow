from uuid import UUID

from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.nodes import NodeCapability
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, authenticate
from astrophotoflow.modules.nodes.public import describe_node, list_nodes

router = APIRouter(prefix='/api/v1/nodes', dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


@router.get('', response_model=list[NodeCapability], operation_id='nodes_api_v1_nodes_get')
def nodes(request: Request, query: str | None = None):
    return list_nodes(request.app.state.settings, query)


@router.get('/{definition_id}', response_model=NodeCapability, operation_id='node_api_v1_nodes__definition_id__get')
def node(definition_id: UUID, request: Request):
    return describe_node(request.app.state.settings, definition_id)
