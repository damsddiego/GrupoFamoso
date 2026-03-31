# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Module Overview

`stock_warehouse_security` is an OCA (Odoo Community Association) module for Odoo 18 that restricts user access in multi-warehouse environments. Users with a non-empty `warehouse_ids` list can only see and operate on stock records belonging to their allowed warehouses. Users with an empty list have no restrictions.

**Key design decision:** No new groups are introduced — restriction is purely via `ir.rule` domain filters on `user.warehouse_ids`.

## Running Tests

Tests require a running Odoo instance. Run a specific test module with:

```bash
python odoo-bin -d <database> --test-enable --stop-after-init -i stock_warehouse_security
```

Run a single test class or method:

```bash
python odoo-bin -d <database> --test-enable --stop-after-init -i stock_warehouse_security \
  --test-tags /stock_warehouse_security:TestStockWarehouseAccess.test_read_stock_picking_limited_user
```

## Architecture

### Access Control Mechanism

The restriction is implemented in two layers:

1. **`ir.rule` records** (`security/stock_security.xml`) — applied to all stock models. The domain pattern used throughout:
   ```
   ['|', (1 if user.warehouse_ids.ids == [] else 0, "=", 1),
    '|', ('warehouse_id', '=', False),
         ('warehouse_id', 'in', user.warehouse_ids.ids)]
   ```
   - If `warehouse_ids` is empty → first condition `(1, "=", 1)` is always true → no filter applied.
   - If `warehouse_ids` is set → only records with no warehouse or a matching warehouse pass.

   Models covered: `stock.location`, `stock.picking.type`, `stock.picking`, `stock.move`, `stock.move.line`, `stock.quant`, `stock.quant.package`, `stock.warehouse.orderpoint`.

2. **`product.product._get_domain_locations_new()`** (`models/product.py`) — filters `location_ids` to only those belonging to the user's allowed warehouses when computing product stock quantities.

### Model Extension

`res.users` gains a `warehouse_ids` Many2many field to `stock.warehouse`. The field is added to `_get_invalidation_fields()` so Odoo invalidates the rules cache when it changes.

### Test Structure

- `tests/common.py`: Base class `TestStockCommon` sets up 3 warehouses across 2 companies and 3 test users with different warehouse/company combinations. The `@allowed_companies()` decorator mimics UI company selection for multi-company tests.
- `tests/test_stock_warehouse.py`: Tests for warehouse-related behavior.
- `tests/test_stock_warehouse_security_rules.py`: Tests for `ir.rule` enforcement — verifies that users only see records from their allowed warehouses.

### Known Gaps (ROADMAP)

- Default warehouse behavior when a user also processes sales is not unit-tested.
- Transit goods between warehouses are not unit-tested.
