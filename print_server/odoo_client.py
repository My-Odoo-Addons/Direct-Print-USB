# CLIENT XML-RPC POUR ODOO

import xmlrpc.client
from .config import ODOO_CONFIG


class OdooClient:
    """Client XML-RPC pour communiquer avec Odoo"""

    def __init__(self):
        self.url = ODOO_CONFIG["url"]
        self.db = ODOO_CONFIG["database"]
        self.username = ODOO_CONFIG["username"]
        self.password = ODOO_CONFIG["password"]
        self.uid = None
        self.models = None

    def connect(self):
        """Authentification et connexion à Odoo"""
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, self.username, self.password, {})

            if not self.uid:
                raise Exception("Échec de l'authentification Odoo")

            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
            print(f"✓ Connecté à Odoo (uid: {self.uid})")
            return True
        except Exception as e:
            print(f"✗ Erreur de connexion Odoo: {e}")
            return False

    def search_read(self, model, domain, fields, limit=None):
        """Recherche et lecture des enregistrements"""
        if not self.uid:
            self.connect()

        if not self.models:
            raise Exception("Non connecté à Odoo")

        params = {"fields": fields}
        if limit:
            params["limit"] = limit

        return self.models.execute_kw(
            self.db, self.uid, self.password, model, "search_read", [domain], params
        )

    def get_order_data(self, order_name):
        """Récupère les données complètes d'une commande POS"""

        if not order_name:
            return None

        # Rechercher la commande par référence ou nom
        domain = [
            "|",
            ("pos_reference", "ilike", order_name),
            ("name", "ilike", order_name),
        ]

        # Récupérer la commande
        orders = self.search_read(
            "pos.order",
            domain,
            [
                "id",
                "name",
                "pos_reference",
                "date_order",
                "amount_total",
                "amount_tax",
                "amount_paid",
                "partner_id",
                "user_id",
                "company_id",
                "table_id",
                "customer_count",
                "session_id",
            ],
            limit=1,
        )

        if not orders:
            print(f"Commande non trouvée: {order_name}")
            return None

        order = orders[0]
        order_id = order["id"]

        # Récupérer les lignes de commande (avec tax_ids pour détails taxes)
        lines = self.search_read(
            "pos.order.line",
            [("order_id", "=", order_id)],
            [
                "product_id",
                "qty",
                "price_unit",
                "price_subtotal_incl",
                "discount",
                "price_subtotal",
                "points_cost",
                "is_reward_line",
                "tax_ids",
            ],
        )
        
        # Calculer les points utilisés à partir des lignes
        total_points_used = sum(line.get("points_cost", 0) or 0 for line in lines)
        
        # Récupérer les détails des taxes
        tax_details = self._get_tax_details(lines)

        # Récupérer les paiements
        payments = self.search_read(
            "pos.payment",
            [("pos_order_id", "=", order_id)],
            ["payment_method_id", "amount"],
        )

        # Récupérer les infos de la société
        company = self._get_company(order.get("company_id"))

        # Récupérer la devise
        currency = self._get_currency(company.get("currency_id"))

        # Récupérer le caissier
        cashier = self._get_user_name(order.get("user_id"))

        # Récupérer le client
        customer = self._get_partner_name(order.get("partner_id"))

        # Récupérer le numéro de caisse
        pos_config_name = self._get_pos_config_name(order.get("session_id"))

        # Calculer le rendu de monnaie
        # Utiliser la somme des paiements positifs pour éviter les problèmes avec amount_paid
        total_paid_positive = sum(p.get("amount", 0) for p in payments if p.get("amount", 0) > 0)
        change = max(0, total_paid_positive - order["amount_total"])

        # Calculer les totaux avec/sans remise
        # Exclure les lignes de remise globale (prix négatif et nom contenant remise/discount/%)
        def is_discount_line(line):
            name = line.get("product_id", [0, ""])[1] if line.get("product_id") else ""
            price = line.get("price_unit", 0)
            return price < 0 and any(word in name.lower() for word in ["remise", "discount", "%", "sur votre"])
        
        regular_lines = [line for line in lines if not is_discount_line(line)]
        discount_lines = [line for line in lines if is_discount_line(line)]
        
        total_before_discount_ht = sum(
            line.get("qty", 1) * line.get("price_unit", 0) for line in regular_lines
        )
        
        # Calculer le taux de TVA moyen pour obtenir le total TTC avant remise
        # Utiliser le taux de TVA du subtotal actuel pour estimer
        tax_rate = order["amount_tax"] / (order["amount_total"] - order["amount_tax"]) if (order["amount_total"] - order["amount_tax"]) > 0 else 0
        total_before_discount = total_before_discount_ht * (1 + tax_rate)
        
        # Calculer la remise totale (valeur absolue des lignes de remise)
        total_discount_amount = abs(sum(
            line.get("qty", 1) * line.get("price_unit", 0) * (1 + tax_rate) for line in discount_lines
        ))
        
        # Vérifier avec le calcul alternatif basé sur les totaux
        calculated_discount = total_before_discount - order["amount_total"]
        total_discount = max(total_discount_amount, calculated_discount) if total_discount_amount > 0 else calculated_discount

        # Construire les données du ticket
        return {
            "order_id": order_id,
            "order_name": order.get("pos_reference") or order.get("name"),
            "date_order": order.get("date_order"),
            "company_id": order.get("company_id", [0])[0] if order.get("company_id") else 0,
            "company_name": company.get("name", ""),
            "company_phone": company.get("phone", ""),
            "company_email": company.get("email", ""),
            "company_website": company.get("website", ""),
            "pos_config_name": pos_config_name,
            "cashier": cashier,
            "customer": customer,
            "table": order["table_id"][1] if order.get("table_id") else "",
            "customer_count": order.get("customer_count", ""),
            "lines": [
                {
                    "name": (
                        line["product_id"][1] if line.get("product_id") else "Produit"
                    ),
                    "qty": line.get("qty", 1),
                    "price": line.get("price_unit", 0),
                    "standard_price": self._get_product_standard_price(line.get("product_id", [0])[0]) if line.get("product_id") else 0,
                    "subtotal": line.get("price_subtotal_incl", 0),
                    "discount": line.get("discount", 0),
                    "is_free": line.get("price_subtotal_incl", 0) == 0,
                }
                for line in lines
            ],
            "subtotal": order["amount_total"] - order["amount_tax"],
            "tax": order["amount_tax"],
            "total": order["amount_total"],
            "total_before_discount": (
                total_before_discount if total_discount > 0 else None
            ),
            "total_discount": total_discount if total_discount > 0 else 0,
            "change": change,
            "payments": [
                {
                    "name": (
                        p["payment_method_id"][1]
                        if p.get("payment_method_id")
                        else "Paiement"
                    ),
                    "amount": p.get("amount", 0),
                }
                for p in payments
            ],
            "currency_symbol": currency.get("symbol", "Ar"),
            "currency_position": currency.get("position", "after"),
            # Détails des taxes
            "tax_details": tax_details,
            # Données fidélité (si disponibles)
            "loyalty": self._get_loyalty_data(order_id, order.get("partner_id"), total_points_used),
        }

    def _get_company(self, company_id):
        """Récupère les infos d'une société"""
        if not company_id:
            return {}

        cid = company_id[0] if isinstance(company_id, (list, tuple)) else company_id
        companies = self.search_read(
            "res.company",
            [("id", "=", cid)],
            ["name", "phone", "email", "website", "currency_id", "logo"],
            limit=1,
        )

        if companies:
            company = companies[0]
            # Sauvegarder le logo si disponible
            if company.get("logo"):
                self._save_company_logo(company["logo"], cid)
            return company
        return {}

    def _save_company_logo(self, logo_base64, company_id):
        """Sauvegarde le logo de la société en fichier PNG"""
        import base64
        import os
        from .config import PRINTER_CONFIG, BASE_DIR

        try:
            # Décoder le logo base64
            logo_data = base64.b64decode(logo_base64)

            # Chemin du logo
            logo_path = os.path.join(BASE_DIR, f"logo.png")

            # Sauvegarder le fichier
            with open(logo_path, "wb") as f:
                f.write(logo_data)

            # Mettre à jour le chemin du logo dans la config
            PRINTER_CONFIG["logo_path"] = logo_path
            print(f"✓ Logo société sauvegardé: {logo_path}")

        except Exception as e:
            print(f"Erreur sauvegarde logo: {e}")

    def _get_currency(self, currency_id):
        """Récupère les infos d'une devise"""
        if not currency_id:
            return {}

        cid = currency_id[0] if isinstance(currency_id, (list, tuple)) else currency_id
        currencies = self.search_read(
            "res.currency", [("id", "=", cid)], ["name", "symbol", "position"], limit=1
        )
        return currencies[0] if currencies else {}

    def _get_user_name(self, user_id):
        """Récupère le nom d'un utilisateur"""
        if not user_id:
            return ""

        uid = user_id[0] if isinstance(user_id, (list, tuple)) else user_id
        users = self.search_read("res.users", [("id", "=", uid)], ["name"], limit=1)
        return users[0]["name"] if users else ""

    def _get_partner_name(self, partner_id):
        """Récupère le nom d'un partenaire/client"""
        if not partner_id:
            return ""

        pid = partner_id[0] if isinstance(partner_id, (list, tuple)) else partner_id
        partners = self.search_read("res.partner", [("id", "=", pid)], ["name"], limit=1)
        return partners[0]["name"] if partners else ""

    def _get_pos_config_name(self, session_id):
        """Récupère le nom de la configuration POS depuis la session"""
        if not session_id:
            return ""

        sid = session_id[0] if isinstance(session_id, (list, tuple)) else session_id
        sessions = self.search_read(
            "pos.session", 
            [("id", "=", sid)], 
            ["config_id"], 
            limit=1
        )
        
        if sessions and sessions[0].get("config_id"):
            config_id = sessions[0]["config_id"][0]
            configs = self.search_read(
                "pos.config", 
                [("id", "=", config_id)], 
                ["name"], 
                limit=1
            )
        return configs[0]["name"] if configs else ""
    
    def _get_product_standard_price(self, product_id):
        """Récupère le prix standard d'un produit"""
        if not product_id:
            return 0
        
        try:
            products = self.search_read(
                "product.product", 
                [("id", "=", product_id)], 
                ["list_price"], 
                limit=1
            )
            return products[0]["list_price"] if products else 0
        except Exception:
            return 0    
        return ""

    def _get_tax_details(self, lines, order_tax=0):
        """
        Récupère et agrège les détails des taxes à partir des lignes de commande
        
        Args:
            lines: Liste des lignes de commande
            order_tax: Montant total de taxe de la commande (fallback)
        
        Retourne une liste de dict:
        [
            {
                "name": "TVA 15%",
                "rate": 15.0,
                "base": 100.0,      # Montant HT
                "amount": 15.0,     # Montant de la taxe
                "total": 115.0      # Montant TTC
            }
        ]
        """
        if not lines:
            return []
        
        # Collecter tous les tax_ids uniques
        all_tax_ids = set()
        for line in lines:
            tax_ids = line.get("tax_ids", [])
            if tax_ids:
                all_tax_ids.update(tax_ids)
        
        # Calculer les totaux depuis les lignes
        total_base = sum(line.get("price_subtotal", 0) or 0 for line in lines)
        total_ttc = sum(line.get("price_subtotal_incl", 0) or 0 for line in lines)
        total_tax = total_ttc - total_base
        
        # Fallback: si pas de tax_ids mais il y a des taxes calculées
        if not all_tax_ids and total_tax > 0:
            # Calculer le taux approximatif
            if total_base > 0:
                rate = round((total_tax / total_base) * 100, 0)
            else:
                rate = 0
            
            return [{
                "name": f"TVA {rate:.0f}%",
                "rate": rate,
                "base": round(total_base, 2),
                "amount": round(total_tax, 2),
                "total": round(total_ttc, 2)
            }]
        
        if not all_tax_ids:
            return []
        
        # Récupérer les infos des taxes
        taxes = self.search_read(
            "account.tax",
            [("id", "in", list(all_tax_ids))],
            ["id", "name", "amount", "amount_type", "price_include"]
        )
        
        # Créer un dictionnaire tax_id -> tax_info
        tax_map = {t["id"]: t for t in taxes}
        
        # Agréger les montants par taxe
        tax_totals = {}  # tax_id -> {base, amount, total}
        
        for line in lines:
            tax_ids = line.get("tax_ids", [])
            price_subtotal = line.get("price_subtotal", 0) or 0  # Montant HT
            price_subtotal_incl = line.get("price_subtotal_incl", 0) or 0  # Montant TTC
            tax_amount = price_subtotal_incl - price_subtotal  # Montant taxe
            
            for tax_id in tax_ids:
                if tax_id not in tax_totals:
                    tax_totals[tax_id] = {
                        "base": 0,
                        "amount": 0,
                        "total": 0
                    }
                
                tax_totals[tax_id]["base"] += price_subtotal
                tax_totals[tax_id]["amount"] += tax_amount
                tax_totals[tax_id]["total"] += price_subtotal_incl
        
        # Construire la liste des détails de taxes
        tax_details = []
        for tax_id, totals in tax_totals.items():
            tax_info = tax_map.get(tax_id, {})
            tax_details.append({
                "name": tax_info.get("name", f"Taxe {tax_id}"),
                "rate": tax_info.get("amount", 0),
                "base": round(totals["base"], 2),
                "amount": round(totals["amount"], 2),
                "total": round(totals["total"], 2)
            })
        
        # Trier par taux de taxe
        tax_details.sort(key=lambda x: x["rate"])
        
        return tax_details

    def _get_loyalty_data(self, order_id, partner_id, points_used_from_lines=0):
        """
        Récupère les données du programme fidélité pour un client
        Compatible avec le module loyalty de Odoo 18
        
        Args:
            order_id: ID de la commande
            partner_id: ID du client
            points_used_from_lines: Points utilisés calculés depuis pos.order.line.points_cost
        """
        if not partner_id:
            return None

        pid = partner_id[0] if isinstance(partner_id, (list, tuple)) else partner_id

        try:
            # Chercher l'historique de fidélité pour cette commande
            # C'est la source la plus fiable pour les points gagnés
            history = self.search_read(
                "loyalty.history",
                [("order_id", "=", order_id)],
                ["card_id", "issued", "used", "description"],
            )
            
            if history:
                # Trouver l'entrée du programme de fidélité (pas Gift Card)
                for h in history:
                    card_id = h["card_id"][0] if h.get("card_id") else None
                    if card_id:
                        # Récupérer les infos de la carte
                        cards = self.search_read(
                            "loyalty.card",
                            [("id", "=", card_id)],
                            ["code", "points", "program_id", "point_name"],
                            limit=1
                        )
                        
                        if cards:
                            card = cards[0]
                            program_name = card["program_id"][1] if card.get("program_id") else ""
                            
                            # Privilégier le programme "Loyalty" et ignorer les Gift Cards
                            if "loyalty" in program_name.lower() or "fidélité" in program_name.lower():
                                points_earned = h.get("issued", 0)
                                # Utiliser points_used_from_lines si disponible, sinon l'historique
                                points_used = points_used_from_lines if points_used_from_lines > 0 else h.get("used", 0)
                                current_points = card.get("points", 0)
                                
                                return {
                                    "card_number": card.get("code", ""),
                                    "program_name": program_name,
                                    "point_name": card.get("point_name", "pts"),
                                    "current_points": current_points,
                                    "previous_points": current_points - points_earned + points_used,
                                    "points_earned": points_earned,
                                    "points_used": points_used,
                                }
                
                # Si pas de programme Loyalty trouvé, prendre le premier historique non-Gift Card
                for h in history:
                    card_id = h["card_id"][0] if h.get("card_id") else None
                    if card_id:
                        cards = self.search_read(
                            "loyalty.card",
                            [("id", "=", card_id)],
                            ["code", "points", "program_id", "point_name"],
                            limit=1
                        )
                        
                        if cards:
                            card = cards[0]
                            program_name = card["program_id"][1] if card.get("program_id") else ""
                            
                            # Ignorer les Gift Cards
                            if "gift" not in program_name.lower():
                                points_earned = h.get("issued", 0)
                                # Utiliser points_used_from_lines si disponible
                                points_used = points_used_from_lines if points_used_from_lines > 0 else h.get("used", 0)
                                current_points = card.get("points", 0)
                                
                                return {
                                    "card_number": card.get("code", ""),
                                    "program_name": program_name,
                                    "point_name": card.get("point_name", "pts"),
                                    "current_points": current_points,
                                    "previous_points": current_points - points_earned + points_used,
                                    "points_earned": points_earned,
                                    "points_used": points_used,
                                }
            
            # Fallback: chercher la carte fidélité du client (programme type "loyalty")
            loyalty_cards = self.search_read(
                "loyalty.card", 
                [("partner_id", "=", pid)], 
                ["points", "code", "program_id", "point_name"]
            )

            for card in loyalty_cards:
                program_name = card["program_id"][1] if card.get("program_id") else ""
                # Chercher uniquement les programmes de type fidélité
                if "loyalty" in program_name.lower() or "fidélité" in program_name.lower():
                    return {
                        "card_number": card.get("code", ""),
                        "program_name": program_name,
                        "point_name": card.get("point_name", "pts"),
                        "current_points": card.get("points", 0),
                        "previous_points": None,
                        "points_earned": None,
                        "points_used": points_used_from_lines,
                    }
                    
        except Exception as e:
            # Module loyalty non installé ou erreur
            print(f"Données fidélité non disponibles: {e}")

        # Fallback: essayer avec pos.loyalty si disponible
        try:
            partner = self.search_read(
                "res.partner",
                [("id", "=", pid)],
                ["loyalty_points", "barcode"],
                limit=1,
            )

            if partner and partner[0].get("loyalty_points") is not None:
                return {
                    "card_number": partner[0].get("barcode", ""),
                    "current_points": partner[0].get("loyalty_points", 0),
                    "previous_points": None,
                    "points_earned": None,
                    "points_used": None,
                }
        except Exception:
            pass

        return None

    def _get_models(self):
        """Retourne la liste des modèles disponibles (pour vérifier les modules installés)"""
        try:
            return self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                "ir.model",
                "search_read",
                [[]],
                {"fields": ["model"], "limit": 1000},
            )
        except Exception:
            return []
