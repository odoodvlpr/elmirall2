from odoo.tests import common
from faker import Faker
from odoo.addons.oct_gls.models.gls_api.gls_response import GlsValidateResponse

class TestGls(common):

    def setUp(self):

        super(TestGls, self).setUp()
        self.uom_kg = self.env.ref('uom.product_uom_kgm')
        self.product_aw = self.env['product.product'].create({
            'name': 'Product AW',
            'type': 'product',
            'weight': 2.4,
            'uom_id': self.uom_kg.id,
            'uom_po_id': self.uom_kg.id
        })
        self.product_bw = self.env['product.product'].create({
            'name': 'Product BW',
            'type': 'product',
            'weight': 0.3,
            'uom_id': self.uom_kg.id,
            'uom_po_id': self.uom_kg.id
        })
        test_carrier_product = self.env['product.product'].create({
            'name': 'Test carrier product',
            'type': 'service',
        })
        self.test_carrier_national = self.env['delivery.carrier'].create({
            'name': 'Test carrier Nacional',
            'delivery_type': 'gls',
            'product_id': test_carrier_product.id,
            'gls_senderid': 'de49c620-5569-46c7-921a-6d79e40f686a',
            'gls_url': 'https://wsclientes.asmred.com/b2b.asmx?wsdl',
            'gls_default_service_type': 1
        })
        self.test_carrier_international = self.env['delivery.carrier'].create({
            'name': 'Test carrier Internacional',
            'delivery_type': 'gls',
            'product_id': test_carrier_product.id,
            'gls_senderid': 'de49c620-5569-46c7-921a-6d79e40f686a',
            'gls_url': 'https://wsclientes.asmred.com/b2b.asmx?wsdl',
            'gls_default_service_type': 76
        })

        self.stock_location = self.env.ref('stock.stock_location_stock')
        self.customer_location = self.env.ref('stock.stock_location_customers')
        self.warehouse = self.env['stock.warehouse'].search([('lot_stock_id', '=', self.stock_location.id)], limit=1)
        faker = Faker('es_ES')
        self.patner_nacional = self.env['res.partner'].create({
            'name':faker.name(),
            'is_company':1,
            'street':faker.street_address(),
            'city':faker.city(),
            'zip':faker.postcode(),
            'country_id':self.env.ref("base.es"),
            'email': faker.company_email(),
            'phone':faker.phone_number(),
            'mobile':faker.phone_number()
        })
        faker_int = Faker('fr_FR')
        self.patner_internacional = self.env['res.partner'].create({
            'name': faker_int.name(),
            'is_company': 1,
            'street': faker_int.street_address(),
            'city': faker_int.city(),
            'zip': faker_int.postcode(),
            'country_id': self.env.ref("base.fr"),
            'email': faker_int.company_email(),
            'phone': faker_int.phone_number(),
            'mobile': faker_int.phone_number()
        })

        self.partner_bad = self.env['res.partner'].create({
            'name': faker_int.name(),
            'is_company': 1,
            'street': faker_int.street_address(),
            'city': faker_int.city(),
            'zip': faker_int.postcode(),
            'country_id': self.env.ref("base.es"),
            'email': faker_int.company_email(),
            'phone': faker_int.phone_number(),
            'mobile': faker_int.phone_number()
        })


    """def test_01_gls_send_request_shipment(self):
        picking_ship_nacional = self.env['stock.picking'].create({
            'partner_id': self.patner_nacional.id,
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'carrier_id': self.test_carrier_national.id
        })


        response_good_address_nacional = picking_ship_nacional.carrier_id.gls_send_request_shipment(picking_ship)

        #good address
        self.assertIn(type(response),[dict,bool],"Error in send_request_shipment E:[dict,bool] R:{}".format(type(response_good_address_nacional)))

        if response:


        validateresponse = GlsValidateResponse()
        self.assertIn(type(validateresponse.gls_validate_response_shipment(response, picking_ship)),[bool],"Error in gls_validate_response_shipment E:[bool] R:{}".format(type(validateresponse.gls_validate_response_shipment(response, picking_ship))))

        tracking = validateresponse.gls_get_tracking_of_response(response, picking_ship)
        self.assertIn(type(tracking),[bool,str],"Error in gls_get_tracking_of_response E:[bool,str] R:{}".format(type(tracking)))

        if tracking:
            label_response = self.gls_send_request_label(tracking, picking_ship)
            self.assertIn(type(label_response),[bool,dict])"""






