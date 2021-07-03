# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################


METAMAP = {
	'product.category': {
		'model'       : 'channel.category.mappings',
		'local_field' : 'odoo_category_id',
		'remote_field': 'store_category_id'
	},
	'product.template': {
		'model'       : 'channel.template.mappings',
		'local_field' : 'odoo_template_id',
		'remote_field': 'store_product_id'
	},
	'product.product': {
		'model'       : 'channel.product.mappings',
		'local_field' : 'erp_product_id',
		'remote_field': 'store_variant_id'
	}
}


class Transaction:
	def __init__(self, channel, *args, **kwargs):
		self.instance = channel
		self.channel = channel.channel
		self.env = channel.env
		self.evaluate_feed = channel.auto_evaluate_feed
		self.display_message = channel.display_message

	def import_data(self, object, object_id):
		msg = "Current channel doesn't allow it."
		success_ids, error_ids = [],[]
		if hasattr(self.instance,'import_{}'.format(self.channel)):
			msg = ''
			data_list = getattr(self.instance,'import_{}'.format(self.channel))(object,object_id)
			try:
				if object == 'product.category':
					success_ids,error_ids=self.create_categories(data_list)
				elif object == 'product.template':
					success_ids,error_ids=self.create_products(data_list)
				elif object == 'res.partner':
					success_ids,error_ids=self.create_partners(data_list)
				elif object == 'sale.order':
					success_ids,error_ids=self.create_orders(data_list)
				else:
					msg ='I have yet to learn to import it.'
			except Exception as e:
				msg = 'Something went wrong: `{}`'.format(e.args[0])

			if not msg:
				if success_ids:
					msg += "<p style='color:green'>{} imported.</p>".format(success_ids)
				if error_ids:
					msg += "<p style='color:red'>{} not imported.</p>".format(error_ids)
		return self.display_message(msg)

	def create_categories(self,category_data_list):
		success_ids,error_ids = [],[]
		for category_data in category_data_list:
			res,category_feed = self.create_category(category_data)
			if res:
				success_ids.append(category_data.get('store_id'))
			else:
				error_ids.append(category_data.get('store_id'))
		return success_ids,error_ids

	def create_category(self,category_data):
		res = False
		category_feed = self.env['category.feed'].create(category_data)
		if category_feed:
			res = True
			if self.evaluate_feed:
				mapping_ids = category_feed.with_context(get_mapping_ids=True).import_items()
				res = bool(mapping_ids.get('create_ids')+mapping_ids.get('update_ids'))
		return res,category_feed

	def create_products(self,product_data_list):
		success_ids,error_ids = [],[]
		for product_data in product_data_list:
			res,product_feed =  self.create_product(product_data)
			if res:
				success_ids.append(product_data.get('store_id'))
			else:
				error_ids.append(product_data.get('store_id'))
		return success_ids,error_ids

	def create_product(self,product_data):
		res = False
		variant_data_list = product_data.pop('variants')
		product_feed = self.env['product.feed'].create(product_data)
		if product_feed:
			res = True
			for variant_data in variant_data_list:
				variant_data.update(feed_templ_id=product_feed.id)
				self.env['product.variant.feed'].create(variant_data)
			if self.evaluate_feed:
				mapping_ids = product_feed.with_context(get_mapping_ids=True).import_items()
				res = bool(mapping_ids.get('create_ids')+mapping_ids.get('update_ids'))
		return res,product_feed

	def create_partners(self,partner_data_list):
		success_ids,error_ids = [],[]
		for partner_data in partner_data_list:
			res,partner_feeds = self.create_partner(partner_data)
			if res:
				success_ids.append(partner_data.get('store_id'))
			else:
				error_ids.append(partner_data.get('store_id'))
		return success_ids,error_ids

	def create_partner(self,partner_data):
		res = False
		address_data_list = partner_data.pop('addresses',[])
# Todo: Change feed field from state_id,country_id to state_code,country_code
		partner_data['state_id']   = partner_data.pop('state_code',False)
		partner_data['country_id'] = partner_data.pop('country_code',False)
# & remove this code
		partner_feed = self.env['partner.feed'].create(partner_data)
		if partner_feed:
			res = True
			if self.evaluate_feed:
				mapping_ids = partner_feed.with_context(get_mapping_ids=True).import_items()
				res = bool(mapping_ids.get('create_ids')+mapping_ids.get('update_ids'))
			for address_data in address_data_list:
				r,address_feed = self.create_partner(address_data)
		return res,partner_feed

	def create_orders(self,order_data_list):
		success_ids,error_ids = [],[]
		for order_data in order_data_list:
			res,order_feed = self.create_order(order_data)
			if res:
				success_ids.append(order_data.get('store_id'))
			else:
				error_ids.append(order_data.get('store_id'))
		return success_ids,error_ids

	def create_order(self,order_data):
		res = False
