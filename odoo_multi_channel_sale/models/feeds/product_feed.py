# -*- coding:utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL :<https://store.webkul.com/license.html/>
##############################################################################
from odoo import api, fields, models
from odoo.addons.odoo_multi_channel_sale.tools import parse_float, extract_list as EL

from collections import Counter
from logging import getLogger

_logger = getLogger(__name__)


class ProductBundle(models.Model):
    _name = 'product.bundle'

    name = fields.Char("Name")
    id_product = fields.Integer("Id Product")
    quantity = fields.Integer("Quantity")

    bundle_templ_id = fields.Many2one('product.feed', 'Bundle ID', ondelete='cascade')


class ProductFeed(models.Model):
    _name = 'product.feed'
    _inherit = 'product.variant.feed'
    _description = 'Product Feed'

    need_sync = fields.Selection(
        selection=[('yes', 'Yes'), ('no', 'No')],
        string='Update Required',
        default='no',
        required=True
    )

    feed_variants = fields.One2many(
        string='Variants',
        comodel_name='product.variant.feed',
        inverse_name='feed_templ_id'
    )
    product_bundle = fields.One2many(
        string='Products Bundle',
        comodel_name='product.bundle',
        inverse_name='bundle_templ_id',
        ondelete='cascade'
    )

    description_presta = fields.Html(string='description presta')
    description_sale_presta = fields.Html(string='description corta presta')
    taxes_id = fields.Integer(string='taxes')

    is_pack = fields.Boolean("Is Kit")

    def match_attribute(self, attribute):
        return self.env['product.attribute'].search([('name', '=', attribute)]) \
               or self.env['product.attribute'].create({'name': attribute})

    def match_attribute_value(self, value, attribute_id):
        value = value.strip("'").strip("'")
        return self.env['product.attribute.value'].search(
            [
                ('name', '=', str(value)),
                ('attribute_id', '=', attribute_id)
            ]
        ) or self.env['product.attribute.value'].create(
            {
                'name': value,
                'attribute_id': attribute_id
            }
        )

    @api.model
    def create_attribute_string(self, name_values):
        attstring = ''
        message = ''
        try:
            for name_value in eval(name_values):
                attstring += name_value['value'] + ","
        except Exception as e:
            _logger.error('-----Exception--------------%r', e)
            message += '<br/>%s' % (e)
        attstring = attstring.rstrip(',')
        return dict(
            attstring=attstring,
            message=message
        )

    def update_product_variants(self, variant_ids, template_id, store_id, location_id, channel_id):
        _logger.info("::::update : %r ::::::::::::", 'update')
        prod_env = self.env['product.product']
        message = ''
        context = dict(self._context or {})
        context.update({'channel_id': channel_id.id})
        context.update({'channel': channel_id.channel})

        variant_objs = self.env['product.variant.feed'].browse(variant_ids)
        for variant in variant_objs:
            attr_string_res = self.create_attribute_string(variant.name_value)
            attr_string = attr_string_res.get('attstring')
            message += attr_string_res.get('message')
            if variant.store_id:
                variant_store_id = variant.store_id
            else:
                variant_store_id = attr_string
            exists = channel_id.match_product_mappings(
                store_id, variant_store_id, default_code=variant.default_code, barcode=variant.barcode)
            if not exists:
                self.with_context(context)._create_product_line(
                    variant, template_id, store_id, location_id, channel_id)
            else:
                attribute_value_ids = prod_env.with_context(context).check_for_new_attrs(
                    template_id, variant)
                if variant.list_price:
                    exists.product_name.wk_extra_price = parse_float(
                        variant.list_price) - parse_float(template_id.list_price)

                    price = parse_float(variant.list_price)  # - template_id.list_price
                    self.wk_change_product_price(
                        product_id=exists.product_name,
                        price=price,
                        channel_id=channel_id
                    )
                if context.get('wk_qty_update', True) and variant.qty_available and eval(variant.qty_available) > 0:
                    res = self.wk_change_product_qty(
                        exists.product_name, variant.qty_available, location_id)
        return message

    def get_variant_extra_values(self, template_id, variant, channel_id):
        vals = {}
        state = 'done'
        if variant.image:
            vals.update({'image_1920': variant.image})
        else:
            image_url = variant.image_url
            if image_url and (image_url not in ['false', 'False', False]):
                image_res = channel_id.read_website_image_url(image_url)
                if image_res: vals['image_1920'] = image_res
        if variant.description_sale:
            vals['description_sale'] = variant.description_sale
        weight_unit = variant.weight_unit
        if weight_unit:
            uom_id = channel_id.get_uom_id(name=weight_unit).id
            if uom_id:
                vals['uom_id'] = uom_id
                vals['uom_po_id'] = uom_id

        dimensions_unit = variant.dimensions_unit
        if dimensions_unit:
            vals['dimensions_uom_id'] = channel_id.get_uom_id(
                name=dimensions_unit).id
        if not variant.wk_product_id_type:
            vals['wk_product_id_type'] = 'wk_upc'
        else:
            vals['wk_product_id_type'] = variant.wk_product_id_type
        if variant.description_sale:
            vals['description_sale'] = variant.description_sale
        if variant.description:
            vals['description'] = variant.description
        if variant.list_price and template_id:
            vals['wk_extra_price'] = parse_float(variant.list_price) - parse_float(template_id.list_price)
        if variant.default_code:
            vals['default_code'] = variant.default_code
        if variant.default_code:
            vals['barcode'] = variant.barcode
        return {'vals': vals, 'state': state}

    def _create_product_line(self, variant, template_id, store_id, location_id, channel_id):
        _logger.info("::::update11 : %r ::::::::::::", 'update')
        context = dict(self._context or {})
        prod_env = self.env['product.product']
        context.update({'channel_id': channel_id.id})
        context.update({'channel': channel_id.channel})

        message = ''
        variant_id = variant.store_id or 'No Variants'
        exists = channel_id.match_product_mappings(
            store_id, variant_id, default_code=variant.default_code, barcode=variant.barcode)
        # t=self.taxes_id
        if self.taxes_id:
            tx = self.env['channel.account.mappings'].search([('id', '=', self.taxes_id)])
            t = tx.odoo_tax_id
            tax = self.env['account.tax'].search([('id', '=', t)])
        else:
            tax = None
        if not exists:
            vals = {
                'name': template_id.name,
                'description': template_id.description,
                'description_sale': template_id.description_sale,
                'description_presta': template_id.description_presta,
                'description_sale_presta': template_id.description_sale_presta,
                'type': template_id.type,
                'categ_id': template_id.categ_id.id,
                'uom_id': template_id.uom_id.id,
                'uom_po_id': template_id.uom_po_id.id,
                'product_tmpl_id': template_id.id,
                'default_code': variant.default_code,
                'taxes_id': tax
            }
            if variant.barcode: vals['barcode'] = variant.barcode

            product_template_attribute_value_ids = prod_env.with_context(context).check_for_new_attrs(
                template_id, variant)
            _logger.info("::::product_template_attribute_value_ids : %r ::::::::::::",
                         product_template_attribute_value_ids)
            vals.update({'product_template_attribute_value_ids': product_template_attribute_value_ids})
            res = self.get_variant_extra_values(template_id, variant, channel_id)
            state = res['state']
            vals.update(res['vals'])
            product_exists_odoo = channel_id.match_odoo_product(vals)
            if not product_exists_odoo:
                product_id = prod_env.with_context(context).create(vals)
                vals.pop('message_follower_ids', '')
                status = True
                if variant.list_price and eval(variant.list_price):
                    price = parse_float(variant.list_price)  # - template_id.list_price
                    self.wk_change_product_price(
                        product_id=product_id,
                        price=price,
                        channel_id=channel_id
                    )
                if variant.qty_available and eval(variant.qty_available) > 0:
                    self.wk_change_product_qty(
                        product_id, variant.qty_available, location_id)
                # FIX EXTRA FIELDS
                mapping_id = self.channel_id.create_product_mapping(
                    template_id, product_id, store_id, variant_id,
                    vals=dict(default_code=vals.get('default_code'), barcode=vals.get('barcode'))
                )
            else:
                # product_exists_odoo.write(vals)
                product_id = product_exists_odoo
                mapping_id = channel_id.create_product_mapping(
                    product_id.product_tmpl_id, product_id, store_id, variant_id,
                    vals=dict(default_code=variant.default_code, barcode=variant.barcode)
                )
        else:
            mapping_id = exists
        return message

    def _create_product_lines(self, variant_ids, template_id, store_id, location_id, channel_id):
        message = ''
        for variant_id in self.env['product.variant.feed'].browse(variant_ids):
            message += self._create_product_line(
                variant_id, template_id, store_id, location_id, channel_id)
        return message

    @api.model
    def wk_change_product_price(self, product_id, price, channel_id):

        pricelist_item = channel_id.pricelist_name.item_ids.filtered(
            lambda pitem: pitem.product_id.id == product_id.id
                          and pitem.applied_on == '0_product_variant'
        )
        if pricelist_item:
            pricelist_item = pricelist_item[0]
            pricelist_item.write(dict(fixed_price=price))
        else:
            pricelist_item = self.env['product.pricelist.item'].create({
                'pricelist_id': channel_id.pricelist_name.id,
                'applied_on': '0_product_variant',
                'product_id': product_id.id,
                'fixed_price': (price),
            })

    @api.model
    def wk_change_product_qty(self, product_id, qty_available, location_id):
        if qty_available and product_id.type == 'product':
            self.env['stock.quant'].with_context(inventory_mode=True).create(
                {
                    'product_id': product_id.id,
                    'location_id': location_id.id,
                    'inventory_quantity': qty_available,
                }
            )

    def check_attribute_value(self, variant_ids):
        state, message = 'done', ''

        for variant in variant_ids:
            name_values = eval(variant.name_value)
            cnt = Counter()
            for name_value in name_values:
                cnt[name_value.get('name')] += 1
            multi_occur = filter(lambda i: i[1] != 1, cnt.items())
            for multi_oc in multi_occur:
                state = 'error'
                items = map(lambda item: '%s(%s times)' % (item[0], item[1]), multi_occur)
                message += 'Attributes  are duplicate \n %r' % (','.join(items))
                return dict(message=message, state=state)
        return dict(message=message, state=state)

    def import_product(self, channel_id):
        self.ensure_one()
        message = ""
        create_id = None
        update_id = None
        context = dict(self._context)
        context.update({
            'pricelist': channel_id.pricelist_name.id,
            'lang': channel_id.language_id.code,
        })
        vals = EL(self.read(self.get_product_fields()))
        store_id = vals.pop('store_id')

        state = 'done'
        if not vals.get('name'):
            message += "<br/>Product without name can't evaluated"
            state = 'error'
        if not store_id:
            message += "<br/>Product without store ID can't evaluated"
            state = 'error'
        categ_id = channel_id.default_category_id.id
        if categ_id:
            vals['categ_id'] = categ_id
        weight_unit = vals.pop('weight_unit')
        if weight_unit:
            uom_id = channel_id.get_uom_id(name=weight_unit).id
            if uom_id:
                vals['uom_id'] = uom_id
                vals['uom_po_id'] = uom_id

        dimensions_unit = vals.pop('dimensions_unit')
        if dimensions_unit:
            vals['dimensions_uom_id'] = channel_id.get_uom_id(
                name=dimensions_unit).id
        if not vals.pop('wk_product_id_type'):
            vals['wk_product_id_type'] = 'wk_upc'
        variant_lines = vals.pop('feed_variants')
        feed_variants = self.feed_variants
        if variant_lines:
            check_attr = self.check_attribute_value(feed_variants)
            state = check_attr.get('state')
            message += check_attr.get('message')

        list_price = vals.get('list_price')
        list_price = list_price and parse_float(list_price) or 0
        image_url = vals.pop('image_url')
        location_id = channel_id.location_id
        b64_image = vals.pop('image')

        if b64_image:
            vals['image_1920'] = b64_image
        if not b64_image and image_url and (image_url not in ['false', 'False', False]):
            image_res = channel_id.read_website_image_url(image_url)
            if image_res: vals['image_1920'] = image_res
        match = channel_id.match_template_mappings(store_id, **vals)
        template_exists_odoo = channel_id.match_odoo_template(
            vals, variant_lines=feed_variants)
        vals.pop('website_message_ids', '')
        vals.pop('message_follower_ids', '')

        if state == 'done':
            if match:
                # t=self.taxes_id
                if self.taxes_id:
                    tx = self.env['channel.account.mappings'].search([('id', '=', self.taxes_id)])
                    t = tx.odoo_tax_id
                    tax = self.env['account.tax'].search([('id', '=', t)])
                else:
                    tax = None
                vals['taxes_id'] = tax

                extra_categ_ids = vals.pop('extra_categ_ids')
                if not template_exists_odoo:
                    template_id = match.template_name
                    template_id.with_context(context).write(vals)

                else:

                    template_exists_odoo.with_context(context).write(vals)
                    template_id = template_exists_odoo

                match.write({'default_code': vals.get('default_code'), 'barcode': vals.get('barcode')})
                extra_categ = self.env['extra.categories'].search(
                    [('instance_id', '=', channel_id.id), ('product_id', '=', template_id.id)])
                if extra_categ_ids:
                    res = self.get_extra_categ_ids(extra_categ_ids, channel_id)
                    message += res.get('message', '')
                    categ_ids = res.get('categ_ids')
                    if categ_ids:
                        # code for instance wise category ids
                        data = {
                            'extra_category_ids': [(6, 0, categ_ids)],
                            'instance_id': channel_id.id,
                            'category_id': categ_id,
                        }
                        extra_categ = extra_categ.with_context(context).write(data)
                    else:
                        state = 'error'
                if len(variant_lines):
                    context['wk_qty_update'] = False
                    res = self.with_context(context).update_product_variants(
                        variant_lines, template_id, store_id, location_id, channel_id)
                    if res:
                        message += res
                        state = 'error'
                else:
                    for variant_id in template_id.product_variant_ids:
                        variant_vals = variant_id.read(['default_code', 'barcode'])[0]
                        self.wk_change_product_price(
                            product_id=variant_id,
                            price=list_price,
                            channel_id=channel_id
                        )
                        # if qty_available and eval(qty_available) > 0:
                        #     self.wk_change_product_qty(
                        #         variant_id,qty_available,location_id)
                        match_product = channel_id.match_product_mappings(
                            store_id, 'No Variants', default_code=variant_vals.get('default_code'),
                            barcode=variant_vals.get('barcode'))
                        if not match_product:
                            channel_id.create_product_mapping(
                                template_id, variant_id, store_id, 'No Variants',
                                {'default_code': variant_vals.get('default_code'),
                                 'barcode': variant_vals.get('barcode')})
                update_id = match

            else:
                template_id = None
                try:
                    if self.taxes_id:
                        tx = self.env['channel.account.mappings'].search([('id', '=', self.taxes_id)])
                        t = tx.odoo_tax_id
                        tax = self.env['account.tax'].search([('id', '=', t)])

                    else:
                        tax = None

                    vals['taxes_id'] = tax
                    vals['supplier_taxes_id'] = None
                    if not template_exists_odoo:
                        if variant_lines:
                            context['create_product_product'] = 1
                            vals.pop('barcode')
                        extra_categ_ids = vals.pop('extra_categ_ids')
                        if extra_categ_ids:
                            res = self.get_extra_categ_ids(extra_categ_ids, channel_id)
                            message += res.get('message', '')
                            categ_ids = res.get('categ_ids')
                            if categ_ids:
                                # code for instance wise category ids
                                data = {
                                    'extra_category_ids': [(6, 0, categ_ids)],
                                    'instance_id': channel_id.id,
                                    'category_id': categ_id,
                                }
                                extra_categ = self.env['extra.categories'].with_context(context).create(data)
                                vals['channel_category_ids'] = [(6, 0, [extra_categ.id])]
                                template_id = self.env['product.template'].with_context(context).create(vals)
                            else:
                                state = 'error'
                        else:
                            template_id = self.env['product.template'].with_context(context).create(vals)
                    else:
                        # template_exists_odoo.with_context(context).write(vals)
                        template_id = template_exists_odoo
                        extra_categ_ids = vals.pop('extra_categ_ids')
                        if extra_categ_ids:
                            res = self.get_extra_categ_ids(extra_categ_ids, channel_id)
                            message += res.get('message', '')
                            categ_ids = res.get('categ_ids')
                            if categ_ids:
                                # code for instance wise category ids
                                data = {
                                    'extra_category_ids': [(6, 0, categ_ids)],
                                    'instance_id': channel_id.id,
                                    'category_id': categ_id,
                                }
                                template_id.channel_category_ids = [(0, 0, data)]
                            else:
                                state = 'error'
                                template_id = None

                    if len(variant_lines) and template_id:
                        res = self._create_product_lines(
                            variant_lines, template_id, store_id, location_id, channel_id)
                        if res:
                            res += message
                            state = 'error'

                    elif template_id:
                        for variant_id in template_id.product_variant_ids:
                            variant_vals = variant_id.read(['default_code', 'barcode'])[0]
                            self.wk_change_product_price(
                                product_id=variant_id,
                                price=list_price,
                                channel_id=channel_id
                            )

                            match = channel_id.match_product_mappings(
                                store_id, 'No Variants', default_code=variant_vals.get('default_code'),
                                barcode=variant_vals.get('barcode'))
                            if not match:
                                channel_id.create_product_mapping(
                                    template_id, variant_id, store_id, 'No Variants',
                                    {'default_code': variant_vals.get('default_code'),
                                     'barcode': variant_vals.get('barcode')})
                except Exception as e:
                    state = 'error'
                    _logger.error('----------Exception------------%r', e)
                    message += '<br/>Error in variants %s' % (e)
                    state = 'error'
                if state == 'done':
                    template_id = template_id and template_id or template_exists_odoo
                    if template_id:
                        create_id = channel_id.create_template_mapping(
                            template_id, store_id,
                            {'default_code': vals.get('default_code'), 'barcode': vals.get('barcode')})

            if state == 'done':
                message += '<br/> Product %s Successfully Evaluate' % (
                    vals.get('name', ''))
        try:
            self.set_feed_state(state=state)
            self.message = "%s <br/> %s" % (self.message, message)
        except Exception as e:

            _logger.error('----------Exception------------%r', e)

        return dict(
            update_id=update_id,
            create_id=create_id,
            message=message
        )

    def import_items(self):
        update_ids = []
        create_ids = []

        message = ''

        for record in self:
            sync_vals = dict(
                status='error',
                action_on='template',
                action_type='import',
            )
            channel_id = record.channel_id
            res = record.import_product(channel_id)
            msz = res.get('message', '')
            message += msz
            update_id = res.get('update_id')
            if update_id:
                update_ids.append(update_id)
            create_id = res.get('create_id')
            if create_id:
                create_ids.append(create_id)
            mapping_id = update_id or create_id
            if mapping_id:
                mapping_vals = mapping_id.read(['store_product_id', 'odoo_template_id'])[0]
                sync_vals['status'] = 'success'
                sync_vals['ecomstore_refrence'] = mapping_vals.get('store_product_id')
                sync_vals['odoo_id'] = mapping_vals.get('odoo_template_id')
            sync_vals['summary'] = msz
            record.channel_id._create_sync(sync_vals)
        if self._context.get('get_mapping_ids'):
            return dict(
                update_ids=update_ids,
                create_ids=create_ids,
            )
        message = self.get_feed_result(feed_type='Product')
        return self.env['multi.channel.sale'].display_message(message)

    @api.model
    def cron_import_product(self):
        for record in self.search([('state', '!=', 'done')]):
            record.import_product(record.channel_id)
        return True
