
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
        
        params = {'fields': fields}
        if limit:
            params['limit'] = limit
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search_read',
            [domain], params
        )
    
    def get_order_data(self, order_name):
        """Récupère les données complètes d'une commande POS"""
        
        if not order_name:
            return None
        
        # Rechercher la commande par référence ou nom
        domain = ['|', 
            ('pos_reference', 'ilike', order_name), 
            ('name', 'ilike', order_name)
        ]
        
        # Récupérer la commande
        orders = self.search_read('pos.order', domain, [
            'id', 'name', 'pos_reference', 'date_order', 'amount_total',
            'amount_tax', 'amount_paid', 'partner_id', 'user_id',
            'company_id', 'table_id', 'customer_count'
        ], limit=1)
        
        if not orders:
            print(f"⚠ Commande non trouvée: {order_name}")
            return None
        
        order = orders[0]
        order_id = order['id']
        
        # Récupérer les lignes de commande
        lines = self.search_read('pos.order.line',
            [('order_id', '=', order_id)],
            ['product_id', 'qty', 'price_unit', 'price_subtotal_incl']
        )
        
        # Récupérer les paiements
        payments = self.search_read('pos.payment',
            [('pos_order_id', '=', order_id)],
            ['payment_method_id', 'amount']
        )
        
        # Récupérer les infos de la société
        company = self._get_company(order.get('company_id'))
        
        # Récupérer la devise
        currency = self._get_currency(company.get('currency_id'))
        
        # Récupérer le caissier
        cashier = self._get_user_name(order.get('user_id'))
        
        # Construire les données du ticket
        return {
            'order_name': order.get('pos_reference') or order.get('name'),
            'date_order': order.get('date_order'),
            'company_name': company.get('name', ''),
            'company_phone': company.get('phone', ''),
            'company_email': company.get('email', ''),
            'company_website': company.get('website', ''),
            'cashier': cashier,
            'table': order['table_id'][1] if order.get('table_id') else '',
            'customer_count': order.get('customer_count', ''),
            'lines': [{
                'name': line['product_id'][1] if line.get('product_id') else 'Produit',
                'qty': line.get('qty', 1),
                'price': line.get('price_unit', 0),
                'subtotal': line.get('price_subtotal_incl', 0)
            } for line in lines],
            'subtotal': order['amount_total'] - order['amount_tax'],
            'tax': order['amount_tax'],
            'total': order['amount_total'],
            'payments': [{
                'name': p['payment_method_id'][1] if p.get('payment_method_id') else 'Paiement',
                'amount': p.get('amount', 0)
            } for p in payments],
            'currency_symbol': currency.get('symbol', 'Ar'),
            'currency_position': currency.get('position', 'after')
        }
    
    def _get_company(self, company_id):
        """Récupère les infos d'une société"""
        if not company_id:
            return {}
        
        cid = company_id[0] if isinstance(company_id, (list, tuple)) else company_id
        companies = self.search_read('res.company',
            [('id', '=', cid)],
            ['name', 'phone', 'email', 'website', 'currency_id'],
            limit=1
        )
        return companies[0] if companies else {}
    
    def _get_currency(self, currency_id):
        """Récupère les infos d'une devise"""
        if not currency_id:
            return {}
        
        cid = currency_id[0] if isinstance(currency_id, (list, tuple)) else currency_id
        currencies = self.search_read('res.currency',
            [('id', '=', cid)],
            ['name', 'symbol', 'position'],
            limit=1
        )
        return currencies[0] if currencies else {}
    
    def _get_user_name(self, user_id):
        """Récupère le nom d'un utilisateur"""
        if not user_id:
            return ""
        
        uid = user_id[0] if isinstance(user_id, (list, tuple)) else user_id
        users = self.search_read('res.users',
            [('id', '=', uid)],
            ['name'],
            limit=1
        )
        return users[0]['name'] if users else ""
