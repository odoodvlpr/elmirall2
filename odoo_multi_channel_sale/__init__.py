# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from . import models
from . import wizard
from . import controllers
from . import tools


def pre_init_check(cr):
	from odoo.service import common
	from odoo.exceptions import Warning
	version_info = common.exp_version()
	server_serie = version_info.get('server_serie')
	if server_serie != '14.0':
		raise Warning(
			'Module support Odoo series 13.0 found {}.'.format(server_serie))
	return True
