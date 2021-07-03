# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductDescriptionHTML(models.Model):
    _inherit = 'product.template'

    description_sale_presta = fields.Html(string='Descripción de Venta para presta')
    description_presta = fields.Html(string='Descripción para presta')
