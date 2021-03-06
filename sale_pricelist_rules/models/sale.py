# -*- encoding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses/.
#
##############################################################################

from openerp import models, fields, api, _
import openerp.addons.decimal_precision as dp


class SaleOrderLineSubtotal(models.Model):
    _name = 'sale.order.line.subtotal'

    @api.one
    def _calculate_subtotal(self):
        price = (self.line_id.price_unit *
                 (1 - (self.item_id.discount or 0.0) / 100) *
                 (1 - (self.item_id.discount2 or 0.0) / 100))
        qty = self.line_id.product_uom_qty
        if self.item_id.offer_id:
            total = (self.item_id.offer_id.free_qty +
                     self.item_id.offer_id.paid_qty)
            qty = round((qty / total) * self.item_id.offer_id.paid_qty)
        taxes = self.line_id.tax_id.compute_all(
            price, qty, self.line_id.product_id, self.order_id.partner_id)
        cur = self.order_id.pricelist_id.currency_id
        self.subtotal = cur.round(taxes['total'])

    line_id = fields.Many2one(
        comodel_name='sale.order.line', string='Line', ondelete='cascade')
    sale_id = fields.Many2one(
        comodel_name='sale.order', string='Sale Order',
        related='line_id.order_id', store=True)
    item_id = fields.Many2one(
        comodel_name='product.pricelist.item', string='Pricelist Item',
        ondelete='cascade')
    subtotal = fields.Float(
        string='Subtotal', digits=dp.get_precision('Account'),
        compute=_calculate_subtotal)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _calc_price_subtotal(self):
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        return price * (1 - (self.discount2 or 0.0) / 100.0)

    def _calc_qty(self):
        qty = self.product_uom_qty
        if self.offer_id:
            total = self.offer_id.free_qty + self.offer_id.paid_qty
            qty = round((qty / total) * self.offer_id.paid_qty)
        return qty

    @api.one
    def _amount_line(self):
        new_price_subtotal = self._calc_price_subtotal()
        qty = self._calc_qty()
        taxes = self.tax_id.compute_all(
            new_price_subtotal, qty, self.product_id,
            self.order_id.partner_id)
        cur = self.order_id.pricelist_id.currency_id
        self.price_subtotal = cur.round(taxes['total'])

    discount2 = fields.Float(
        string='Discount (%)', digits=dp.get_precision('Discount'),
        readonly=True, states={'draft': [('readonly', False)]}, default=0.0)
    offer_id = fields.Many2one(
        comodel_name='product.pricelist.item.offer', string='Offer')
    item_id = fields.Many2one(
        comodel_name='product.pricelist.item', string='Pricelist Item')
    subtotal_ids = fields.One2many(
        comodel_name='sale.order.line.subtotal', inverse_name='line_id',
        string='Subtotals by pricelist')
    price_subtotal = fields.Float(
        string='Subtotal', digits=dp.get_precision('Account'),
        compute=_amount_line)

    _sql_constraints = [
        ('discount2_limit', 'CHECK (discount2 <= 100.0)',
         _('Second discount must be lower than 100%.')),
    ]

    def default_get(self, cr, uid, fields_list, context=None):
        res = super(SaleOrderLine, self).default_get(cr, uid, fields_list,
                                                     context=context)
        item_obj = self.pool['product.pricelist.item']
        if context.get('pricelist_id'):
            item_id = item_obj.get_best_pricelist_item(
                cr, uid, context['pricelist_id'], context=context)
            res.update({'item_id': item_id})
        return res

    @api.multi
    def product_id_change(
            self, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False,
            name='', partner_id=False, lang=False, update_tax=True,
            date_order=False, packaging=False, fiscal_position=False,
            flag=False):
        res = super(SaleOrderLine, self).product_id_change(
            pricelist, product, qty=qty, uom=uom, qty_uos=qty_uos, uos=uos,
            name=name, partner_id=partner_id, lang=lang, update_tax=update_tax,
            date_order=date_order, packaging=packaging,
            fiscal_position=fiscal_position, flag=flag)
        if product:
            item_obj = self.env['product.pricelist.item']
            item_id = item_obj.get_best_pricelist_item(
                pricelist, product_id=product, qty=qty)
            res['value'].update({'item_id': item_id})
        return res

    @api.one
    @api.onchange('item_id')
    def onchange_item_id(self):
        if self.item_id:
            self.discount = self.item_id.discount
            self.discount2 = self.item_id.discount2
            self.offer_id = self.item_id.offer.id


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _amount_line_tax(self, line):
        val = 0.0
        new_price_subtotal = line._calc_price_subtotal()
        qty = line._calc_qty()
        for c in line.tax_id.compute_all(new_price_subtotal,
                                         qty, line.product_id,
                                         line.order_id.partner_id)['taxes']:
            val += c.get('amount', 0.0)
        return val

    subtotal_ids = fields.One2many(
        comodel_name='sale.order.line.subtotal', inverse_name='sale_id',
        string='Subtotals per line by pricelist')
