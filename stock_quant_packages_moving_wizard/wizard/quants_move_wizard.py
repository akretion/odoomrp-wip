# -*- coding: utf-8 -*-
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models, fields, api


class StockQuantsMoveWizard(models.TransientModel):
    _name = 'stock.quants.move'

    line_ids = fields.One2many(
        comodel_name='stock.quants.move_items', inverse_name='wizard_id',
        string='Quants')
    dest_location_id = fields.Many2one(
        comodel_name='stock.location', string='Destination Location',
        domain=[('usage', '!=', 'view')], required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(StockQuantsMoveWizard, self).default_get(fields_list)
        assert self._context.get('active_model') == 'stock.quant'
        quants_ids = self._context.get('active_ids', [])
        quants = self.env['stock.quant'].browse(quants_ids)
        lines = []
        for quant in quants.filtered(lambda q: not q.package_id):
            lines.append((0, 0, {'quant_id': quant.id,
                                 'src_location_id': quant.location_id.id,
                                 'qty': quant.qty,
                                 'lot_id': quant.lot_id.id or False,
                                 'uom_id': quant.product_id.uom_id.id,
                                 }))
        res['line_ids'] = lines
        return res

    def run(self):
        self.ensure_one()
        quant_ids = []
        for line in self.line_ids:
            if line.quant_id.location_id != self.dest_location_id:
                line.quant_id.move_to(self.dest_location_id)
                quant_ids.append(line.quant_id.id)
        action = self.env['ir.actions.act_window'].for_xml_id(
            'stock', 'quantsact')
        action['context'] = {}  # remove default filters
        if len(quant_ids) == 1:
            action.update({
                'res_id': quant_ids[0],
                'view_mode': 'form,tree,pivot',
                'views': False,
                })
        else:
            action['domain'] = [('id', 'in', quant_ids)]
        return action


class StockQuantsMoveItems(models.TransientModel):
    _name = 'stock.quants.move_items'
    _description = 'Picking wizard items'

    wizard_id = fields.Many2one(
        comodel_name='stock.quants.move', string='Quant Move')
    quant_id = fields.Many2one(
        comodel_name='stock.quant', string='Quant', required=True,
        domain=[('package_id', '=', False)])
    qty = fields.Float(related='quant_id.qty', readonly=True)
    uom_id = fields.Many2one(
        related='quant_id.product_id.uom_id', readonly=True)
    lot_id = fields.Many2one(related='quant_id.lot_id', readonly=True)
    src_location_id = fields.Many2one(
        related='quant_id.location_id', readonly=True)
