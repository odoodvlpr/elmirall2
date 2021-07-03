# -*- coding: utf-8 -*-
{
    'name': "oct_cex_conector",

    'summary': """
        This module conect whit correos express""",

    'description': """
        Octupus technologies S.L.
    """,

    'author': "Octupus technologies S.L.",
    'website': "https://www.octupus.es",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Operations',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','delivery'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}