# CONFIGURATION DU SERVEUR D'IMPRESSION POS

import os

# Chemin de base du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    "name": "POS80",  # Nom CUPS de l'imprimante
    "width": 42,  # Largeur en caractères (42 pour 80mm)
    "encoding": "cp437",  # Encodage pour imprimante thermique
    "logo_path": os.path.join(BASE_DIR, "logo.png"),  # Chemin du logo
    "logo_max_width": 384,  # Largeur max du logo en pixels
    "print_logo": True,  # Activer/désactiver le logo
    "print_barcode": True,  # Activer/désactiver le code-barres
}

# Messages personnalisables
RECEIPT_CONFIG = {
    "footer_message": "Merci de votre visite !",
    "goodbye_message": "A bientot !",
}

# Configuration Programme Fidélité (optionnel)
LOYALTY_CONFIG = {
    "enabled": True,  # Activer l'affichage fidélité si données présentes
    "points_conversion": 1000,  # 1 point par X montant dépensé
    "min_points_redeem": 50,  # Points minimum pour utilisation
    "discount_rate": 5,  # % de remise avec fidélité
}
