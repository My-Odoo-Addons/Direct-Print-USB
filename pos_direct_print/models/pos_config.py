# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # ==========================================
    # ACTIVATION ET CONNEXION AGENT
    # ==========================================
    use_direct_print = fields.Boolean(
        string="Impression Directe USB",
        default=False,
        help="Activer l'impression directe via agent local"
    )
    
    # direct_print_host = fields.Char(
    #     string="Adresse Agent",
    #     # default="localhost",
    #     help="Adresse IP ou hostname de l'agent d'impression"
    # )
    
    # direct_print_port = fields.Integer(
    #     string="Port HTTP",
    #     default=8766,
    #     help="Port HTTP de l'agent d'impression"
    # )
    
    # ==========================================
    # CONFIGURATION IMPRIMANTE
    # ==========================================
    # direct_print_printer_name = fields.Char(
    #     string="Nom Imprimante CUPS",
    #     default="POS80",
    #     help="Nom de l'imprimante dans CUPS (ex: POS80, TM-T20)"
    # )
    
    direct_print_width = fields.Integer(
        string="Largeur (caractères)",
        default=42,
        help="Largeur du ticket en caractères (42 pour 80mm, 32 pour 58mm)"
    )
    
    direct_print_encoding = fields.Selection([
        ('cp437', 'CP437 (Standard)'),
        ('cp850', 'CP850 (Europe occidentale)'),
        ('cp858', 'CP858 (Europe + Euro)'),
        ('utf-8', 'UTF-8'),
    ], string="Encodage", default='cp437',
        help="Encodage des caractères pour l'imprimante thermique"
    )

    # ==========================================
    # OPTIONS DU TICKET
    # ==========================================
    direct_print_logo = fields.Boolean(
        string="Imprimer le logo",
        default=True,
        help="Imprimer le logo de la société sur le ticket"
    )
    
    direct_print_barcode = fields.Boolean(
        string="Imprimer le code-barres",
        default=True,
        help="Imprimer le code-barres de la commande"
    )
    
    direct_print_show_loyalty = fields.Boolean(
        string="Afficher fidélité",
        default=True,
        help="Afficher les informations de fidélité sur le ticket"
    )

    # ==========================================
    # MESSAGES PERSONNALISABLES
    # ==========================================
    direct_print_footer = fields.Char(
        string="Message de remerciement",
        default="Merci de votre visite !",
        help="Message affiché en bas du ticket"
    )
    
    direct_print_goodbye = fields.Char(
        string="Message d'au revoir",
        default="A bientôt !",
        help="Second message en bas du ticket"
    )


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_config(self):
        """Ajoute les champs d'impression directe au chargement du POS"""
        result = super()._loader_params_pos_config()
        result['search_params']['fields'].extend([
            'use_direct_print',
            # 'direct_print_host', 
            # 'direct_print_port',
            # 'direct_print_printer_name',
            'direct_print_width',
            'direct_print_encoding',
            'direct_print_logo',
            'direct_print_barcode',
            'direct_print_show_loyalty',
            'direct_print_footer',
            'direct_print_goodbye',
        ])
        return result
