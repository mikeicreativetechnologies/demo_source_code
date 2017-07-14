# -*- coding: utf-8 -*-
import logging
import werkzeug
import webbrowser
import ast

from openerp import http
from openerp.http import request
from openerp import tools
from openerp.osv.orm import browse_record
from openerp.addons.website.models.website import slug
from openerp.tools.translate import _
from openerp.addons.website_sale.controllers.main import website_sale

_logger = logging.getLogger(__name__)

PPG = 10  # Products Per Page
PPR = 4  # Categs Per Row
SEARCH_RESULT_DIC = {}  # Global variable used to manage history on 'Modify Search'

class ComputeTable(object):

    def __init__(self):
        self.table = {}

    def _check_pos(self, posx, posy, sizex, sizey):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx + x >= PPR:
                    res = False
                    break
                row = self.table.setdefault(posy + y, {})
                if row.setdefault(posx + x) is not None:
                    res = False
                    break
            for x in range(PPR):
                self.table[posy + y].setdefault(x, None)
        return res

    def proc(self, products, ppg=PPG):
        # Compute category positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        for prod in products:
            sizex = min(max(prod.size_x, 1), PPR)
            sizey = min(max(prod.size_y, 1), PPR)
            if index >= ppg:
                sizex = sizey = 1

            pos = minpos
            while not self._check_pos(pos % PPR, pos / PPR, sizex, sizey):
                pos += 1

            if index >= ppg and ((pos + 1.0) / PPR) > maxy:
                break

            if sizex == 1 and sizey == 1:
                minpos = pos / PPR

            for y2 in range(sizey):
                for x2 in range(sizex):
                    self.table[(pos / PPR) + y2][(pos % PPR) + x2] = False
            self.table[pos / PPR][pos % PPR] = {
                'product': prod, 'x': sizex, 'y': sizey,
                'class': " ".join(map(lambda sizex: sizex.html_class or '', prod.style_ids))
            }
            if index <= ppg:
                maxy = max(maxy, sizey + (pos / PPR))
            index += 1

        # Format table according to HTML needs
        rows = self.table.items()
        rows.sort()
        rows = map(lambda x: x[1], rows)
        for col in range(len(rows)):
            cols = rows[col].items()
            cols.sort()
            sizex += len(cols)
            rows[col] = [c for c in map(lambda sizex: sizex[1], cols) if c]

        return rows


class QueryURL(object):
    def __init__(self, path='', path_args=None, **args):
        self.path = path
        self.args = args
        self.path_args = set(path_args or [])

    def __call__(self, path=None, path_args=None, **kw):
        path = path or self.path
        for key, value in self.args.items():
            kw.setdefault(key, value)
        path_args = set(path_args or []).union(self.path_args)
        paths, fragments = [], []
        for key, value in kw.items():
            if value and key in path_args:
                if isinstance(value, browse_record):
                    paths.append((key, slug(value)))
                else:
                    paths.append((key, value))
            elif value:
                if isinstance(value, list) or isinstance(value, set):
                    fragments.append(werkzeug.url_encode([(key, item) for item in value]))
                else:
                    fragments.append(werkzeug.url_encode([(key, value)]))
        for key, value in paths:
            path += '/' + key + '/%s' % value
        if fragments:
            path += '?' + '&'.join(fragments)
        return path


