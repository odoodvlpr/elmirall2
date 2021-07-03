# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from odoo.addons.odoo_multi_channel_sale.tools import extract_list as EL

from logging import getLogger
_logger = getLogger(__name__)


class CategoryFeed(models.Model):
	_name        = 'category.feed'
	_inherit     = 'wk.feed'
	_description = 'Category Feed'

	description   = fields.Text('Description')
	parent_id     = fields.Char('Store Parent ID')
	leaf_category = fields.Boolean('Leaf Category')


	@api.model
	def get_channel_specific_categ_vals(self,channel_id,vals):
		if hasattr(self,'get_%s_specific_categ_vals'%channel_id.channel):
			return getattr(
				self,'get_%s_specific_categ_vals'%channel_id.channel
			)(channel_id,vals)
		return vals

	def import_category(self,channel_id):
		self.ensure_one()
		message   = ""
		update_id = None
		create_id = None
		state     = 'done'

		vals     = EL(self.read(self.get_category_fields()))
		vals     = self.get_channel_specific_categ_vals(channel_id,vals)
		store_id = vals.pop('store_id')

		if not vals.get('name'):
			message += "<br/>Category without name can't evaluated"
			state = 'error'
		if not store_id:
			message += "<br/>Category without store ID can't evaluated"
			state = 'error'

		parent_id = vals.pop('parent_id')
		if parent_id:
			res = self.get_categ_id(parent_id,channel_id)
			res_parent_id = res.get('categ_id')
			if res_parent_id:
				vals['parent_id'] = res_parent_id
			else:
				_logger.error('#CategError1 %r'%res)
				state = 'error'
		vals.pop('description',None)
		vals.pop('website_message_ids','')
		vals.pop('message_follower_ids','')

		match = channel_id.match_category_mappings(store_id)
		if match:
			if state == 'done':
				update_id = match
				try:
					match.category_name.write(vals)
					message += '<br/> Category %s successfully updated'%(vals.get('name',''))
				except Exception as e:
					_logger.error('#CategError2 %r',e)
					message += '<br/>%s' % (e)
					state = 'error'
			elif state == 'error':
				message += '<br/>Error while category update.'
		else:
			if state == 'done':
				try:
					erp_id = self.env['product.category'].create(vals)
					create_id = channel_id.create_category_mapping(
						erp_id,store_id,self.leaf_category
					)
					message += '<br/> Category %s Successfully Evaluate' % (
						vals.get('name',''))
				except Exception as e:
					_logger.error('#CategError3 %r',e)
					message += '<br/>%s' % (e)
					state = 'error'

		self.set_feed_state(state=state)
		self.message = "%s <br/> %s" % (self.message,message)
		return dict(
			create_id=create_id,
			update_id=update_id,
			message=message
		)

	def import_items(self):
		update_ids = []
		create_ids = []
		message = ''

		for record in self:
			sync_vals = dict(
				status      = 'error',
				action_on   = 'category',
				action_type = 'import',
			)
			channel_id = record.channel_id
			res        = record.import_category(channel_id)
			msz        = res.get('message','')
			message += msz

			update_id = res.get('update_id')
			if update_id:
				update_ids.append(update_id)
			create_id = res.get('create_id')
			if create_id:
				create_ids.append(create_id)
			mapping_id = update_id or create_id
			if mapping_id:
				sync_vals['status'] = 'success'
				sync_vals['ecomstore_refrence'] = mapping_id.store_category_id
				sync_vals['odoo_id'] = mapping_id.odoo_category_id
			sync_vals['summary'] = msz
			channel_id._create_sync(sync_vals)
		if self._context.get('get_mapping_ids'):
			return dict(
				update_ids=update_ids,
				create_ids=create_ids,
			)
		message = self.get_feed_result(feed_type='Category')
		return self.env['multi.channel.sale'].display_message(message)

	@api.model
	def cron_import_category(self):
		for record in self.search([('state','!=','done')]):
			record.import_category(record.channel_id)
		return True
