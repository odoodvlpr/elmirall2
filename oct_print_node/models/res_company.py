from odoo import fields, models, _


class ResUsers(models.Model):
    _inherit = "res.company"

    printer_ids = fields.One2many('printing.printer', 'company_id', 'Print Node Printers')

    def update_company_print_node_printers(self):
        company = self.env.company
        self.env['printing.printer'].update_print_node_printers(company=company)
        return True

    def update_company_print_node_printers_status(self):
        company = self.env.company
        self.env['printing.printer'].update_print_node_printers_status(company=company)
        return True
