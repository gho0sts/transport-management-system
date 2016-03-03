
# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################


from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
import time

# Wizard que permite generar la partida contable a pagar correspondiente al Anticipo del Operador


class tms_advance_invoice(osv.osv_memory):

    """ To create invoice for each Advance"""

    _name = 'tms.advance.invoice'
    _description = 'Make Invoices from Advances'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Advance and create Invoice
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        if context is None:
            record_ids = ids
        else:
            record_ids =  context.get('active_ids',[])
        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            user_obj=self.pool.get('res.users')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            account_jrnl_obj=self.pool.get('account.journal')
            period_obj = self.pool.get('account.period')
            move_obj = self.pool.get('account.move')
            advance_obj=self.pool.get('tms.advance')
            adv_line_obj=self.pool.get('tms.advance.line')
            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'general'),('tms_advance_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Account Journal for Travel Advances...')
            journal_id = journal_id and journal_id[0]
            #partner = partner_obj.browse(cr,uid,user_obj.browse(cr,uid,[uid])[0].company_id.partner_id.id)
            cr.execute("select distinct employee_id, currency_id from tms_advance where move_id is null and state='approved' and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv('Warning !',
                                 'Selected records are not Approved or already sent for payment...')
            #print data_ids
            for data in data_ids:
                cr.execute("select id from tms_advance where move_id is null and state='approved' and employee_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                advance_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                inv_lines = []
                notes = _('Driver Advances.')                
                move_lines = []
                precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
                for line in advance_obj.browse(cr,uid,advance_ids):
                    a = line.employee_id.tms_advance_account_id.id
                    if not a:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no advance account defined for this driver: "%s" (id:%d)') % \
                                        (line.employee_id.name, line.employee_id.id,))
                    a = account_fiscal_obj.map_account(cr, uid, False, a)

                    b = line.employee_id.address_home_id.property_account_payable.id
                    if not b:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no address created for this driver: "%s" (id:%d)') % \
                                        (line.employee_id.name, line.employee_id.id,))
                    b = account_fiscal_obj.map_account(cr, uid, False, b)

                    period_id = period_obj.search(cr, uid, [('date_start', '<=', line.date),('date_stop','>=', line.date), ('state','=','draft')], context=None)
                    if not period_id:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no valid account period for this date %s. Period does not exists or is already closed') % \
                                        (line.date,))
                    move_line = (0,0, {
                            'name'          : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'ref'           : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'account_id'    : a,
                            'debit'         : round(line.total, precision),
                            'credit'        : 0.0,
                            'journal_id'    : journal_id,
                            'period_id'     : period_id[0],
                            'vehicle_id'    : line.unit_id.id,
                            'employee_id'   : line.employee_id.id,
                            'sale_shop_id'  : line.shop_id.id,
                            'partner_id'    : line.employee_id.address_home_id.id,
                            })
                    move_lines.append(move_line)
                    move_line = (0,0, {
                            'name'          : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'ref'           : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'account_id'    : b,
                            'debit'         : 0.0,
                            'credit'        : round(line.total, precision),
                            'journal_id'    : journal_id,
                            'period_id'     : period_id[0],
                            'vehicle_id'    : line.unit_id.id,
                            'employee_id'   : line.employee_id.id,
                            'sale_shop_id'  : line.shop_id.id,
                            'partner_id'    : line.employee_id.address_home_id.id,
                            })
                    move_lines.append(move_line)                    
                    notes += '\n' + line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name
                move = {
                            'ref'               : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'journal_id'        : journal_id,
                            'narration'         : notes,
                            'line_id'           : [x for x in move_lines],
                            'date'              : line.date,
                            'period_id'         : period_id[0],
                        }
                move_id = move_obj.create(cr, uid, move)
                if move_id:
                    move_obj.button_validate(cr, uid, [move_id])                            
                advance_obj.write(cr,uid,advance_ids, {'move_id': move_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               
        return True
