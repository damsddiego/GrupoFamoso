# Stock Warehouse Security - Agent Guide

## Project Overview

**Stock Warehouse Security** is an Odoo 18.0 module (OCA) that restricts user access in multi-warehouse environments. It allows administrators to define a restricted list of warehouses that each user can see and operate with.

- **Version**: 18.0.1.0.0
- **License**: AGPL-3
- **Category**: Warehouse Management
- **Development Status**: Alpha (not for production use)
- **Maintainer**: Pierre Verkest (@petrus-v)
- **Repository**: https://github.com/OCA/stock-logistics-warehouse

### Key Characteristics

- **No new groups introduced**: Unlike previous versions, this module does not create new user groups
- **Optional restriction**: If no warehouses are defined for a user, they have unrestricted access
- **No "current warehouse" concept**: Users cannot switch between warehouses (unlike the v12.0 predecessor)

## Technology Stack

- **Framework**: Odoo 18.0
- **Language**: Python 3
- **Build System**: [whool](https://pypi.org/project/whool/) (build backend for Odoo modules)
- **Dependencies**: 
  - `stock` (Odoo core module)

## Project Structure

```
stock_warehouse_security/
├── __init__.py                 # Module initialization (imports models)
├── __manifest__.py             # Odoo module manifest
├── pyproject.toml              # Build system configuration (whool)
├── README.rst                  # Auto-generated readme (from readme/ fragments)
├── models/                     # Python business logic
│   ├── __init__.py             # Imports res_users, product
│   ├── res_users.py            # Extends res.users with warehouse_ids field
│   └── product.py              # Extends product.product with location domain filtering
├── security/                   # Access rules and security definitions
│   └── stock_security.xml      # Ir rules for warehouse-based access control
├── views/                      # UI views and forms
│   └── res_users.xml           # Extension to user form to add warehouse selection
├── tests/                      # Unit tests
│   ├── __init__.py             # Test imports
│   ├── common.py               # Common test utilities and base classes
│   ├── test_stock_warehouse.py # Tests for warehouse access scenarios
│   └── test_stock_warehouse_security_rules.py # Security rules tests
├── i18n/                       # Internationalization
│   ├── stock_warehouse_security.pot  # Translation template
│   ├── stock_multi_warehouse_security.pot  # Legacy template
│   ├── fr.po                   # French translation
│   └── it.po                   # Italian translation
├── readme/                     # Documentation fragments
│   ├── CONTRIBUTORS.md         # Contributors list
│   ├── DESCRIPTION.md          # Module description
│   ├── ROADMAP.md              # Future development plans
│   └── USAGE.md                # Usage instructions
└── static/description/         # Module metadata
    ├── icon.png                # Module icon
    └── index.html              # Module description HTML
```

## Core Functionality

### 1. User Model Extension (`models/res_users.py`)

Extends `res.users` with a Many2many field `warehouse_ids` to store allowed warehouses:

```python
warehouse_ids = fields.Many2many(
    "stock.warehouse",
    string="Allowed Warehouses",
)
```

Also implements `_get_invalidation_fields()` for proper cache invalidation.

### 2. Product Model Extension (`models/product.py`)

Extends `product.product` to filter locations based on user warehouse permissions:

- Overrides `_get_domain_locations_new()` to restrict location queries to allowed warehouses

### 3. Security Rules (`security/stock_security.xml`)

Defines `ir.rule` records for warehouse-based access control on:

- `stock.location` - Filter by `warehouse_id`
- `stock.picking.type` - Filter by `warehouse_id`
- `stock.picking` - Filter by `picking_type_id.warehouse_id`
- `stock.move` - Filter by `picking_type_id.warehouse_id`
- `stock.move.line` - Filter by `picking_type_id.warehouse_id`
- `stock.quant` - Filter by `location_id.warehouse_id`
- `stock.quant.package` - Filter by `location_id.warehouse_id`
- `stock.warehouse.orderpoint` - Filter by `warehouse_id`

The domain force logic:
```python
['|', (1 if user.warehouse_ids.ids == [] else 0, "=", 1), ...]
```

This means: **if user has no warehouses defined, they can access all records**.

### 4. User Interface (`views/res_users.xml`)

Adds a "Multi Warehouse" section in the Access Rights tab of the user form, allowing administrators to select allowed warehouses using a many2many_tags widget.

## Build and Test Commands

### Building

This module uses `whool` as the build backend. To build:

```bash
# Using pip (builds a wheel)
pip install build
python -m build

# Or using whool directly
pip install whool
whool build
```

### Testing

Tests are run using Odoo's testing framework:

```bash
# Run all tests for this module
odoo -i stock_warehouse_security --test-enable --stop-after-init

# Run specific test file
odoo -i stock_warehouse_security --test-enable --stop-after-init -u stock_warehouse_security --test-tags /stock_warehouse_security
```

### Test Structure

- **`tests/common.py`**: Base test class `TestStockCommon` with:
  - Test data setup (companies, warehouses, users, products, pickings)
  - `allowed_companies()` decorator for multi-company context simulation
  - Helper method `_create_picking()`

- **`tests/test_stock_warehouse_security_rules.py`**: Main test coverage for security rules:
  - `TestStockWarehouseAccess`: Tests for pickings, moves, locations, orderpoints
  - `TestStockWarehouseAccessWithReceivedGoods`: Tests for move lines and quants
  - `TestStockWarehouseAccessWithReceivedPackedGoods`: Tests for packages

- **`tests/test_stock_warehouse.py`**: Additional tests for warehouse settings:
  - Default warehouse setting with sale_stock module
  - Warehouse reading permissions

### Test Users

Three test user profiles are defined in `common.py`:

| User | Companies | Allowed Warehouses | Use Case |
|------|-----------|-------------------|----------|
| `stock_user_c1_wh12` | Company 1 | All (empty) | Unlimited user |
| `stock_user_c12_wh2` | Companies 1 & 2 | Warehouse 2 only | Restricted user |
| `stock_user_c12_wh23` | Companies 1 & 2 | Warehouses 2 & 3 | Multi-company restricted |

## Code Style Guidelines

### Python

- Follow **PEP 8** style guide
- Use **Black** formatter (implied by standard OCA practices)
- **Copyright headers** required on all Python files:
  ```python
  # Copyright (C) YEAR Company Name
  # @author Author Name <email>
  # License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
  ```
- Use absolute imports: `from odoo import ...` and `from odoo.addons.stock_warehouse_security.tests.common import ...`

### XML

- Use 4-space indentation
- Follow Odoo XML schema conventions
- Use `noupdate="1"` for ir.rules (security data)

### Testing Conventions

- Use `@users()` decorator to switch between test users
- Use `@allowed_companies()` decorator (custom) for multi-company tests
- Test method naming: `test_<action>_<object>_<scenario>`
- Always use `@classmethod` for `setUpClass()`

## Development Notes

### Adding New Security Rules

When adding new warehouse-based security for models:

1. Add the ir.rule in `security/stock_security.xml`
2. Follow the domain pattern:
   ```xml
   <field name="domain_force">['|',(1 if user.warehouse_ids.ids == [] else 0, "=", 1), '|', ('warehouse_id', '=', False), ('warehouse_id', 'in', user.warehouse_ids.ids)]</field>
   ```
3. Add tests in `tests/test_stock_warehouse_security_rules.py`
4. Update the translation template if new strings are added

### Extending Models

When extending models with warehouse-related functionality:

1. Create file in `models/`
2. Add import to `models/__init__.py`
3. Inherit from the target model: `_inherit = "model.name"`
4. Add copyright header

### Roadmap / Known Issues

Per `readme/ROADMAP.md`:

- Test default warehouse setting with sale_stock module (not unit-tested)
- Add unit tests for transit goods between warehouses

## Security Considerations

1. **Alpha Status**: This module is in Alpha development status - data model and design may change without warning. Not recommended for production use.

2. **No New Groups**: Unlike previous versions, this module does not introduce new security groups. Access control is purely based on the `warehouse_ids` field.

3. **Empty Warehouse List = No Restriction**: If a user has no warehouses in their `warehouse_ids` field, they can access all warehouses.

4. **Ir Rules**: All security enforcement is done through Odoo's `ir.rule` records, which operate at the ORM level.

5. **Multi-Company Compatibility**: The module is designed to work in multi-company environments. Users can have access to warehouses across multiple companies.

## Contributing

This module follows OCA (Odoo Community Association) contribution guidelines:

- https://odoo-community.org/page/Contribute
- Bug reports: https://github.com/OCA/stock-logistics-warehouse/issues

### Contributors

- Pierre Verkest (Foodles) <pierreverkest84@gmail.com>
- Florian da Costa (Akretion) <florian.dacosta@akretion.com>
- Christian Ramos (Tecnativa)
