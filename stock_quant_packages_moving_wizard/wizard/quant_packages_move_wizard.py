# -*- coding: utf-8 -*-
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models, fields, api


class StockQuantPackageMove(models.TransientModel):
    _name = 'stock.quant.package.move'

    dest_location_id = fields.Many2one(
        comodel_name='stock.location', string='Destination Location',
        required=True, domain=[('usage', '!=', 'view')])
    line_ids = fields.One2many(
        comodel_name='stock.quant.package.move_items',
        inverse_name='wizard_id', string='Packs')

    @api.model
    def default_get(self, fields_list):
        res = super(StockQuantPackageMove, self).default_get(fields_list)
        assert self._context.get('active_model') == 'stock.quant.package'
        packages_ids = self.env.context.get('active_ids', [])
        packages = self.env['stock.quant.package'].browse(packages_ids)
        lines = []
        for package in packages:
            if not package.parent_id and package.location_id:
                lines.append((0, 0, {
                    'package_id': package.id,
                    'src_location_id': package.location_id.id,
                    }))
        res['line_ids'] = lines
        return res

    def run(self):
        self.ensure_one()
        package_ids = []
        for line in self.line_ids:
            if self.dest_location_id != line.src_location_id:
                package = line.package_id
                package_ids.append(package.id)
                for quant in package.quant_ids:
                    quant.move_to(self.dest_location_id)
                    quant.package_id = package.id
                # TODO support more than 2 layers of packaging
                for cpackage in package.children_ids:
                    for quant in cpackage.quant_ids:
                        quant.move_to(self.dest_location_id)
                        quant.package_id = cpackage.id
        action = self.env['ir.actions.act_window'].for_xml_id(
            'stock', 'action_package_view')
        if len(line.package_id) == 1:
            action.update({
                'res_id': package_ids[0],
                'view_mode': 'form,tree,pivot',
                'views': False,
                })
        else:
            action['domain'] = [('id', 'in', package_ids)]
        return action


class StockQuantPackageMoveItems(models.TransientModel):
    _name = 'stock.quant.package.move_items'
    _description = 'Picking wizard items'

    wizard_id = fields.Many2one(
        comodel_name='stock.quant.package.move', string='Package move wizard')
    package_id = fields.Many2one(
        comodel_name='stock.quant.package', string='Package',
        required=True,
        domain=[('parent_id', '=', False), ('location_id', '!=', False)])
    src_location_id = fields.Many2one(
        string='Current Location', related='package_id.location_id',
        readonly=True)
