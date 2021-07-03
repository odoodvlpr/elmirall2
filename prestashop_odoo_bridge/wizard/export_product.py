# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################
from xmlrpc.client import Error
import itertools
from odoo import api, fields, models, _
from odoo.addons.prestashop_odoo_bridge.models.prestapi import PrestaShopWebService, PrestaShopWebServiceDict, \
    PrestaShopWebServiceError, PrestaShopAuthenticationError
from odoo.exceptions import UserError, RedirectWarning, ValidationError, Warning
from odoo.addons.odoo_multi_channel_sale.tools import extract_list as EL
from odoo.addons.odoo_multi_channel_sale.tools import ensure_string as ES
from odoo.addons.odoo_multi_channel_sale.tools import JoinList as JL
from odoo.addons.odoo_multi_channel_sale.tools import MapId
import logging

_logger = logging.getLogger(__name__)

CHANNELDOMAIN = [
    ('channel', '=', 'prestashop'),
    ('state', '=', 'validate')
]


class ExportProductsPrestashop(models.TransientModel):
    _inherit = ['export.products']

    def prestashop_export_product(self):
        message = ''
        context = self.env.context.copy() or {}
        context.update({'channel_id': self.channel_id})
        for rec in self:
            message += rec.env['export.templates'].with_context(
                context).prestashop_export_product()
        return self.env['multi.channel.sale'].display_message(message)


