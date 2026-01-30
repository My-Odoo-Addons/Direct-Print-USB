# FORMATAGE DES TICKETS DE CAISSE


from datetime import datetime
import re
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

    # === MÉTHODES UTILITAIRES ===

    def _to_bytes(self, text):
        """Convertit du texte en bytes pour l'imprimante"""
        if isinstance(text, bytes):
            return text
        return str(text).encode(self.encoding, errors="replace")

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

    # === MÉTHODES DE FORMATAGE DES SECTIONS ===

    def _format_header(self, output, data):
        """Formate l'en-tête du ticket"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        def add_bytes(data):
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
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        add_text(f"Date : {date_str}")

        if data.get("cashier"):
            add_text(f"Caissier: {data['cashier']}")

        if data.get("customer"):
            add_text(f"Client: {data['customer']}")

        if data.get("table"):
            salle, table_num = data['table'].split(', ', 1)
            table_info = f"Salle : {salle} - Table : {table_num}"
            if data.get("customer_count"):
                table_info += f"\nCouvert(s): {data['customer_count']}"
            add_text(table_info)

        add_text(self.separator())

    def _format_products(self, output, data, tax_details, currency, currency_pos):
        """Formate la liste des produits"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        # Séparer les lignes normales des lignes de remise
        all_lines = data.get("lines", [])
        normal_lines = []
        discount_lines = []

        for item in all_lines:
            if isinstance(item, dict):
                name = item.get("name", "")
                price = item.get("price", 0)
                # Identifier les lignes de remise (prix négatif + nom contenant remise/discount/%)
                if price < 0 and any(word in name.lower() for word in ["remise", "discount", "%", "sur votre"]):
                    discount_lines.append(item)
                else:
                    normal_lines.append(item)

        # === LIGNES DE PRODUITS ===
        for item in normal_lines:
            name = item.get("name", "Produit")
            qty = item.get("qty", 1)
            price = item.get("price", 0)  # Prix unitaire TTC
            subtotal = item.get("subtotal", qty * price)  # Total TTC
            discount = item.get("discount", 0)
            is_free = item.get("is_free", False)

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

            # Saut de ligne avant le prochain produit
            add_text("")

        return discount_lines

    def _format_discounts(self, output, discount_lines):
        """Formate la section des remises"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        # === REMISES ===
        if discount_lines:
            add_text(self.separator())
            for item in discount_lines:
                name = item.get("name", "")
                # Extraire le pourcentage de remise du nom (ex: "10% sur votre commande")
                discount_percent = "?"
                if "%" in name:
                    try:
                        match = re.search(r'(\d+(?:\.\d+)?)%', name)
                        if match:
                            discount_percent = match.group(1)
                    except:
                        pass

                add_cmd(escpos.ALIGN_CENTER + escpos.BOLD_ON)
                add_text(f"Remise de {discount_percent}% sur votre commande")
                add_cmd(escpos.BOLD_OFF + escpos.ALIGN_LEFT)
                add_text("")

    def _format_totals(self, output, data, tax_details, currency, currency_pos):
        """Formate la section des totaux"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        add_text(self.separator())

        # === TOTAUX ===
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

        # === TOTAL SANS REMISE ===
        if data.get("total_before_discount"):
            add_text(
                self.format_table_row(
                    [
                        {
                            "text": "TOTAL SANS REMISE",
                            "width": 0.55,
                            "align": "left",
                        },
                        {
                            "text": self.format_money(data["total_before_discount"], currency, currency_pos),
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )

        # === TOTAL DES REMISES ===
        if data.get("total_discount") and data["total_discount"] > 0:
            add_text(
                self.format_table_row(
                    [
                        {
                            "text": "TOTAL DES REMISES",
                            "width": 0.55,
                            "align": "left",
                        },
                        {
                            "text": f"{self.format_money(data['total_discount'], currency, currency_pos)}",
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )

        # === TOTAL A PAYER ===
        total_qty = sum(item.get("qty", 1) for item in data.get("lines", []) if isinstance(item, dict))
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
                        "text": self.format_money(data.get("total", 0), currency, currency_pos),
                        "width": 0.25,
                        "align": "right",
                    },
                ]
            )
        )
        add_cmd(escpos.BOLD_OFF)

    def _format_payments(self, output, data, currency, currency_pos):
        """Formate la section des paiements"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        # === PAIEMENTS ===
        payments = data.get("payments", [])
        if payments:
            add_text("")
            add_text("Encaissement:")
            for payment in payments:
                if isinstance(payment, dict) and payment.get("amount", 0) > 0:
                    payment_name = payment.get("name", "Paiement")
                    payment_amount = payment.get("amount", 0)
                    add_text(
                        self.format_table_row(
                            [
                                {"text": payment_name, "width": 0.6, "align": "left"},
                                {"text": self.format_money(payment_amount, currency, currency_pos), "width": 0.4, "align": "right"},
                            ]
                        )
                    )

        # === MONNAIE RENDUE ===
        change = data.get("change", 0)
        if change > 0:
            add_text(
                self.format_table_row(
                    [
                        {"text": "Rendu", "width": 0.6, "align": "left"},
                        {"text": self.format_money(change, currency, currency_pos), "width": 0.4, "align": "right"},
                    ]
                )
            )

    def _format_loyalty(self, output, data):
        """Formate la section fidélité"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        # === PROGRAMME FIDÉLITÉ ===
        loyalty = data.get("loyalty")
        if loyalty and LOYALTY_CONFIG.get("enabled", True):
            add_text("")
            add_cmd(escpos.BOLD_ON)
            add_cmd(escpos.ALIGN_CENTER)
            add_text("******** VOTRE COMPTE FIDÉLITÉ ********")
            add_cmd(escpos.BOLD_OFF)
            add_cmd(escpos.ALIGN_LEFT)

            add_text(f"Numéro Carte: {loyalty['card_number']}")
            add_text(self.separator("-"))

            if loyalty.get("previous_points") is not None and loyalty["previous_points"] > 0:
                add_text(f"Points de fidélité : {loyalty['previous_points']:.1f} pts")
            if loyalty.get("points_earned") is not None and loyalty["points_earned"] > 0:
                add_text(f"Points gagnés: +{loyalty['points_earned']:.1f} pts")
            if loyalty.get("points_used") is not None and loyalty["points_used"] > 0:
                add_text(f"Points utilisés: {loyalty['points_used']:.1f} pts")
            if loyalty.get("current_points") is not None and loyalty.get("current_points") > 0:
                add_cmd(escpos.BOLD_ON)
                add_text(f"Nouveau solde: {loyalty['current_points']:.1f} pts")
                add_cmd(escpos.BOLD_OFF)

        elif not loyalty and LOYALTY_CONFIG.get("enabled", True):
            # Message pour inciter à prendre une carte fidélité
            add_text("")
            add_cmd(escpos.ALIGN_CENTER)
            add_cmd(escpos.BOLD_ON)
            add_text("*** PAS DE CARTE FIDÉLITÉ ? ***")
            add_cmd(escpos.BOLD_OFF)
            add_text("Demandez votre carte, elle est gratuite!")
            add_cmd(escpos.ALIGN_LEFT)

    def _format_footer(self, output, data):
        """Formate le pied du ticket"""
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        def add_bytes(data):
            if isinstance(data, bytes):
                output.extend(data)
            elif isinstance(data, bytearray):
                output.extend(data)
            else:
                output.extend(self._to_bytes(data))

        # === MESSAGE DE REMERCIEMENT ===
        add_text("")
        add_cmd(escpos.ALIGN_CENTER)
        add_text(self.footer_message)
        if self.goodbye_message:
            add_text(self.goodbye_message)

        # === CODE-BARRES EAN-13 ===
        if self.print_barcode and data.get("order_name"):
            add_cmd(escpos.FEED_LINES(1))
            add_cmd(escpos.ALIGN_CENTER)
            add_text("CODE-BARRES COMMANDE")
            add_cmd(escpos.FEED_LINES(1))
            barcode_data = self._generate_barcode_data(data)
            if barcode_data:
                barcode_cmd = escpos.barcode_ean13(barcode_data)
                add_cmd(barcode_cmd)

        # === AVANCE PAPIER ET COUPE ===
        add_cmd(escpos.FEED_LINES(4))
        add_cmd(escpos.CUT_PAPER)

    def _generate_barcode_data(self, data):
        """Génère les données du code-barres EAN-13 contenant id magasin, numéro caisse, date et heure compactes, et numéro commande"""
        try:
            # 1. ID magasin (company_id) - 2 chiffres
            company_id = data.get("company_id", 1)
            store_id = str(company_id).zfill(2)[-2:]  # 2 derniers chiffres

            # 2. Numéro de caisse - 2 chiffres
            pos_config = data.get("pos_config_name", "")
            if pos_config:
                # Extraire les chiffres du nom de config (ex: "POS/001" -> "01")
                import re
                numbers = re.findall(r'\d+', pos_config)
                if numbers:
                    register_num = str(int(numbers[-1])).zfill(2)[-2:]
                else:
                    register_num = "01"  # Défaut
            else:
                # Utiliser l'id de l'utilisateur comme fallback
                user_id = data.get("user_id", [1])[0] if isinstance(data.get("user_id"), list) else 1
                register_num = str(user_id).zfill(2)[-2:]

            # 3. Date compacte (MMDD) - 4 chiffres
            from datetime import datetime
            date_order = data.get("date_order")
            if date_order:
                if isinstance(date_order, str):
                    dt = datetime.fromisoformat(date_order.replace('Z', '+00:00'))
                else:
                    dt = date_order
                date_str = dt.strftime("%m%d")  # MMDD
            else:
                date_str = "0129"  # Date par défaut

            # 4. Heure compacte (HHMM) - 4 chiffres
            if date_order:
                if isinstance(date_order, str):
                    dt = datetime.fromisoformat(date_order.replace('Z', '+00:00'))
                else:
                    dt = date_order
                time_str = dt.strftime("%H%M")  # HHMM
            else:
                time_str = "1125"

            # 5. ID commande - 4 chiffres (utiliser l'ID réel de pos_order)
            order_id = data.get("order_id", 0)
            if order_id:
                order_id_str = str(order_id).zfill(4)[-4:]
            # else:
            #     # Fallback vers l'extraction du nom
            #     order_name = data.get("order_name", "")
            #     if order_name:
            #         import re
            #         numbers = re.findall(r'\d+', order_name)
            #         if numbers:
            #             order_id_str = str(int(numbers[-1])).zfill(4)[-4:]
            #         else:
            #             order_id_str = "0001"
            #     else:
            #         order_id_str = "0001"

            # Combiner: store_id (2) + register_num (2) + date_str (4) + order_id_str (4) = 12 chiffres
            barcode_str = f"{store_id}{register_num}{date_str}{order_id_str}"
            
            return barcode_str
            
        except Exception as e:
            print(f"Erreur génération code-barres: {e}")
            # Fallback: utiliser le numéro de commande
            order_name = data.get("order_name", "0000000000001")
            return order_name.replace('/', '').replace('-', '')[:12].zfill(12)

    # === MÉTHODE PRINCIPALE ===

    def format_receipt(self, data):
        """Génère le contenu formaté du ticket en bytes"""
        currency = data.get("currency_symbol", "Ar")
        currency_pos = data.get("currency_position", "after")

        # Récupérer les détails des taxes en avance (pour calcul HT/TVA par ligne)
        tax_details = data.get("tax_details", [])

        # Utiliser bytearray pour construire le ticket
        output = bytearray()

        # Fonctions helper pour ajouter du contenu
        def add_text(text):
            output.extend(self._to_bytes(text))
            output.extend(b"\n")

        def add_cmd(cmd):
            output.extend(self._to_bytes(cmd))

        def add_bytes(data):
            if isinstance(data, bytes):
                output.extend(data)
            elif isinstance(data, bytearray):
                output.extend(data)
            else:
                output.extend(self._to_bytes(data))

        # Formater chaque section du ticket
        self._format_header(output, data)
        discount_lines = self._format_products(output, data, tax_details, currency, currency_pos)
        self._format_discounts(output, discount_lines)
        self._format_totals(output, data, tax_details, currency, currency_pos)
        self._format_payments(output, data, currency, currency_pos)
        self._format_loyalty(output, data)
        self._format_footer(output, data)

        return bytes(output)