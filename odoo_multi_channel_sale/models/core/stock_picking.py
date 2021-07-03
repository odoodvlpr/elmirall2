# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models


class StockPicking(models.Model):
	_inherit = 'stock.picking'

	def action_done(self):
		self.ensure_one()
		self.wk_pre_do_transfer()
		result = super(StockPicking,self).action_done()
		self.wk_post_do_transfer(result)
		return result

	def wk_pre_do_transfer(self):
		order_id = self.sale_id
		if order_id:
			mapping_ids = order_id.channel_mapping_ids
			channel_id  = mapping_ids.mapped('channel_id')
			channel_id  = channel_id and channel_id[0] or channel_id
			if hasattr(channel_id,'%s_pre_do_transfer'%channel_id.channel):
				res = getattr(
					channel_id,'%s_pre_do_transfer'%channel_id.channel
				)(self,mapping_ids)
		return True

	def wk_post_do_transfer(self,result):
		order_id = self.sale_id
		if order_id:
			mapping_ids = order_id.channel_mapping_ids
			channel_id  = mapping_ids.mapped('channel_id')
			channel_id  = channel_id and channel_id[0] or channel_id
			if hasattr(channel_id,'%s_post_do_transfer'%channel_id.channel):
				res = getattr(
					channel_id,'%s_post_do_transfer'%channel_id.channel
				)(self,mapping_ids,result)
		return True
