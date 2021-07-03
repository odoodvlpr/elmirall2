# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "Multi Channel Prestashop Odoo Bridge(POB)",
  "summary"              :  "The module facilitates Prestashop integration with Odoo. The user can configure Prestashop with Odoo and manage Prestashop orders, customers, products, etc in Odoo.",
  "category"             :  "Website",
  "version"              :  "1.5.1",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com/Multi-Channel-Prestashop-Odoo-Bridge.html",
  "description"          :  """Multi Channel Prestashop Odoo Bridge
Multi-Channel Prestashop Odoo Bridge
Prestashop Odoo Bridge
Odoo Prestashop
Prestashop Odoo Connector
Odoo Prestashop connector
Prestashop to odoo
Odoo to Prestashop
Prestashop connector
Prestashop bridge
Prestashop marketplace
Manage orders
Manage products
Import products
Import customers 
Import orders
Ebay to Odoo
Odoo multi-channel bridge
Multi channel connector
Multi platform connector
Multiple platforms bridge
Connect Amazon with odoo
Amazon bridge
Flipkart Bridge
Magento Odoo Bridge
Odoo magento bridge
Woocommerce odoo bridge
Odoo woocommerce bridge
Ebay odoo bridge
Odoo ebay bridge
Multi channel bridge
Prestashop odoo bridge
Odoo prestahop
Akeneo bridge
Marketplace bridge
Multi marketplace connector
Multiple marketplace platform""",
  "live_test_url"        :  "http://prestashop.webkul.com/pob/odoo_multichannel/en/content/6-prestashop-multichannel-odoo-bridge",
  "depends"              :  ['odoo_multi_channel_sale'],
  "data"                 :  [
                             'security/ir.model.access.csv',
                             'data/cron.xml',
                             'data/data.xml',
                             'views/dashboard.xml',
                             'wizard/import_operation.xml',
                             'wizard/export_operation.xml',
                             'views/channel_views.xml',
                             'views/views.xml',

                            ],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  99,
  "currency"             :  "EUR",
  "external_dependencies":  {'python': ['html2text']},
}