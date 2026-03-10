/** @odoo-module **/

import { menuService } from "@web/webclient/menus/menu_service";
import { patch } from "@web/core/utils/patch";

patch(menuService, {
    async start(env) {
        const menuAPI = await super.start(...arguments);
        const { orm, company } = env.services;
        
        // Use activeCompanyIds to get the currently selected companies.
        const companyIds = company.activeCompanyIds;
        
        const hiddenMenuIds = await orm.call(
            "ir.ui.menu",
            "get_menus_to_hide",
            [companyIds]
        );

        if (!hiddenMenuIds || hiddenMenuIds.length === 0) {
            return menuAPI; // No menus to hide, return original service.
        }
        
        const hiddenMenuIdsSet = new Set(hiddenMenuIds);

        // Patch getMenu: if a menu is hidden, return undefined.
        // For other menus, filter out any hidden children from their `children` array.
        const originalGetMenu = menuAPI.getMenu.bind(menuAPI);
        menuAPI.getMenu = (menuId) => {
            if (hiddenMenuIdsSet.has(menuId)) {
                return undefined;
            }
            const menu = originalGetMenu(menuId);
            if (menu && menu.children) {
                const newChildren = menu.children.filter(childId => !hiddenMenuIdsSet.has(childId));
                return { ...menu, children: newChildren };
            }
            return menu;
        };

        // Patch getAll: return only menus that are not in the hidden list.
        const originalGetAll = menuAPI.getAll.bind(menuAPI);
        menuAPI.getAll = () => {
            return originalGetAll().filter(m => !hiddenMenuIdsSet.has(m.id));
        };

        return menuAPI;
    }
});