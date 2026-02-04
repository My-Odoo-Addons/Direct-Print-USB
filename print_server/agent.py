#!/usr/bin/env python3
"""
AGENT D'IMPRESSION POS - Version légère
Récupère les tickets formatés depuis Odoo et les envoie à l'imprimante.
"""

import asyncio
import json
import socket
import urllib.request
import urllib.parse
import websockets
from aiohttp import web
import os
import argparse

from .config import WEBSOCKET_CONFIG
from .printer import Printer


def get_local_ip():
    """Détecte l'IP locale de la machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class PrintAgent:
    """Agent léger d'impression - récupère les tickets depuis Odoo"""

    def __init__(self, odoo_url=None):
        # Déterminer l'URL Odoo : argument -> variable d'env -> saisie interactive
        self.odoo_url = odoo_url or os.environ.get('ODOO_URL')
        if not self.odoo_url:
            try:
                # prompt interactif si lancé depuis un terminal
                self.odoo_url = input('URL Odoo (ex: http://host:port) : ').strip() or None
            except Exception:
                self.odoo_url = None

        # Détecter imprimante si config locale vide
        self.printer = None
        try:
            detected = Printer.detect_printer()
        except Exception:
            detected = None

        self.printer = Printer(detected)

    def get_receipt_from_odoo(self, order_name):
        """
        Récupère le ticket formaté (bytes ESC/POS) depuis Odoo.
        """
        if not self.odoo_url:
            print("   ✗ URL Odoo non fournie")
            return None

        try:
            # Encoder le nom de commande pour l'URL
            encoded_name = urllib.parse.quote(order_name, safe='')
            url = f"{self.odoo_url}/pos_direct_print/receipt/{encoded_name}"
            
            print(f"   📡 Récupération: {url}")
            
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return response.read()
                else:
                    print(f"   ✗ Erreur HTTP: {response.status}")
                    return None
                    
        except urllib.error.HTTPError as e:
            print(f"   ✗ Erreur HTTP {e.code}: {e.reason}")
            return None
        except Exception as e:
            print(f"   ✗ Erreur: {e}")
            return None

    async def handle_connection(self, websocket):
        """Gère les connexions WebSocket entrantes"""
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get("type") == "print":
                    order_name = data.get("order_name")
                    print(f"📥 Demande d'impression: {order_name}")
                    
                    # Récupérer le ticket depuis Odoo
                    receipt_data = self.get_receipt_from_odoo(order_name)
                    
                    if receipt_data:
                        # Imprimer directement les bytes ESC/POS
                        if self.printer.print_raw(receipt_data):
                            print(f"   ✓ Ticket imprimé: {order_name}")
                        else:
                            print(f"   ✗ Échec d'impression: {order_name}")
                    else:
                        print(f"   ✗ Ticket non récupéré: {order_name}")
                        
            except json.JSONDecodeError as e:
                print(f"✗ Erreur JSON: {e}")
            except Exception as e:
                print(f"✗ Erreur: {e}")

    async def start(self):
        """Démarre l'agent (WebSocket + HTTP info)"""
        host = WEBSOCKET_CONFIG["host"]
        port = WEBSOCKET_CONFIG["port"]
        http_port = WEBSOCKET_CONFIG.get("http_port", 8766)
        local_ip = get_local_ip()
        # Afficher le nom d'imprimante réellement utilisé
        displayed_printer = getattr(self.printer, 'printer_name', None)
        if not displayed_printer:
            try:
                displayed_printer = detect_printer()
            except Exception:
                displayed_printer = None

        print("=" * 50)
        print("🖨️  AGENT D'IMPRESSION POS")
        print("=" * 50)
        print(f"📡 Odoo: {self.odoo_url}")
        print(f"🔌 WebSocket: ws://{local_ip}:{port}")
        print(f"🌐 HTTP API: http://{local_ip}:{http_port}")
        print(f"🖨️  Imprimante: {displayed_printer}")
        print("=" * 50)

        # Serveur HTTP pour la découverte
        app = web.Application()
        app.router.add_get("/info", self.http_info)
        app.router.add_options("/info", self.http_options)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, http_port)
        await site.start()
        print(f"✓ Serveur HTTP démarré sur le port {http_port}")

        # Serveur WebSocket
        async with websockets.serve(self.handle_connection, host, port):
            print(f"✓ Serveur WebSocket démarré sur le port {port}")
            print("✓ Agent prêt !")
            await asyncio.Future()

    async def http_info(self, request):
        """Endpoint HTTP pour la découverte de l'agent"""
        local_ip = get_local_ip()
        return web.json_response({
            "ip": local_ip,
            "websocket_port": WEBSOCKET_CONFIG["port"],
            "websocket_url": f"ws://{local_ip}:{WEBSOCKET_CONFIG['port']}",
        }, headers={"Access-Control-Allow-Origin": "*"})

    async def http_options(self, request):
        """Gère les requêtes CORS preflight"""
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='PrintAgent')
    parser.add_argument('--odoo-url', dest='odoo_url', help='URL base d\'Odoo (ex: http://host:8070)')
    args = parser.parse_args()

    agent = PrintAgent(odoo_url=args.odoo_url)
    asyncio.run(agent.start())


if __name__ == "__main__":
    main()
