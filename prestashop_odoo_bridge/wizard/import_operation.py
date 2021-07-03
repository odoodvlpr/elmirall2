# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

from odoo import api, fields, models, _

class PrestashopImportOperation(models.TransientModel):
    _inherit = "import.operation"

    ps_import_update_date = fields.Datetime("Created/Update After", help="""
        Import/Update (product or orders or partners) in odoo which are created at Prestashop after last (product or orders or partners) import date.
    """)