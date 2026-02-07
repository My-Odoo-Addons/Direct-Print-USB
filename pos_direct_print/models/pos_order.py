# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, api
import base64
import io

# ============================================================
# COMMANDES ESC/POS
# ============================================================
ESC = "\x1b"
GS = "\x1d"

INIT_PRINTER = ESC + "@"
BOLD_ON = ESC + "E\x01"
BOLD_OFF = ESC + "E\x00"
ALIGN_LEFT = ESC + "a\x00"
ALIGN_CENTER = ESC + "a\x01"
SIZE_NORMAL = ESC + "!\x00"
SIZE_DOUBLE_HEIGHT = ESC + "!\x10"
CUT_PAPER = GS + "V\x00"
OPEN_CASH_DRAWER = ESC + "p\x00\x19\xfa"
OPEN_CASH_DRAWER_ALTERNATIVE = ESC + "p\x01\x19\xfa"


def feed(n):
    return ESC + f"d{chr(n)}"


def barcode_ean13(data):
    """Génère un code-barres EAN-13"""
    digits = "".join(filter(str.isdigit, str(data)))[:12].zfill(12)
    return (
        GS
        + "h"
        + chr(100)
        + GS
        + "w"
        + chr(3)
        + GS
        + "H"
        + chr(2)
        + GS
        + "f"
        + chr(0)
        + GS
        + "k"
        + "\x02"
        + digits
        + "\x00"
    )


def print_raster_image(image_data, width_bytes, height):
    """Imprime une image raster"""
    xL = width_bytes % 256
    xH = width_bytes // 256
    yL = height % 256
    yH = height // 256
    header = bytes([0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH])
    return header + image_data


