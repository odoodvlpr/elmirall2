# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################
from xmlrpc.client import Error
import logging
import itertools
from odoo.exceptions import  UserError,RedirectWarning, ValidationError
from odoo import api, fields, models, _
from odoo.addons.prestashop_odoo_bridge.models.prestapi import PrestaShopWebService,PrestaShopWebServiceDict,PrestaShopWebServiceError,PrestaShopAuthenticationError
try:
    from odoo.loglevels import ustr as pob_decode
except:
    from odoo.tools.misc import ustr as pob_decode
_logger = logging.getLogger(__name__)

CHANNELDOMAIN = [
    ('channel', '=', 'prestashop'),
    ('state', '=', 'validate')
]
Source = [
    ('all', 'All'),
    ('parent_categ_id', 'Parent ID'),
]

def split_seq(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))

class ImportPrestashopCategories(models.TransientModel):
    _inherit = ['import.categories']
    _name = "import.prestashop.categories"

    @api.model
    def _get_parent_categ_domain(self):
        res = self._get_ecom_store_domain()
        return res

    source = fields.Selection(Source, required=1, default='all')
    parent_categ_id = fields.Many2one(
        'channel.category.mappings',
        'Parent Category',
        domain = _get_parent_categ_domain
    )

    def _fetch_prestashop_categories(self, prestashop, category_id):
        message = ''
        data = None
        cat_data = {}
        channel_id = self.channel_id
        try:
            data = prestashop.get('categories', category_id)
        except Exception as e:
            message += '<br/>Error while importing the Prestashop Category %s<br/>%s'%(category_id, str(e))
            raise UserError(_(message))
        return data['category']

    def _prestashop_update_category_feed(self, prestashop, mapping, category_id, vals):
        mapping.write(vals)
        mapping.state = 'update'
        return mapping

    def _prestashop_create_category_feed(self, prestashop, category_id, vals):
        feed_obj = self.env['category.feed']
        feed_id = self.channel_id._create_feed(feed_obj, vals)
        # _logger.info('..................Feed: %r ................',feed_id)
        return feed_id

    def _prestashop_import_category(self, prestashop, category_id):
        category_feed_obj = self.env['category.feed']
        message = ''
        match = self.channel_id._match_feed(
            category_feed_obj, [('store_id', '=', category_id)])
        update = False
        data = self._fetch_prestashop_categories(prestashop, category_id)
        if (data['id_parent'] != '0') and not category_feed_obj.search([('store_id', '=', data['id_parent'])]):
            self._prestashop_import_category(prestashop, data['id_parent'])
        categ_vals = dict(self.prestashop_extract_categ_data(data))
        if match:
            self._prestashop_update_category_feed( prestashop, match, category_id, categ_vals)
            update = True
        else:
            map_match = self.channel_id.match_category_mappings(category_id)
            if map_match:
                try:
                    match = map_match.category_name.write({'name':categ_vals.get('name')})
                    match = map_match.category_name
                    update = True
                    message += '<br/> Category %s successfully updated' % (
                        categ_vals.get('name', ''))
                except Exception as e:
                    _logger.info('-----Exception--------------%r', e)
                    message += '<br/>%s' % (e)
            else:
                match = self._prestashop_create_category_feed(prestashop, category_id, categ_vals)
        
        return dict(
            feed_id = match,
            update = update
        )

    def prestashop_extract_categ_data(self, data):
        name = ' '
        parent_id = False
        if data.get('id_parent') != '0':
            parent_id = data.get('id_parent')
        # parent_id = int(data.get('id_parent'))
        channel_id = self.channel_id
        if type(data['name']['language'])==list:
            channel_lang = channel_id.ps_language_id.split(str(channel_id.id)+'-')[1]
            for cat_name in data['name']['language']:
                if cat_name['attrs']['id'] == channel_lang:
                    name = cat_name['value']
        else:
            name = data.get('name')['language']['value']
        #_logger.info('.............. Name and id  : %r ............', [name, self.channel_id.ps_language_id, data['name']])
        return dict(
            name = name,
            store_id = data.get('id'),
            parent_id = parent_id and parent_id
            )


    def _prestashop_import_categories(self, prestashop, items):
        create_ids = []
        update_ids = []
        for cat_id in items:
            import_res = self._prestashop_import_category(prestashop, cat_id)
            feed_id = import_res.get('feed_id')
            if  import_res.get('update'):
                update_ids.append(feed_id)
            else:
                create_ids.append(feed_id)
        return dict(
            create_ids = create_ids,
            update_ids = update_ids,
        )

    def _get_prestashop_category_list(self, prestashop):
        message = ''
        data = None
        cat_ids = []
        category_list = []
        mapped_ids = []
        try:
            data = prestashop.get('categories')
        except Exception as e:
            message+='<br/>For Category %s<br/>%s'%(data, str(e))
        if data:
            category_list = data['categories']['category']
            mapped_ids = self.channel_id.match_category_mappings(domain=[], limit=None).mapped("store_category_id")

        if self.operation=='import':
            if type(category_list) == dict:
                cat_ids.append(category_list['attrs']['id'])
            else:
                cat_ids = [i['attrs']['id'] for i in category_list if i['attrs']['id'] not in mapped_ids]
                cat_ids = list(split_seq(cat_ids, 100))

        else:
            if type(category_list) == dict:
                cat_ids.append(category_list['attrs']['id'])
            else:
                cat_ids = [i['attrs']['id'] for i in category_list if i['attrs']['id'] in mapped_ids]
                cat_ids = list(split_seq(cat_ids, 100))
        
        return dict(
            data = cat_ids,
            message = message
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
                fetch_res = record._get_prestashop_category_list(prestashop)
                categories_li = fetch_res.get('data', {})
                message += fetch_res.get('message', '')
                if not categories_li:
                    message += "Category data not received."
                else:
                    for categories in categories_li:
                        feed_res = record._prestashop_import_categories(prestashop, categories)
                        post_res = self.post_feed_import_process(channel_id, feed_res)
                        create_ids += post_res.get('create_ids')
                        update_ids += post_res.get('update_ids')
                        map_create_ids += post_res.get('map_create_ids')
                        map_update_ids += post_res.get('map_update_ids')
                        self._cr.commit()
        # _logger.info("==== create_ids update_ids map_create_ids map_update_ids %r",[create_ids, update_ids, map_create_ids, map_update_ids])
        message += self.env['multi.channel.sale'].get_feed_import_message(
            'category', create_ids, update_ids, map_create_ids, map_update_ids
        )
        return self.env['multi.channel.sale'].display_message(message)

    @api.model
    def _cron_prestashop_import_categories(self):
        for channel_id in self.env['multi.channel.sale'].search(CHANNELDOMAIN):
            vals = dict(
                channel_id = channel_id.id,
            )
            obj = self.create(vals)
            obj.import_now()


class ExportPrestashopCategories(models.TransientModel):
    _inherit = ['export.categories']
    _name = "export.prestashop.categories"

    def create_categories(self, prestashop, cat_id, name, is_root_category, id_parent, active, link_rewrite='None', description='None', meta_description='None', meta_keywords='None', meta_title='None'):
        cntx = self.env.context.copy()
        channel_id = self.channel_id
        cat_data = None
        if not channel_id:
            channel_id = cntx.get('channel_id')
        if self.operation=="update":
            try:
                cat_data = prestashop.get('categories', )
            except Exception as e:
                return [0,'\r\nCategory Id:%s ;Error in Creating blank schema for categories.Detail : %s'%(str(cat_id.id),str(e)),False]
        else:
            try:
                cat_data = prestashop.get('categories', options={'schema': 'blank'})
            except Exception as e:
                return [0,'\r\nCategory Id:%s ;Error in Creating blank schema for categories.Detail : %s'%(str(cat_id.id),str(e)),False]
        if cat_data:
            if type(cat_data['category']['name']['language']) == list:
                for i in range(len(cat_data['category']['name']['language'])):
                    cat_data['category']['name']['language'][i]['value'] = name
                    cat_data['category']['link_rewrite']['language'][i]['value'] = channel_id._get_link_rewrite(zip, name)
                    cat_data['category']['description']['language'][i]['value'] = description
                    cat_data['category']['meta_description']['language'][i]['value'] = meta_description
                    cat_data['category']['meta_keywords']['language'][i]['value'] = meta_keywords
                    cat_data['category']['meta_title']['language'][i]['value'] = name
            else:
                cat_data['category']['name']['language']['value'] = name
                cat_data['category']['link_rewrite']['language']['value'] = channel_id._get_link_rewrite(zip, name)
                cat_data['category']['description']['language']['value'] = description
                cat_data['category']['meta_description']['language']['value'] = meta_description
                cat_data['category']['meta_keywords']['language']['value'] = meta_keywords
                cat_data['category']['meta_title']['language']['value'] = name
            cat_data['category']['is_root_category'] = is_root_category
            cat_data['category']['id_parent'] = id_parent
            cat_data['category']['active'] = active
            try:
                returnid = prestashop.add('categories', cat_data)
            except Exception as e:
                _logger.info('.......... %r ................', [str(e), cat_id.id, cat_data])
                return [0, '\r\nCategory Id:%s ;Error in creating Category(s).Detail : %s'%(str(cat_id.id), str(e)), False]
            if returnid:
                cid = returnid
                mapping_id=channel_id.create_category_mapping(cat_id, cid)
                return [1,'',cid, mapping_id]

    def update_categories(self, prestashop, cat_id, presta_id, name, is_root_category, id_parent, active, link_rewrite='None', description='None', meta_description='None', meta_keywords='None', meta_title='None'):
        cntx = self.env.context.copy()
        channel_id = self.channel_id
        cat_data = None
        if not channel_id:
            channel_id = cntx.get('channel_id')
        try:
            cat_data = prestashop.get('categories', presta_id)
        except Exception as e:
            return [0,'\r\nCategory Id:%s ;Error in Creating blank schema for categories.Detail : %s'%(str(cat_id.id),str(e)),False]
        if cat_data:
            if type(cat_data['category']['name']['language']) == list:
                for i in range(len(cat_data['category']['name']['language'])):
                    cat_data['category']['name']['language'][i]['value'] = name
                    cat_data['category']['link_rewrite']['language'][i]['value'] = channel_id._get_link_rewrite(zip, name)
                    cat_data['category']['description']['language'][i]['value'] = description
                    cat_data['category']['meta_description']['language'][i]['value'] = meta_description
                    cat_data['category']['meta_keywords']['language'][i]['value'] = meta_keywords
                    cat_data['category']['meta_title']['language'][i]['value'] = name
            else:
                cat_data['category']['name']['language']['value'] = name
                cat_data['category']['link_rewrite']['language']['value'] = channel_id._get_link_rewrite(zip, name)
                cat_data['category']['description']['language']['value'] = description
                cat_data['category']['meta_description']['language']['value'] = meta_description
                cat_data['category']['meta_keywords']['language']['value'] = meta_keywords
                cat_data['category']['meta_title']['language']['value'] = name
            cat_data['category']['is_root_category'] = is_root_category
            cat_data['category']['id_parent'] = id_parent
            cat_data['category']['active'] = active
            try:
                returnid = prestashop.put('categories',presta_id, cat_data)
            except Exception as e:
                _logger.info('.......... %r ................', [str(e), cat_id.id, cat_data])
                return [0, '\r\nCategory Id:%s ;Error in creating Category(s).Detail : %s'%(str(cat_id.id), str(e)), False]
            if returnid:
                cid = returnid
                # mapping_id=channel_id.create_category_mapping(cat_id, cid)
                return [1,'',cid]
    def export_now(self):
        mapping_ids = []
        message = ''
        create_ids = []
        update_ids = []
        exclude_type_ids = []
        mapped = []
        cat_to_export = []
        already_mapped = []
        if not self.category_ids:
            already_mapped = self.env['channel.category.mappings'].search([('channel_id','=', self.channel_id.id), ('need_sync','=',True)])
        for record in self:
            channel_id = record.channel_id
            prestashop = PrestaShopWebServiceDict(channel_id.prestashop_base_uri, channel_id.prestashop_api_key)
            
            for m in already_mapped:
                mapped.append(m.category_name.id)
            
            # cat_to_export = self.env['product.category'].search(cat_ids)
            # cat_to_export = self.category_ids if self.category_ids else self.env['product.category'].search(
            #     [('id', 'not in', mapped)])
            if not prestashop:
                message += "Error in connection"
            if record.operation=="export":
                cat_to_export = self.category_ids if self.category_ids else self.env['product.category'].search(
                    [('id', 'not in', mapped)])
                for i in cat_to_export:
                    cat_id = self.with_context({'err_msg':'', 'mapping_ids':mapping_ids, 'create_ids': []}).sync_categories(prestashop, i, 1)
                    create_ids += cat_id[2]
            # elif mapped and self.operation=="update":
            #     for mapped_categ in mapped:
            #         cat_id = self.with_context({'err_msg':'', 'mapping_ids':mapping_ids, 'create_ids': []}).sync_categories(prestashop, i, 1)
                    
            else:
                message += '<br/> No category is available to be exported!'
        if len(create_ids):
           message += '<br/> Total %s  Categories exported.'%(len(create_ids))
        return self.env['multi.channel.sale'].display_message(message)


    def sync_categories(self, prestashop, cat_id, active='1', presta_id=None):
        ctx = self.env.context.copy()
        channel_id = self.channel_id
        if 'channel_id' in ctx:
            channel_id = ctx['channel_id']
        mapping_obj = self.env['channel.category.mappings']
        domain = [('odoo_category_id', '=',cat_id.id), ('channel_id','=', channel_id.id)]
        check = channel_id._match_mapping(
            mapping_obj,
            domain,
            limit=1
        )
        if not check:
            obj_catg = cat_id
            name = pob_decode(obj_catg.name)
            if obj_catg.parent_id.id:
                p_cat_id = self.with_context(ctx).sync_categories(prestashop, obj_catg.parent_id, 1)[0]
            else:
                get_response=self.with_context(ctx).create_categories(prestashop, cat_id, name, '0', '2', active)
                if get_response[0] > 0:
                    ctx['create_ids'] += get_response[3]
                p_cat_id = get_response[2]
                ctx['err_msg'] += get_response[1]
                return [p_cat_id,ctx['err_msg'], ctx['create_ids']]
            get_response = self.with_context(ctx).create_categories(prestashop, cat_id, name, '0', p_cat_id, active, presta_id)
            try:
                ctx['create_ids'] += get_response[3]
            except:
                ctx['err_msg'] += "Error while exporting category"
            p_cat_id = get_response[2]
            ctx['err_msg'] += get_response[1]
            return [p_cat_id,ctx['err_msg'], ctx['create_ids']]
        else:

            return [check.store_category_id,ctx['err_msg'], ctx['create_ids']]
