# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

from ...ApiTransaction import Transaction


class ImportOperation(models.TransientModel):
	_name  = 'import.operation'
	_description = 'Import Operation'
	_inherit = 'channel.operation'


	object = fields.Selection([])
	object_id = fields.Char('Object Id')

	operation = fields.Selection(
		selection = [
			('import',"Import"),
			('update','Update')
		],
		default ='import',
		required = True
	)

	def import_button(self):
		return Transaction(channel=self.channel_id).import_data(
			object = self.object,
			object_id = self.object_id
		)