class DiamondShop(website_sale):

    @http.route([
        '/shop',
    ], type='http', auth="user", website=True)
    def shop(self, ppg=False, **post):
        """Shop page with four diamond categories"""
        if ppg:
            try:
                ppg = int(ppg)
            except ValueError:
                ppg = PPG
            post["ppg"] = ppg
        else:
            ppg = PPG

        keep = QueryURL('/shop')

        Categories = request.env['product.public.category']

        categs_count = Categories.search_count([])
        categs = Categories.search([], limit=ppg, offset=0)

        values = {
                  'categs': categs,
                  'bins': ComputeTable().proc(categs, ppg),
                  'ROWS': categs_count,
                  'keep': keep,
                }
        return request.render("avalon_diamond_shop.prod_categs", values)

    @http.route([
        '/shop/category/search/<model("product.public.category"):product>',
    ], type='http', auth="public", website=True)
    def search_diamonds(self, product, **post):
        """redirect to template based on chosen diamond category"""
        global SEARCH_RESULT_DIC
        for key, value in SEARCH_RESULT_DIC.iteritems():
            SEARCH_RESULT_DIC[key] = [str(x) for x in value]
        values = SEARCH_RESULT_DIC
        SEARCH_RESULT_DIC = {}
        diamond_category = product.diamond_category
        request._cr.execute(("SELECT DISTINCT ct FROM avalon_diamonds_idex where diamond_prod_cate_id=%s Order By ct") % (product.id))
        carat_from_vals = request._cr.fetchall()
        request._cr.execute(("SELECT DISTINCT lab FROM avalon_diamonds_idex where diamond_prod_cate_id=%s Order By lab") % (product.id))
        labs_vals = request._cr.fetchall()

        values.update({
                'diamond_categ': diamond_category,
                'cut_items': [cut.name for cut in request.env['avalon.diamonds.cut'].sudo().search([], order="sequence asc, id asc") if cut.name],
                'carat_from_vals': carat_from_vals,
                'carat_to_vals': carat_from_vals,
                'col_vals': [col.name for col in request.env['avalon.diamonds.color'].sudo().search([], order="sequence asc, id asc") if col.name],
                'clarity_vals': [cl.name for cl in request.env['avalon.diamonds.cl'].sudo().search([], order="sequence asc, id asc") if cl.name],
                'cut_grades': [mk.name for mk in request.env['avalon.diamonds.mk'].sudo().search([], order="sequence asc, id asc") if mk.name],
                'labs': labs_vals,
                'polish': [pol.name for pol in request.env['avalon.diamonds.pol'].sudo().search([], order="sequence asc, id asc") if pol.name],
                'symmetry': [sym.name for sym in request.env['avalon.diamonds.sym'].sudo().search([], order="sequence asc, id asc") if sym.name],
                'intensity': [fl.name for fl in request.env['avalon.diamonds.fl'].sudo().search([], order="sequence asc, id asc") if fl.name],
                'condition': [cc.name for cc in request.env['avalon.diamonds.cc'].sudo().search([]) if cc.name],
                'size': [cs.name for cs in request.env['avalon.diamonds.cs'].sudo().search([]) if cs.name],
                'color': [color.name for color in request.env['avalon.diamonds.color'].sudo().search([], order="sequence asc, id asc") if color.name],
                'girdle': [gd.name for gd in request.env['avalon.diamonds.gd'].sudo().search([]) if gd.name],
                'NFC_Intensity': [nfci.name for nfci in request.env['avalon.diamonds.nfci'].sudo().search([]) if nfci.name],
                'Overtone': [nfco.name for nfco in request.env['avalon.diamonds.nfco'].sudo().search([]) if nfco.name],
                'NFC': [nfc.name for nfc in request.env['avalon.diamonds.nfc'].sudo().search([]) if nfc.name]
                })
        return request.render("avalon_diamond_shop.search_temp", values)

    @http.route(['/shop/searchdiamondsresults', '/shop/searchdiamondsresults/page/<int:page>'], type='http', auth="public", website=True)
    def search_idex_products(self, page=1, ppg=False, **post):
        """display idex products based on search results"""
        diamond_user = request.env.user.has_group('avalon_diamonds.group_avalon_diamonds_user')
        if page and page == 1 and post and 'check_post' not in post.keys():
            global SEARCH_RESULT_DIC
            SEARCH_RESULT_DIC = {}
        if post.get('categ'):
            categ = request.env['product.public.category'].sudo().search([('diamond_category', '=', post.get('categ'))])
        else:
            categ = request.env['product.public.category'].sudo().search([('diamond_category', '=', 'all')])
        domain = []
        all_final_list = []
        cart_prods = []
        sort_attr = []
        sort_by_tp = []
        Product = request.env['avalon.diamonds.idex']
        if categ.diamond_category != 'all' and not post.get('SortList1', False):
            domain = [('diamond_prod_cate_id', '=', categ.id)]
            field_mapping = {
                      'Cut': ['cut', 'avalon.diamonds.cut', 'in'],
                      'Color': ['col', 'avalon.diamonds.color', 'in'],
                      'Clarity': ['cl', 'avalon.diamonds.cl', 'in'],
                      'Cut_Grade': ['mk', 'avalon.diamonds.mk', 'in'],
                      'PolishList': ['pol', 'avalon.diamonds.pol', 'in'],
                      'SymmetryList': ['sym', 'avalon.diamonds.sym', 'in'],
                      'FluorescenceIntensityList': ['fl', 'avalon.diamonds.fl', 'in'],
                      'CuletSizeList': ['cs', 'avalon.diamonds.cs', 'in'],
                      'ColorList': ['col', 'avalon.diamonds.color', 'in'],
                      'FluorescenceColorList': ['fc', 'avalon.diamonds.color', 'in'],
                      'GirdleList': ['gd', 'avalon.diamonds.gd', 'in'],
                      'nfc_intensity': ['nfci', 'avalon.diamonds.nfci', 'in'],
                      'overtone': ['nfco', 'avalon.diamonds.nfco', 'in'],
                      'CuletConditionList': ['cc', 'avalon.diamonds.cc', 'in'],
                      'nfc': ['nfc', 'avalon.diamonds.nfc', 'in'],
                      'MakeDepthFrom': ['dp', 'number', '>='],
                      'MakeDepthTo': ['dp', 'number', '<='],
                      'MakeTableFrom': ['tb', 'number', '>='],
                      'MakeTableTo': ['tb', 'number', '<='],
                      'MeasurementHeightTo': ['mes', 'number', '='],
                      'MeasurementHeightFrom': ['mes', 'number', '='],
                      'MeasurementWidthFrom': ['mes', 'number', '='],
                      'MeasurementWidthTo': ['mes', 'number', '='],
                      'MeasurementLengthTo': ['mes', 'number', '='],
                      'MeasurementLengthFrom': ['mes', 'number', '='],
                      'Price': ['ap', 'number', '='],
                      'PerCaratPriceFrom': ['ap', 'number', '>='],
                      'PerCaratPriceTo': ['ap', 'number', '<='],
                      'PerStonePriceFrom': ['tp', 'number', '>='],
                      'PerStonePriceTo': ['tp', 'number', '<='],
                      'CaratRangeFromList': ['ct', 'number', '>='],
                      'CaratRangeToList': ['ct', 'number', '<='],
                      'CertifN': ['cn', 'char', 'like'],
                      'Cert': ['lab', 'char', 'like']
                    }

            if not SEARCH_RESULT_DIC:
                for k, v in post.items():
                    SEARCH_RESULT_DIC[k] = request.httprequest.form.getlist(k)
            for key, val in SEARCH_RESULT_DIC.items():
                if ('all' not in val) and ('' not in val) and (key not in ['check_post', 'categ', 'Carat', 'Price', 'MeasurementHeightTo', 'MeasurementHeightFrom', 'MeasurementWidthFrom', 'MeasurementWidthTo', 'MeasurementLengthTo', 'MeasurementLengthFrom', 'Girdle']):
                    field = field_mapping[key]
                    if field[1] in ('number'):
                        if val:
                            val = eval(val[0])
                        domain.append((field[0], field[2], val))
                    elif field[1] in ('char'):
                        domain.append((field[0], field[2], str(val[0])))
                    else:
                        field_ids = request.env[field[1]].sudo().search([('name', 'in', val)])
                        if field_ids:
                            domain.append((field[0], field[2], field_ids.ids))
            filtered_ids = Product.search(domain).ids
            length_from = post.get('MeasurementLengthFrom') and float(post.get('MeasurementLengthFrom'))
            length_to = post.get('MeasurementLengthTo') and float(post.get('MeasurementLengthTo'))
            width_from = post.get('MeasurementWidthFrom') and float(post.get('MeasurementWidthFrom'))
            width_to = post.get('MeasurementWidthTo') and float(post.get('MeasurementWidthTo'))
            height_from = post.get('MeasurementHeightFrom') and float(post.get('MeasurementHeightFrom'))
            height_to = post.get('MeasurementHeightTo') and float(post.get('MeasurementHeightTo'))
            if (((length_from or length_from == 0.0) and (length_to or length_to == 0.0)) or ((width_from or width_from == 0.0 and width_to or width_to == 0.0)) or ((height_from or height_from == 0.0 and height_to or height_to == 0.0))):
                for p in Product.search(domain):
                    if not p.mes:
                        filtered_ids.remove(p.id)
                    elif 'x' in p.mes:
                        mes_list = p.mes.split('x')
                        if len(mes_list) >= 1 and (float(mes_list[0]) <= length_from or float(mes_list[0]) >= length_to):
                            if p.id in filtered_ids:
                                filtered_ids.remove(p.id)
                        if len(mes_list) >= 2 and (float(mes_list[1]) <= width_from or float(mes_list[1]) >= width_to):
                            if p.id in filtered_ids:
                                filtered_ids.remove(p.id)
                        if len(mes_list) >= 3 and (float(mes_list[2]) <= height_from or float(mes_list[2]) >= height_to):
                            if p.id in filtered_ids:
                                filtered_ids.remove(p.id)
            domain.append(('id', 'in', filtered_ids))

        # initially sort by total price
        if Product.sudo().search_count(domain) > 0 and not post.get('SortList1', False):
            where_clause = tuple(Product.search(domain).ids)
            where_len = len(where_clause)
            where_clause = str(where_clause)
            if where_len <= 1:
                where_clause = where_clause.replace(',', '')
            request._cr.execute("""
                        SELECT id
                        FROM avalon_diamonds_idex WHERE id in """ + where_clause + """
                        ORDER BY tp = 0, tp""")
            sort_by_tp = [i[0] for i in request._cr.fetchall()]
        ppg = PPG
        keep = QueryURL('/shop/searchdiamondsresults', search='')

        if post:
            post['check_post'] = "idex_pager"
        Products = Product.sudo().search(domain, offset=(page - 1) * ppg, limit=ppg)
        final_list = Products.ids
        page_from_slice = ((page - 1) * ppg)
        page_to_slice = (page * ppg)

