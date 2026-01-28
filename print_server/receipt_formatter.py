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

        # === INFOS TICKET ===
        order_name = data.get("order_name", "")
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        add_text(f"Ticket: {order_name[:16].ljust(16)}  {date_str}")

        if data.get("cashier"):
            add_text(f"Caissier: {data['cashier']}")

        if data.get("table"):
            table_info = f"Table: {data['table']}"
            if data.get("customer_count"):
                table_info += f"  Couverts: {data['customer_count']}"
            add_text(table_info)

        add_text(self.separator())

        # === EN-TÊTE TABLEAU ARTICLES ===
        add_text(
            self.format_table_row(
                [
                    {"text": "ARTICLES", "width": 0.70, "align": "left"},
                    {"text": "TOTAL", "width": 0.30, "align": "right"},
                ]
            )
        )
        add_text("")

        # === LIGNES DE PRODUITS ===
        total_qty = 0
        for item in data.get("lines", []):
            if isinstance(item, dict):
                name = item.get("name", "Produit")
                qty = item.get("qty", 1)
                price = item.get("price", 0)
                subtotal = item.get("subtotal", qty * price)
                discount = item.get("discount", 0)
                is_free = item.get("is_free", False)

                total_qty += qty

                # Ligne principale: (Qté) Nom ........... Total
                qty_str = f"({int(qty)})"
                display_name = f"{qty_str} {name[:25]}"

                if is_free:
                    total_str = "*OFFERT"
                else:
                    total_str = self.format_money(subtotal, currency, currency_pos)

                add_cmd(escpos.BOLD_ON)
                add_text(
                    self.format_table_row(
                        [
                            {"text": display_name, "width": 0.65, "align": "left"},
                            {"text": total_str, "width": 0.35, "align": "right"},
                        ]
                    )
                )
                add_cmd(escpos.BOLD_OFF)

                # Sous-ligne: prix unitaire
                unit_price = self.format_money(price, currency, currency_pos)
                add_text(f"   {qty:.2f} x {unit_price} / Unite")

                # Remise si applicable
                if discount and float(discount) > 0:
                    add_text(
                        self.format_table_row(
                            [
                                {"text": "   Remise", "width": 0.65, "align": "left"},
                                {
                                    "text": f"-{self.format_money(discount, currency, currency_pos)}",
                                    "width": 0.35,
                                    "align": "right",
                                },
                            ]
                        )
                    )

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
                                    payment.get("amount", 0), currency, currency_pos
                                ),
                                "width": 0.35,
                                "align": "right",
                            },
                        ]
                    )
                )

        # === RENDU MONNAIE ===
        change = data.get("change", 0)
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

        # === RECAP TVA ===
        tax_details = data.get("tax_details", [])
        if tax_details:
            add_text(self.separator())
            add_text(
                self.format_table_row(
                    [
                        {"text": "TAUX", "width": 0.20, "align": "left"},
                        {"text": "HT", "width": 0.25, "align": "left"},
                        {"text": "TVA", "width": 0.25, "align": "left"},
                        {"text": "TTC", "width": 0.30, "align": "left"},
                    ]
                )
            )
            for tax in tax_details:
                add_text(
                    self.format_table_row(
                        [
                            {
                                "text": f"{tax.get('rate', 0)}%",
                                "width": 0.20,
                                "align": "left",
                            },
                            {
                                "text": f"{tax.get('base', 0):.2f}",
                                "width": 0.25,
                                "align": "left",
                            },
                            {
                                "text": f"{tax.get('amount', 0):.2f}",
                                "width": 0.25,
                                "align": "left",
                            },
                            {
                                "text": f"{tax.get('total', 0):.2f}",
                                "width": 0.30,
                                "align": "left",
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
                add_text(f"Solde precedent: {loyalty['previous_points']} pts")
            if loyalty.get("points_earned") is not None:
                add_text(f"Points gagnes: +{loyalty['points_earned']} pts")
            if loyalty.get("points_used") is not None and loyalty["points_used"] > 0:
                add_text(f"Points utilises: -{loyalty['points_used']} pts")
            if loyalty.get("current_points") is not None:
                add_cmd(escpos.BOLD_ON)
                add_text(f"Nouveau solde: {loyalty['current_points']} pts")
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
