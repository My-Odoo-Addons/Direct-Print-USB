from pathlib import Path

# CONFIGURATION DE L'AGENT D'IMPRESSION
# Seules les infos LOCALES sont ici (Odoo gère le reste)

# ============================================
# CONNEXION ODOO
# ============================================
# ODOO_CONFIG = {
#     "url": "http://192.168.2.125:8070",
# }

# ============================================
# CONFIGURATION RÉSEAU LOCALE
# ============================================
WEBSOCKET_CONFIG = {
    "host": "0.0.0.0",
    "port": 8765,
    "http_port": 8766,
}

# ============================================
# IMPRIMANTE LOCALE (nom CUPS)
# C'est une config matérielle locale, pas Odoo
# Trouver le nom: lpstat -p -d
# ============================================
# PRINTER_NAME = "POS80"
ENCODING = "cp437"

# ============================================
# SAVE/LOAD CONFIG
# Le reste de la config (URL Odoo, nom imprimante) 
# est géré dynamiquement dans gui.py et 
# sauvegardé dans un fichier local
# ============================================
CONFIG_DIR = Path.home() / ".pos_agent"
CONFIG_FILE = CONFIG_DIR / "config.json"