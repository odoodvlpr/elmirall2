# -*- coding: utf-8 -*-

{
    'name': "Product description html",

    'summary': """
        change description of product as html
        """,

    'description': """
        Module extended description
        
    """,

    'author': "claribel Dominguez",
    'website': "https://www.octupus.es",

    'category': 'productivity',
    'version': '0.1',

    'depends': ['base', 'product', 'sale'],

    'data': [
        'security/ir.model.access.csv',
        'views/product_description.xml',

    ],
    'installable': True,
    'application': False,
}
