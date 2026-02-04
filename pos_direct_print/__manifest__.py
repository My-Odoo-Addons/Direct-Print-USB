{
    "name": "POS Direct Printing",
    "version": "18.0.1.0.0",
    "summary": "Impression directe via USB depuis le Point de Vente",
    "category": "Point of Sale",
    "depends": ["point_of_sale"],
    "author": "Sarobidy",
    "license": "LGPL-3",
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_direct_print/static/src/js/print.js",
        ],
    },
    "installable": True,
    "application": False,
}
