{
    "name": "POS Direct Printing",
    "version": "18.0.1.0.0",
    "summary": "Impression directe via USB depuis le Point de Vente",
    "category": "Point of Sale",
    "depends": ["point_of_sale"],
    "author": "Sarobidy",
    "license": "LGPL-3",
    
    # Data XML (pour les vues backend uniquement)
    "data": [
        "views/pos_config_views.xml",
    ],
    
    # Assets (pour les fichiers JS/XML du POS)
    "assets": {
        "point_of_sale._assets_pos": [
            # JavaScript
            "pos_direct_print/static/src/app/reprint_button.js",
            "pos_direct_print/static/src/js/print.js",  # Si vous en avez besoin
            
            # Templates XML
            "pos_direct_print/static/src/app/reprint_button.xml",
        ],
    },
    
    "installable": True,
    "application": False,
}