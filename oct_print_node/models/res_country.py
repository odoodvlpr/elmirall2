from odoo import fields, models, api


class ResCountry(models.Model):
    _inherit = 'res.country'

    need_comercial_invoice = fields.Boolean('Need Comercial Invoice')
