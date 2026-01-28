
# FORMATAGE DES TICKETS DE CAISSE


from datetime import datetime
from .config import PRINTER_CONFIG, RECEIPT_CONFIG
from . import escpos


class ReceiptFormatter:
    """Formate les tickets de caisse pour imprimantes thermiques"""
    
    def __init__(self):
        self.width = PRINTER_CONFIG["width"]
        self.footer_message = RECEIPT_CONFIG["footer_message"]
    
    def format_line(self, left, right):
        """Formate une ligne avec texte à gauche et à droite"""
        space = self.width - len(str(left)) - len(str(right))
        if space < 1:
            space = 1
        return str(left) + " " * space + str(right)
    
    def format_money(self, amount, symbol="Ar", position="after"):
        """Formate un montant avec la devise"""
        try:
            amount_str = f"{float(amount):,.2f}".replace(",", " ")
        except (ValueError, TypeError):
            amount_str = "0.00"
        
        if position == "before":
            return f"{symbol} {amount_str}"
        return f"{amount_str} {symbol}"
    
    def format_receipt(self, data):
        """Génère le contenu formaté du ticket"""
        currency = data.get("currency_symbol")
        # currency = data.get("currency_symbol", RECEIPT_CONFIG["default_currency"])

        # currency_pos = data.get("currency_position", RECEIPT_CONFIG["default_currency_position"])
        currency_pos = data.get("currency_position")
        
        lines = []
        
        # === EN-TÊTE : NOM DE LA SOCIÉTÉ ===
        lines.append(escpos.ALIGN_CENTER + escpos.BOLD_ON + escpos.SIZE_DOUBLE_HEIGHT)
        lines.append(data.get("company_name"))
        # lines.append(data.get("company_name", "MA SOCIETE"))
        lines.append(escpos.SIZE_NORMAL + escpos.BOLD_OFF)
        
        # === INFORMATIONS DE CONTACT ===
        lines.append(escpos.ALIGN_CENTER)
        if data.get("company_phone"):
            lines.append(f"Tel: {data['company_phone']}")
        if data.get("company_email"):
            lines.append(data["company_email"])
        if data.get("company_website"):
            lines.append(data["company_website"])
        
        lines.append("-" * self.width)
        
        # === CAISSIER / TABLE ===
        if data.get("cashier"):
            lines.append(f"Servi par: {data['cashier']}")
        if data.get("table"):
            table_info = f"Table: {data['table']}"
            if data.get("customer_count"):
                table_info += f", Couverts: {data['customer_count']}"
            lines.append(table_info)
        
        # === NUMÉRO DE COMMANDE (EN GRAND) ===
        lines.append("")
        lines.append(escpos.ALIGN_CENTER + escpos.BOLD_ON + escpos.SIZE_DOUBLE)
        order_name = data.get("order_name", "")
        order_num = order_name.split("-")[-1] if order_name else ""
        lines.append(order_num or order_name)
        lines.append(escpos.SIZE_NORMAL + escpos.BOLD_OFF)
        lines.append("")
        
        # === DATE & HEURE ===
        lines.append(escpos.ALIGN_CENTER)
        lines.append(datetime.now().strftime("%d/%m/%Y %H:%M"))
        lines.append(escpos.ALIGN_LEFT)
        lines.append("")
        
        # === LIGNES DE PRODUITS ===
        for item in data.get("lines", []):
            if isinstance(item, dict):
                name = item.get("name", "Produit")
                qty = item.get("qty", 1)
                price = item.get("price", 0)
                subtotal = item.get("subtotal", qty * price)
                
                lines.append(escpos.BOLD_ON)
                lines.append(self.format_line(
                    name[:22], 
                    self.format_money(subtotal, currency, currency_pos)
                ))
                lines.append(escpos.BOLD_OFF)
                lines.append(f"  {qty:.2f} x {self.format_money(price, currency, currency_pos)} / Unite(s)")
        
        # === SÉPARATEUR ===
        lines.append("")
        lines.append("-" * self.width)
        
        # === MONTANT HORS TAXES ===
        if data.get("subtotal") is not None:
            lines.append(self.format_line(
                "Montant hors taxes",
                self.format_money(data['subtotal'], currency, currency_pos)
            ))
        
        # === TAXES ===
        if data.get("tax") and float(data.get("tax", 0)) > 0:
            lines.append(self.format_line(
                "Taxes",
                self.format_money(data['tax'], currency, currency_pos)
            ))
        
        # === SÉPARATEUR ===
        lines.append("-" * self.width)
        
        # === TOTAL ===
        lines.append("")
        lines.append(escpos.BOLD_ON + escpos.SIZE_DOUBLE_HEIGHT)
        lines.append(self.format_line(
            "TOTAL",
            self.format_money(data.get('total', 0), currency, currency_pos)
        ))
        lines.append(escpos.SIZE_NORMAL + escpos.BOLD_OFF)
        
        # === PAIEMENTS ===
        for payment in data.get("payments", []):
            if isinstance(payment, dict):
                lines.append(self.format_line(
                    payment.get("name", "Paiement"),
                    self.format_money(payment.get("amount", 0), currency, currency_pos)
                ))
        
        # === PIED DE PAGE ===
        lines.append("")
        lines.append("-" * self.width)
        lines.append(escpos.ALIGN_CENTER)
        lines.append(self.footer_message)
        lines.append("")
        
        # === AVANCE PAPIER ET COUPE ===
        lines.append(escpos.FEED_LINES(4))
        lines.append(escpos.CUT_PAPER)
        
        return "\n".join(lines)
