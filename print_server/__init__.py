
# SERVEUR D'IMPRESSION POS


from .config import WEBSOCKET_CONFIG
from .printer import Printer

__all__ = [
    'Printer',
    'WEBSOCKET_CONFIG',
]
