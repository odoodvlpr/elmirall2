# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class ChannelOrderMappings(models.Model):
	_name        = 'channel.order.mappings'
	_inherit     = 'channel.mappings'
	_description = 'Order Mapping'

	store_order_id =  fields.Char('Store Order ID',required=True)
	order_name = fields.Many2one('sale.order','Odoo Order')
	odoo_order_id = fields.Integer('Odoo Order ID',required=True)
	odoo_partner_id = fields.Many2one(related='order_name.partner_id')
	
	
	def unlink(self):
		for record in self:
			match = record.store_order_id and record.channel_id.match_order_feeds(record.store_order_id)
			if match: match.unlink()
		return super(ChannelOrderMappings, self).unlink()

	@api.onchange('order_name')
	def change_odoo_id(self):
		self.odoo_order_id = self.order_name.id

	def _compute_name(self):
		for record in self:
			record.name = record.order_name.name if record.order_name else 'Deleted'
