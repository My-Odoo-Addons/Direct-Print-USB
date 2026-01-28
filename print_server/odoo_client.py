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
            ],
            limit=1,
        )

        if not orders:
            print(f"Commande non trouvée: {order_name}")
            return None

        order = orders[0]
        order_id = order["id"]

        # Récupérer les lignes de commande
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
            ],
        )

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

        # Calculer le rendu de monnaie
        total_paid = sum(p.get("amount", 0) for p in payments)
        change = max(0, total_paid - order["amount_total"])

        # Calculer les totaux avec/sans remise
        total_before_discount = sum(
            line.get("qty", 1) * line.get("price_unit", 0) for line in lines
        )
        total_discount = total_before_discount - (
            order["amount_total"] - order["amount_tax"]
        )

        # Construire les données du ticket
        return {
            "order_name": order.get("pos_reference") or order.get("name"),
            "date_order": order.get("date_order"),
            "company_name": company.get("name", ""),
            "company_phone": company.get("phone", ""),
            "company_email": company.get("email", ""),
            "company_website": company.get("website", ""),
            "cashier": cashier,
            "table": order["table_id"][1] if order.get("table_id") else "",
            "customer_count": order.get("customer_count", ""),
            "lines": [
                {
                    "name": (
                        line["product_id"][1] if line.get("product_id") else "Produit"
                    ),
                    "qty": line.get("qty", 1),
                    "price": line.get("price_unit", 0),
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
            # Données fidélité (si disponibles)
            "loyalty": self._get_loyalty_data(order_id, order.get("partner_id")),
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

    def _get_loyalty_data(self, order_id, partner_id):
        """
        Récupère les données du programme fidélité pour un client
        Compatible avec le module loyalty de Odoo
        """
        if not partner_id:
            return None

        pid = partner_id[0] if isinstance(partner_id, (list, tuple)) else partner_id

        try:
            # Essayer de récupérer les données fidélité (Odoo 16+)
            # Le modèle peut varier selon la version et les modules installés

            # Vérifier si le module loyalty est installé
            loyalty_cards = self.search_read(
                "loyalty.card", [("partner_id", "=", pid)], ["points", "code"], limit=1
            )

            if loyalty_cards:
                card = loyalty_cards[0]

                # Récupérer l'historique des points pour cette commande
                points_history = (
                    self.search_read(
                        "loyalty.history",
                        [("card_id", "=", card["id"]), ("order_id", "=", order_id)],
                        ["points", "type"],
                        limit=10,
                    )
                    if "loyalty.history" in self._get_models()
                    else []
                )

                points_earned = sum(
                    h["points"] for h in points_history if h.get("type") == "add"
                )
                points_used = sum(
                    abs(h["points"]) for h in points_history if h.get("type") == "use"
                )

                return {
                    "card_number": card.get("code", ""),
                    "current_points": card.get("points", 0),
                    "previous_points": card.get("points", 0)
                    - points_earned
                    + points_used,
                    "points_earned": points_earned,
                    "points_used": points_used,
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
