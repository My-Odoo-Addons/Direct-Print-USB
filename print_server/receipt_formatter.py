# FORMATAGE DES TICKETS DE CAISSE


from datetime import datetime
from .config import PRINTER_CONFIG, RECEIPT_CONFIG, LOYALTY_CONFIG
from . import escpos


class ReceiptFormatter:
    """Formate les tickets de caisse pour imprimantes thermiques"""

    def __init__(self):
        self.width = PRINTER_CONFIG["width"]
        self.encoding = PRINTER_CONFIG.get("encoding", "cp437")
        self.footer_message = RECEIPT_CONFIG["footer_message"]
        self.goodbye_message = RECEIPT_CONFIG.get("goodbye_message", "")
        self.logo_path = PRINTER_CONFIG.get("logo_path")
        self.print_logo = PRINTER_CONFIG.get("print_logo", False)
        self.print_barcode = PRINTER_CONFIG.get("print_barcode", True)

    def _to_bytes(self, text):
        """Convertit du texte en bytes pour l'imprimante"""
        if isinstance(text, bytes):
            return text
        return str(text).encode(self.encoding, errors="replace")

    # FORMATAGE TABLEAUX

    def format_line(self, left, right=""):
        """Formate une ligne avec texte à gauche et à droite"""
        left = str(left)
        right = str(right)
        space = self.width - len(left) - len(right)
        if space < 1:
            space = 1
        return left + " " * space + right

    def format_table_row(self, columns):
        """
        Formate une ligne de tableau avec colonnes proportionnelles
        columns: liste de dicts {text, width (0-1), align ('left'/'right'/'center')}
        """
        result = ""
        remaining = self.width

        for i, col in enumerate(columns):
            text = str(col.get("text", ""))
            width_ratio = col.get("width", 0.5)
            align = col.get("align", "left")

            # Calculer la largeur de la colonne
            col_width = int(self.width * width_ratio)
            if i == len(columns) - 1:
                col_width = remaining
            remaining -= col_width

            # Tronquer si trop long
            if len(text) > col_width:
                text = text[: col_width - 1] + "."

            # Appliquer l'alignement
            if align == "right":
                text = text.rjust(col_width)
            elif align == "center":
                text = text.center(col_width)
            else:
                text = text.ljust(col_width)

            result += text

        return result

    def format_money(self, amount, symbol="Ar", position="after"):
        """Formate un montant avec la devise"""
        try:
            amount_str = f"{float(amount):,.2f}".replace(",", " ")
        except (ValueError, TypeError):
            amount_str = "0.00"

        if position == "before":
            return f"{symbol}{amount_str}"
        return f"{amount_str}{symbol}"

    def separator(self, char="-"):
        """Retourne une ligne de séparation"""
        return char * self.width

    # FORMATAGE DU TICKET COMPLET

    def format_receipt(self, data):
        """Génère le contenu formaté du ticket en bytes"""
        currency = data.get("currency_symbol", "Ar")
        currency_pos = data.get("currency_position", "after")
        
        # Récupérer les détails des taxes en avance (pour calcul HT/TVA par ligne)
        tax_details = data.get("tax_details", [])

        # Utiliser bytearray pour construire le ticket
        output = bytearray()

        def add_text(text):
            """Ajoute du texte avec newline"""
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            """Ajoute une commande ESC/POS (str ou bytes)"""
            output.extend(self._to_bytes(cmd))

        def add_bytes(data):
            """Ajoute des données binaires brutes"""
            if isinstance(data, bytes):
                output.extend(data)
            elif isinstance(data, bytearray):
                output.extend(data)
            else:
                output.extend(self._to_bytes(data))

        # === INITIALISATION ===
        add_cmd(escpos.INIT_PRINTER)

        # === LOGO ===
        if self.print_logo and self.logo_path:
            logo_cmd = escpos.print_logo(
                self.logo_path, PRINTER_CONFIG.get("logo_max_width", 384)
            )
            if logo_cmd:
                add_cmd(escpos.ALIGN_CENTER)
                add_bytes(logo_cmd)
                add_cmd(escpos.FEED_LINES(2))

        # === EN-TÊTE : NOM DE LA SOCIÉTÉ ===
        add_cmd(escpos.ALIGN_CENTER + escpos.BOLD_ON + escpos.SIZE_DOUBLE_HEIGHT)
        add_text(f"--- {data.get('company_name', 'MAGASIN')} ---")
        add_cmd(escpos.SIZE_NORMAL + escpos.BOLD_OFF)

        # === INFORMATIONS DE CONTACT ===
        if data.get("company_phone"):
            add_text(f"Tel: {data['company_phone']}")
        if data.get("company_email"):
            add_text(data["company_email"])
        if data.get("company_website"):
            add_text(data["company_website"])

        add_text(self.separator())
        add_cmd(escpos.ALIGN_LEFT)

        # # === INFOS TICKET ===
        # order_name = data.get("order_name", "")
        # date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        # add_text(f"Ticket: {order_name[:16].ljust(16)}  {date_str}")
        
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        add_text(f"Date : {date_str}")

        if data.get("cashier"):
            add_text(f"Caissier: {data['cashier']}")

        if data.get("table"):
            # table_info = f"Salle : {data['table'][0]} - Table : {data['table'][1]}"
            salle, table_num = data['table'].split(', ', 1)
            table_info = f"Salle : {salle} - Table : {table_num}"
            if data.get("customer_count"):
                table_info += f"\nCouvert(s): {data['customer_count']}"
            add_text(table_info)

        add_text(self.separator())

        # === LIGNES DE PRODUITS ===
        total_qty = 0
        for item in data.get("lines", []):
            if isinstance(item, dict):
                name = item.get("name", "Produit")
                qty = item.get("qty", 1)
                price = item.get("price", 0)  # Prix unitaire TTC
                subtotal = item.get("subtotal", qty * price)  # Total TTC
                discount = item.get("discount", 0)
                is_free = item.get("is_free", False)

                total_qty += qty

                # Calculer le prix HT et la TVA
                tax_rate = 15  # Taux par défaut
                if tax_details and len(tax_details) > 0:
                    tax_rate = tax_details[0].get("rate", 15)
                
                # Calcul HT et TVA pour la ligne
                subtotal_ht = subtotal / (1 + tax_rate / 100)
                tva_line = subtotal - subtotal_ht

                # Ligne 1: (Qté) Nom produit ... HT (en gras)
                qty_str = f"({int(qty)})"
                display_name = f"{qty_str} {name[:28]}"

                if is_free:
                    ht_str = "*OFFERT"
                else:
                    ht_str = self.format_money(subtotal_ht, currency, currency_pos)

                add_cmd(escpos.BOLD_ON)
                add_text(
                    self.format_table_row(
                        [
                            {"text": display_name, "width": 0.65, "align": "left"},
                            {"text": ht_str, "width": 0.35, "align": "right"},
                        ]
                    )
                )
                add_cmd(escpos.BOLD_OFF)

                # Ligne 2: Qté x Prix unitaire
                if not is_free:
                    price_unit_ht = price / (1 + tax_rate / 100)
                    add_text(f"   {int(qty)} x {self.format_money(price_unit_ht, currency, currency_pos)}")

                # Ligne 3: Taux : X% ... TVA
                if not is_free:
                    tva_str = self.format_money(tva_line, currency, currency_pos)
                    add_text(
                        self.format_table_row(
                            [
                                {"text": f"Taux : {tax_rate:.0f}%", "width": 0.65, "align": "left"},
                                {"text": tva_str, "width": 0.35, "align": "right"},
                            ]
                        )
                    )

                # Remise si applicable
                if discount and float(discount) > 0:
                    add_text(
                        self.format_table_row(
                            [
                                {"text": "Remise", "width": 0.65, "align": "left"},
                                {
                                    "text": f"-{self.format_money(discount, currency, currency_pos)}",
                                    "width": 0.35,
                                    "align": "right",
                                },
                            ]
                        )
                    )

                # Saut de ligne avant le prochain produit
                add_text("")

        add_text(self.separator())

        # === TOTAUX ===
        total_sans_remise = data.get("total_before_discount")
        total_remise = data.get("total_discount", 0)

        if total_sans_remise and float(total_remise) > 0:
            add_text(
                self.format_table_row(
                    [
                        {"text": "TOTAL SANS REMISE", "width": 0.65, "align": "left"},
                        {
                            "text": self.format_money(
                                total_sans_remise, currency, currency_pos
                            ),
                            "width": 0.35,
                            "align": "right",
                        },
                    ]
                )
            )
            add_text(
                self.format_table_row(
                    [
                        {"text": "TOTAL DES REMISES", "width": 0.65, "align": "left"},
                        {
                            "text": f"-{self.format_money(total_remise, currency, currency_pos)}",
                            "width": 0.35,
                            "align": "right",
                        },
                    ]
                )
            )

        # === TOTAL A PAYER ===
        # Calcul HT et TVA totaux
        for tax in tax_details:
            add_text(
                self.format_table_row(
                    [
                        {
                            "text": "HT ",
                            "width": 0.55,
                            "align": "left",
                        },
                        {
                            "text": self.format_money(tax.get("base", 0), currency, currency_pos),
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )
            add_text(
                self.format_table_row(
                    [
                        {
                            "text": "TVA ",
                            "width": 0.55,
                            "align": "left",
                        },
                        {
                            "text": self.format_money(tax.get("amount", 0), currency, currency_pos),
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )
            

        add_cmd(escpos.BOLD_ON)
        add_text(
            self.format_table_row(
                [
                    {
                        "text": f"TOTAL A PAYER ({int(total_qty)})",
                        "width": 0.55,
                        "align": "left",
                    },
                    {
                        "text": self.format_money(
                            data.get("total", 0), currency, currency_pos
                        ),
                        "width": 0.45,
                        "align": "right",
                    },
                ]
            )
        )
        add_cmd(escpos.BOLD_OFF)

        # === ENCAISSEMENTS ===
        add_text("")
        add_text("Encaissement:")
        for payment in data.get("payments", []):
            if isinstance(payment, dict):
                amount = payment.get("amount", 0)
                if amount and float(amount) > 0:
                    add_text(
                        self.format_table_row(
                            [
                                {
                                    "text": f"  {payment.get('name', 'Paiement')}",
                                    "width": 0.65,
                                    "align": "left",
                                },
                                {
                                    "text": self.format_money(
                                        amount, currency, currency_pos
                                    ),
                                    "width": 0.35,
                                    "align": "right",
                                },
                            ]
                        )
                    )

        # === RENDU MONNAIE ===
        change = data.get("change", 0)
        print(f"Debug - Rendu monnaie: {change}")
        if change and float(change) > 0:
            add_text("")
            add_text(
                self.format_table_row(
                    [
                        {"text": "Rendu:", "width": 0.65, "align": "left"},
                        {
                            "text": self.format_money(change, currency, currency_pos),
                            "width": 0.35,
                            "align": "right",
                        },
                    ]
                )
            )

        # === PROGRAMME FIDÉLITÉ ===
        loyalty = data.get("loyalty")
        if loyalty and LOYALTY_CONFIG.get("enabled", True):
            add_text("")
            add_cmd(escpos.BOLD_ON)
            add_cmd(escpos.ALIGN_CENTER)
            add_text("******** VOTRE COMPTE FIDELITE ********")
            add_cmd(escpos.BOLD_OFF)
            add_cmd(escpos.ALIGN_LEFT)

            if loyalty.get("card_number"):
                add_text(f"Numero Carte: {loyalty['card_number']}")
            add_text(self.separator("-"))

            if loyalty.get("previous_points") is not None:
                add_text(f"Points de fidélité : {loyalty['previous_points']:.1f} pts")
            if loyalty.get("points_earned") is not None and loyalty["points_earned"] > 0:
                add_text(f"Points gagnes: +{loyalty['points_earned']:.1f} pts")
            if loyalty.get("points_used") is not None and loyalty["points_used"] > 0:
                add_text(f"Points utilises: {loyalty['points_used']:.1f} pts")
            if loyalty.get("current_points") is not None:
                add_cmd(escpos.BOLD_ON)
                add_text(f"Nouveau solde: {loyalty['current_points']:.1f} pts")
                add_cmd(escpos.BOLD_OFF)

            add_cmd(escpos.BOLD_ON)
            add_cmd(escpos.ALIGN_CENTER)
            add_text("***************************************")
            add_cmd(escpos.BOLD_OFF)
        elif not loyalty and LOYALTY_CONFIG.get("enabled", True):
            # Message pour inciter à prendre une carte fidélité
            add_text("")
            add_cmd(escpos.ALIGN_CENTER)
            add_cmd(escpos.BOLD_ON)
            add_text("*** PAS DE CARTE FIDELITE ? ***")
            add_cmd(escpos.BOLD_OFF)
            add_text("Demandez votre carte, elle est gratuite!")
            add_cmd(escpos.ALIGN_LEFT)

        # === MESSAGE DE REMERCIEMENT ===
        add_text("")
        add_cmd(escpos.ALIGN_CENTER)
        add_text(self.footer_message)
        if self.goodbye_message:
            add_text(self.goodbye_message)

        # === CODE-BARRES EAN-13 ===
        if self.print_barcode and data.get("order_name"):
            add_cmd(escpos.FEED_LINES(2))
            add_cmd(escpos.ALIGN_CENTER)
            barcode_data = data.get("barcode") or data.get("order_name")
            barcode_cmd = escpos.barcode_ean13(barcode_data)
            add_cmd(barcode_cmd)

        # === AVANCE PAPIER ET COUPE ===
        add_cmd(escpos.FEED_LINES(4))
        add_cmd(escpos.CUT_PAPER)

        return bytes(output)
