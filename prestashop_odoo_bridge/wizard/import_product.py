# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################
import logging, ast
import itertools
import binascii

from io import BytesIO
from PIL import Image
import base64

from xmlrpc.client import Error
from odoo import api, fields, models, _
from odoo.addons.odoo_multi_channel_sale.tools import MapId
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.prestashop_odoo_bridge.models.prestapi import PrestaShopWebService, PrestaShopWebServiceDict, \
    PrestaShopWebServiceError, PrestaShopAuthenticationError

import re

try:
    import html2text
except Exception as e:
    pass

_logger = logging.getLogger(__name__)

OdooType = [
    ('simple', 'product'),
    ('downloadable', 'service'),  # digital
    ('grouped', 'service'),
    ('virtual', 'service'),
    ('bundle', 'service'),
]

CHANNELDOMAIN = [
    ('channel', '=', 'prestashop'),
    ('state', '=', 'validate')
]


def _unescape(text):
    ##
    # Replaces all encoded characters by urlib with plain utf8 string.
    #
    # @param text source text.
    # @return The plain text.
    from urllib.parse import unquote
    try:
        temp = unquote(text.encode('utf8'))
    except Exception as e:
        temp = text
    return temp


class ImportPrestashopProducts(models.TransientModel):
    _inherit = ['import.templates']
    _name = "import.prestashop.products"

    def _get_data(self, prestashop, resource, id):
        data = None
        message = ''
        try:
            data = prestashop.get(resource, id)
        except Exception as e:
            message += 'Error while getting the data %s' % (e)
        if data:
            return dict(
                data=data,
                message=message
            )
        return dict(
            data=False,
            message=message
        )

    def get_attribute_value(self, id):
        data = None
        message = ''
        prestashop = self._context['prestashop']
        channel_id = self.channel_id
        channel_lang = channel_id.ps_language_id.split(str(channel_id.id) + '-')[1]
        try:
            data = prestashop.get('product_option_values', id).get('product_option_value')
        except Exception as e:
            message += 'Error while getting the attribute data'
        if type(data['name']['language']) == list:
            for cat_name in data['name']['language']:
                if cat_name['attrs']['id'] == channel_lang:
                    attr_val_name = cat_name['value']
        else:
            attr_val_name = data.get('name')['language']['value']

        attr_id = data.get('id_attribute_group')
        try:
            attr_data = prestashop.get('product_options', attr_id).get('product_option')
        except Exception as e:
            message += 'Error while getting the country data'
        if type(attr_data['name']['language']) == list:
            for cat_name in attr_data['name']['language']:
                if cat_name['attrs']['id'] == channel_lang:
                    attr_name = cat_name['value']
        else:
            attr_name = attr_data.get('name')['language']['value']
        return {
            'name': _unescape(attr_name),
            'attr_val_id': id,
            'attr_id': attr_id,
            'option': _unescape(attr_val_name)
        }

    def create_variants(self, combination_ids):
        variant_list = []
        message = ''
        quantity = 0
        for i in combination_ids:
            try:
                combination_data = self._context['prestashop'].get('combinations',
                                                                   i).get('combination')
                """stock_id = self._context['prestashop'].get('stock_availables',
                    options={'filter[id_product_attribute]': i})
                if type(stock_id['stock_availables']['stock_available'])==list:
                    stock_id = stock_id.get(
                    'stock_availables').get('stock_available')[0].get('attrs').get('id')
                else:
                    stock_id = stock_id.get(
                    'stock_availables').get('stock_available').get('attrs').get('id')
                quantity = self._context['prestashop'].get('stock_availables',
                stock_id).get('stock_available').get('quantity')"""
            except Exception as e:
                message += 'Error while getting the Stock data %s' % (e)
                _logger.info(':::::::::::::::: Variant error  %r ::::::::::::::::::', message)
            attribute_list = []
            product_var_ids = combination_data['associations']['product_option_values'].get('product_option_value')
            if type(product_var_ids) == list:
                for attributes in product_var_ids:
                    attr_data = self.get_attribute_value(attributes['id'])
                    attr = {}
                    attr['name'] = str(attr_data['name'])
                    attr['attrib_name_id'] = attr_data['attr_id']
                    attr['attrib_value_id'] = attr_data['attr_val_id']
                    attr['value'] = str(_unescape(attr_data['option']))
                    attribute_list.append(attr)
            else:
                if product_var_ids:
                    attr_data = self.get_attribute_value(product_var_ids['id'])
                    attr = {}
                    attr['name'] = str(attr_data['name'])
                    attr['attrib_name_id'] = attr_data['attr_id']
                    attr['attrib_value_id'] = attr_data['attr_val_id']
                    attr['value'] = str(_unescape(attr_data['option']))
                    attribute_list.append(attr)

            varaint_dict = {
                'name_value': attribute_list,
                'store_id': combination_data['id'],
                'default_code': combination_data['reference'],
                # 'wk_product_id_type': 'wk_ean',
                # 'qty_available' : quantity,
                'list_price': str(float(combination_data['price']) + float(self._context.get('list_price'))),
                'standard_price': combination_data.get('wholesale_price'),
            }
            if combination_data['ean13']:
                varaint_dict['barcode'] = combination_data['ean13']
                varaint_dict['wk_product_id_type'] = 'wk_ean'
            if 'image' in combination_data['associations']['images']:
                if not type(combination_data['associations']['images']['image']) == list:
                    image_id = combination_data['associations']['images']['image']['id']
                else:
                    image_id = combination_data['associations']['images']['image'][0]['id']
                try:
                    image_data = 'images/products/%s/%s' % (combination_data['id_product'], image_id)
                    image_data = self.channel_id._prestashop_get_product_images_vals(image_data)

                    image = Image.open(BytesIO(base64.b64decode(image_data.get('image'))))
                    w, h = image.size
                    _logger.info(":::: image_size product variation : %r ::::::::::::::::::", [w, h])

                    if image.width > 1028 or image.height > 1028:
                        if image.height > image.width:
                            factor = 1028 / image.height
                        else:
                            factor = 1028 / image.width
                        tn_image1 = False
                        #  tn_image = image.resize((int(image.width * factor), int(image.height * factor)))
                    #
                    #  buffered = BytesIO()
                    #  tn_image.save(buffered, image.format)
                    #
                    #  tn_image1 = base64.b64encode(buffered.getvalue())
                    #  tn_image1 = tn_image1.decode()

                    #  _logger.info(":::: image_size ENTROOOOO 1 : %r ::::::::::::::::::", [w, h, data.get('ean13')])
                    else:
                        tn_image1 = image_data.get('image')

                    varaint_dict.update({
                        'image': tn_image1,
                    })
                except Exception as e:
                    message += ' Error in image variant : %s' % (e)
                    _logger.info(":::: Error in image variants : %r ::::::::::::::::::", [e, i, image_data])
                    pass
            variant_list.append((0, 0, varaint_dict))
        return variant_list

    def _get_stock(self, stock_id):
        message = ''
        quantity = False
        try:
            quantity = self._context['prestashop'].get('stock_availables',
                                                       stock_id).get('stock_available').get('quantity')
        except Exception as e:
            message += ' Error in getting stock : %s' % (e)
            _logger.info('======> %r.', message)
        return quantity

    def get_product_vals(self, product_id, product_data):
        #_logger.info(":::: product_data : %r ::::::::::::::::::", product_data['name'])
        taxx = ''
        variants = [(5, 0, 0)]
        message = ''
        qty = 0
        stock_id = False
        extra_categ_ids = False
        channel_id = self.channel_id
        channel_lang = channel_id.ps_language_id.split(str(channel_id.id) + '-')[1]
        if 'category' in product_data['associations']['categories']:
            cat_data = product_data['associations']['categories']['category']
            if type(cat_data) == list:
                category_ids = [i['id'] for i in cat_data]
            else:
                category_ids = [cat_data['id']]
            extra_categ_ids = ','.join(category_ids)
        if 'categories' in product_data['associations']['categories']:
            cat_data = product_data['associations']['categories']['categories']
            if type(cat_data) == list:
                category_ids = [i['id'] for i in cat_data]
            else:
                category_ids = [cat_data['id']]
            extra_categ_ids = ','.join(category_ids)
        if type(product_data['name']['language']) == list:
            for pro_name in product_data['name']['language']:
                if pro_name['attrs']['id'] == channel_lang:
                    name = pro_name['value']
                    break
        else:
            name = product_data.get('name')['language']['value']
        is_pack = False
        list_bundles = []
        if product_data.get('type').get('value') == 'pack':
            is_pack = True

            if type(product_data.get('associations').get('product_bundle').get('product')) == list:
                index = 1
                for i in product_data.get('associations').get('product_bundle').get('product'):
                    id = int(i['id'])
                    quantity = int(i['quantity'])
                    bundles_dict = {
                        'name': "Bundle " + str(index),
                        'id_product': id,
                        'quantity': quantity
                    }
                    index += 1
                    list_bundles.append((0, 0, bundles_dict))
            else:
                index = 1
                id = int(product_data.get('associations').get('product_bundle').get('product').get('id'))
                quantity = int(product_data.get('associations').get('product_bundle').get('product').get('quantity'))
                bundles_dict = {
                    'name': "Bundle " + str(index),
                    'id_product': id,
                    'quantity': quantity
                }
                list_bundles.append((0, 0, bundles_dict))

        vals = dict(
            name=_unescape(name),
            default_code=product_data.get('reference'),
            type=dict(OdooType).get(product_data.get('type').get('value'), 'service'),
            store_id=product_id,
            # wk_product_id_type = 'wk_ean',
            extra_categ_ids=extra_categ_ids,
            is_pack=is_pack,
            product_bundle=list_bundles
        )

        if type(product_data.get('associations').get('combinations').get('combination')) == list:
            combination_ids = [i['id'] for i in product_data.get(
                'associations').get('combinations').get('combination')]
            variants = self.with_context(list_price=product_data.get('price')).create_variants(combination_ids)
        elif type(product_data.get('associations').get('combinations').get('combination')) == dict:
            combination_ids = [product_data.get('associations').get('combinations').get('combination').get('id')]
            variants = self.with_context(list_price=product_data.get('price')).create_variants(combination_ids)
        else:
            if product_data.get('ean13'):
                vals['barcode'] = product_data.get('ean13')
                vals['wk_product_id_type'] = 'wk_ean'
            """if product_data.get('associations').get('stock_availables').get('stock_available') == list:
                try:
                    stock_id = product_data.get('associations').get('stock_availables').get('stock_available')[0].get('id')
                except:
                    stock_id = product_data.get('associations').get('stock_availables').get('stock_available')[0].get('id')
            elif product_data.get('associations').get('stock_availables').get('stock_available'):
                try:
                    stock_id = product_data.get('associations').get('stock_availables').get('stock_available').get('id')
                except:
                    stock_id = product_data.get('associations').get('stock_availables').get('stock_available')[0].get('id')
            if stock_id:
                qty = self._get_stock(stock_id)
            vals['qty_available'] = qty"""
        data = product_data
        description_sale = ''
        if type(data['description_short']['language']) == list:
            for pro_name in data['description_short']['language']:
                if pro_name['attrs']['id'] == channel_lang:
                    try:
                        # description_sale = pro_name['value']
                        description_sale = html2text.html2text(pro_name['value'])
                    except:
                        description_sale = pro_name['value']
        else:
            try:
                description_sale = html2text.html2text(data.get('description_short')['language']['value'])

                # description_sale = data.get('description_short')['language']['value']
            except:
                description_sale = data.get('description_short')['language']['value']
        description = ''
        if type(data['description']['language']) == list:
            for pro_name in data['description']['language']:
                if pro_name['attrs']['id'] == channel_lang:
                    try:
                        # description = pro_name['value']
                        description = html2text.html2text(pro_name['value'])

                    except:
                        description = pro_name['value']
        else:
            try:
                # description = data.get('description_short')['language']['value']
                description = html2text.html2text(data.get('description')['language']['value'])
            except:
                description = data.get('description_short')['language']['value']

        description_sale_presta = ''
        if type(data['description_short']['language']) == list:
            for pro_name in data['description_short']['language']:
                if pro_name['attrs']['id'] == channel_lang:
                    try:
                        description_sale_presta = pro_name['value']
                        # description_sale = html2text.html2text(pro_name['value'])
                    except:
                        description_sale_presta = pro_name['value']
        else:
            try:
                # description_sale = html2text.html2text(data.get('description_short')['language']['value'])

                description_sale_presta = data.get('description_short')['language']['value']
            except:
                description_sale_presta = data.get('description_short')['language']['value']

        description_presta = ''
        if type(data['description']['language']) == list:
            for pro_name in data['description']['language']:
                if pro_name['attrs']['id'] == channel_lang:
                    try:
                        description_presta = pro_name['value']
                        # description = html2text.html2text(pro_name['value'])

                    except:
                        description_presta = pro_name['value']
        else:
            try:
                description_presta = data.get('description')['language']['value']
                # description = html2text.html2text(data.get('description')['language']['value'])
            except:
                description_presta = data.get('description')['language']['value']

        tax = int(product_data.get('id_tax_rules_group'))
        # config_ids = self.search([('channel', '=', 'prestashop')])
        # _logger.info(":::: config_ids : %r ::::::::::::::::::", config_ids)
        tax_record = self.env['account.tax']
        tax_mapping_obj = self.env['channel.account.mappings']

        if tax:
            _logger.info(":::: tax : %r ::::::::::::::::::", tax)

            conf = self.env['multi.channel.sale'].search([('id', '=',self.channel_id.id)])
            url = conf.prestashop_base_uri
            key = conf.prestashop_api_key

            _logger.info(":::: dir : %r :::::%r:::::::::::::", url, key)

            try:
                prestashop = PrestaShopWebServiceDict(url, key)
            except PrestaShopWebServiceError as e:
                raise UserError(_('Error %s') % str(e))

            if prestashop:
                data_tax = prestashop.get('tax_rules',
                                          options={'display': '[id,id_tax]', 'filter[id_tax_rules_group]': tax})
                for tx in data_tax['tax_rules']['tax_rule']:
                    _logger.info(":::: tx : %r ::::::::::::::::::", tx)
                    # tax_group=int(tx['attrs']['id'])
                    id_tax = int(tx.get('id_tax'))
                    break

                if id_tax:

                    taxes = prestashop.get('taxes', options={'display': '[id,rate,name]', 'filter[id]': id_tax})
                    id = ""
                    rate = ""
                    name = ""
                    for txs in taxes['taxes']['tax']:
                        for a in taxes['taxes']['tax'][txs]:
                            if txs == "id":
                                id = a
                            elif txs == "rate":
                                rate = rate + a
                            elif txs == "name":
                                name = "IVA" + rate
                                # for i in taxes['taxes']['tax'][txs]['language']['value']:
                                #     name = name + i


                    tax_dict = {
                        'name': name,
                        'amount_type': 'percent',
                        'price_include': False,
                        'amount': rate,
                    }

                    tax_id = tax_record.search([('name', '=', tax_dict['name'])])

                    if not tax_id:
                        tax_id = tax_record.create(tax_dict)
                        tax_map_vals = {
                            'channel_id': channel_id.id,
                            'tax_name': tax_id.id,
                            'store_tax_value_id': str(tax_id.amount),
                            'tax_type': tax_id.amount_type,
                            'include_in_price': tax_id.price_include,
                            'odoo_tax_id': tax_id.id,
                        }
                        id = channel_id._create_mapping(tax_mapping_obj, tax_map_vals)

                    taxx = self.env['channel.account.mappings'].search([('tax_name', '=', tax_id.name)])
                    #_logger.info("::::taxx : %r ::::::::::::::::::", taxx)
                else:
                    taxx = None
                    #_logger.info("::::taxx : %r ::::::::::::::::::", taxx)
        if not taxx:
            taxx = None

        """"tax_dict={
            'name'            : name,
			'amount_type'     : tax_type,
			'price_include'   : inclusive,
			'amount'          : float(tax['rate']),
            }"""

        if data:
            vals['description_sale'] = re.sub(r'\*|', '', _unescape(description_sale))
            vals['weight'] = data.get('weight')
            vals['length'] = data.get('depth')
            vals['width'] = data.get('width')
            vals['height'] = data.get('height')
            vals['list_price'] = data.get('price')
            vals['standard_price'] = data.get('wholesale_price')
            vals['feed_variants'] = variants
            vals['description'] = re.sub(r'\*|', '', _unescape(description))
            vals['description_presta'] = description_presta
            vals['description_sale_presta'] = description_sale_presta
            vals['taxes_id'] = taxx

            if data.get('id_default_image').get('value'):
                image_data = 'images/products/%s/%s' % (product_id, data.get('id_default_image').get('value'))
                try:
                    res_img = channel_id._prestashop_get_product_images_vals(image_data)

                    image = Image.open(BytesIO(base64.b64decode(res_img.get('image'))))
                    w, h = image.size
                    _logger.info(":::: image_size product : %r ::::::::::::::::::", [w, h])

                    if image.width > 1028 or image.height > 1028:
                        if image.height > image.width:
                            factor = 1028 / image.height
                        else:
                            factor = 1028 / image.width
                        #  tn_image = image.resize((int(image.width * factor), int(image.height * factor)))

                        #  buffered = BytesIO()
                        #  tn_image.save(buffered, image.format)

                        #  tn_image1 = base64.b64encode(buffered.getvalue())
                        #  tn_image1 = tn_image1.decode()

                        #  _logger.info(":::: image_size ENTROOOOO 1 : %r ::::::::::::::::::", [w, h, data.get('ean13')])
                        tn_image1 = False
                    else:
                        tn_image1 = res_img.get('image')
                        # _logger.info(":::: image_BUENAAA : %r ::::::::::::::::::", [image_data])
                    vals['image'] = tn_image1
                except Exception as e:
                    message += 'Error in image product : %s' % (e)
                    _logger.info(":::: Error in image product : %r ::::::::::::::::::", [e, product_id, image_data])
                    pass
        return vals

    def _prestashop_create_product_categories(self, data):
        message = ''
        if type(data) == list:
            category_ids = [int(i['id']) for i in data]
        else:
            category_ids = [int(data['id'])]
        mapping_obj = self.env['channel.category.mappings']
        feed_obj = self.env['category.feed']
        domain = [('store_category_id', 'in', category_ids)]
        mapped = self.channel_id._match_mapping(mapping_obj, domain).mapped('store_category_id')
        feed_map = self.channel_id._match_feed(feed_obj, [('store_id', 'in', category_ids)], limit=1).mapped('store_id')
        category_ids = list(set(category_ids) - set(mapped) - set(feed_map))
        if len(category_ids):
            message = 'For product category imported %s' % (category_ids)
            try:
                import_category_obj = self.env['import.prestashop.categories']
                vals = dict(
                    channel_id=self.channel_id.id,
                )
                import_category_id = import_category_obj.create(vals)
                # import_category_id.import_now()
                import_category_id._prestashop_import_categories(self._context.get('prestashop'), category_ids)
            except Exception as e:
                message = "Error while product's category import %s" % (e)

    #
    def _prestashop_update_product_feed(self, data, feed, product_id):
        vals = self.get_product_vals(product_id, data)
        if feed.feed_variants:
            feed.write(dict(feed_variants=[(5, 0, 0)]))
        feed.write(vals)
        feed.state = 'update'
        return feed

    def _prestashop_create_product_feed(self, product_data, product_id):
        vals = self.get_product_vals(product_id, product_data)
        vals['store_id'] = product_id
        feed_obj = self.env['product.feed']
        feed_id = self.channel_id._create_feed(feed_obj, vals)
        _logger.info('......................Feed id %r......................', feed_id)
        return feed_id

    def _prestashop_import_product(self, product_data):
        update = False
        status = True
        match = False
        # self.channel_id.update_feed =True
        if not self.channel_id.ps_language_id:
            raise UserError("Please select the language in configuration first.!")
        # _logger.info('...... Called product id: %r........', product_data)
        feed_obj = self.env['product.feed']
        channel_id = self.channel_id
        message = ''
        product_data = self._get_data(self._context.get('prestashop'), 'products', product_data)
        prestashop = self.env.context['prestashop']
        if product_data['data']:
            product_data = product_data['data'].get('product')
            product_id = product_data['id']
            match = self.channel_id._match_feed(
                feed_obj, [('store_id', '=', product_id)], limit=1)

            if match:
                if self.channel_id.update_feed:
                    if product_data['associations']['categories']:
                        if 'category' in product_data['associations']['categories']:
                            self._prestashop_create_product_categories(
                                product_data['associations']['categories']['category'])
                        if 'categories' in product_data['associations']['categories']:
                            self._prestashop_create_product_categories(
                                product_data['associations']['categories']['categories'])
                    self._prestashop_update_product_feed(product_data, match, product_id)
                update = True
            else:
                if product_data['associations']['categories']:
                    if 'category' in product_data['associations']['categories']:
                        self._prestashop_create_product_categories(
                            product_data['associations']['categories']['category'])
                    if 'categories' in product_data['associations']['categories']:
                        self._prestashop_create_product_categories(
                            product_data['associations']['categories']['categories'])
                map_match = self.channel_id.match_template_mappings(product_id, {})
                if map_match:
                    # pass
                    vals = self.get_product_vals(product_id, product_data)
                    try:
                        map_match.template_name.write(vals)
                        # match = map_match.template_name
                        # update = True
                        message += '<br/> Product %s successfully updated' % (
                            vals.get('name', ''))
                    except Exception as e:
                        _logger.info('-----Exception--------------%r', e)
                        message += '<br/>%s' % (e)
                else:
                    match = self._prestashop_create_product_feed(product_data, product_id)
        else:
            status = False
        return dict(
            feed_id=match,
            update=update,
            status=status
        )

    def _prestashop_import_products(self, items):
        create_ids = []
        update_ids = []
        for item in items:
            import_res = self._prestashop_import_product(item)
            if import_res['status']:
                feed_id = import_res.get('feed_id')
                if import_res.get('update'):
                    update_ids.append(feed_id)
                else:
                    create_ids.append(feed_id)
        return dict(
            create_ids=create_ids,
            update_ids=update_ids,
        )

    def import_now(self):
        date = fields.Datetime.to_string(self.ps_import_update_date)
        limit = self.api_record_limit
        operation = self.operation
        create_ids, update_ids, map_create_ids, map_update_ids = [], [], [], []
        context = self.env.context.copy()
        message = ''
        for record in self:
            channel_id = record.channel_id
            # channel_id.check_prestashop_lang_set()
            fetch_res = channel_id.with_context({'operation': operation})._fetch_prestashop_products(date, limit)
            prestashop = fetch_res.get('prestashop')
            context.update({'prestashop': prestashop})
            product_ids = fetch_res.get('data', [])
            message += fetch_res.get('message', '')
            for ids_limit in product_ids:
                if not ids_limit:
                    message += "Product data not received."
                else:
                    feed_res = record.with_context(context)._prestashop_import_products(ids_limit)
                    self.env.cr.commit()
                    post_res = self.post_feed_import_process(channel_id, feed_res)
                    create_ids += post_res.get('create_ids')
                    update_ids += post_res.get('update_ids')
                    map_create_ids += post_res.get('map_create_ids')
                    map_update_ids += post_res.get('map_update_ids')
        message += self.env['multi.channel.sale'].get_feed_import_message(
            'product', create_ids, update_ids, map_create_ids, map_update_ids
        )
        packs = self.env['product.feed'].search([('is_pack', '=', True)])
        for pack in packs:
            template = self.env['channel.product.mappings'].search([('store_product_id', '=', pack.store_id)], limit=1)
            if template:
                product_template = template.odoo_template_id
                mrp = self.env['mrp.bom'].search([('product_tmpl_id', '=', product_template.id)])
                if not mrp:
                    bom_line_ids = pack.product_bundle
                    list_bom = []
                    for bom in bom_line_ids:
                        p = self.env['channel.product.mappings'].search(
                            [('store_product_id', '=', str(bom.id_product))], limit=1)
                        if p:
                            bundles_dict = {
                                'product_id': p.product_name.id,
                                'product_qty': bom.quantity,
                                'product_uom_id': p.product_name.uom_id.id
                            }
                            list_bom.append((0, 0, bundles_dict))

                    self.env['mrp.bom'].create({
                        'product_tmpl_id': product_template.id,
                        'type': 'phantom',
                        'product_uom_id': product_template.uom_id.id,
                        'product_qty': 1,
                        'consumption': 'warning',
                        'bom_line_ids': list_bom,

                    })
        return self.env['multi.channel.sale'].display_message(message)

    @api.model
    def _cron_prestashop_import_products(self):
        for channel_id in self.env['multi.channel.sale'].search(CHANNELDOMAIN):
            vals = dict(
                channel_id=channel_id.id,
                source='all',
                operation='import',
                api_record_limit=100,
            )
            obj = self.create(vals)
            obj.import_now()