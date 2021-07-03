# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################
from xmlrpc.client import Error
import logging
from odoo import api, fields, models, _
from odoo.addons.prestashop_odoo_bridge.models.prestapi import PrestaShopWebService,PrestaShopWebServiceDict,PrestaShopWebServiceError,PrestaShopAuthenticationError
_logger = logging.getLogger(__name__)
import itertools

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

customerInfoFields = [
]
Boolean = [

    ('all', 'True/False'),
    ('1', 'True'),
    ('0', 'False'),
]
Source = [
    ('all', 'All'),
    ('partner_ids', 'Partner ID(s)'),
]

class ImportPrestashoppartners(models.TransientModel):
    _inherit = ['import.partners']
    _name = "import.prestashop.partners"


    def _get_data(self, prestashop, resource, id):
        data = {}
        message = ''
        try:
            data = prestashop.get(resource, id)
        except Exception as e:
            message += 'Error while getting the country data'
            return dict(message=message)
        return dict(
            data = data,
            message = message
        )

    @api.model
    def _get_prestashop_group(self):
        groups = [('all','All')]
        return groups

    source = fields.Selection(Source, required=1, default='all')
    group_id = fields.Selection(
        selection = _get_prestashop_group,
        string = 'Group ID',
        required = 1,
        default = 'all'
    )

    def _fetch_prestashop_partners(self, prestashop):
        message = ''
        data = None
        data_list = []
        li_customer_ids = []
        date_add = fields.Datetime.to_string(self.ps_import_update_date)
        PartnerMapping = self.env["channel.partner.mappings"]
        mapped = self.channel_id._match_mapping(PartnerMapping, [('type','=','contact')]).mapped("store_customer_id")
        operation = self.operation
        if date_add:
            try:
                data = prestashop.get('customers', options={'display':'[id, firstname, lastname, email]', 'filter[date_add]':'>['+date_add+']', 'date':1})
            except Exception as e:
                message += '<br/>For Customer %s<br/>%s'%(data, str(e))
                _logger.info('_______________ Error: %r _____________', message)
            
            if data:
                if data['customers']=='':
                    return dict(
                        data = [],
                        message = 'No customer had been registered after created after  %s. Please select a different date to import. \n'%(date_add)
                    )
                if type(data['customers']['customer'])==list:
                    for i in data['customers']['customer']:
                        if operation=='import' and i['id'] not in mapped:
                            data_list.append(i)
                        elif i['id'] in mapped:
                            data_list.append(i)

                else:
                    data_list.append(data['customers']['customer'])
                # if self.operation=='import':
                #     customer_list = list(set(data_list)-mapped)
                # else:
                #     _logger.info("====datalist mapp %r",[data_list,mapped])
                #     customer_list = list(set(data_list)&mapped)
                # _logger.info('_______________ list: %r _____________', data_list)
                li_customer_ids = list(split_seq(data_list, 100))
            return dict(
                data = li_customer_ids,
                message = message
            )
        return dict(
            data = li_customer_ids,
            message = "Import/Update date not set. "
        )

    def _fetch_prestashop_customer_address(self, prestashop, customer_id):
        message = ''
        data = None
        address_ids = []
        address_data = []
        try:
            data = prestashop.get('addresses', options={'filter[id_customer]': customer_id})
        except Exception as e:
            message += '<br/>For Customer %s<br/>%s'%(data, str(e))
        if data and data['addresses']:
            address_list = data['addresses']['address']
            if type(address_list) == dict:
                address_ids.append(address_list['attrs']['id'])
            else:
                address_ids = [i['attrs']['id'] for i in address_list]
            for address_id in address_ids:
                data_add = None
                try:
                    data_add = prestashop.get('addresses', address_id)
                except Exception as e:
                    message += '<br/>For Address %s<br/>%s'%(address_id, str(e))
                    _logger.info("------ Error : %r ------------------", message)
                if data_add:
                    address_data.append(data_add['address'])
        return dict(
            data = address_data,
            message = message
        )

    def _parse_prestashop_customer_address(self, data, parent_id, prestashop):
        update_ids = []
        create_ids = []
        for item in data:
            country_id = ''
            state_id = ''
            name = item.get('firstname')
            if item.get('lastname'):
                name += ' %s'%(item.get('lastname'))
            _type = 'invoice'
            if item.get('is_default_shipping'):
                _type = 'delivery'
            if item.get('id_country') != '0':
                country_data = self._get_data(prestashop, 'countries', item.get('id_country'))
                country_data = country_data.get('data', {'country':{'iso_code':' '}})
                country_id = country_data['country']['iso_code']
            if item.get('id_state') != '0':
                state_data = self._get_data(prestashop, 'states', item.get('id_state'))
                state_data = state_data.get('data', {'state':{'iso_code':' '}})
                state_id = state_data['state']['iso_code']
            vals= dict(
                name = name,
                street = item.get('address1'),
                street2 = item.get('address2'),
                # phone = item.get('telephone'),
                city = item.get('city'),
                state_name = state_id,
                country_id = country_id,
                zip = item.get('postcode'),
                store_id = item.get('id') or item.get('email'),
                parent_id = parent_id,
                phone = item.get('phone'),
                mobile = item.get('phone_mobile'),
                type = _type
            )
            feed_obj = self.env['partner.feed']
            match = self.channel_id._match_feed(
                feed_obj, [('store_id', '=', item.get('id')), ('type', '!=', 'contact')])
            if match:
                match.write(vals)
                match.write(dict(state = 'update'))
                update_ids.append(match)
            else:
                feed_id = self.channel_id._create_feed(feed_obj, vals)
                create_ids.append(feed_id)
        return dict(
            create_ids = create_ids,
            update_ids = update_ids,
        )


    def get_customer_vals(self, prestashop, customer_id, customer_data):
        vals = dict(
            name = customer_data.get('firstname'),
            last_name = customer_data.get('lastname'),
            email = customer_data.get('email'),
            type = 'contact'
        )
        res_address = self._fetch_prestashop_customer_address(prestashop, customer_id)
        data = res_address.get('data')
        if data:
            import_res = self._parse_prestashop_customer_address(data, customer_id, prestashop)
            # post_res = self.post_feed_import_process(channel_id, import_res)
            vals['addresses'] = import_res
        return vals

    def _prestashop_update_customer_feed(self, prestashop, mapping, customer_id, data):
        channel_id = self.channel_id
        vals =self.get_customer_vals(prestashop, customer_id, data)
        mapping.write(vals)
        mapping.write(dict(state = 'update'))
        if 'addresses' in vals:
            import_res = vals.pop('addresses')
            post_res = self.post_feed_import_process(channel_id, import_res)
        return mapping

    def _prestashop_create_customer_feed(self, prestashop, customer_id, data):
        channel_id = self.channel_id
        vals = self.get_customer_vals(prestashop, customer_id, data)
        # import_res = vals.pop('addresses')
        vals['store_id'] = customer_id
        feed_obj = self.env['partner.feed']
        if 'addresses' in vals:
            import_res = vals.pop('addresses')
            feed_id = self.channel_id._create_feed(feed_obj, vals)
            post_res = self.post_feed_import_process(channel_id, import_res)
        else:
            feed_id = self.channel_id._create_feed(feed_obj, vals)

        return feed_id

    def _prestashop_import_customer(self, prestashop, customer_id, data):
        feed_obj = self.env['partner.feed']
        match = self.channel_id._match_feed(
            feed_obj, [('store_id', '=', customer_id),('type', '=', 'contact')])
        update = False
        if match:
            if self.channel_id.update_feed:
                self._prestashop_update_customer_feed( prestashop, match, customer_id, data)
            update = True
        else:
            match = self._prestashop_create_customer_feed(prestashop, customer_id, data)
        return dict(
            feed_id = match,
            update = update
        )

    def _prestashop_import_partners(self, prestashop, items):
        create_ids = []
        update_ids = []
        for customer_data in items:
            customer_id = customer_data['id']
            data = customer_data
            import_res = self._prestashop_import_customer(prestashop, customer_id, data)
            feed_id = import_res.get('feed_id')
            if  import_res.get('update'):
                update_ids.append(feed_id)
            else:
                create_ids.append(feed_id)
        return dict(
            create_ids = create_ids,
            update_ids = update_ids,
        )

    def import_now(self):
        create_ids, update_ids, map_create_ids, map_update_ids = [], [], [], []
        message = ''
        for record in self:
            channel_id = record.channel_id
            prestashop = PrestaShopWebServiceDict(channel_id.prestashop_base_uri, channel_id.prestashop_api_key)
            if not prestashop:
                message += "Error in connection"
            else:
                fetch_res = record._fetch_prestashop_partners(prestashop)
                partners = fetch_res.get('data', {})
                message += fetch_res.get('message', '')
                if not partners:
                    message += "</br>Partners data not received."
                else:
                    for select_rec in partners:
                        feed_res = record._prestashop_import_partners(prestashop, select_rec)
                        post_res = self.post_feed_import_process(channel_id, feed_res)
                        create_ids += post_res.get('create_ids')
                        update_ids += post_res.get('update_ids')
                        map_create_ids += post_res.get('map_create_ids')
                        map_update_ids += post_res.get('map_update_ids')
                        self.env.cr.commit()
        message += self.env['multi.channel.sale'].get_feed_import_message(
            'partner',create_ids,update_ids,map_create_ids,map_update_ids
        )
        return self.env['multi.channel.sale'].display_message(message)
    @api.model
    def _cron_prestashop_import_partners(self):
        for channel_id in self.env['multi.channel.sale'].search(CHANNELDOMAIN):
            vals = dict(
                channel_id = channel_id.id,
                source = 'all',
                operation = 'import',
            )
            obj = self.create(vals)
            obj.import_now()
