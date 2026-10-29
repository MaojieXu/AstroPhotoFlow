from uuid import UUID
from fastapi import APIRouter, Depends, Request
from astrophotoflow.core.http import authenticate, ERROR_RESPONSES
from astrophotoflow.contracts.nodes import NodeCapability
from astrophotoflow.modules.nodes.catalog import list_nodes, describe_node

router = APIRouter(prefix='/api/v1/nodes', dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


@router.get('', response_model=list[NodeCapability])
def nodes(request: Request, query: str | None = None):
    return list_nodes(request.app.state.settings, query)


@router.get('/{definition_id}', response_model=NodeCapability)
def node(definition_id: UUID, request: Request):
    return describe_node(request.app.state.settings, definition_id)
