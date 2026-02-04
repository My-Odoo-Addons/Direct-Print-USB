from print_server.odoo_client import OdooClient
from print_server.receipt_formatter import ReceiptFormatter
from print_server.printer import Printer

client = OdooClient()
client.connect()

order = input('Numéro de commande à imprimer: ')
data = client.get_order_data(order)
if data:
    formatter = ReceiptFormatter()
    ticket = formatter.format_receipt(data)
    
    printer = Printer()
    result = printer.print_raw(ticket)
    print('Impression:', 'OK' if result else 'ERREUR')