class ExportPrestashopProducts(models.TransientModel):
    _inherit = ['export.templates']

    def deduct_price(self, total_price):
        tax = self.env['channel.account.mappings'].search([('channel_id', '=', self.channel_id.id)])[0]
        if tax.tax_type == 'percent' and tax.include_in_price:
            rate = float(tax.store_tax_value_id) / 100 + 1
            price_no_tax = float(total_price) / rate
            return round(price_no_tax, 2)
        else:
            return round(total_price, 2)

    def prestashop_export_templates(self):
        mapping_ids = []
        message = ''
        config_tmpl_ids = []
        create_ids = []
        update_ids = []
        exclude_type_ids = []
        for record in self:
            channel_id = record.channel_id
            # channel_id.check_prestashop_lang_set()
            prestashop = PrestaShopWebServiceDict(
                channel_id.prestashop_base_uri, channel_id.prestashop_api_key)
            if not prestashop:
                message += "Error in connection"
            if prestashop:
                post_res = record.export_all_products(prestashop)
                create_ids = post_res.get('create_ids')
                message += post_res.get('message')
        message += '<br/> Total %s  product exported.' % (len(create_ids))
        return self.env['multi.channel.sale'].display_message(message)

    def prestashop_export_product(self):
        context = self.env.context.copy() or {}
        message = ''
        count = 0
        need_to_export = []
        prod_obj = self.env['product.product']
        selected_ids = context.get('active_ids')
        channel_id = self.channel_id
        if not channel_id:
            channel_id = context['channel_id']
        prestashop = PrestaShopWebServiceDict(
            channel_id.prestashop_base_uri, channel_id.prestashop_api_key)

        if prestashop:
            context.update({'channel_id': channel_id, 'export_product': True})
            # Add Update Stock Operation
            if self.operation == 'update_stock' or context.get('operation') == 'update_stock':
                for k in selected_ids:
                    check_ups = self.env['channel.product.mappings'].search(
                        [('product_name', '=', k), ('channel_id', '=', channel_id.id)])

                    if check_ups:
                        for check_up in check_ups:
                            pick_details = {
                                'product_id': check_up.product_name.id,
                                'location_dest_id': channel_id.location_id.id,
                                'product_qty': 1,
                                'channel_ids': channel_id.ids,
                                'source_loc_id': channel_id.location_id.id,
                            }

                            self.env['stock.move'].multichannel_sync_quantity(pick_details)
                    else:
                        message = 'Este producto  %s no esta mapeado en el canal seleccionado'
                        return message
                message = 'Se ha actualizado el stock de %s productos' % len(check_ups)
                return message

            for j in selected_ids:
                check = self.env['channel.product.mappings'].search(
                    [('product_name', '=', j), ('channel_id', '=', channel_id.id)], limit=1)
                if not check:
                    need_to_export.append(j)
            if len(need_to_export) == 0:
                message = 'Selected product(s) are already exported to Prestashop.'
            for erp_product_id in need_to_export:
                product_bs = prestashop.get(
                    'products', options={'schema': 'blank'})
                combination_bs = prestashop.get(
                    'combinations', options={'schema': 'blank'})
                response = self.with_context(context).export_product(
                    prestashop, product_bs, combination_bs, erp_product_id)
                if response[0] > 0:
                    count = count + 1
        message = message + '\r\n' + \
                  '%s products has been exported to Prestashop .\r\n' % (count)
        return message

    def prestashop_export_template(self):
        context = self.env.context.copy() or {}
        message = ''
        count = 0
        update = [0]
        need_to_export = []
        exported_ids = []
        erp_product_ids = []
        prod_obj = self.env['product.template']
        selected_ids = context.get('active_ids')
        channel_id = self.channel_id
        prestashop = PrestaShopWebServiceDict(
            channel_id.prestashop_base_uri, channel_id.prestashop_api_key)
        if prestashop:
            # product_bs = prestashop.get(
            #     'products', options={'schema': 'blank'})
            # combination_bs = prestashop.get(
            #     'combinations', options={'schema': 'blank'})

            if self.operation == 'update_stock':
                for k in selected_ids:
                    check_ups = self.env['channel.product.mappings'].search(
                        [('odoo_template_id', '=', k), ('channel_id', '=', channel_id.id)])

                    if check_ups:
                        for check_up in check_ups:
                            pick_details = {
                                'product_id': check_up.product_name.id,
                                'location_dest_id': channel_id.location_id.id,
                                'product_qty': 1,
                                'channel_ids': channel_id.ids,
                                'source_loc_id': channel_id.location_id.id,
                            }

                            self.env['stock.move'].multichannel_sync_quantity(pick_details)
                    else:
                        raise UserError(
                            _('Este producto  %s no esta mapeado en el canal seleccionado') % k)
                message = 'Se ha actualizado el stock de %s productos' % len(check_ups)
                return self.env['multi.channel.sale'].display_message(message)

            for j in selected_ids:
                check = self.env['channel.template.mappings'].search(
                    [('odoo_template_id', '=', j), ('channel_id', '=', channel_id.id)], limit=1)
                if check:
                    if check.need_sync == 'yes':
                        exported_ids.append(j)
                else:
                    need_to_export.append(j)

            if exported_ids and prestashop:
                pp_obj = self.env['channel.template.mappings']
                for j in exported_ids:
                    need_update_id = pp_obj.search(
                        [('odoo_template_id', '=', j), ('channel_id', '=', channel_id.id)], limit=1)
                    presta_id = need_update_id.store_product_id
                    erp_id = j
                    if prestashop and need_update_id:
                        temp_obj = self.env['product.template'].with_context(
                            context).browse(erp_id)
                        if temp_obj:
                            if not temp_obj.name:
                                name = 'None'
                            else:
                                name = temp_obj.name
                            if temp_obj.description_presta:
                                description = temp_obj.description_presta
                            else:
                                if temp_obj.description:
                                    description = temp_obj.description
                                else:
                                    description = ' '
                            if temp_obj.description_sale_presta:
                                description_sale = temp_obj.description_sale_presta
                            else:
                                if temp_obj.description_sale:
                                    description_sale = temp_obj.description_sale
                                else:
                                    description_sale = ' '
                            if temp_obj.default_code:
                                default_code = temp_obj.default_code
                            else:
                                default_code = ' '
                            if temp_obj.list_price:
                                price = round(temp_obj.with_context(pricelist=channel_id.pricelist_name.id).price, 2)
                            else:
                                price = 0.0
                            if temp_obj.weight:
                                weight = temp_obj.weight
                            else:
                                weight = 0.000000
                            if temp_obj.standard_price:
                                cost = round(temp_obj.standard_price, 3)
                            else:
                                cost = 0.0
                            if temp_obj.categ_id:
                                def_categ = temp_obj.categ_id.id
                            else:
                                raise UserError(
                                    _('Template Must have a Default Category'))
                            context.update({'price': price, 'reference': default_code,
                                            'weight': weight, 'cost': cost, 'def_categ': def_categ,
                                            'temp_obj': temp_obj})
                            update = self.with_context(context).update_template(
                                prestashop, erp_id, presta_id, name, description, description_sale)
                            if update[0]:
                                temp_obj.channel_mapping_ids.with_context(
                                    {'search_default_filter_by_channel_id': channel_id.id}).write({'need_sync': 'no'})
                                self.env.cr.commit()
            if need_to_export and prestashop:
                for k in self.env['product.template'].browse(need_to_export):
                    for l in k.product_variant_ids:
                        erp_product_ids.append(l.id)
                prod_ids = self.env['product.product'].search(
                    [('id', 'in', erp_product_ids), ('type', 'not in', ['service'])])
                for erp_product_id in prod_ids:
                    product_bs = prestashop.get(
                        'products', options={'schema': 'blank'})
                    combination_bs = prestashop.get(
                        'combinations', options={'schema': 'blank'})
                    response = self.with_context(context).export_product(
                        prestashop, product_bs, combination_bs, erp_product_id.id)
            message = 'Product Template(s) Updated: %s\r\nNumber of Product Template(s) Exported: %s' % (
                update[0] and len(exported_ids), len(need_to_export)) + ' \r\n' + message
        return self.env['multi.channel.sale'].display_message(message)

    def export_all_products(self, prestashop):
        context = self.env.context.copy() or {}
        message = ''
        create_ids = []
        mapped = []
        prod_obj = self.env['product.product']
        if prestashop:
            already_mapped = self.env['channel.product.mappings'].search([('channel_id', '=', self.channel_id.id)])
            for m in already_mapped:
                mapped.append(m.product_name.id)
            need_to_export = prod_obj.search(
                [('id', 'not in', mapped), ('type', 'not in', ['service'])])
            if len(need_to_export) == 0:
                message = 'Nothing to Export. All product(s) are already exported to Prestashop.'
            for erp_product_id in need_to_export:
                product_bs = prestashop.get(
                    'products', options={'schema': 'blank'})
                combination_bs = prestashop.get(
                    'combinations', options={'schema': 'blank'})
                response = self.export_product(
                    prestashop, product_bs, combination_bs, erp_product_id.id)
                if response[0] > 0:
                    create_ids += [response[0], ]
        return {'create_ids': create_ids,
                'message': message
                }

    def export_product(self, prestashop, product_bs, combination_bs, erp_product_id):
        context = self.env.context.copy() or {}
        message = ''
        response = [0]
        default_attr = 0  # Change '0' by 0
        channel_id = self.channel_id if self.channel_id else context.get("channel_id")
        template_obj = self.env['channel.template.mappings']
        prod_obj = self.env['product.product']
        product_data = prod_obj.browse(erp_product_id)

        if product_data.product_tmpl_id:
            erp_template_id = product_data.product_tmpl_id.id

            check = template_obj.search(
                [('odoo_template_id', '=', erp_template_id), ('channel_id', '=', channel_id.id)])
            if check:
                ps_template_id = int(check[0].store_product_id)
            else:
                response = self.export_template(
                    prestashop, product_bs, erp_template_id)
                if response[0] > 0:
                    ps_template_id = response[0]
                    default_attr = 1  # Change '1' by 1
                else:
                    return response
            if product_data.attribute_line_ids:
                response_combination = self.create_combination(
                    prestashop, combination_bs, ps_template_id, product_data.product_tmpl_id, erp_product_id,
                    default_attr)
                if context.get("export_product"):
                    return response_combination
            else:
                response_update = self.create_normal_product(
                    prestashop, product_data.product_tmpl_id, erp_product_id, ps_template_id)
                if context.get("export_product"):
                    return response_update
            return response

    def _get_store_categ_id(self, erp_id):
        mapping_obj = self.env['channel.category.mappings']
        domain = [('odoo_category_id', '=', erp_id)]
        check = self.channel_id._match_mapping(
            mapping_obj,
            domain,
            limit=1
        )

        if not check:
            vals = dict(
                channel_id=self.channel_id.id,
                operation='export',
                category_ids=[(6, 0, [erp_id])]
            )
            obj = self.env['export.prestashop.categories'].create(vals)
            obj.export_now()
            check = self.channel_id._match_mapping(
                mapping_obj,
                domain,
                limit=1
            )
        return check.store_category_id

    def export_template(self, prestashop, product_bs, erp_template_id):
        obj_template = self.env['product.template']
        channel_id = self.channel_id or self._context['channel_id']
        template_data = obj_template.browse(erp_template_id)
        cost = template_data.standard_price
        default_code = template_data.default_code or ''
        erp_category_id = template_data.categ_id.id
        presta_default_categ_id = self._get_store_categ_id(erp_category_id)
        if not presta_default_categ_id:
            raise UserError("This product category is not mapped in Prestashop")
        ps_extra_categ = []
        extra_categories = self.env['extra.categories'].search(
            [('instance_id', '=', channel_id.id), ('product_id', '=', erp_template_id)])
        extra_categories_set = set()
        if extra_categories:
            for extra_category in extra_categories:
                for categ in extra_category.extra_category_ids:
                    cat_id = self._get_store_categ_id(categ.id)
                    if cat_id not in extra_categories_set:
                        extra_categories_set.add(cat_id)
                        ps_extra_categ.append({'id': str(cat_id)})
        template_price = round(template_data.with_context(pricelist=channel_id.pricelist_name.id).price, 2)
        price_no_tax = self.deduct_price(template_price)
        product_bs['product'].update({
            'price': str(price_no_tax),
            'active': '1',
            'weight': str(template_data.weight),
            'redirect_type': '404',
            'minimal_quantity': '1',
            'available_for_order': '1',
            'show_price': '1',
            'depth': str(template_data.length),
            'width': str(template_data.width),
            'height': str(template_data.height),
            'state': '1',
            'ean13': template_data.barcode or '',
            'reference': default_code or '',
            'out_of_stock': '2',
            'condition': 'new',
            'id_category_default': str(presta_default_categ_id)
        })
        tax = self.env['channel.account.mappings'].search([('channel_id', '=', channel_id.id)])
        if tax[0].store_id:
            product_bs['product']['id_tax_rules_group'] = str(tax[0].store_id)
        if cost:
            product_bs['product']['wholesale_price'] = str(round(cost, 3))
        if type(product_bs['product']['name']['language']) == list:
            for i in range(len(product_bs['product']['name']['language'])):
                product_bs['product']['name']['language'][i]['value'] = template_data.name
                product_bs['product']['link_rewrite']['language'][i]['value'] = channel_id._get_link_rewrite(
                    '', template_data.name)
                if template_data.description_presta and template_data.description_sale_presta:
                    product_bs['product']['description']['language'][i]['value'] = template_data.description_presta
                    product_bs['product']['description_short']['language'][i][
                        'value'] = template_data.description_sale_presta
                else:
                    product_bs['product']['description']['language'][i]['value'] = template_data.description
                    product_bs['product']['description_short']['language'][i]['value'] = template_data.description_sale
        else:
            product_bs['product']['name']['language']['value'] = template_data.name
            product_bs['product']['link_rewrite']['language']['value'] = channel_id._get_link_rewrite(
                '', template_data.name)
            if template_data.description_presta and template_data.description_sale_presta:
                product_bs['product']['description']['language']['value'] = template_data.description_presta
                product_bs['product']['description_short']['language']['value'] = template_data.description_sale_presta
            else:
                product_bs['product']['description']['language']['value'] = template_data.description
                product_bs['product']['description_short']['language']['value'] = template_data.description_sale
        if 'category' in product_bs['product']['associations']['categories']:
            product_bs['product']['associations']['categories']['category']['id'] = str(
                presta_default_categ_id)
        if 'categories' in product_bs['product']['associations']['categories']:
            product_bs['product']['associations']['categories']['categories']['id'] = str(
                presta_default_categ_id)
        pop_attr = product_bs['product']['associations'].pop(
            'combinations', None)
        a1 = product_bs['product']['associations'].pop('images', None)
        a2 = product_bs['product'].pop('position_in_category', None)
        if ps_extra_categ:
            if 'category' in product_bs['product']['associations']['categories']:
                a3 = product_bs['product']['associations']['categories']['category'] = ps_extra_categ
            if 'categories' in product_bs['product']['associations']['categories']:
                a3 = product_bs['product']['associations']['categories']['categories'] = ps_extra_categ

        try:
            returnid = prestashop.add('products', product_bs)

        except Exception as e:
            return [0, ' Error in creating Product Template(ID: %s).%s' % (str(presta_default_categ_id), str(e))]
        if returnid:
            channel_id.create_template_mapping(
                template_data, returnid, {'default_code': default_code, 'barcode': '', 'operation': 'export'})
            return [int(returnid), '']
        return [0, 'Unknown Error']

    def create_combination(self, prestashop, add_comb, presta_main_product_id, erp_template_id, erp_product_id,
                           default_attr):
        channel_id = self.channel_id or self._context['channel_id']
        obj_pro = self.env['product.product'].browse(erp_product_id)
        qty = obj_pro._product_available()
        image_id = False
        quantity = qty[erp_product_id]['qty_available'] - \
                   qty[erp_product_id]['outgoing_qty']
        if type(quantity) == str:
            quantity = quantity.split('.')[0]
        if type(quantity) == float:
            quantity = quantity.as_integer_ratio()[0]
        image = obj_pro.image_1920
        if image:
            image_id = self.create_images(
                prestashop, image, presta_main_product_id)
        price_extra = round(float(obj_pro.with_context(pricelist=channel_id.pricelist_name.id).lst_price) - float(
            obj_pro.with_context(pricelist=channel_id.pricelist_name.id).list_price), 2)
        ean13 = obj_pro.barcode or ''
        default_code = obj_pro.default_code or ''
        weight = obj_pro.weight
        presta_dim_list = []
        # Here changed attribute_value_ids by product_template_attribute_value_ids. Add recursion in product_attribute_value_id
        for product_attr in obj_pro.product_template_attribute_value_ids:
            for value_id in product_attr.product_attribute_value_id:

                m_id = self.env['channel.attribute.value.mappings'].search(
                    [('odoo_attribute_value_id', '=', value_id.id)])
                if m_id:
                    presta_id = m_id[0].store_attribute_value_id
                    presta_dim_list.append({'id': str(presta_id)})
                else:
                    return [0, 'Please synchronize all Dimensions/Attributes first.']
        add_comb['combination']['associations']['product_option_values']['product_option_values'] = presta_dim_list
        add_comb['combination']['associations']['product_option_values'].pop('product_option_value')
        add_comb['combination'].update({
            'ean13': ean13,
            'weight': str(weight),
            'reference': default_code,
            'price': str(price_extra),
            'quantity': quantity,
            'default_on': default_attr,
            'id_product': str(presta_main_product_id),
            'minimal_quantity': '1',
        })
        try:
            returnid = prestashop.add('combinations', add_comb)
        except Exception as e:
            return [0, ' Error in creating Variant(ID: %s).%s' % (str(erp_product_id), str(e))]
        if returnid:
            temp_data = False
            data = {'combination': {
                'ean13': ean13,
                'reference': default_code,
                'associations': {'images': {'image': {'id': str(image_id)}}},
                'minimal_quantity': '1',
                'id_product': str(presta_main_product_id),
                'id': str(returnid),
                'quantity': quantity,
                'active': '1'}}
            try:
                prestashop.edit('combinations', returnid, data)
            except Exception as e:
                pass

            if default_attr:
                try:
                    temp_data = prestashop.get('products', presta_main_product_id)
                except Exception as e:
                    msg = ' Error in Updating default variant(ID: %s).%s' % (str(erp_product_id), str(e))
                    _logger.info('..Error: %r ////...', msg)
                if temp_data:
                    temp_data['product']['id_default_combination'] = returnid
                    a1 = temp_data['product'].pop('position_in_category', None)
                    a2 = temp_data['product'].pop('manufacturer_name', None)
                    a3 = temp_data['product'].pop('quantity', None)
                    a4 = temp_data['product'].pop('type', None)

                    # Fix product price
                    if not float(temp_data['product']['price']):
                        channel_id = self.channel_id or self._context['channel_id']
                        template_price = round(
                            erp_template_id.with_context(pricelist=channel_id.pricelist_name.id).price, 2
                        )
                        price_no_tax = self.deduct_price(template_price)
                        temp_data['product']['price'] = str(price_no_tax)

                    try:
                        prestashop.edit('products', presta_main_product_id, temp_data)
                    except Exception as e:
                        _logger.info("ERROR SETTING DEFAULT COMBINATION: %s" % e)
                        pass
            pid = int(returnid)
            temp = channel_id.create_product_mapping(
                erp_template_id, obj_pro, presta_main_product_id, pid,
                {'default_code': default_code, 'barcode': '', 'operation': 'export'})
            if float(quantity) > 0.0:
                get = self.update_quantity(
                    prestashop, presta_main_product_id, quantity, None, pid)
                return [pid, get[1]]
            return [pid, '']

    def create_normal_product(self, prestashop, erp_template_id, erp_product_id, prest_main_product_id):
        if self._context is None:
            self._context = {}
        channel_id = self.channel_id or self._context['channel_id']
        obj_product = self.env['product.product']
        product_data = obj_product.browse(erp_product_id)
        erp_category_id = product_data.categ_id.id
        default_code = product_data.default_code or ''
        presta_default_categ_id = self._get_store_categ_id(erp_category_id)
        if prestashop:
            add_data = prestashop.get('products', prest_main_product_id)
        if add_data:
            template_price = round(erp_template_id.with_context(pricelist=channel_id.pricelist_name.id).price, 2)
            price_no_tax = self.deduct_price(template_price)
            add_data['product'].update({
                'price': str(price_no_tax),
                'active': '1',
                'redirect_type': '404',
                'minimal_quantity': '1',
                'available_for_order': '1',
                'show_price': '1',
                'state': '1',
                'out_of_stock': '2',
                'default_on': '1',
                'condition': 'new',
                'reference': default_code,
                'id_category_default': presta_default_categ_id
            })
            a1 = add_data['product'].pop('position_in_category', None)
            a2 = add_data['product'].pop('manufacturer_name', None)
            a3 = add_data['product'].pop('quantity', None)
            a4 = add_data['product'].pop('type', None)
            try:
                returnid = prestashop.edit(
                    'products', prest_main_product_id, add_data)
            except Exception as e:
                return [0, ' Error in creating Product(ID: %s).%s' % (str(erp_product_id), str(e))]
            if returnid:
                temp = channel_id.create_product_mapping(
                    erp_template_id, product_data, prest_main_product_id, 'No Variants',
                    {'default_code': default_code, 'barcode': '', 'operation': 'export'})

            if product_data.image_1920:
                get = self.create_images(
                    # Here changed product_data.image by product_data.image_1920
                    prestashop, product_data.image_1920, prest_main_product_id)
            qty = product_data._product_available()
            quantity = qty[erp_product_id]['qty_available'] - qty[erp_product_id]['outgoing_qty']
            if type(quantity) == str:
                quantity = quantity.split('.')[0]
            if type(quantity) == float:
                quantity = quantity.as_integer_ratio()[0]
            if float(quantity) > 0.0:
                get = self.update_quantity(
                    prestashop, prest_main_product_id, quantity)
            return [prest_main_product_id, '']

    @api.model
    def create_images(self, prestashop, image_data, resource_id, image_name=None, resource='images/products'):
        if image_name == None:
            image_name = 'op' + str(resource_id) + '.png'
        try:
            returnid = prestashop.add(
                str(resource) + '/' + str(resource_id), image_data, image_name)
            return returnid
        except Exception as e:
            return False

    # def update_product_prestashop(self, prestashop):
    #     context = self.env.context.copy() or {}
    #     message = ''
    #     error_message = ''
    #     update = 0
    #     map = []
    #     prod_obj = self.env['product.product']
    #     if prestashop:
    #         need_update_id = self.env['channel.product.mappings'].search(
    #             [('need_sync', '=', 'yes')])
    #         if len(need_update_id) == 0:
    #             message = 'Nothing to Update. All product(s) are already updated to Prestashop.'
    #         else:
    #             context = self.get_context_from_config()
    #             context['ps_language_id'] = obj.ps_language_id
    #         if need_update_id:
    #             pp_obj = self.env['channel.product.mappings']
    #             for m in need_update_id:
    #                 attribute_id = m.store_variant_id
    #                 presta_id = m.store_product_id
    #                 erp_id = m.erp_product_id
    #                 if int(attribute_id) >= 0 and int(presta_id) not in [0, -1]:
    #                     response = self.with_context(context).export_update_products(
    #                         prestashop, erp_id, presta_id, attribute_id)
    #                     if response[0] == 0:
    #                         error_message += response[1]
    #                     else:
    #                         update += 1
    #             if len(error_message) == 0:
    #                 message = message + '\r\n' + \
    #                     '%s Products Successfully Updated to Prestashop .\r\n' % (
    #                         update)
    #             else:
    #                 message = message + '\r\n' + \
    #                     'Error in Updating product(s): %s.\r\n' % (
    #                         error_message)
    #         return {'update_ids': update,
    #                 'message': message}

    # def export_update_products(self, prestashop, erp_id, presta_id, attribute_id):
    #     context = self.env.context.copy() or {}
    #     ps_option_ids = []
    #     obj_pro = self.env['product.product'].browse(erp_id)
    #     if obj_pro:
    #         if not obj_pro.name:
    #             name = ''
    #         else:
    #             name = pob_decode(obj_pro.name)
    #         if obj_pro.list_price:
    #             price = str(obj_pro.list_price)
    #         else:
    #             price = '0.00'
    #         categ_id = obj_pro.categ_id.id
    #         p_categ_id = self.env['export.prestashop.categories'].with_context(
    #             {'err_msg': ''}).sync_categories(prestashop, categ_id, 1)[0]
    #         if obj_pro.description:
    #             description = pob_decode(obj_pro.description)
    #         else:
    #             description = ''
    #         if obj_pro.description_sale:
    #             description_sale = pob_decode(obj_pro.description_sale)
    #         else:
    #             description_sale = ''
    #         qty = obj_pro._product_available()
    #         quantity = qty[erp_id]['qty_available'] - \
    #             qty[erp_id]['outgoing_qty']
    #         image = obj_pro.image
    #         ean13 = obj_pro.barcode or ''
    #         default_code = obj_pro.default_code or ''
    #         context = self.env.context.copy()
    #         context['weight'] = obj_pro.weight
    #         if obj_pro.attribute_value_ids:
    #             for value_id in obj_pro.attribute_value_ids:
    #                 m_id = self.env['channel.attribute.value.mappings'].search(
    #                     [('odoo_attribute_value_id', '=', value_id.id)])
    #                 if m_id:
    #                     presta_value_id = m_id[0].presta_id
    #                     ps_option_ids.append({'id': str(presta_value_id)})
    #                 else:
    #                     return [0, 'Please synchronize all Dimensions first.']
    #         context['ps_option_ids'] = ps_option_ids
    #         response = self.with_context(context).update_products(prestashop, erp_id, presta_id, attribute_id, name, price, quantity, p_categ_id, 'new', description,
    #                                                               description_sale, image, default_code, ean13)
    #         return response

    # def update_products(self, prestashop, erp_id, presta_id, attribute_id, name, price, quantity, id_category_default='2', condition='new', description='None', description_short='None', image_data=False, default_code='', ean13=''):
    #     # message='Error in Updating Product with ERP-ID '+str(erp_id)
    #     context = self.env.context.copy()
    #     message = ''
    #     if int(presta_id) in [0, -1, -2, -3]:
    #         map_id = self.env['channel.product.mappings'].search(
    #             [('product_name', '=', erp_id), ('channel_id', '=', self.channel_id.id)])
    #         map_id.need_sync = 'no'
    #         # self._cr.execute(
    #         #     "UPDATE prestashop_product SET need_sync='no' WHERE erp_product_id=%s" % erp_id)
    #         # self._cr.commit()
    #     else:
    #         try:
    #             product_data = prestashop.get('products', presta_id)
    #         except Exception as e:
    #             return [0, ' Error in Updating Product,can`t get product data %s' % str(e)]
    #         if product_data:
    #             if int(attribute_id) == 0:
    #                 product_data['product'].update({
    #                     'price': price,
    #                     'reference': default_code,
    #                     'ean13': ean13
    #                 })
    #                 if self._context.has_key('weight'):
    #                     product_data['product']['weight'] = str(
    #                         self._context['weight'])
    #                 if type(product_data['product']['name']['language']) == list:
    #                     for i in range(len(product_data['product']['name']['language'])):
    #                         presta_lang_id = product_data['product']['name']['language'][i]['attrs']['id']
    #                         if presta_lang_id == str(self._context['ps_language_id']):
    #                             product_data['product']['name']['language'][i]['value'] = name
    #                             product_data['product']['link_rewrite']['language'][i]['value'] = self.channel_id._get_link_rewrite(
    #                                 zip, name)
    #                             product_data['product']['description']['language'][i]['value'] = description
    #                             product_data['product']['description_short']['language'][i]['value'] = description_short
    #                 else:
    #                     product_data['product']['name']['language']['value'] = name
    #                     product_data['product']['link_rewrite']['language']['value'] = self.channel_id._get_link_rewrite(
    #                         zip, name)
    #                     product_data['product']['description']['language']['value'] = description
    #                     product_data['product']['description_short']['language']['value'] = description_short
    #                 a1 = product_data['product'].pop(
    #                     'position_in_category', None)
    #                 a2 = product_data['product'].pop('manufacturer_name', None)
    #                 a3 = product_data['product'].pop('quantity', None)
    #                 a4 = product_data['product'].pop('type', None)
    #                 a4 = product_data['product'].pop('combinations', None)
    #                 try:
    #                     returnid = prestashop.edit(
    #                         'products', presta_id, product_data)
    #                 except Exception as e:
    #                     return [0, ' Error in updating Product(s) %s' % str(e)]
    #                 if not product_data['product']['associations']['images'].has_key('image'):
    #                     if image_data:
    #                         get = self.create_images(
    #                             prestashop, image_data, presta_id)
    #                 up = True
    #             else:
    #                 resp = self.update_products_with_attributes(
    #                     prestashop, erp_id, presta_id, attribute_id, price, default_code, ean13)
    #                 returnid = resp[0]
    #                 up = False
    #                 message = message + resp[1]
    #             if returnid:
    #                 if up:
    #                     if not self._context.has_key('template'):
    #                         map_id = self.env['channel.product.mappings'].search(
    #                             [('product_name', '=', erp_id), ('channel_id', '=', self.channel_id.id)])
    #                         map_id.need_sync = 'no'
    #                         # self._cr.execute(
    #                         #     "UPDATE prestashop_product SET need_sync='no' WHERE odoo_product_id=%s" % (erp_id))
    #                         # self._cr.commit()
    #                 if type(product_data['product']['associations']['stock_availables']['stock_available']) == list:
    #                     for data in product_data['product']['associations']['stock_availables']['stock_available']:
    #                         if int(data['id_product_attribute']) == int(attribute_id):
    #                             stock_id = data['id']
    #                 else:
    #                     stock_id = product_data['product']['associations']['stock_availables']['stock_available']['id']
    #                 if float(quantity) > 0.0:
    #                     return self.update_quantity(prestashop, presta_id, quantity, stock_id, attribute_id)
    #                 else:
    #                     return [1, '']
    #             else:
    #                 return [0, message]

    # def update_products_with_attributes(self, prestashop, erp_id, presta_id, attribute_id, new_price, reference=None, ean13=None):
    #     context = self.env.context.copy()
    #     flag = True
    #     message = ''
    #     if self._context.has_key('ps_option_ids'):
    #         ps_option_ids = self._context['ps_option_ids']
    #     try:
    #         attribute_data = prestashop.get('combinations', attribute_id)
    #     except Exception as e:
    #         message = ' Error in Updating Product Attribute,can`t get product attribute data %s' % str(
    #             e)
    #         flag = False
    #     map_id = self.env['channel.product.mappings'].search(
    #         [('erp_product_id', '=', int(erp_id))])
    #     if flag and attribute_data and map_id:
    #         obj_pro = self.env['product.product'].browse(erp_id)
    #         impact_on_price = float(obj_pro.lst_price) - \
    #             float(obj_pro.list_price)
    #         attribute_data['combination']['price'] = str(impact_on_price)
    #         qq = attribute_data['combination']['associations'].pop('images')
    #         if ps_option_ids:
    #             if attribute_data['combination']['associations']['product_option_values'].has_key('value'):
    #                 a1 = attribute_data['combination']['associations']['product_option_values'].pop(
    #                     'value')
    #             if attribute_data['combination']['associations']['product_option_values'].has_key('product_option_value'):
    #                 a2 = attribute_data['combination']['associations']['product_option_values'].pop(
    #                     'product_option_value')
    #             a3 = attribute_data['combination']['associations']['product_option_values']['product_option_value'] = [
    #             ]
    #             for j in ps_option_ids:
    #                 attribute_data['combination']['associations']['product_option_values']['product_option_value'].append(
    #                     j)
    #         if reference:
    #             attribute_data['combination']['reference'] = reference
    #         if ean13:
    #             attribute_data['combination']['ean13'] = ean13
    #         if self._context.has_key('weight'):
    #             attribute_data['combination']['weight'] = str(
    #                 self._context['weight'])
    #         try:
    #             returnid = prestashop.edit(
    #                 'combinations', attribute_id, attribute_data)
    #         except Exception as e:
    #             message = ' Error in updating Product(s) %s' % str(e)
    #             flag = False
    #         if flag:
    #             map_id = self.env['channel.product.mappings'].search(
    #                 [('product_name', '=', erp_id), ('channel_id', '=', self.channel_id.id)])
    #             map_id.need_sync = 'no'
    #             # self._cr.execute(
    #             #     "UPDATE prestashop_product SET need_sync='no' WHERE erp_product_id=%s" % (erp_id))
    #             # self._cr.commit()
    #     return [flag, message]

    def update_quantity(self, prestashop, pid, quantity, stock_id=None, attribute_id=None):
        if attribute_id is not None:
            try:
                stock_search = prestashop.get('stock_availables',
                                              options={'filter[id_product]': pid,
                                                       'filter[id_product_attribute]': attribute_id})
            except Exception as e:
                return [0, ' Unable to search given stock id', check_mapping[0]]
            if type(stock_search['stock_availables']) == dict:
                stock_id = stock_search['stock_availables']['stock_available']['attrs']['id']
                try:
                    stock_data = prestashop.get('stock_availables', stock_id)
                except Exception as e:
                    return [0, ' Error in Updating Quantity,can`t get stock_available data.']
                if type(quantity) == str:
                    quantity = quantity.split('.')[0]
                if type(quantity) == float:
                    quantity = int(quantity)
                stock_data['stock_available']['quantity'] = int(quantity)
                try:
                    up = prestashop.edit(
                        'stock_availables', stock_id, stock_data)
                except Exception as e:
                    pass
                return [1, '']
            else:
                return [0,
                        ' No stock`s entry found in prestashop for given combination (Product id:%s ; Attribute id:%s)' % str(
                            pid) % str(attribute_id)]
        if stock_id is None and attribute_id is None:
            try:
                product_data = prestashop.get('products', pid)
            except Exception as e:
                return [0, ' Error in Updating Quantity,can`t get product data.']
            stock_id = product_data['product']['associations']['stock_availables']['stock_available']['id']
        if stock_id:
            try:
                stock_data = prestashop.get('stock_availables', stock_id)
            except Exception as e:
                return [0, ' Error in Updating Quantity,can`t get stock_available data.']
            except Exception as e:
                return [0, ' Error in Updating Quantity,%s' % str(e)]
            if type(quantity) == str:
                quantity = quantity.split('.')[0]
            if type(quantity) == float:
                quantity = quantity.as_integer_ratio()[0]
            stock_data['stock_available']['quantity'] = quantity
            try:
                up = prestashop.edit('stock_availables', stock_id, stock_data)
            except Exception as e:
                return [0, ' Error in Updating Quantity,Unknown Error.']
            except Exception as e:
                return [0, ' Error in Updating Quantity,Unknown Error.%s' % str(e)]
            return [1, '']
        else:
            return [0, ' Error in Updating Quantity,Unknown stock_id.']

    @api.model
    def update_template(self, prestashop, erp_id, presta_id, name, description, description_sale):
        context = self.env.context.copy()
        message = ''
        template_data = self.update_template_category(
            prestashop, erp_id, presta_id)
        if isinstance(template_data, dict):
            if 'price' in context:
                template_data['product']['price'] = str(context['price'])
            if 'cost' in context:
                template_data['product']['wholesale_price'] = str(
                    context['cost'])
            if 'weight' in context:
                template_data['product']['weight'] = str(context['weight'])
            if 'temp_obj' in context:
                template_data['product']['depth'] = str(context['temp_obj'].length)
                template_data['product']['width'] = str(context['temp_obj'].width)
                template_data['product']['height'] = str(context['temp_obj'].height)
                if context['temp_obj'].image_1920:
                    image_id = self.create_images(prestashop, context['temp_obj'].image_1920, presta_id)
                # template_data['product']['ean'] = str(context['temp_obj'].barcode)

            if 'reference' in context:
                template_data['product']['reference'] = str(
                    context['reference'])

            if type(template_data['product']['name']['language']) == list:
                for i in range(len(template_data['product']['name']['language'])):
                    template_data['product']['name']['language'][i]['value'] = name
                    template_data['product']['description']['language'][i]['value'] = description
                    template_data['product']['description_short']['language'][i]['value'] = description_sale
            else:
                template_data['product']['name']['language']['value'] = name
                template_data['product']['description']['language']['value'] = description
                template_data['product']['description_short']['language']['value'] = description_sale
                # template_data['product']['associations']['categories']['category']['id']=str(presta_default_categ_id)
            a1 = template_data['product'].pop('position_in_category', None)
            a2 = template_data['product'].pop('manufacturer_name', None)
            a3 = template_data['product'].pop('quantity', None)
            a4 = template_data['product'].pop('type', None)
            try:
                returnid = prestashop.edit(
                    'products', presta_id, template_data)
            except Exception as e:
                return [0, ' Error in updating Template(s) %s' % str(e)]
            if returnid:
                map_id = self.env['channel.template.mappings'].search(
                    [('odoo_template_id', '=', erp_id), ('channel_id', '=', self.channel_id.id)], limit=1)
                map_id.with_context({'search_default_filter_by_channel_id': self.channel_id.id}).write(
                    {'need_sync': 'no'})
                return [1, 'Template Successfully Updated']

            else:
                return [0, str(e)]
        else:
            return template_data

    @api.model
    def update_template_category(self, prestashop, erp_id, presta_id):
        message = ''
        count = 0
        cat_id = []
        cat_obj = self.env['channel.category.mappings']
        template_obj = self.env['product.template'].browse(erp_id)
        try:
            template_data = prestashop.get('products', presta_id)
        except Exception as e:
            return [0, ' Error in Updating Product,can`t get product data %s' % str(e)]
        search_cat = cat_obj.search(
            [('odoo_category_id', '=', template_obj.categ_id.id)], limit=1)
        if search_cat:
            default_category = search_cat[0].store_category_id
        else:
            resp = self.env['export.prestashop.categories'].with_context(
                {'err_msg': '', 'mapping_ids': [], 'create_ids': [], 'channel_id': self.channel_id}).sync_categories(
                prestashop, template_obj.categ_id, active='1')
            default_category = resp[0]
        template_data['product'].update(
            {'id_category_default': default_category})

        ps_extra_categ = []
        # template_obj = self.env['product.template'].browse(erp_id)
        extra_categ = self.env['extra.categories'].search(
            [('instance_id', '=', self.channel_id.id), ('product_id', '=', erp_id)])
        if extra_categ:
            for categ in extra_categ.extra_category_ids:
                cat_id = self.env['export.prestashop.categories'].with_context(
                    {'err_msg': '', 'mapping_ids': [], 'create_ids': [],
                     'channel_id': self.channel_id}).sync_categories(
                    prestashop, categ, 1)[0]
                ps_extra_categ.append({'id': str(cat_id)})
        if ps_extra_categ:
            a2 = template_data['product']['associations']['categories']['categories'] = ps_extra_categ
            if 'categories' in template_data['product']['associations']['categories']:
                a2 = template_data['product']['associations']['categories']['categories'] = ps_extra_categ
            if 'category' in template_data['product']['associations']['categories']:
                a2 = template_data['product']['associations']['categories']['category'] = ps_extra_categ
        return template_data