# Todo: Change feed field from state_id,country_id to state_code,country_code
		order_data['invoice_state_id']    = order_data.pop('invoice_state_code',False)
		order_data['invoice_country_id']  = order_data.pop('invoice_country_code',False)

		if not order_data.get('same_shipping_billing'):
			order_data['shipping_state_id']   = order_data.pop('shipping_state_code',False)
			order_data['shipping_country_id'] = order_data.pop('shipping_country_code',False)
# & remove this code
		order_feed = self.env['order.feed'].create(order_data)
		if order_feed:
			if self.evaluate_feed:
				mapping_ids = order_feed.with_context(get_mapping_ids=True).import_items()
				res = bool(mapping_ids.get('create_ids')+mapping_ids.get('update_ids'))
		return res,order_feed

	def export_data(self, object, object_ids, operation='export'):
		msg = "Selected Channel doesn't allow it."
		success_ids, error_ids  = [], []

		mappings = self.env[METAMAP.get(object).get('model')].search(
			[
				('channel_id','=',self.instance.id),
				(
					METAMAP.get(object).get('local_field'),
					'in',
					object_ids
				)
			]
		)
		local_ids = mappings.mapped(
			lambda mapping: int(getattr(mapping,METAMAP.get(object).get('local_field')))
		)

		if operation == 'export' and hasattr(self.instance,'export_{}'.format(self.channel)):
			msg = ''
			local_ids = set(object_ids)-set(local_ids)
			if not local_ids:
				return self.display_message(
					"""<p style='color:orange'>
						Selected records have already been exported.
					</p>"""
				)
			operation = 'exported'
			for record in self.env[object].browse(local_ids):
				res,remote_object = getattr(self.instance,'export_{}'.format(self.channel))(record)
				if res:
					self.create_mapping(record,remote_object)
					success_ids.append(record.id)
				else:
					error_ids.append(record.id)

		elif operation == 'update' and hasattr(self.instance,'update_{}'.format(self.channel)):
			msg = ''
			if not local_ids:
				return self.display_message(
					"""<p style='color:orange'>
						Selected records haven't been exported yet.
					</p>"""
				)
			operation = 'updated'
			for record in self.env[object].browse(local_ids):
				res,remote_object = getattr(self.instance,'update_{}'.format(self.channel))(
					record = record,
					get_remote_id = self.get_remote_id
				)
				if res:
					success_ids.append(record.id)
				else:
					error_ids.append(record.id)

		if not msg:
			if success_ids:
				msg += "<p style='color:green'>{} {}.</p>".format(success_ids,operation)
			if error_ids:
				msg += "<p style='color:red'>{} not {}.</p>".format(error_ids,operation)
		return self.display_message(msg)

	def get_remote_id(self,record):
		mapping =  self.env[METAMAP.get(record._name).get('model')].search(
			[
				('channel_id','=',self.instance.id),
				(METAMAP.get(record._name).get('local_field'),'=',record.id)
			]
		)
		return getattr(mapping,METAMAP.get(record._name).get('remote_field'))

	def create_mapping(self,local_record,remote_object):
		if local_record._name == 'product.category':
			self.env['channel.category.mappings'].create(
				{
					'channel_id'       : self.instance.id,
					'ecom_store'       : self.instance.channel,
					'category_name'    : local_record.id,
					'odoo_category_id' : local_record.id,
					'store_category_id': remote_object.id,
					'operation'        : 'export',
				}
			)
		elif local_record._name == 'product.template':
			self.env['channel.template.mappings'].create(
				{
					'channel_id'      : self.instance.id,
					'ecom_store'      : self.instance.channel,
					'template_name'   : local_record.id,
					'odoo_template_id': local_record.id,
					'default_code'    : local_record.default_code,
					'barcode'         : local_record.barcode,
					'store_product_id': remote_object.id,
					'operation'       : 'export',
				}
			)
			for local_variant,remote_variant in zip(local_record.product_variant_ids,remote_object.variants):
				self.env['channel.product.mappings'].create(
					{
						'channel_id'      : self.instance.id,
						'ecom_store'      : self.instance.channel,
						'product_name'    : local_variant.id,
						'erp_product_id'  : local_variant.id,
						'default_code'    : local_variant.default_code,
						'barcode'         : local_variant.barcode,
						'store_product_id': remote_object.id,
						'store_variant_id': remote_variant.id
					}
				)