def convert_image_to_raster(image_binary, max_width=384):
    """Convertit une image en données raster pour imprimante thermique"""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_binary))
        img = img.convert("L")
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        img = img.point(lambda x: 0 if x < 128 else 255, "1")
        width = img.width
        height = img.height
        width_bytes = (width + 7) // 8
        pixels = list(img.getdata())
        data = bytearray()
        for y in range(height):
            for x_byte in range(width_bytes):
                byte = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < width:
                        pixel_index = y * width + x
                        if pixel_index < len(pixels) and pixels[pixel_index] == 0:
                            byte |= 1 << (7 - bit)
                data.append(byte)
        return bytes(data), width_bytes, height
    except Exception:
        return None


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _get_loyalty_data(self):
        """Récupère les données complètes du programme fidélité"""
        if not self.partner_id:
            return None

        try:
            # Chercher l'historique de fidélité pour cette commande
            LoyaltyHistory = self.env["loyalty.history"].sudo()
            history = LoyaltyHistory.search([("order_id", "=", self.id)])

            # Calculer les points utilisés depuis les lignes
            total_points_used = sum(
                ln.points_cost or 0 for ln in self.lines if hasattr(ln, "points_cost")
            )

            if history:
                for h in history:
                    if h.card_id:
                        card = h.card_id
                        program_name = card.program_id.name if card.program_id else ""

                        # Privilégier le programme Loyalty (pas Gift Card)
                        if (
                            "loyalty" in program_name.lower()
                            or "fidélité" in program_name.lower()
                        ):
                            points_earned = h.issued or 0
                            points_used = (
                                total_points_used
                                if total_points_used > 0
                                else (h.used or 0)
                            )
                            current_points = card.points or 0

                            return {
                                "card_number": card.code or str(card.id),
                                "program_name": program_name,
                                "point_name": getattr(card, "point_name", "pts")
                                or "pts",
                                "current_points": current_points,
                                "previous_points": current_points
                                - points_earned
                                + points_used,
                                "points_earned": points_earned,
                                "points_used": points_used,
                            }

            # Fallback: chercher carte fidélité du client
            LoyaltyCard = self.env["loyalty.card"].sudo()
            cards = LoyaltyCard.search([("partner_id", "=", self.partner_id.id)])

            for card in cards:
                program_name = card.program_id.name if card.program_id else ""
                if (
                    "loyalty" in program_name.lower()
                    or "fidélité" in program_name.lower()
                ):
                    return {
                        "card_number": card.code or str(card.id),
                        "program_name": program_name,
                        "point_name": getattr(card, "point_name", "pts") or "pts",
                        "current_points": card.points or 0,
                        "previous_points": None,
                        "points_earned": None,
                        "points_used": total_points_used,
                    }

            # Aucune carte de type loyalty, retourner la première non-gift
            for card in cards:
                program_name = card.program_id.name if card.program_id else ""
                if "gift" not in program_name.lower():
                    return {
                        "card_number": card.code or str(card.id),
                        "program_name": program_name,
                        "point_name": getattr(card, "point_name", "pts") or "pts",
                        "current_points": card.points or 0,
                        "previous_points": None,
                        "points_earned": None,
                        "points_used": total_points_used,
                    }

        except Exception:
            pass

        return None

    def _get_loyalty_discount_pct(self):
        """Récupère le pourcentage de remise fidélité depuis les lignes reward"""
        for ln in self.lines:
            if hasattr(ln, "reward_id") and ln.reward_id:
                try:
                    discount = ln.reward_id.discount
                    if discount and discount > 0:
                        return discount
                except Exception:
                    pass
        return None

    def _get_table_info(self):
        """Récupère les infos de table de façon sécurisée"""
        if not hasattr(self, "table_id") or not self.table_id:
            return None

        try:
            table = self.table_id
            # Essayer différents attributs pour le nom de la table
            table_name = None
            for attr in ["table_number", "name", "display_name"]:
                val = getattr(table, attr, None)
                if val:
                    table_name = str(val)
                    break
            if not table_name:
                table_name = str(table.id)

            # Récupérer le nom de la salle
            floor_name = "Salle"
            if hasattr(table, "floor_id") and table.floor_id:
                floor_name = table.floor_id.name or "Salle"

            return {
                "floor": floor_name,
                "table": table_name,
            }
        except Exception:
            return None

    def _get_tax_details(self):
        """Récupère les détails des taxes par taux"""
        tax_totals = {}

        for ln in self.lines:
            ht = ln.price_subtotal or 0
            ttc = ln.price_subtotal_incl or 0
            tax_amount = ttc - ht

            # Déterminer le taux
            rate = 0
            if ln.tax_ids:
                for tax in ln.tax_ids:
                    if tax.amount > 0:
                        rate = tax.amount
                        break
            elif ht > 0:
                rate = round((tax_amount / ht) * 100, 0)

            if rate not in tax_totals:
                tax_totals[rate] = {"base": 0, "amount": 0, "total": 0}

            tax_totals[rate]["base"] += ht
            tax_totals[rate]["amount"] += tax_amount
            tax_totals[rate]["total"] += ttc

        # Convertir en liste triée
        return [
            {
                "rate": rate,
                "base": data["base"],
                "amount": data["amount"],
                "total": data["total"],
            }
            for rate, data in sorted(tax_totals.items())
        ]

    def generate_escpos_receipt(self, reprint=False):
        """
        Génère les commandes ESC/POS pour le ticket de caisse.
        Utilise la configuration depuis pos.config.
        """
        self.ensure_one()

        # Récupérer la configuration depuis pos.config
        config = self.config_id
        width = config.direct_print_width or 42
        encoding = config.direct_print_encoding or "cp437"
        print_logo = (
            config.direct_print_logo if config.direct_print_logo is not None else True
        )
        print_barcode = (
            config.direct_print_barcode
            if config.direct_print_barcode is not None
            else True
        )
        show_loyalty = (
            config.direct_print_show_loyalty
            if config.direct_print_show_loyalty is not None
            else True
        )
        footer_message = config.direct_print_footer or "Merci de votre visite !"
        goodbye_message = config.direct_print_goodbye or "A bientôt !"

        output = bytearray()

        def to_bytes(text):
            if isinstance(text, bytes):
                return text
            return str(text).encode(encoding, errors="replace")

        def add(text):
            output.extend(to_bytes(text))
            output.extend(b"\n")

        def cmd(c):
            if isinstance(c, bytes):
                output.extend(c)
            else:
                output.extend(to_bytes(c))

        def table_row(columns):
            result = ""
            remaining = width
            for i, col in enumerate(columns):
                text = str(col.get("text", ""))
                width_ratio = col.get("width", 0.5)
                align = col.get("align", "left")
                col_width = int(width * width_ratio)
                if i == len(columns) - 1:
                    col_width = remaining
                remaining -= col_width
                if len(text) > col_width:
                    text = text[: col_width - 1] + "."
                if align == "right":
                    text = text.rjust(col_width)
                elif align == "center":
                    text = text.center(col_width)
                else:
                    text = text.ljust(col_width)
                result += text
            return result

        def separator(char="-"):
            return char * width

        def format_money(amount, symbol=None, position=None):
            currency = self.currency_id
            sym = symbol or currency.symbol or "Ar"
            pos = position or ("before" if currency.position == "before" else "after")
            try:
                amount_str = f"{float(amount):,.2f}".replace(",", " ")
            except (ValueError, TypeError):
                amount_str = "0.00"
            if pos == "before":
                return f"{sym}{amount_str}"
            return f"{amount_str} {sym}"

        company = self.company_id

        # === INITIALISATION ===
        cmd(INIT_PRINTER)

        # === LOGO ===
        if print_logo and company.logo:
            try:
                logo_binary = base64.b64decode(company.logo)
                result = convert_image_to_raster(logo_binary, 384)
                if result:
                    data, width_bytes, height = result
                    cmd(ALIGN_CENTER)
                    cmd(print_raster_image(data, width_bytes, height))
                    cmd(feed(2))
            except Exception:
                pass

        # === EN-TÊTE ===
        cmd(ALIGN_CENTER + BOLD_ON + SIZE_DOUBLE_HEIGHT)
        add(f"--- {company.name} ---")
        cmd(SIZE_NORMAL + BOLD_OFF)

        if company.phone:
            add(f"Tel: {company.phone}")
        if company.email:
            add(company.email)
        if company.website:
            add(company.website)

        add(separator())
        cmd(ALIGN_LEFT)

        # === INFOS TICKET ===
        add(f"Date : {self.date_order.strftime('%d/%m/%Y %H:%M')}")
        add(f"Caisse : {self.config_id.name} (ID:{self.config_id.id})")

        if self.user_id:
            add(f"Caissier: {self.user_id.name}")
        if self.partner_id:
            add(f"Client: {self.partner_id.name}")

        # Restaurant: Table et couverts
        table_info = self._get_table_info()
        if table_info:
            add(f"Salle : {table_info['floor']} - Table : {table_info['table']}")
            if hasattr(self, "customer_count") and self.customer_count:
                add(f"Couvert(s): {self.customer_count}")

        add(separator())

        # === PRODUITS ===
        cmd(BOLD_ON)
        add(
            table_row(
                [
                    {"text": "ARTICLES", "width": 0.55, "align": "left"},
                    {"text": "Totals TTC", "width": 0.25, "align": "right"},
                ]
            )
        )
        cmd(BOLD_OFF)

        # Calculer taux de taxe principal
        tax_rate = 0
        for ln in self.lines:
            if ln.tax_ids:
                for tax in ln.tax_ids:
                    if tax.amount > 0:
                        tax_rate = tax.amount / 100
                        break
                break

        total_sans_remise = 0
        individual_discounts = 0

        # Séparer lignes normales et lignes de remise
        normal_lines = []
        discount_lines = []

        for ln in self.lines:
            is_reward = hasattr(ln, "is_reward_line") and ln.is_reward_line
            is_discount_line = ln.price_unit < 0 and any(
                word in (ln.product_id.name or "").lower()
                for word in ["remise", "discount", "%", "sur votre"]
            )

            if is_reward or is_discount_line:
                discount_lines.append(ln)
            else:
                normal_lines.append(ln)

        # Afficher les produits normaux
        for ln in normal_lines:
            qty = int(ln.qty)
            name = ln.product_id.name[:28] if ln.product_id else "Produit"
            subtotal = ln.price_subtotal_incl
            discount = ln.discount or 0
            standard_price = ln.product_id.lst_price if ln.product_id else 0
            price_unit = ln.price_unit

            # Calculer remise pricelist
            pricelist_discount = 0
            if standard_price > 0 and price_unit < standard_price and discount == 0:
                pricelist_discount = (
                    (standard_price - price_unit) / standard_price
                ) * 100

            # Total sans remise
            standard_price_ttc = standard_price * (1 + tax_rate)
            total_sans_remise += standard_price_ttc * qty

            # Vérifier si produit offert
            is_free = subtotal == 0 or (
                hasattr(ln, "is_reward_line") and ln.is_reward_line and subtotal == 0
            )

            # Afficher la ligne
            cmd(BOLD_ON)
            if is_free:
                add(
                    table_row(
                        [
                            {"text": f"({qty}) {name}", "width": 0.65, "align": "left"},
                            {"text": "*OFFERT", "width": 0.35, "align": "right"},
                        ]
                    )
                )
            else:
                add(
                    table_row(
                        [
                            {"text": f"({qty}) {name}", "width": 0.65, "align": "left"},
                            {
                                "text": format_money(subtotal),
                                "width": 0.35,
                                "align": "right",
                            },
                        ]
                    )
                )
            cmd(BOLD_OFF)

            # Afficher remise si présente
            effective_discount = discount if discount > 0 else pricelist_discount
            if effective_discount > 0 and not is_free:
                price_ttc = price_unit * (1 + tax_rate)
                discount_amount = (standard_price_ttc - price_ttc) * qty
                individual_discounts += discount_amount
                add(
                    f"   Remise {effective_discount:.0f}% (-{format_money(discount_amount)})"
                )

            add("")

        # === REMISE GLOBALE (fidélité) ===
        loyalty_discount_pct = self._get_loyalty_discount_pct()
        if loyalty_discount_pct and loyalty_discount_pct > 0:
            add(separator())
            cmd(ALIGN_CENTER + BOLD_ON)
            add(f"Remise de {loyalty_discount_pct:.0f}% sur votre commande")
            cmd(BOLD_OFF + ALIGN_LEFT)

        add(separator())

        # === TOTAUX ===

        # Total sans remise
        if total_sans_remise > self.amount_total + 0.01:
            add(
                table_row(
                    [
                        {"text": "TOTAL SANS REMISE", "width": 0.55, "align": "left"},
                        {
                            "text": format_money(total_sans_remise),
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )

        # Remises sur produits
        if individual_discounts > 0:
            add(
                table_row(
                    [
                        {
                            "text": "REMISES SUR PRODUITS",
                            "width": 0.55,
                            "align": "left",
                        },
                        {
                            "text": format_money(individual_discounts),
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )

        # Remise globale (fidélité)
        if loyalty_discount_pct and loyalty_discount_pct > 0:
            subtotal_before_global = total_sans_remise - individual_discounts
            global_discount = subtotal_before_global * (loyalty_discount_pct / 100)
            if global_discount > 0:
                add(
                    table_row(
                        [
                            {"text": "REMISE GLOBALE", "width": 0.55, "align": "left"},
                            {
                                "text": format_money(global_discount),
                                "width": 0.25,
                                "align": "right",
                            },
                        ]
                    )
                )

        # Total des remises
        total_discount = individual_discounts
        if loyalty_discount_pct and loyalty_discount_pct > 0:
            subtotal_before_global = total_sans_remise - individual_discounts
            total_discount += subtotal_before_global * (loyalty_discount_pct / 100)

        if total_discount > 0:
            add(
                table_row(
                    [
                        {"text": "TOTAL DES REMISES", "width": 0.55, "align": "left"},
                        {
                            "text": format_money(total_discount),
                            "width": 0.25,
                            "align": "right",
                        },
                    ]
                )
            )

        # Total à payer
        total_qty = sum(l.qty for l in self.lines if l.price_unit >= 0)
        cmd(BOLD_ON)
        add(
            table_row(
                [
                    {
                        "text": f"TOTAL A PAYER ({int(total_qty)})",
                        "width": 0.55,
                        "align": "left",
                    },
                    {
                        "text": format_money(self.amount_total),
                        "width": 0.25,
                        "align": "right",
                    },
                ]
            )
        )
        cmd(BOLD_OFF)

        # === DÉTAILS TAXES ===
        tax_details = self._get_tax_details()
        if tax_details and self.amount_tax > 0:
            add("")
            add(
                table_row(
                    [
                        {"text": "TAUX", "width": 0.25, "align": "center"},
                        {"text": "HT", "width": 0.25, "align": "right"},
                        {"text": "TVA", "width": 0.25, "align": "right"},
                        {"text": "TTC", "width": 0.25, "align": "right"},
                    ]
                )
            )
            add(separator())

            for tax in tax_details:
                add(
                    table_row(
                        [
                            {
                                "text": f"{tax['rate']:.0f}%",
                                "width": 0.25,
                                "align": "center",
                            },
                            {
                                "text": format_money(tax["base"]),
                                "width": 0.25,
                                "align": "right",
                            },
                            {
                                "text": format_money(tax["amount"]),
                                "width": 0.25,
                                "align": "right",
                            },
                            {
                                "text": format_money(tax["total"]),
                                "width": 0.25,
                                "align": "right",
                            },
                        ]
                    )
                )

        # === PAIEMENTS ===
        if self.payment_ids:
            add("")
            add("Encaissement:")
            for payment in self.payment_ids:
                if payment.amount > 0:
                    add(
                        table_row(
                            [
                                {
                                    "text": payment.payment_method_id.name,
                                    "width": 0.6,
                                    "align": "left",
                                },
                                {
                                    "text": format_money(payment.amount),
                                    "width": 0.4,
                                    "align": "right",
                                },
                            ]
                        )
                    )

        # Rendu monnaie
        total_paid = sum(p.amount for p in self.payment_ids if p.amount > 0)
        change = total_paid - self.amount_total
        if change > 0.01:
            add(
                table_row(
                    [
                        {"text": "Rendu", "width": 0.6, "align": "left"},
                        {"text": format_money(change), "width": 0.4, "align": "right"},
                    ]
                )
            )

        # === FIDÉLITÉ ===
        loyalty = self._get_loyalty_data() if show_loyalty else None

        if loyalty:
            add("")
            cmd(BOLD_ON + ALIGN_CENTER)
            add("******** VOTRE COMPTE FIDÉLITÉ ********")
            cmd(BOLD_OFF + ALIGN_LEFT)

            add(f"Numéro Carte: {loyalty['card_number']}")
            add(separator("-"))

            # Points précédents
            if (
                loyalty.get("previous_points") is not None
                and loyalty["previous_points"] > 0
            ):
                add(f"Points de fidélité : {loyalty['previous_points']:.1f} pts")

            # Points gagnés
            if (
                loyalty.get("points_earned") is not None
                and loyalty["points_earned"] > 0
            ):
                add(f"Points gagnés: +{loyalty['points_earned']:.1f} pts")

            # Points utilisés
            if loyalty.get("points_used") is not None and loyalty["points_used"] > 0:
                add(f"Points utilisés: {loyalty['points_used']:.1f} pts")

            # Nouveau solde
            if (
                loyalty.get("current_points") is not None
                and loyalty["current_points"] > 0
            ):
                cmd(BOLD_ON)
                add(f"Nouveau solde: {loyalty['current_points']:.1f} pts")
                cmd(BOLD_OFF)
        else:
            add("")
            cmd(ALIGN_CENTER + BOLD_ON)
            add("*** PAS DE CARTE FIDÉLITÉ ? ***")
            cmd(BOLD_OFF)
            add("Demandez votre carte, elle est gratuite!")
            cmd(ALIGN_LEFT)

        # === PIED DE PAGE ===
        add("")
        cmd(ALIGN_CENTER)
        add(footer_message)
        add(goodbye_message)

        # === CODE-BARRES ===
        if print_barcode:
            cmd(feed(1))
            cmd(ALIGN_CENTER)
            cmd(feed(1))

            # Utiliser barcode_value si disponible, sinon générer
            barcode_data = getattr(self, "barcode_value", None)
            # barcode_data = getattr(self, 'barcode_value', None) or self._generate_barcode_data()
            if barcode_data:
                cmd(barcode_ean13(barcode_data))

        

        # === OUVRIR TIROIR CAISSE ===
        # si payment_id.payment_method_id.name == "Especes": lancer ouverture tiroir caisse
        if reprint is False:
            for payment in self.payment_ids:
                if (
                    payment.payment_method_id.name
                    and payment.payment_method_id.name.lower() == "cash"
                ):
                    try:
                        cmd(OPEN_CASH_DRAWER)
                    except Exception:
                        cmd(OPEN_CASH_DRAWER_ALTERNATIVE)
                    break
        
        else: 
            # En cas de réimpression, ajouter une note pour indiquer que c'est une copie
            cmd(ALIGN_CENTER + BOLD_ON)
            message = f" *** Réimpression du Ticket {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}***"
            add(message)
            cmd(BOLD_OFF + ALIGN_LEFT)
        
        # === COUPE PAPIER ===
        cmd(feed(4))
        cmd(CUT_PAPER)
            
        return bytes(output)

    def _generate_barcode_data(self):
        """Génère les données du code-barres EAN-13"""
        store_id = str(self.company_id.id).zfill(2)[-2:]
        register_num = str(self.config_id.id).zfill(2)[-2:]
        date_str = self.date_order.strftime("%m%d")
        order_id_str = str(self.id).zfill(4)[-4:]
        return f"{store_id}{register_num}{date_str}{order_id_str}"

    # Methode pour récuperer la derneire commande
    @api.model
    def get_last_order(self, config_id=None, user_id=None):
        """
        Récupère la dernière commande POS pour une caisse ou un utilisateur donné.
        Si aucun paramètre n'est fourni, retourne la dernière commande globale.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info("=" * 60)
        _logger.info("🔍 GET_LAST_ORDER - Début")
        _logger.info(f"📥 Paramètres reçus:")
        _logger.info(f"   - config_id: {config_id} (type: {type(config_id).__name__})")
        _logger.info(f"   - user_id: {user_id} (type: {type(user_id).__name__})")
        
        domain = []
        if config_id:
            domain.append(("session_id.config_id", "=", config_id))
            _logger.info(f"✓ Filtre ajouté: session_id.config_id = {config_id}")
        else:
            _logger.info(f"⚠️  Aucun filtre config_id (valeur: {config_id})")
            
        if user_id:
            domain.append(("user_id", "=", user_id))
            _logger.info(f"✓ Filtre ajouté: user_id = {user_id}")
        else:
            _logger.info(f"⚠️  Aucun filtre user_id (valeur: {user_id})")
        
        _logger.info(f"🔎 Domain final: {domain}")
        
        last_order = self.search(domain, order="id desc", limit=1)
        
        if last_order:
            _logger.info(f"✅ Commande trouvée:")
            _logger.info(f"   - Nom: {last_order.name}")
            _logger.info(f"   - ID: {last_order.id}")
            _logger.info(f"   - Session: {last_order.session_id.name}")
            _logger.info(f"   - Config ID: {last_order.session_id.config_id.id}")
            _logger.info(f"   - Config Name: {last_order.session_id.config_id.name}")
            _logger.info(f"   - User: {last_order.user_id.name}")
            _logger.info(f"   - Montant: {last_order.amount_total}")
        else:
            _logger.warning(f"❌ Aucune commande trouvée avec domain: {domain}")
        
        _logger.info("🔍 GET_LAST_ORDER - Fin")
        _logger.info("=" * 60)
        
        return last_order

    @api.model
    def get_receipt_by_name(self, order_name):
        """Récupère une commande par son nom et génère le ticket."""
        order = self.search([("name", "=", order_name)], limit=1)
        if not order:
            return None
        return order.generate_escpos_receipt()
