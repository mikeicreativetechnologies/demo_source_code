# -*- coding: utf-8 -*-
from openerp import api, fields, models
import MySQLdb
from openerp.exceptions import UserError
from datetime import datetime
from openerp.addons.base_geoengine import geo_model
from openerp.addons.base_geoengine import fields as geo_fields
from openerp import tools


class mail_message(geo_model.GeoModel):
    _inherit = "mail.message"

    """ Inherit Mail Meassage from Geo model 
    to generate Map view """
    msg_id = fields.Integer()
    vehicle = fields.Char("Vehicle")
    device = fields.Char("Device")
    send_time = fields.Datetime("Send Time")
    received_time = fields.Datetime("Received Time")
    content = fields.Char("Content")
    image_data = fields.Binary("Image")
    latitude = fields.Integer("Latitude", size=11)
    longitude = fields.Integer("Longitude")
    timesheet_created = fields.Boolean("")
    the_point = geo_fields.GeoPoint('Coordinate')

    @api.model
    def automated_message_method(self):
        """ Automation Action method which fetch messages from Android My sQL database which is
        configure in settings"""
        config = self.env['base.config.settings'].search([], limit=1)
        try:
            if config.android_db_conf:
                db = MySQLdb.connect(host=config.host, port=config.port, user=config.user, passwd=config.password or '', db=config.db)
                cur = db.cursor()
                cur.execute("""SELECT * FROM message;""")
                for d in cur:
                    res_id = False
                    body = d[8]
                    if d[2] and ":" in d[2]:
                        task = d[2].split(':')[1]
                        res_id = self.env['project.task'].search([('name', '=', task.strip())], limit=1)
                        author = self.env['res.users'].search([('name', '=', d[3].strip())], limit=1)
                        if not author:
                            author = self.env['res.users'].create({'name': d[3].strip(), 'login': d[3].strip()})
                        dt = str(datetime.today().year) + " " + d[6]
                        date = datetime.strptime(dt, '%Y %d %b %H:%M').strftime('%Y-%m-%d %H:%M:%S')

                    if res_id:
                        if not self.env['mail.message'].search([('res_id', '=', res_id.id), ('msg_id', '=', d[0])]):
                            if not self.env['mail.message'].search([('content', '=', d[8]), ('received_time', '=', str(d[7]))]):
                                self.env['mail.message'].create({
                                    'body': body,
                                    'model': 'project.task',
                                    'res_id': res_id.id,
                                    'message_type': 'comment',
                                    'author_id': author.partner_id.id,
                                    'msg_id': d[0],
                                    'content': d[8],
                                    'vehicle': d[4],
                                    'device': d[5],
                                    'send_time': date,
                                    'received_time': d[7] or False,
                                    'image_data': str(d[10]).encode('hex'),
                                    'latitude': d[11],
                                    'longitude': d[12]})
                db.commit()
                db.close()
            else:
                raise UserError("Please, configure Android database setting in General settings.")
        except Exception, e:
            msg = u"%s" % e
            raise UserError(msg)
        return True



class report_project_task_user(models.Model,mail_message):
    _inherit = "report.project.task.user"
    _order = 'project_id'
    """ Create Map view report to display message location, Photos as per latitude and longitude"""

    device = fields.Char('Device', size=64, readonly=True)
    vehicle = fields.Char('Vehicle', index=True,readonly=True)
    latitude = fields.Integer("Latitude", size=11)
    longitude = fields.Integer("Longitude")
    image_data = fields.Binary("Image")
    attachment_id = fields.Many2one('ir.attachment',"Attachment")

    def _select(self):
        select_str = """
             SELECT
                    (select 1 ) AS nbr,
                    m.id as id,
                    t.date_start as date_start,
                    t.date_end as date_end,
                    t.date_last_stage_update as date_last_stage_update,
                    t.date_deadline as date_deadline,
                    abs((extract('epoch' from (t.write_date-t.date_start)))/(3600*24))  as no_of_days,
                    t.user_id,
                    t.project_id,
                    t.priority,
                    t.name as name,
                    t.company_id,
                    t.partner_id,
                    t.stage_id as stage_id,
                    t.kanban_state as state,
                    (extract('epoch' from (t.write_date-t.create_date)))/(3600*24)  as closing_days,
                    (extract('epoch' from (t.date_start-t.create_date)))/(3600*24)  as opening_days,
                    (extract('epoch' from (t.date_deadline-(now() at time zone 'UTC'))))/(3600*24)  as delay_endings_days,
                    m.latitude as latitude,
                    m.longitude as longitude,
                    m.vehicle as vehicle,
                    m.device as device,
                    m.the_point,
                    m.image_data as image_data,
                    (select attachment_id from message_attachment_rel a where a.message_id=m.id) as attachment_id

        """
        return select_str

    def _group_by(self):
        group_by_str = """
                GROUP BY
                    m.id,
                    t.kanban_state,
                    m.latitude,
                    m.longitude,
                    m.vehicle ,
                    m.device ,
                    m.the_point,
                    t.create_date,
                    t.write_date,
                    date_start,
                    date_end,
                    date_deadline,
                    date_last_stage_update,
                    t.user_id,
                    t.project_id,
                    t.priority,
                    name,
                    t.company_id,
                    t.partner_id,
                    stage_id
        """
        return group_by_str

    def init(self, cr):
        #  Execute query to fetch data to display in MAP.
        tools.sql.drop_view_if_exists(cr, 'report_project_task_user')
        cr.execute("""
            CREATE view report_project_task_user as
              %s
              FROM project_task t
              JOIN mail_message m ON t.id = m.res_id
                WHERE t.active = 'true'
                %s
        """% (self._select(), self._group_by())
