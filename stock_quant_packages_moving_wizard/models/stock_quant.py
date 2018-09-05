# -*- coding: utf-8 -*-
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models, _
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _prepare_move_to(self, dest_location):
        self.ensure_one()
        vals = {
            'name': '%s: Move to %s' % (
                self.product_id.display_name,
                dest_location.complete_name),
            'product_id': self.product_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': dest_location.id,
            'product_uom_qty': self.qty,
            'product_uom': self.product_id.uom_id.id,
            'restrict_lot_id': self.lot_id.id or False,
            'origin': _('Quant Move'),
        }
        return vals

    def move_to(self, dest_location):
        if dest_location.usage == 'view':
            raise UserError(_(
                "Cannot move to location '%s' which is a view location.")
                % dest_location.complete_name)
        smo = self.env['stock.move']
        for quant in self:
            if quant.location_id == dest_location:
                continue
            # if the quant is reserved for another move,
            # we should cleanly un-reserve it first, so that
            # the picking that booked this quant comes back from
            # available to waiting availability
            # If you have the OCA module stock_quant_merge
            # make sure that you have the code of this PR:
            # https://github.com/OCA/stock-logistics-warehouse/pull/475/files
            # So that the quant is not merged with other quants right before
            # the move!
            if quant.reservation_id:
                quant.reservation_id.with_context(
                    disable_stock_quant_merge=True).do_unreserve()
                if quant.reservation_id:
                    raise UserError(_(
                        "Odoo failed to unreserve the quant ID %d") % quant.id)
            vals = quant._prepare_move_to(dest_location)
            new_move = smo.create(vals)
            # No group has write access on stock.quant -> we need sudo()
            quant.sudo().reservation_id = new_move
            new_move.with_context(quant_moving=True).action_done()

    @api.model
    def quants_get_preferred_domain(
            self, qty, move, ops=False, lot_id=False, domain=None,
            preferred_domain_list=[]):
        if self.env.context.get('quant_moving'):
            quant = move.reserved_quant_ids[0]
            res = [(quant, quant.qty)]
            return res
        return super(StockQuant, self).quants_get_preferred_domain(
            qty, move, ops=ops, lot_id=lot_id, domain=domain,
            preferred_domain_list=preferred_domain_list)
