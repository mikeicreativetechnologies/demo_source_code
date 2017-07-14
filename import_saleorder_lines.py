from openerp import fields, models, exceptions, api, _
import base64
import csv
import cStringIO


class ImportSaleorderLines(models.TransientModel):
    _name = 'import.saleorder.lines'
    _description = 'Import Saleorder Lines'

    name = fields.Char('Filename',readonly=True)
    data = fields.Binary('File', required=True)


    @api.one
    def action_import(self):
        """Load Inventory data from the CSV file."""
        ctx = self._context
        sale_obj = self.env['sale.order']
        product_obj = self.env['product.product']
        saleorder_line_obj = self.env['sale.order.line']
        if 'active_id' in ctx:
            sale_order = sale_obj.browse(ctx['active_id'])
        if not self.data:
            raise exceptions.Warning(_("You need to select a file!"))
        # Decode the file data
        data = base64.b64decode(self.data)
        file_input = cStringIO.StringIO(data)
        file_input.seek(0)
        reader_info = []

        reader = csv.reader(file_input, delimiter=',',lineterminator='\r\n')
        try:
            reader_info.extend(reader)
        except Exception:
            raise exceptions.Warning(_("Not a valid file!"))
        keys = reader_info[0]
        # check if keys exist
        if not isinstance(keys, list) or ('code' not in keys or 'quantity' not in keys):
            raise exceptions.Warning(
                _("Not 'code' or 'quantity' keys found"))
        del reader_info[0]
        values = {}
        for i in range(len(reader_info)):
            val = {}
            field = reader_info[i]
            values = dict(zip(keys, field))
            prod_lst = product_obj.search([('trikker_code', '=',values['code'])],limit = 1)
            if prod_lst:
                flag = False
                for order_line in sale_order.order_line:
                    if order_line.product_id.trikker_code == values['code']:
                        order_line.write({'product_uom_qty': (order_line.product_uom_qty + float(values['quantity']) ) })
                        flag = True
                        break
                if flag:
                    continue

                val['product_id'] = prod_lst.id
                val['product_uom_qty'] = values['quantity']
                val['order_id'] = sale_order.id
                saleorder_line_obj.create(val)
        return True