#!/usr/bin/env python
# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

from odoo import api, fields, models, _
from odoo import tools
from .prestapi import PrestaShopWebService, PrestaShopWebServiceDict, PrestaShopWebServiceError, \
    PrestaShopAuthenticationError
from odoo.tools.translate import _
from datetime import datetime, timedelta
from odoo.addons.odoo_multi_channel_sale.tools import extract_list as EL
from odoo.addons.odoo_multi_channel_sale.tools import _unescape

from odoo.exceptions import UserError
import re
import base64
import itertools
import logging

_logger = logging.getLogger(__name__)


def split_seq(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))


Type = [
    ('simple', 'Simple Product'),
    ('downloadable', 'Downloadable Product'),
    ('grouped', 'Grouped Product'),
    ('virtual', 'Virtual Product'),
    ('bundle', 'Bundle Product'),
]
TaxType = [
    ('include', 'Include In Price'),
    ('exclude', 'Exclude In Price')
]
Boolean = [
    ('1', 'True'),
    ('0', 'False'),
]


class ShippingFeed(models.Model):
    _inherit = "shipping.feed"

    @api.model
    def get_shiping_carrier(self, carrier_name, channel_id=None):
        channel_id = channel_id or self.channel_id
        if channel_id.channel == 'prestashop':
            car_name = self._context['name']
            carrier_obj = self.env['delivery.carrier']
            partner_id = self.env.user.company_id.partner_id.id
            exists = carrier_obj.search([('name', 'in', [carrier_name, car_name])])
            data = {
                'name': carrier_name,
                'fixed_price': 0,
                'product_id': channel_id.delivery_product_id.id
            }
            if not exists:
                carrier_id = carrier_obj.create(data)
            else:
                exists.name = car_name
                carrier_id = exists
            return carrier_id
        else:
            return super(ShippingFeed, self).get_shiping_carrier(carrier_name, channel_id)


