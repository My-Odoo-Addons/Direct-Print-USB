#!/usr/bin/env python3

# SERVEUR WEBSOCKET D'IMPRESSION POS


import asyncio
import json
import socket
import websockets
from aiohttp import web

from .config import ODOO_CONFIG, WEBSOCKET_CONFIG
from .odoo_client import OdooClient
from .receipt_formatter import ReceiptFormatter
from .printer import Printer


def get_local_ip():
    """Détecte l'IP locale de la machine"""
    try:
        # Crée une connexion UDP fictive pour obtenir l'IP locale
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class PrintServer:
    """Serveur WebSocket pour l'impression des tickets POS"""
    
    def __init__(self):
        self.odoo = OdooClient()
        self.formatter = ReceiptFormatter()
        self.printer = Printer()
    
    async def handle_connection(self, websocket):
        """Gère les connexions WebSocket entrantes"""
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get("type") == "print":
                    await self.handle_print(data)
                    
            except json.JSONDecodeError as e:
                print(f"✗ Erreur JSON: {e}")
            except Exception as e:
                print(f"✗ Erreur: {e}")
    
    async def handle_print(self, data):
        """Traite une demande d'impression"""
        order_name = data.get("order_name")
        
        print(f"📥 Demande d'impression: {order_name}")
        
        # Récupérer les données depuis Odoo
        order_data = self.odoo.get_order_data(order_name)
        
        if not order_data:
            print(f"✗ Commande non trouvée: {order_name}")
            return
        
        # Formater le ticket
        receipt_text = self.formatter.format_receipt(order_data)
        
        # Imprimer
        if self.printer.print_text(receipt_text):
            print(f"✓ Ticket imprimé - {order_data.get('order_name')} - Total: {order_data.get('total')}")
        else:
            print(f"✗ Échec d'impression: {order_name}")
    
    async def start(self):
        """Démarre le serveur WebSocket et HTTP"""
        host = WEBSOCKET_CONFIG["host"]
        port = WEBSOCKET_CONFIG["port"]
        http_port = WEBSOCKET_CONFIG.get("http_port", 8766)
        local_ip = get_local_ip()
        
        print("=" * 50)
        print("🖨️  SERVEUR D'IMPRESSION POS")
        print("=" * 50)
        print(f"📡 Odoo: {ODOO_CONFIG['url']}")
        print(f"📊 Base: {ODOO_CONFIG['database']}")
        print(f"🔌 WebSocket: ws://{local_ip}:{port}")
        print(f"🌐 HTTP API: http://{local_ip}:{http_port}")
        print("=" * 50)
        
        # Connexion initiale à Odoo
        self.odoo.connect()
        
        # Configurer le serveur HTTP pour l'API
        app = web.Application()
        app.router.add_get('/info', self.http_info)
        app.router.add_options('/info', self.http_options)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, http_port)
        await site.start()
        print(f"✓ Serveur HTTP démarré sur le port {http_port}")
        
        # Démarrer le serveur WebSocket
        async with websockets.serve(self.handle_connection, host, port):
            print(f"✓ Serveur WebSocket démarré sur le port {port}")
            await asyncio.Future()
    
    async def http_info(self, request):
        """Endpoint HTTP pour retourner les infos du serveur"""
        local_ip = get_local_ip()
        data = {
            "ip": local_ip,
            "websocket_port": WEBSOCKET_CONFIG["port"],
            "websocket_url": f"ws://{local_ip}:{WEBSOCKET_CONFIG['port']}"
        }
        return web.json_response(data, headers={
            "Access-Control-Allow-Origin": "*"
        })
    
    async def http_options(self, request):
        """Gère les requêtes CORS preflight"""
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })


def main():
    """Point d'entrée principal"""
    server = PrintServer()
    asyncio.run(server.start())


if __name__ == "__main__":
    main()
