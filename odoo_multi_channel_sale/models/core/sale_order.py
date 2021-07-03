# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import fields,models


class SaleOrder(models.Model):
	_inherit = 'sale.order'

	channel_mapping_ids = fields.One2many(
		string       = 'Mappings',
		comodel_name = 'channel.order.mappings',
		inverse_name = 'order_name',
		copy         = False
	)
