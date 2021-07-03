from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    default_printer_id = fields.Many2one('printing.printer', 'Print Node Printer')
