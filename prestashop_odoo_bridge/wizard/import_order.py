# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################
from xmlrpc.client import Error
import logging
import itertools
from odoo import api, fields, models, _
from odoo.exceptions import UserError,RedirectWarning, ValidationError
from odoo.addons.prestashop_odoo_bridge.models.prestapi import PrestaShopWebService,PrestaShopWebServiceDict,PrestaShopWebServiceError,PrestaShopAuthenticationError
_logger = logging.getLogger(__name__)

CHANNELDOMAIN = [
    ('channel', '=', 'prestashop'),
    ('state', '=', 'validate')
]

def split_seq(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))

OrderStatus = [
    ('0','All'),
    ('6','Canceled'),
    ('5','Shipped'),
    ('2','Complete'),
    ('12','Complete'),
    ('3','Processing'),
    ('13','On Hold'),
    ('9','Pending'),
    ('1','Pending Payment'),
    ('10','Pending Payment'),
    ('14','Pending Payment'),
    ('11','Pending Payment'),
    ('4', 'Shipped')
]

class ImportOrders(models.TransientModel):
    _inherit = ['import.orders']
    _name = 'import.prestashop.orders'
    status = fields.Selection(
        OrderStatus,
        required = 1,
        default = '0'
    )

    def _fetch_prestashop_orders(self, prestashop):
        message = ''
        orders = None
        li_order_ids = []
        order_ids = []
        mapping_obj = self.env['channel.order.mappings']
        mapped = set(self.channel_id._match_mapping(mapping_obj,[]).mapped('store_order_id'))
        date_add = fields.Datetime.to_string(self.ps_import_update_date)
        if date_add:
            try:
                orders = prestashop.get('orders', options = {'filter[date_add]':'>['+date_add+']', 'date':1})
            except Error as e:
                e = str(e).strip('>').strip('<')
                message += '<br/>%s'%(e)
            except Exception as e:
                message += '<br/>%s'%(e)
            if orders:
                if 'orders' in orders and orders['orders']=='':
                    return dict(
                        data = [],
                        message = message+"No order had been placed after %s. Please select a different date to import. \n"%(date_add)
                    )
                orders = orders['orders']['order']
                if type(orders) == dict:
                    order_ids.append(orders['attrs']['id'])
                else:
                    order_ids = [i['attrs']['id'] for i in orders]
                if self.operation=='import':
                    todo_ids = list(set(order_ids)-mapped)
                else:
                    todo_ids = list(set(order_ids)&mapped)                    
                li_order_ids = list(split_seq(todo_ids, 100))

            return dict(
                data = li_order_ids,
                message = message
            )
        # return dict(
        #     data = li_order_ids,
        #     message = "Order import date not set. Please select date for order import"
        # )

    def _fetch_prestashop_order_data(self, prestashop, order_id):
        message = ''
        data = None
        try:
            data = prestashop.get('orders', order_id)
        except Error as e:
            e =str(e).strip('>').strip('<')
            message+='<br/>%s'%(e)
        except Exception as e:
            message+='<br/>%s'%(e)
        return dict(
            data=data['order'],
            message=message
        )

    def import_products(self, product_tmpl_ids):
        context = self.env.context.copy()
        channel_id = self.channel_id
        prestashop = context['prestashop']
        mapping_obj = self.env['channel.product.mappings']
        feed_obj = self.env['product.feed']
        domain = [('store_product_id', 'in', product_tmpl_ids)]
        mapped = self.channel_id._match_mapping(mapping_obj, domain).mapped('store_product_id')
        feed_map = self.channel_id._match_feed(feed_obj, [('store_id', 'in', product_tmpl_ids)]).mapped('store_id')
        product_tmpl_ids = list(set(product_tmpl_ids)-set(mapped)-set(feed_map))
        message = ''
        product_list = []
        if len(product_tmpl_ids):
            message = 'For order product imported %s'%(product_tmpl_ids)
            try:
                import_product_obj = self.env['import.prestashop.products']
                vals = dict(
                    channel_id = self.channel_id.id,
                    source = 'product_tmpl_ids',
                    operation = 'import',
                    product_tmpl_ids = ','.join(product_tmpl_ids)
                )
                for product_id in product_tmpl_ids:
                    product_list.append(product_id)
                import_product_id=import_product_obj.create(vals)
                feed_res = import_product_id._prestashop_import_products(product_list)
                self.env.cr.commit()
                post_res = import_product_id.post_feed_import_process(channel_id,feed_res)
            except Exception as e:
                message = "Error while  order product import %s"%(e)
                _logger.info("====>OrderProductImport : %r ", message)
        mapped = self.channel_id._match_mapping(mapping_obj,domain)
        return message

    def update_shipping_info(self,order_items,order_data,price):
        name = 'Shipping'
        order_items+=[dict(
            product_id=name,
            unit_price_tax_excl=price,
            line_price_unit=price,
            product_quantity=1,
            product_name=name,
            line_source ='delivery',
            description=name,
            tax_amount ='0',
        )]
        return order_items

    def get_discount_line_info(self,price):
        name = '%s discount'%(price)
        return dict(
            product_id=name,
            unit_price_tax_excl='%s'%(abs(float(price))),
            line_price_unit='%s'%(abs(float(price))),
            product_quantity=1,
            product_name=name,
            line_source ='discount',
            description=name,
            tax_amount ='0',
        )

    def prestashop_get_tax_line(self,item):
        tax_percent = float(item.get('tax_percent'))
        tax_type = 'percent'
        # if tax_percent > '0.0':
        name = 'Tax {} % '.format(tax_percent)
        return {
            'rate':tax_percent,
            'name':name,
            'include_in_price':self.channel_id.default_tax_type== 'include'and True or False,
            'tax_type':tax_type
        }

    def prestashop_get_order_line_info(self,order_item):
        line_price_unit = order_item.get('unit_price_tax_excl')
        line_variant_ids= order_item.get('product_id')
        line_product_id=None
        # if order_item.get('line_source') not in ['discount','delivery']:
        if self.channel_id.default_tax_type=='include' and order_item.get('line_source') not in ['discount','delivery']:
            line_price_unit =  order_item.get('unit_price_tax_incl') and order_item.get('unit_price_tax_incl') or order_item.get('product_price')

        line=dict(
                    line_product_uom_qty = order_item.get('product_quantity'),
                    line_product_id =order_item.get('product_id'),
                    line_variant_ids =order_item.get('product_attribute_id'),
                    line_name = order_item.get('product_name'),
                    line_price_unit=line_price_unit,
                    line_source = order_item.get('line_source','product'),
        )
        if line['line_variant_ids'] in [0,'0']:
            line['line_variant_ids'] = 'No Variants'
        return line

    def prestashop_get_order_line(self, prestashop, order_id, carrier_id, order_data):
        data = dict()
        message = ''
        order_items = []
        tax_data = False
        order_line_details = False
        order_detail_ids = []
        try:
            order_line_details = prestashop.get('order_details',
             options={'filter[id_order]': order_id})
        except Exception as e:
            message += 'Error in getting sale order lines :%s'%(e)
        if order_line_details:
            if order_line_details.get('order_details'):
                order_line_details = order_line_details.get(
                'order_details').get('order_detail')
                if type(order_line_details) == list:
                    order_detail_ids = [i.get('attrs').get('id') for i in order_line_details]
                else:
                    order_detail_ids = [order_line_details.get('attrs').get('id')]
        for i in order_detail_ids:
            try:
                data1 = prestashop.get('order_details', i).get('order_detail')
            except Exception as e:
                message += 'Error in getting sale order lines details :%s'%(e)
            if data1:
                order_items.append(data1)

        if order_items:
            product_tmpl_ids = list(set(map(lambda item:item.get('product_id'),order_items)))
            message += self.with_context({'prestashop':prestashop}).import_products(product_tmpl_ids=product_tmpl_ids)
            lines = []
            shipping_amount = order_data.get('total_shipping_tax_excl')
            if self.channel_id.default_tax_type=='include':
                shipping_amount = order_data.get('total_shipping_tax_incl')
            if carrier_id:
                order_items = self.update_shipping_info(
                    order_items, order_data, shipping_amount
                )

            # if config_id.default_tax_type == 'include':
            discount_amount=order_data.get('total_discounts_tax_incl')
            if float(discount_amount):
                order_items += [self.get_discount_line_info(
                    discount_amount
                )]
            size = len(order_items)
            if size == 1:
                order_item = order_items[0]
                line = self.prestashop_get_order_line_info(order_item)
                if (order_item.get('associations').get('taxes').get('tax')):
                    try:
                        tax_data = self._get_data(prestashop, 'taxes',order_item.get('associations').get('taxes').get('tax').get('id'))
                    except Exception as e:
                        message += 'Error in getting order tax lines :%s'%(e)
                    if tax_data['data']:
                        tax_rate = tax_data.get('data').get('tax').get('rate')
                        order_item['tax_percent'] = tax_rate
                        line['line_taxes'] = [self.prestashop_get_tax_line(order_item)]
                data.update(line)
            else:
                data['line_type'] = 'multi'
                for order_item in order_items:
                    line=self.prestashop_get_order_line_info(order_item)
                    if order_item.get('line_source') not in ['discount','delivery']:
                        if (order_item.get('associations').get('taxes').get('tax')):
                            try:
                                tax_data = self._get_data(prestashop, 'taxes',order_item.get('associations').get('taxes').get('tax').get('id'))
                            except Exception as e:
                                message += 'Error in getting order tax lines :%s'%(e)
                            if tax_data['data']:
                                tax_rate = tax_data.get('data').get('tax').get('rate')
                                order_item['tax_percent'] = tax_rate
                                line['line_taxes'] = [self.prestashop_get_tax_line(order_item)]
                    elif order_item.get('line_source')=='delivery':
                        if float(order_data.get('carrier_tax_rate')) > float('0.0'):
                            order_item['tax_percent'] = order_data.get('carrier_tax_rate')
                            line['line_taxes'] = [self.prestashop_get_tax_line(order_item)]
                    lines += [(0, 0, line)]
                    # if config_id.default_tax_type!= 'include':
                    #     discount_amount = float(order_item.get('reduction_percent', '0.0'))
                    #     if discount_amount > float('0.0'):
                    #         discount_data = self.get_discount_line_info('0')
                    #         discount_line=self.prestashop_get_order_line_info(discount_data)
                    #         discount_data['tax_percent'] = discount_amount
                    #         discount_line['line_taxes'] = [self.prestashop_get_tax_line(discount_data)]
                    #         lines += [(0, 0, discount_line)]
            data['line_ids'] = lines
        return dict(
            data=data,
            message=message
            )

    def get_ps_invoice_address(self, prestashop, id, customer_email):
        message = ''
        country_id, state_id = False, False
        item = False
        if id:
            try:
                item = self._get_data(prestashop, 'addresses', id)
            except Exception as e:
                message += 'Error in getting Invoice address: %s'%(e)
            if item and item['data']:
                item = item.get('data').get('address')
                name = item.get('firstname')
                if item.get('lastname'):
                    name+=' %s'%(item.get('lastname'))
                if 'id_country' in item and item.get('id_country') != '0':
                    country_data = self._get_data(prestashop, 'countries', item.get('id_country'))
                    country_data = country_data.get('data', {'country':{'iso_code':' '}})
                    if country_data:
                        country_id = country_data['country']['iso_code']
                if 'id_state' in item and item.get('id_state') != '0':
                    state_data = self._get_data(prestashop, 'states', item.get('id_state'))
                    state_data = state_data.get('data', {'state':{'iso_code':' '}})
                    if state_data:
                        state_id = state_data['state']['iso_code']
                return dict(
                    invoice_name = name,
                    invoice_email = customer_email,
                    invoice_street = item.get('address1'),
                    invoice_street2 = item.get('address2'),
                    invoice_phone = item.get('phone'),
                    invoice_mobile = item.get('phone_mobile'),
                    invoice_city = item.get('city'),
                    invoice_country_id = country_id,
                    invoice_zip = item.get('postcode'),
                    invoice_partner_id = item.get('id') or '0',
                    invoice_state_name = state_id,
                )
        return False

    def get_ps_shipping_address(self, prestashop, id, customer_email):
        message = ''
        item = False
        country_id, state_id = False, False
        if id:
            try:
                item = self._get_data(prestashop, 'addresses', id)
            except Exception as e:
                message += 'Error in getting shipping address: %s'%(e)
            if item and item['data']:
                item = item.get('data').get('address')
                name = item.get('firstname')
                if item.get('firstname'):
                    name+=' %s'%(item.get('lastname'))
                if 'id_country' in item and item.get('id_country') != '0':
                    country_data = self._get_data(prestashop, 'countries', item.get('id_country'))
                    country_data = country_data.get('data', {'country':{'iso_code':' '}})
                    if country_data:
                        country_id = country_data['country']['iso_code']
                if 'id_state' in item and item.get('id_state') != '0':
                    state_data = self._get_data(prestashop, 'states', item.get('id_state'))
                    state_data = state_data.get('data', {'state':{'iso_code':' '}})
                    if state_data:
                        state_id = state_data['state']['iso_code']
                return dict(
                    shipping_name=name,
                    shipping_email=customer_email,
                    shipping_street=item.get('address1'),
                    shipping_street2 = item.get('address2'),
                    shipping_phone=item.get('phone'),
                    shipping_mobile = item.get('phone_mobile'),
                    shipping_city=item.get('city'),
                    shipping_country_id=country_id,
                    shipping_zip=item.get('postcode'),
                    shipping_partner_id=item.get('id') or '0',
                    shipping_state_name=state_id,
                )
        return False

    def _get_data(self, prestashop, resource, id):
        data = None
        message = ''
        try:
            data = prestashop.get(resource, id)
        except Exception as e:
            message += 'Error while getting the data %s'%(e)
        if data:
            return dict(
                data=data,
                message=message
            )
        return dict(
            data = False,
            message=message
            )


    def get_order_vals(self, prestashop, order_id):
        message = ''
        # pricelist_id = self.channel_id.pricelist_name
        res = self._fetch_prestashop_order_data(prestashop, order_id)
        if res.get('data'):
            item = res.get('data')
            status = item.get('current_state')
            customer_id = item.get('id_customer')
            cust_data = self._get_data(prestashop, 'customers', customer_id)
            if cust_data['data']:
                cust_data = cust_data.get('data')['customer']
                order_currency_code = self._get_data(prestashop, 'currencies', item.get('id_currency')).get('data')['currency'].get('iso_code')
                customer_name = cust_data.get('firstname')
                if cust_data.get('lastname'):
                    customer_name+=" %s"%(cust_data.get('lastname'))
                customer_email=cust_data.get('email')
                vals = dict(
                    order_state = status,
                    partner_id = customer_id or '0' ,
                    customer_is_guest = int(cust_data.get('is_guest')),
                    currency = order_currency_code,
                    customer_name = customer_name,
                    customer_email = customer_email,
                    payment_method = item.get('payment'),
                    date_order = item.get('date_add'),
                    confirmation_date = item.get('delivery_date'),
                    date_invoice = item.get('invoice_date'),
                )
                shipping_method = item.get('id_carrier')
                carrier_resp = self._get_data(prestashop, 'carriers', shipping_method)
                carrier_name = shipping_method
                if carrier_resp.get('data'):
                    carrier_name = carrier_resp.get('data')['carrier'].get('name')
                shipping_mapping_id = self.env['shipping.feed'].with_context({'name':carrier_name}).get_shiping_carrier_mapping(
                    self.channel_id, shipping_method
                )
                if shipping_mapping_id:
                    vals['carrier_id']= shipping_mapping_id.shipping_service_id
                line_res= self.prestashop_get_order_line(prestashop,
                    order_id,
                    shipping_mapping_id.odoo_shipping_carrier,res.get('data')
                )
                if line_res.get('data'):
                    vals.update(line_res.get('data'))
                same_shipping_billing  = item.get('id_address_delivery')==item.get('id_address_invoice')
                vals['same_shipping_billing'] = same_shipping_billing
                billing_addr_vals = self.get_ps_invoice_address(prestashop, item.get('id_address_invoice'), customer_email)
                if billing_addr_vals:
                    vals.update(billing_addr_vals)
                if item.get('id_address_delivery') and not(same_shipping_billing):
                    shipping_add_vals = self.get_ps_shipping_address(prestashop, item.get('id_address_delivery'), customer_email)
                    if shipping_add_vals:
                        vals.update(shipping_add_vals)
                vals['store_id'] = item.get('id')
                vals['name'] = item.get('reference')
                return vals
            else:
                message+=cust_data.get('message')
        else:
            message+=res.get('message')

    def _prestashop_update_order_feed(self, prestashop, mapping, order_id):
        vals =self.get_order_vals(prestashop,order_id)
        mapping.write(dict(line_ids=[(5,0)]))
        mapping.write(vals)
        mapping.state='update'
        return mapping

    def _prestashop_create_order_feed(self, prestashop, order_id):
        vals =self.get_order_vals(prestashop, order_id)
        if vals:
            feed_obj = self.env['order.feed']
            feed_id = self.channel_id._create_feed(feed_obj, vals)
            # _logger.info('............. Feed id: %r ................', feed_id)
            return feed_id

    def _prestashop_import_order(self, prestashop, order_id):
        feed_obj = self.env['order.feed']
        match = self.channel_id._match_feed(
            feed_obj, [('store_id', '=', order_id)])
        update =False
        if match :
            if self.channel_id.update_feed:
                self._prestashop_update_order_feed( prestashop,match, order_id)
            update=True
        else:
            match= self._prestashop_create_order_feed(prestashop, order_id)
        return dict(
            feed_id=match,
            update=update
        )

    def _prestashop_import_orders(self, prestashop, items):
        create_ids = []
        update_ids = []
        for item in items:
            import_res =   self._prestashop_import_order(prestashop, item)
            feed_id = import_res.get('feed_id')
            self.env.cr.commit()
            if  import_res.get('update'):
                update_ids.append(feed_id)
            else:
                create_ids.append(feed_id)
        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
        )

    def import_now(self):
        create_ids, update_ids, map_create_ids, map_update_ids = [], [], [], []
        message = ''
        # error_count = 0
        for record in self:
            channel_id = record.channel_id
            try:
                prestashop = PrestaShopWebServiceDict(channel_id.prestashop_base_uri, channel_id.prestashop_api_key)
            except PrestaShopWebServiceError as e:
                raise UserError(_('Error %s')%str(e))
            if prestashop:
                fetch_res =record._fetch_prestashop_orders(prestashop = prestashop)
                orders = fetch_res.get('data', False)
                message += fetch_res.get('message', '')
                if not orders:
                    message += "Orders data not received."
                else:
                    for li in orders:
                        feed_res = record._prestashop_import_orders(prestashop, li)
                        post_res = self.post_feed_import_process(channel_id, feed_res)
                        create_ids += post_res.get('create_ids')
                        update_ids += post_res.get('update_ids')
                        map_create_ids += post_res.get('map_create_ids')
                        map_update_ids += post_res.get('map_update_ids')
        message+=self.env['multi.channel.sale'].get_feed_import_message(
            'order', create_ids, update_ids, map_create_ids, map_update_ids
        )
        return self.env['multi.channel.sale'].display_message(message)

    @api.model
    def _cron_prestashop_import_orders(self):
        for channel_id in self.env['multi.channel.sale'].search(CHANNELDOMAIN):
            vals = dict(
                channel_id = channel_id.id,
                source = 'all',
                status = '0',
                operation = 'import',
            )
            obj=self.create(vals)
            obj.import_now()
