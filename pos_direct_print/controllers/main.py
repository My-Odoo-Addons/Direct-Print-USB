# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import json


class PosDirectPrintController(http.Controller):

    def _verify_request(self):
        """
        Vérifie que la requête est légitime.
        Pour l'instant, vérifie juste que la commande existe et est récente.
        """
        # Pourrait être étendu avec un token/signature
        return True

    @http.route('/pos_direct_print/receipt/<path:order_name>', type='http', auth='public', csrf=False)
    def get_receipt(self, order_name, **kwargs):
        """
        Retourne les données ESC/POS du ticket pour une commande.
        L'agent local appelle cette URL pour récupérer le ticket formaté.
        """
        # Chercher la commande
        order = request.env['pos.order'].sudo().search([('name', '=', order_name)], limit=1)
        
        if not order:
            return Response(
                json.dumps({'error': f'Commande {order_name} non trouvée'}),
                status=404,
                content_type='application/json'
            )
        
        try:
            # Générer le ticket ESC/POS
            receipt_data = order.generate_escpos_receipt()
            
            # Retourner les bytes bruts
            return Response(
                receipt_data,
                status=200,
                content_type='application/octet-stream',
                headers={
                    'Content-Disposition': f'attachment; filename="{order_name}.bin"',
                    'X-Order-Name': order_name,
                    'X-Order-Total': str(order.amount_total),
                    'X-Order-Date': order.date_order.isoformat() if order.date_order else '',
                }
            )
        except Exception as e:
            import traceback
            return Response(
                json.dumps({
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/pos_direct_print/status', type='http', auth='public', csrf=False)
    def status(self, **kwargs):
        """
        Endpoint de statut pour vérifier que le module est actif.
        """
        return Response(
            json.dumps({
                'status': 'ok',
                'module': 'pos_direct_print',
                'version': '18.0.1.0.0'
            }),
            status=200,
            content_type='application/json'
        )

    @http.route('/pos_direct_print/config/<int:config_id>', type='http', auth='public', csrf=False)
    def get_config(self, config_id, **kwargs):
        """
        Retourne la configuration d'impression pour une caisse.
        L'agent peut utiliser cet endpoint pour récupérer sa configuration.
        """
        config = request.env['pos.config'].sudo().browse(config_id)
        
        if not config.exists():
            return Response(
                json.dumps({'error': f'Configuration {config_id} non trouvée'}),
                status=404,
                content_type='application/json'
            )
        
        return Response(
            json.dumps({
                'id': config.id,
                'name': config.name,
                'use_direct_print': config.use_direct_print,
                # 'printer_name' intentionally omitted: agent uses local config only
                'width': config.direct_print_width or 42,
                'encoding': config.direct_print_encoding or 'cp437',
                'print_logo': config.direct_print_logo,
                'print_barcode': config.direct_print_barcode,
                'show_loyalty': config.direct_print_show_loyalty,
                'footer_message': config.direct_print_footer or 'Merci de votre visite !',
                'goodbye_message': config.direct_print_goodbye or 'A bientôt !',
            }),
            status=200,
            content_type='application/json',
            headers={"Access-Control-Allow-Origin": "*"}
        )

    @http.route('/pos_direct_print/test/<path:order_name>', type='http', auth='user', website=False)
    def test_receipt(self, order_name, **kwargs):
        """
        Endpoint de test (nécessite authentification Odoo).
        Retourne un aperçu texte du ticket.
        """
        order = request.env['pos.order'].sudo().search([('name', '=', order_name)], limit=1)
        
        if not order:
            return Response(f"Commande {order_name} non trouvée", status=404)
        
        try:
            receipt_data = order.generate_escpos_receipt()
            
            # Décoder pour affichage (remplacer caractères non-imprimables)
            text_preview = ""
            for byte in receipt_data:
                if 32 <= byte < 127:
                    text_preview += chr(byte)
                elif byte == 10:
                    text_preview += "\n"
                elif byte == 27:
                    text_preview += "[ESC]"
                elif byte == 29:
                    text_preview += "[GS]"
                else:
                    text_preview += f"[{byte:02X}]"
            
            return Response(
                f"<pre style='font-family: monospace; white-space: pre;'>{text_preview}</pre>",
                status=200,
                content_type='text/html'
            )
        except Exception as e:
            import traceback
            return Response(
                f"<pre>Erreur: {e}\n\n{traceback.format_exc()}</pre>",
                status=500,
                content_type='text/html'
            )
