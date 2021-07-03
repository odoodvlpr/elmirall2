# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    binary_label = fields.Binary(string="Etiqueta de Envio")
    url_label = fields.Char(string="Url Label")

    def action_assign(self):
        res = super(StockPicking, self).action_assign()

        self.sudo().env.ref('oct_print_node.action_report_picking_print_node')._render_qweb_pdf(self.id)[0]
        if self.partner_id.country_id and self.partner_id.country_id.need_comercial_invoice:
            self.sudo().env.ref('oct_print_node.action_report_comercial_invoice_print_node')._render_qweb_pdf(self.id)[0]

        return res
