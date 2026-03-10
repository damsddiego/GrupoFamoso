# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from time import gmtime, strftime
from datetime import datetime
import base64
import xlwt
from json import dumps
import ast
import json
from io import BytesIO
