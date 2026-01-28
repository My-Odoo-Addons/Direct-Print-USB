# USB Direct Print - Odoo 18 POS

Impression directe des tickets POS via imprimante thermique USB.

## Architecture

```
Odoo POS (navigateur) → WebSocket → Serveur Python (caisse) → CUPS → Imprimante USB
```

## Prérequis (machine caisse)

### Python
```bash
pip3 install websockets aiohttp
```

### CUPS
```bash
# Fedora/RHEL
sudo dnf install cups

# Debian/Ubuntu
sudo apt install cups

# Ajouter l'utilisateur au groupe lp
sudo usermod -aG lp $USER
```

### Imprimante
1. Brancher l'imprimante USB
2. Ouvrir http://localhost:631
3. Ajouter l'imprimante avec le nom `POS80`

## Configuration

Éditer `print_server/config.py` :

```python
ODOO_CONFIG = {
    "url": "http://192.168.2.125:8070",
    "database": "odoo_test_db",
    "username": "admin",
    "password": "admin",
}

PRINTER_CONFIG = {
    "name": "POS80",  # Nom CUPS
}
```

## Utilisation

```bash
python3 run_server.py
```

## Module Odoo

Copier `pos_direct_print/` dans les addons Odoo et installer le module.

## Ports

| Port | Service |
|------|---------|
| 8765 | WebSocket |
| 8766 | HTTP API |

