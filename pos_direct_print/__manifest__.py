{
    "name": "POS Direct Printing",
    "version": "18.0.1.0.0",
    "summary": "Permettre l'impression directe depuis le point de vente",
    "category": "Point of Sale",
    "depends": ["point_of_sale"],
    "author": "Sarobidy",
    "license": "LGPL-3",
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_direct_print/static/src/js/print.js",
        ],
    },
    "installable": True,
    "application": False,
}
