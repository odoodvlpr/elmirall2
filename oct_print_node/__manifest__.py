# -*- coding: utf-8 -*-
{
    'name': "Oct Print Node Printer",

    'summary': """
        Integrate Print Node printer with Odoo for direct printing
    """,

    'description': """
        Integrate Print Node printer with Odoo for direct printing
    """,

    'author': "Octupus Technologies S.L.",
    'website': "https://www.octupus.es",

    'category': 'Generic Modules',
    'version': '0.14.3',
    'images': ['static/description/icon.png'],

    "depends": [
        'base_report_to_printer',
        'delivery',
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/printing_server_data.xml',
        'views/printing_printer_view.xml',
        'views/res_users_view.xml',
        'views/delivery_carrier.xml',
        'views/res_company.xml',
        'views/res_config.xml',
        'reports/stock_report_print_node.xml',
        'views/res_country.xml'
    ],
    'external_dependencies': {
        'python': ['future'],
    },
}