#         apply sorting on 'SORT' button click
        if post.get('SortList1', False):
            if post.get('domain', False) != '':
                domain = [i for i in ast.literal_eval(post.get('domain', False))]
            sort_dict = {}
            attribs_with_sequence = ['cut', 'cl', 'col', 'pol', 'sym', 'fc', 'fl', 'mk']
            for key, val in post.items():
                if not val.startswith("choose") and key != 'domain':
                    if val in attribs_with_sequence:
                        val = str(val) + '.sequence'
                    sort_dict[key] = val
            if 'SortList1' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList1'])
            if 'SortList2' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList2'])
            if 'SortList3' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList3'])
            if 'SortList4' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList4'])
            if sort_attr:
                if 'idex_pager' in sort_attr:
                    sort_attr.remove('idex_pager')
                Products = Product.sudo().search(domain)
                where_clause = tuple(Products.ids)
                where_clause = str(where_clause)
                if len(where_clause) <= 1:
                    where_clause = where_clause.replace(',', '')
                order_by = u",".join(sort_attr)
                cr = request._cr
                price_asc = u",".join([a + '=0' for a in sort_attr if a in ['ap', 'tp']])
                # query to sort results based on sort attributes
                if price_asc:
                    # sort price column have 0 come last
                    cr.execute("""
                    SELECT ai.id
                    FROM avalon_diamonds_idex as ai LEFT JOIN avalon_diamonds_cut as cut ON cut.id = ai.cut LEFT JOIN avalon_diamonds_color as col ON col.id = ai.col LEFT JOIN avalon_diamonds_mk as mk ON mk.id = ai.mk LEFT JOIN avalon_diamonds_pol as pol ON pol.id = ai.pol LEFT JOIN avalon_diamonds_sym as sym ON sym.id = ai.sym LEFT JOIN avalon_diamonds_fl as fl ON fl.id = ai.fl LEFT JOIN avalon_diamonds_fc as fc ON fc.id = ai.fc LEFT JOIN avalon_diamonds_cl as cl ON cl.id = ai.cl WHERE ai.id in """ + where_clause + """
                    ORDER BY """ + str(price_asc) + ',' + str(order_by))
                else:
                    cr.execute("""
                        SELECT ai.id
                        FROM avalon_diamonds_idex as ai LEFT JOIN avalon_diamonds_cut as cut ON cut.id = ai.cut LEFT JOIN avalon_diamonds_color as col ON col.id = ai.col LEFT JOIN avalon_diamonds_mk as mk ON mk.id = ai.mk LEFT JOIN avalon_diamonds_pol as pol ON pol.id = ai.pol LEFT JOIN avalon_diamonds_sym as sym ON sym.id = ai.sym LEFT JOIN avalon_diamonds_fl as fl ON fl.id = ai.fl LEFT JOIN avalon_diamonds_fc as fc ON fc.id = ai.fc LEFT JOIN avalon_diamonds_cl as cl ON cl.id = ai.cl WHERE ai.id in """ + where_clause + """
                        ORDER BY """ + str(order_by))
                all_final_list = [i[0] for i in cr.fetchall()]
        if sort_by_tp:
            final_list = sort_by_tp[page_from_slice:page_to_slice]
        if all_final_list:
            final_list = all_final_list[page_from_slice:page_to_slice]
        products = Product.sudo().browse(final_list)
        product_count = Product.sudo().search_count(domain)
        pager = request.website.pager(url="/shop/searchdiamondsresults", total=product_count, page=page, step=ppg, scope=7, url_args=post)
        for order in request.env['sale.order'].sudo().search([('state', '=', 'draft'), ('partner_id', '=', request.env.user.partner_id.id)]):
            for line in order.order_line:
                cart_prods.append(line.product_id.diamond_id.avalon_idex_id.id)
        page_result_from = page_from_slice + 1
        page_result_to = page_to_slice
        if page > int(product_count) / 10:
            page_result_to = int(product_count)
        if int(product_count) > 500 and (categ.diamond_category == 'white' or categ.diamond_category == 'color'):
            return request.render('avalon_diamond_shop.alert_user', {'search_count': int(product_count), 'categ': categ, 'keep': keep})
        values = {
            'pager': pager,
            'products': products,
            'final_list': final_list,
            'search_count': int(product_count),
            'bins': ComputeTable().proc(products, ppg),
            'ROWS': PPR,
            'keep': keep,
            'cart_prods': cart_prods,
            'domain': domain,
            'sortlist1': post.get('SortList1', False) if not sort_by_tp else 'tp',
            'sortlist2': post.get('SortList2', False),
            'sortlist3': post.get('SortList3', False),
            'sortlist4': post.get('SortList4', False),
            'categ': categ,
            'from_to': str(page_result_from) + '-' + str(page_result_to),
            'diamond_user': diamond_user,
            }
        return request.render("avalon_diamond_shop.index", values)

    @http.route([
        '/shop/calibrated/search/<model("product.public.category"):product>',
    ], type='http', auth="public", website=True)
    def search_calibrated_diamonds(self, product, **post):
        """Pass calibrated diamond details to template"""
        saved_diamonds = []
        final_list = []
        values = {}
        if post.get('calib_diamonds'):
            calib_diamonds = post.get('calib_diamonds')
            if isinstance(eval(calib_diamonds), int):
                final_list.append(eval(calib_diamonds))
            if isinstance(eval(calib_diamonds), tuple):
                final_list = list(eval(calib_diamonds))
            for rec in final_list:
                saved_diamonds.append(request.env['calibrated.saved.diamonds'].sudo().browse(rec))
        else:
            search_record = request.env['calibrated.saved.diamonds'].sudo().search([('customer', '=', request.env.user.partner_id.id)])
            if search_record.ids:
                saved_diamonds = search_record
        if saved_diamonds:
            values.update({'calib_diamonds': saved_diamonds})
        calibrated_diamonds = request.env['avalon.diamonds'].sudo().search([('diamond_bulk_shop', '=', True)])
        size_in_mm = list(set([cal_diamond.mes for cal_diamond in calibrated_diamonds]))
        values.update({
            'products': calibrated_diamonds,
            'size_in_mm': size_in_mm,
        })
        return request.render("avalon_diamond_shop.calibrated_diamonds", values)

    @http.route(['/add/shopping/cart'], type='json', auth="public", website=True)
    def add_cart(self, **kw):
        """method to add diamonds to shopping cart"""
        avalon_product = False
        if kw.get('selected_diamonds', False):
            for idex_id in kw.get('selected_diamonds'):
                idex_product = request.env['avalon.diamonds.idex'].sudo().browse(int(idex_id))
                avalon_product = idex_product.sudo()._create_avalon_product(request.env.user.partner_id)
                product_id = avalon_product.product_id
                request.website.sale_get_order(force_create=1)._cart_update(product_id=int(product_id), add_qty=1.0, set_qty=1.0)
        if kw.get('saved_check_calibrated', False):
            for saved_diamonds in kw.get('saved_check_calibrated', False):
                if saved_diamonds:
                    current_record = request.env['calibrated.saved.diamonds'].sudo().browse(eval(saved_diamonds))
                    request.website.sale_get_order(force_create=1)._cart_update(product_id=current_record.avalon_id.product_id.id, add_qty=current_record.quantity, set_qty=None)
        if kw.get('calibrated_diamonds', False):
            none_list_check = [a for a in kw.get('calibrated_diamonds', False) if a != None]
            none_list_qty = [b for b in kw.get('qty', False) if b != None]
            count = 0
            if none_list_check and none_list_qty:
                for avalon_id in none_list_check:
                    qty = eval(none_list_qty[count])
                    count += 1
                    avalon_product = request.env['avalon.diamonds'].sudo().browse(eval(avalon_id))
                    product_id = avalon_product.product_id.id
                    request.website.sale_get_order(force_create=1)._cart_update(product_id=product_id, add_qty=qty, set_qty=None)

    @http.route(['/update/cart'], type='json', auth="public", website=True)
    def update_cart(self, **kw):
        """update sale.order on deselecting the item from shopping cart"""
        value = {}
        prod_ids = [int(x) for x in kw.get('deselected_diamonds')]
        order = request.website.sale_get_order(force_create=1)
        if order.state != 'draft':
            request.website.sale_reset()
            return {}
        for prod_id in prod_ids:
            line_id = request.env['sale.order.line'].sudo().search([('product_id', '=', prod_id)])
            value = order._cart_update(product_id=prod_id, line_id=line_id.id, add_qty=0, set_qty=-1)
            order = request.website.sale_get_order()
            value['cart_quantity'] = order.cart_quantity
        return value

    @http.route(['/compare/details'], type='http', auth="public", website=True)
    def comp_details(self, **kw):
        """to compare the details of selected diamonds in new page"""
        sort_attr = []
        cart_prods = []
        idex_ids = []
        idex_records = []
        sort_dict = {}
        diamond_user = request.env.user.has_group('avalon_diamonds.group_avalon_diamonds_user')
        if kw.get('res', False):
            idex_ids = [int(x) for x in kw.get('res').split(',')]
            idex_ids = list(set(idex_ids))
            idex_records = [x for x in request.env['avalon.diamonds.idex'].sudo().browse(idex_ids)]
        # sorting in compare page
        attribs_with_sequence = ['cut', 'cl', 'col', 'pol', 'sym', 'fc', 'fl', 'mk']
        if kw.get('SortList1', False):
            idex_ids = kw.get('cmp_details', False)
            idex_records = request.env['avalon.diamonds.idex'].sudo().browse(eval(idex_ids))
            for key, val in kw.items():
                if not val.startswith("choose") and key != 'cmp_details' and key != 'diamond_details':
                    if val in attribs_with_sequence:
                        val = str(val) + '.sequence'
                    sort_dict[key] = val
            if 'SortList1' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList1'])
            if 'SortList2' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList2'])
            if 'SortList3' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList3'])
            if 'SortList4' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList4'])
            if sort_attr:
                cr = request._cr
                order_by = u",".join(sort_attr)
                where_clause = tuple(eval(idex_ids))
                where_len = len(where_clause)
                where_clause = str(where_clause)
                if where_len <= 1:
                    where_clause = where_clause.replace(',', '')
                cr.execute("""
                    SELECT ai.id
                    FROM avalon_diamonds_idex as ai LEFT JOIN avalon_diamonds_cut as cut ON cut.id = ai.cut LEFT JOIN avalon_diamonds_color as col ON col.id = ai.col LEFT JOIN avalon_diamonds_mk as mk ON mk.id = ai.mk LEFT JOIN avalon_diamonds_pol as pol ON pol.id = ai.pol LEFT JOIN avalon_diamonds_sym as sym ON sym.id = ai.sym LEFT JOIN avalon_diamonds_fl as fl ON fl.id = ai.fl LEFT JOIN avalon_diamonds_fc as fc ON fc.id = ai.fc LEFT JOIN avalon_diamonds_cl as cl ON cl.id = ai.cl WHERE ai.id in """ + where_clause + """
                    ORDER BY """ + str(order_by))
                sorted_ids = [i[0] for i in cr.fetchall()]
                idex_records = request.env['avalon.diamonds.idex'].sudo().browse(sorted_ids)
        total_price = [x.tp for x in idex_records]
        for order in request.env['sale.order'].sudo().search([('state', '=', 'draft'), ('partner_id', '=', request.env.user.partner_id.id)]):
            for line in order.order_line:
                cart_prods.append(line.product_id.diamond_id.avalon_idex_id.id)
        values = {
                    'diamond_details': idex_records,
                    'cmp_details': idex_ids,
                    'cart_prods': cart_prods,
                    'total_price': total_price,
                    'sortlist1': kw.get('SortList1', False),
                    'sortlist2': kw.get('SortList2', False),
                    'sortlist3': kw.get('SortList3', False),
                    'sortlist4': kw.get('SortList4', False),
                    'diamond_user': diamond_user,
                    'from_cart': False
                  }
        return request.render("avalon_diamond_shop.compare_details", values)

    @http.route(['/compare/cart/details'], type='http', auth="public", website=True)
    def comp_cart_details(self, **kw):
        """Redirect to 'Compare' page to compare the details of selected diamonds in shopping cart"""
        sort_attr = []
        product_ids = []
        diamond_rec = []
        diamond_ids = []
        sort_dict = {}
        total_price = []
        res = kw.get('res', False)
        if res:
            product_ids = [int(x) for x in res.split(',')]
            diamond_rec = [x for x in request.env['avalon.diamonds'].sudo().search([('product_id', 'in', product_ids)])]
            diamond_ids = [x.id for x in diamond_rec]
