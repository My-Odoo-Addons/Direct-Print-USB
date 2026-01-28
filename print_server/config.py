
# CONFIGURATION DU SERVEUR D'IMPRESSION POS

# Configuration Odoo XML-RPC
ODOO_CONFIG = {
    "url": "http://192.168.2.125:8070",
    "database": "odoo_test_db",
    "username": "admin",
    "password": "admin",
}

# Configuration WebSocket et HTTP
WEBSOCKET_CONFIG = {
    "host": "0.0.0.0",
    "port": 8765,
    "http_port": 8766,  # Port pour l'API HTTP (détection IP)
}

# Configuration Imprimante
PRINTER_CONFIG = {
    "name": "POS80",           # Nom CUPS de l'imprimante
    "width": 32,               # Largeur en caractères
    "encoding": "cp437",       # Encodage pour imprimante thermique
}

# Messages personnalisables
RECEIPT_CONFIG = {
    "footer_message": "Merci de votre visite !",
    # "default_currency": "Ar",
    # "default_currency_position": "after",
}
