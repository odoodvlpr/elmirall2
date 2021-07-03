# -*- coding: utf-8 -*-
{
    'name': "oct_gls",

    'summary': """
        This module conect whit gls """,

    'description': """
       sgonzalez
    """,

    'author': "Octupus technologies S.L.",
    'website': "https://www.octupus.es",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Operations',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','delivery','oct_print_node'],

    # always loaded
    'data': [
        'views/views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [

    ],
}
