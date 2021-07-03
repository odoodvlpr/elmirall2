# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class PrintNodeJob(models.Model):
    _name = 'print.node.job'
    _description = 'Print Node Job'
    _order = 'id desc'

    name = fields.Char('Job Title')
    job_id = fields.Char('Job ID')
    status = fields.Selection(selection=[
        ('new', 'New'),
        ('sent_to_client', 'Sent'),
        ('queued', 'Queued'),
        ('done', 'Done'),
    ])
    printer_id = fields.Many2one(comodel_name='printing.printer', string="Printer")
    job_response = fields.Text(string="Job Response")
    idempotency_key = fields.Char(string="Idempotency Key", help="Security Key to avoid duplicate printing")
