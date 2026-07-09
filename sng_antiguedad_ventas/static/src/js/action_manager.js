/** @odoo-module **/

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

registry
    .category("ir.actions.report handlers")
    .add("sng_antiguedad_ventas_xlsx", async (action) => {
        if (action.report_type !== "sng_antiguedad_ventas_xlsx") {
            return false;
        }
        await download({
            url: "/sng_antiguedad_ventas/xlsx",
            data: action.data,
        });
        return true;
    });
