# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################

from odoo import api,fields,models,_
from logging import getLogger
_logger=getLogger(__name__)


class FeedSyncWizard(models.TransientModel):
	_name='feed.sync.wizard'

	feed_type=fields.Selection(
		selection=[
			('product.feed','Product'),
			('category.feed','Category'),
			('order.feed','Order'),
			('partner.feed','Partner'),
			('shipping.feed','Shipping')
		],
		string  ='Feed Type',
		required=True
	)


	@api.model
	def default_get(self,fields):
		res=super(FeedSyncWizard,self).default_get(fields)
		if not res.get('feed_type'):
			res.update({'feed_type':self._context.get('active_model')})
		return res

	def sync_feed(self):
		self.ensure_one()
		context=dict(self._context)
		model  =self.env[context.get('active_model')]
		ids    =context.get('active_ids')
		recs   =model.browse(ids)
		return recs.import_items()