#         # sorting in compare page
        attribs_with_sequence = ['cut', 'cl', 'col', 'pol', 'sym', 'fc', 'fl', 'mk']
        if kw.get('SortList1', False):
            diamond_ids = kw.get('cmp_details', False)
            diamond_rec = request.env['avalon.diamonds'].sudo().browse(eval(diamond_ids))
            for key, val in kw.items():
                if not val.startswith("choose") and key != 'cmp_details' and key != 'diamond_details':
                    if val in attribs_with_sequence:
                        val = str(val) + '.sequence'
                    sort_dict[key] = val
            if 'SortList1' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList1'])
            if 'SortList2' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList2'])
            if 'SortList3' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList3'])
            if 'SortList4' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList4'])
            if sort_attr:
                cr = request._cr
                order_by = u",".join(sort_attr)
                where_clause = tuple(eval(diamond_ids))
                where_len = len(where_clause)
                where_clause = str(where_clause)
                if where_len <= 1:
                    where_clause = where_clause.replace(',', '')
                cr.execute("""
                    SELECT ai.id
                    FROM avalon_diamonds as ai LEFT JOIN avalon_diamonds_cut as cut ON cut.id = ai.cut LEFT JOIN avalon_diamonds_color as col ON col.id = ai.col LEFT JOIN avalon_diamonds_mk as mk ON mk.id = ai.mk LEFT JOIN avalon_diamonds_pol as pol ON pol.id = ai.pol LEFT JOIN avalon_diamonds_sym as sym ON sym.id = ai.sym LEFT JOIN avalon_diamonds_fl as fl ON fl.id = ai.fl LEFT JOIN avalon_diamonds_fc as fc ON fc.id = ai.fc LEFT JOIN avalon_diamonds_cl as cl ON cl.id = ai.cl WHERE ai.id in """ + where_clause + """
                    ORDER BY """ + str(order_by))
                sorted_ids = [i[0] for i in cr.fetchall()]
                diamond_rec = request.env['avalon.diamonds'].sudo().browse(sorted_ids)

        order = request.website.sale_get_order()
        for p in diamond_rec:
            for o in order.order_line:
                if p.product_id.id == o.product_id.id:
                    total_price.append(o.price_subtotal)
        values = {
                    'diamond_details': diamond_rec,
                    'cmp_details': diamond_ids,
                    'cart_prods': product_ids,
                    'total_price': total_price,
                    'sortlist1': kw.get('SortList1', False),
                    'sortlist2': kw.get('SortList2', False),
                    'sortlist3': kw.get('SortList3', False),
                    'sortlist4': kw.get('SortList4', False),
                    'from_cart': True
                  }
        return request.render("avalon_diamond_shop.compare_details", values)

    @http.route(['/check/pics'], type='json', auth='public', website=True)
    def check_pics(self, **kw):
        """check if the selected diamonds has pictures or not"""
        if kw.get('selected_diamonds', False):
            idex_ids = [int(x) for x in kw.get('selected_diamonds')]
            idex_ids = list(set(idex_ids))
            idex_records = [x for x in request.env['avalon.diamonds.idex'].browse(idex_ids)]
        if kw.get('deselected_diamonds', False):
            product_ids = list(set([int(x) for x in kw.get('deselected_diamonds')]))
            diamond_rec = [x for x in request.env['avalon.diamonds'].sudo().search([('product_id', 'in', product_ids)])]
            idex_records = [x.avalon_idex_id for x in diamond_rec]
        img_paths = [str(x.imgp) for x in idex_records]
        if any(x != 'False' for x in img_paths):  # check if the selected diamonds has image path
            return {'ok': True}
        else:
            return {'ok': False}

    @http.route(['/open/pics'], type='json', auth='public', website=True)
    def open_pics(self, **kw):
        """open images of selected diamonds in a seperate browser window"""
        if kw.get('selected_diamonds', False):
            idex_ids = [int(x) for x in kw.get('selected_diamonds')]
            idex_ids = list(set(idex_ids))
            idex_records = [x for x in request.env['avalon.diamonds.idex'].browse(idex_ids)]
        if kw.get('deselected_diamonds', False):
            product_ids = list(set([int(x) for x in kw.get('deselected_diamonds')]))
            diamond_rec = [x for x in request.env['avalon.diamonds'].sudo().search([('product_id', 'in', product_ids)])]
            idex_records = [x.avalon_idex_id for x in diamond_rec]
        img_paths = [str(x.imgp) for x in idex_records]
        img_urls = filter(lambda x: x != 'None', img_paths)
        for url in img_urls:
            webbrowser.open_new(url)

    @http.route(['/check/rep'], type='json', auth='public', website=True)
    def check_rep(self, **kw):
        """check if the selected diamonds has online reports or not"""
        if kw.get('selected_diamonds', False):
            idex_ids = [int(x) for x in kw.get('selected_diamonds')]
            idex_ids = list(set(idex_ids))
            idex_records = [x for x in request.env['avalon.diamonds.idex'].browse(idex_ids)]
        if kw.get('deselected_diamonds', False):
            product_ids = list(set([int(x) for x in kw.get('deselected_diamonds')]))
            diamond_rec = [x for x in request.env['avalon.diamonds'].sudo().search([('product_id', 'in', product_ids)])]
            idex_records = [x.avalon_idex_id for x in diamond_rec]
        rep_urls = [str(x.cp) for x in idex_records]
        if any('http' in x for x in rep_urls):  # check if the selected diamonds has online report
            return {'ok': True}
        else:
            return {'ok': False}

    @http.route(['/open/reports'], type='json', auth='public', website=True)
    def open_reports(self, **kw):
        """open online reports of selected diamonds in a seperate browser window"""
        if kw.get('selected_diamonds', False):
            idex_ids = [int(x) for x in kw.get('selected_diamonds')]
            idex_ids = list(set(idex_ids))
            idex_records = [x for x in request.env['avalon.diamonds.idex'].browse(idex_ids)]
        if kw.get('deselected_diamonds', False):
            product_ids = list(set([int(x) for x in kw.get('deselected_diamonds')]))
            diamond_rec = [x for x in request.env['avalon.diamonds'].sudo().search([('product_id', 'in', product_ids)])]
            idex_records = [x.avalon_idex_id for x in diamond_rec]
        report_urls = [str(x.cp) for x in idex_records]
        for url in report_urls:
            webbrowser.open_new(url)

    @http.route(['/shop/cart'], type='http', auth="public", website=True)
    def cart(self, **post):
        """custom shopping cart with sorting functionality"""
        sort_attr = []
        order_lines = []
        sort_dict = {}
        order = request.website.sale_get_order()
        if order:
            order_lines = [line for line in order.order_line]
            from_currency = order.company_id.currency_id
            to_currency = order.pricelist_id.currency_id
            compute_currency = lambda price: from_currency.compute(price, to_currency)
        else:
            compute_currency = lambda price: price
        # apply sorting on shopping cart
        attribs_with_sequence = ['cut', 'cl', 'col', 'pol', 'sym', 'fc', 'fl', 'mk']
        if post.get('SortList1', False):
            for key, val in post.items():
                if not val.startswith("choose"):
                    if val in attribs_with_sequence:
                        val = str(val) + '.sequence'
                    sort_dict[key] = val
            if 'SortList1' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList1'])
            if 'SortList2' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList2'])
            if 'SortList3' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList3'])
            if 'SortList4' in sort_dict.keys():
                sort_attr.append(sort_dict['SortList4'])
            if sort_attr:
                cr = request._cr
                order_by = u",".join(sort_attr)
                where_clause = tuple([line.product_id.diamond_id.id for line in order.order_line])
                where_len = len(where_clause)
                where_clause = str(where_clause)
                if where_len <= 1:
                    where_clause = where_clause.replace(',', '')
                cr.execute("""
                        SELECT ad.id
                        FROM avalon_diamonds as ad LEFT JOIN avalon_diamonds_cut as cut ON cut.id = ad.cut LEFT JOIN avalon_diamonds_color as col ON col.id = ad.col LEFT JOIN avalon_diamonds_mk as mk ON mk.id = ad.mk LEFT JOIN avalon_diamonds_pol as pol ON pol.id = ad.pol LEFT JOIN avalon_diamonds_sym as sym ON sym.id = ad.sym LEFT JOIN avalon_diamonds_fl as fl ON fl.id = ad.fl LEFT JOIN avalon_diamonds_fc as fc ON fc.id = ad.fc LEFT JOIN avalon_diamonds_cl as cl ON cl.id = ad.cl WHERE ad.id in """ + where_clause + """
                        ORDER BY """ + str(order_by))
                sorted_dia_ids = [i[0] for i in cr.fetchall()]
                order_lines = [line for dia_id in sorted_dia_ids for line in order.order_line if line.product_id.diamond_id.id == dia_id]

        values = {
            'website_sale_order': order,
            'website_order_line': order_lines,  # pass sorted order lines to website shopping cart
            'compute_currency': compute_currency,
            'suggested_products': [],
            'sortlist1': post.get('SortList1', False),
            'sortlist2': post.get('SortList2', False),
            'sortlist3': post.get('SortList3', False),
            'sortlist4': post.get('SortList4', False)
        }
        if order:
            _order = order
            if not request.env.context.get('pricelist'):
                _order = order.with_context(pricelist=order.pricelist_id.id)
            values['suggested_products'] = _order._cart_accessories()

        if post.get('type') == 'popover':
            return request.render("website_sale.cart_popover", values)

        if post.get('code_not_available'):
            values['code_not_available'] = post.get('code_not_available')

        return request.render("website_sale.cart", values)
    
    @http.route(['/address/registration'], type='http', auth="user", website=True)
    def fully_registrer(self, **post):
        """open registration form on click of 'Register fully to see prices' button"""
        countries = request.env['res.country'].search([])
        states = request.env['res.country.state'].search([])
        partner_id = request.env.user.partner_id
        return request.website.render("avalon_diamond_shop.register_address", {
            'countries': countries, 'states': states, 'checkout': {'name': partner_id.name, 'email': partner_id.email, 'street': partner_id.street, 'phone': partner_id.phone, 'street2': partner_id.street2, 'city': partner_id.city, 'zip': partner_id.zip, 'country_id': partner_id.country_id.id, 'state_id': partner_id.state_id.id}, 'error': {}})
        
    @http.route(['/submit/registration'], type='http', auth="public", website=True)
    def confirm_registration(self, **post):
        "after registration user will get a email that he have to wait until diamond-manager has checked his account"
        error = dict()
        error_message = []
        values = {'error': {}}
        checkout = {'name': post.get('name'), 'email': post.get('email'), 'street': post.get('street'), 'phone': post.get('phone'), 'street2': post.get('street2'), 'city': post.get('city'), 'zip': post.get('zip'), 'country_id': post.get('country_id')}
        countries = request.env['res.country'].search([])
        states = request.env['res.country.state'].search([])
        values["checkout"] = checkout
        values["countries"] = countries
        values["states"] = states
        # Validation
        for field_name in ["name", "phone", "email", "street2", "city", "country_id"]:
            if not post.get(field_name):
                error[field_name] = 'missing'

        # email validation
        if post.get('email') and not tools.single_email_re.match(post.get('email')):
            error["email"] = 'error'
            error_message.append(_('Invalid Email! Please enter a valid email address.'))
        
        # error message for empty required fields
        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))
        values["error"], values["error_message"] = error, error_message
        if values["error"]:
            return request.website.render("avalon_diamond_shop.register_address", values)
        request.env.user.partner_id.write(values["checkout"])
#         send email to inform user about his successful registration
        template_id = request.env['ir.model.data'].get_object_reference('avalon_diamond_shop', 'send_address_registration_confirmation')[1]
        template_obj = request.env['mail.template'].browse(template_id)
        template_obj.email_to = post.get('email')
        template_obj.sudo().send_mail(request.env.user.partner_id.id, force_send=True)
#         send email to inform company about new registartion for diamond usage
        template_id = request.env['ir.model.data'].get_object_reference('avalon_diamond_shop', 'new_address_registration')[1]
        template_obj = request.env['mail.template'].browse(template_id)
        template_obj.email_to = request.env.user.partner_id.company_id.email
        template_obj.sudo().send_mail(request.env.user.partner_id.id, force_send=True)

        return request.redirect("/shop")
