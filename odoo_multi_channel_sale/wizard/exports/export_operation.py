# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from ...ApiTransaction import Transaction

from odoo import api,fields,models


class ExportOperation(models.TransientModel):
	_name = 'export.operation'
	_description = 'Export Operation'
	_inherit = 'channel.operation'

	operation = fields.Selection(
		selection=[
			('export', 'Export'),
			('update', 'Update'),
			('update_stock', 'Update Stock')
		],
		default='export',
		required=True
	)

	def export_button(self):
		return Transaction(channel=self.channel_id).export_data(
			object=self._context.get('active_model'),
			object_ids=self._context.get('active_ids'),
			operation=self.operation
		)
