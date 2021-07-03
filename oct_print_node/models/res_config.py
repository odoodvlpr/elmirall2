# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import secrets
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    webhook_secret = fields.Char(string="Print Node Webhook Secret",
                                 config_parameter='print_node.webhook.secret')
    print_node_api_key = fields.Char(string="Print Node API Key",
                                     config_parameter='print_node.api.key')
    print_delivery_labels = fields.Boolean(string="Print Delivery Labels",
                                           config_parameter='print_node.print.delivery.labels')
    allow_print_in_dev = fields.Boolean(string="Allow Print in Dev Mode",
                                        config_parameter='print_node.allow.dev')
    avoid_print_duplicity = fields.Boolean(string="Avoid Print Duplicity",
                                           config_parameter='print_node.avoid.duplicity')
    printer_ids = fields.One2many(related="company_id.printer_ids", string="Company Printers")

    def generate_new_secret(self):
        return self.env['ir.config_parameter'].sudo().set_param('print_node.webhook.secret',
                                                                secrets.token_urlsafe(32))

    def action_update_printers(self):
        return self.company_id.update_company_print_node_printers()

    def action_update_printers_status(self):
        return self.company_id.update_print_node_printers_status()