class MultiChannelSale(models.Model):
    _inherit = "multi.channel.sale"

    @api.model
    def _get_list(self):
        return_list = []
        config_ids = self.search([('channel', '=', 'prestashop')])
        if not config_ids:
            raise UserError(_("Connection needs one Active Configuration setting."))
        else:
            for config_id in config_ids:
                url = config_id[0].prestashop_base_uri
                key = config_id[0].prestashop_api_key
                try:
                    prestashop = PrestaShopWebServiceDict(url, key)
                except PrestaShopWebServiceError as e:
                    raise UserError(_('Error %s') % str(e))
                try:
                    if prestashop:
                        languages = prestashop.get('languages', options={'display': '[id,name]', 'filter[active]': '1'})
                        if 'languages' in languages:
                            languages = languages['languages']
                        if type(languages['language']) == list:
                            for row in languages['language']:
                                return_list.append(
                                    (str(config_id.id) + '-' + row['id'], row['name'] + '-' + config_id.name))
                        else:
                            return_list.append((str(config_id.id) + '-' + languages['language']['id'],
                                                languages['language']['name'] + '-' + config_id.name))
                except:
                    pass
            return return_list

    prestashop_base_uri = fields.Char(
        string='Base URI'
    )

    update_feed = fields.Boolean(
        string='Update Feed',
        default=True
    )

    prestashop_api_key = fields.Char(
        string='API Key'
    )

    ps_language_id = fields.Selection(_get_list, 'Prestashop Language')

    @api.model
    def get_default_product_categ_id(self):
        domain = [('ecom_store', '=', 'prestashop')]
        if self._context.get('wk_channel_id'):
            domain += [('channel_id', '=', self._context.get('wk_channel_id'))]
        return self.env['channel.category.mappings'].search(domain, limit=1)

    default_tax_type = fields.Selection(
        selection=TaxType,
        string='Default Tax Type',
        default='exclude',
        required=1
    )

    ps_default_product_type = fields.Selection(
        selection=Type,
        string='Default Product Type',
        default='simple',
        required=1,
    )

    ps_default_tax_rule_id = fields.Char(
        string='Default Tax Class ID',
        default='0',
        required=1,
    )
    export_order_shipment = fields.Selection(
        selection=Boolean,
        string='Export  Order Shipment Over Prestashop',
        default='1',
        required=1,
    )
    export_order_invoice = fields.Selection(
        selection=Boolean,
        string='Export  Order Invoice Over Prestashop',
        default='1',
        required=1,
    )

    ps_imp_products_cron = fields.Boolean(
        string='Import Products'
    )
    ps_imp_orders_cron = fields.Boolean(
        string='Import Orders'
    )
    ps_imp_categories_cron = fields.Boolean(
        string='Import Categories'
    )
    ps_imp_partners_cron = fields.Boolean(
        string='Import Partners'
    )

    @api.onchange('ps_imp_products_cron')
    def set_importproducts_cron(self):
        product_cron = self.env.ref('prestashop_odoo_bridge.cron_import_products_from_prestashop', False)
        if product_cron:
            product_cron.write(dict(active=self.ps_imp_products_cron))

    @api.onchange('ps_imp_orders_cron')
    def set_import_order_cron(self):
        order_cron = self.env.ref('prestashop_odoo_bridge.cron_import_orders_from_prestashop', False)
        if order_cron:
            order_cron.write(dict(active=self.ps_imp_orders_cron))

    @api.onchange('ps_imp_categories_cron')
    def set_import_categories_cron(self):
        cat_cron = self.env.ref('prestashop_odoo_bridge.cron_import_categories_from_prestashop', False)
        if cat_cron:
            cat_cron.write(dict(active=self.ps_imp_categories_cron))

    @api.onchange('ps_imp_partners_cron')
    def set_import_partners_cron(self):
        partner_cron = self.env.ref('prestashop_odoo_bridge.cron_import_partners_from_prestashop', False)
        if partner_cron:
            partner_cron.write(dict(active=self.ps_imp_partners_cron))

    @api.model
    def create_attribute_mapping(self, erp_id, store_id):
        self.ensure_one()
        vals = dict(
            store_attribute_id=store_id,
            odoo_attribute_id=erp_id.id,
            attribute_name=erp_id.id,
        )
        channel_vals = self.get_channel_vals()
        vals.update(channel_vals)
        return self.env['channel.attribute.mappings'].create(vals)

    @api.model
    def create_attribute_value_mapping(self, erp_id, store_id):
        self.ensure_one()
        vals = dict(
            store_attribute_value_id=store_id,
            odoo_attribute_value_id=erp_id.id,
            attribute_value_name=erp_id.id,
        )
        channel_vals = self.get_channel_vals()
        vals.update(channel_vals)
        return self.env['channel.attribute.value.mappings'].create(vals)

    @api.model
    def get_channel(self):
        result = super(MultiChannelSale, self).get_channel()
        result.append(("prestashop", "Prestashop"))
        return result

    def test_prestashop_connection(self):
        message = '<br/> Credentials successfully validated.'
        state = 'validate'
        for obj in self:
            try:
                obj.check_prestashop_lang_set()
                # prestashop = PrestaShopWebServiceDict(self.prestashop_base_uri,self.prestashop_api_key)
                # if prestashop:
                #     languages = prestashop.get("languages", options = {'filter[active]':'1'})
                #     if 'languages' in languages:
                #         state = 'validate'
                #         languages = languages['languages']
                #         message = '<br/> Credentials successfully validated.'
            except Exception as e:
                message = 'Connection Error: ' + str(e) + '\r\n'
                state = 'error'
            obj.state = state
        return self.display_message(message)

    def check_prestashop_lang_set(self):

        message = ''
        ps_lang = self.ps_language_id
        ps_lang_detail = None

        if ps_lang:
            ps_lang_id = ps_lang.split('-')
            prestashop = PrestaShopWebServiceDict(self.prestashop_base_uri, self.prestashop_api_key, debug=True)

            # _logger.info("=======presta  %r",(self,ps_lang,ps_lang_id))
            if ps_lang_id[0] == str(self.id):
                try:
                    ps_lang_detail = prestashop.get('languages', ps_lang_id[1])
                except Exception as e:
                    message += 'Api error in getting language details, check prestashop end. '
                # _logger.info("=======presta  ps_lang_detail%r",(ps_lang_detail))

                if ps_lang_detail:
                    if ps_lang_detail['language'].get('language_code', False):
                        language_code = ps_lang_detail['language']['language_code'].split('-')

                        if len(language_code) < 2 and ps_lang_detail['language'].get('locale', False):
                            language_code = ps_lang_detail['language']['locale'].split('-')
                    code = language_code[0] + '_' + language_code[1].upper()
                    # _logger.info("=======lang details %r",(code,ps_lang_detail,self.language_id.code,self.language_id))
                    message = (message if (code and self.language_id) and (self.language_id.code == code)
                               else 'Prestashop language selected is mismatched with channel default language')
            else:
                message += 'Select prestashop language specific to channel'

        else:
            message += 'Select active prestashop language first from channel'
        if message:
            _logger.info("===msg %r", message)
            raise UserError('%s' % (message))

    def refresh_list(self):
        view_ref = self.env['ir.model.data'].get_object_reference('prestashop_odoo_bridge', 'multi_channel_view_form')
        view_id = view_ref and view_ref[1] or False,

        return {
            'type': 'ir.actions.act_window',
            'name': _('Prestashop Configuration'),
            'res_model': 'multi.channel.sale',
            'res_id': self._ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
        }

    def import_prestashop_products(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            source='all',
            operation='import',
        )
        obj = self.env['import.prestashop.products'].create(vals)
        return obj.import_now()

    def export_prestashop_products(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            operation='export',
        )
        obj = self.env['export.templates'].create(vals)
        return obj.prestashop_export_templates()

    def import_prestashop_categories(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            source='all',
            operation='import',
        )
        obj = self.env['import.prestashop.categories'].create(vals)
        return obj.import_now()

    def export_prestashop_categories(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            operation='export',
        )
        obj = self.env['export.prestashop.categories'].create(vals)
        return obj.export_now()

    def export_prestashop_attribute(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            operation='export',
        )
        obj = self.env['export.prestashop.attribute'].create(vals)
        return obj.export_now()

    def import_prestashop_partners(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            source='all',
            operation='import',
        )
        obj = self.env['import.prestashop.partners'].create(vals)
        return obj.import_now()

    def import_prestashop_orders(self):
        self.ensure_one()
        vals = dict(
            channel_id=self.id,
            source='all',
            status='0',
            operation='import',
        )
        obj = self.env['import.prestashop.orders'].create(vals)
        return obj.import_now()

    @api.model
    def _fetch_prestashop_products(self, date_add, limit):
        result = dict(
            data=None,
            message='',
            prestashop=None
        )
        message = ''
        product_list = []
        # product_ids
        data = False
        mapping_obj = self.env['channel.template.mappings']
        mapped = set(self._match_mapping(mapping_obj, []).mapped('store_product_id'))
        prestashop = PrestaShopWebServiceDict(self.prestashop_base_uri, self.prestashop_api_key)
        # date_add = self.import_product_date
        if prestashop:
            try:
                # 'filter[date_add]':'>['+date_add+']',
                # data =  prestashop.get('products', options={'date':1,'filter[active]':1})
                data = prestashop.get('products', options={'date': 1})
            except Exception as e:
                _logger.info("=====> Error while fetching products : %r.", e)
                e = str(e).strip('>').strip('<')
                message += '<br/>%s' % (e)
                result = {
                    data: False,
                    prestashop: prestashop,
                    message: message
                }
            if data:
                if data['products'] == '':
                    return dict(
                        data=[],
                        prestashop=prestashop,
                        message=message + ' No product is created after %s. Please select a different date to import. \n' % (
                            date_add)
                    )
                if type(data['products']['product']) == list:
                    for i in data['products']['product']:
                        product_list.append(i.get('attrs').get('id'))
                else:
                    product_list.append(data['products']['product'].get('attrs').get('id'))
                if self._context['operation'] == 'import':
                    product_list = list(set(product_list) - mapped)
                else:
                    product_list = list(mapped)
                # for import only use todo_ids
                # _logger.info('........ Length .... %r ,,............', len(todo_ids))
                li_product_ids = list(split_seq(product_list, limit))
                result['data'] = li_product_ids
                result['message'] = message
                result['prestashop'] = prestashop
        return result

    @api.model
    def _prestashop_get_product_images_vals(self, media):
        vals = dict()
        message = ''
        data = None
        image_url = media
        if image_url:
            prestashop = self._context['prestashop']
            try:
                data = prestashop.get(image_url)
            except Exception as e:
                message += '<br/>%s' % (e)
            image_data = base64.b64encode(data)
            vals['image'] = image_data
            return vals
        return {'image': False}

    def _get_link_rewrite(self, zip, string):
        if type(string) != str:
            string = string.encode('ascii', 'ignore')
            string = str(string)
        # import re
        string = re.sub('[^A-Za-z0-9]+', ' ', string)
        string = string.replace(' ', '-').replace('/', '-')
        string = string.lower()
        return string

    @api.model
    def ps_import_orders_status(self, vals):
        channel_id = self.browse(vals['channel_id'])
        store_id = vals['store_id']
        status = vals['status']
        message = ''
        feed_obj = self.env['order.feed']
        update_ids = []
        check = self.env['channel.order.states'].search([('channel_state', '=', status)])
        if check:
            order_state_ids = channel_id.order_state_ids
            default_order_state = order_state_ids.filtered('default_order_state')
            match = channel_id._match_feed(
                feed_obj, [('store_id', '=', store_id)])
            if match:
                res = channel_id.set_order_by_status(
                    channel_id=channel_id,
                    store_id=store_id,
                    status=status,
                    order_state_ids=order_state_ids,
                    default_order_state=default_order_state,
                    payment_method=match.payment_method
                )
                order_match = res.get('order_match')
                if order_match: update_ids += [order_match]
            self._cr.commit()

        return dict(
            update_ids=update_ids,
        )
