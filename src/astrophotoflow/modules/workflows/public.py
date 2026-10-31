"""Public Data-result access for HTTP composition and scientific export."""
from .data_nodes import read_result as get_data_result, checked_member as get_data_member

__all__ = ['get_data_result', 'get_data_member']
