# Sale Account Manager Customer Credit Limit Approval

## Overview

This Odoo 18 module implements a comprehensive customer credit limit management system with multi-level approval workflow for sales orders. It helps organizations manage financial risk by controlling credit exposure per customer through configurable limits and approval processes.

## Key Features

### 1. Customer Credit Limit Configuration
- **Dual-Threshold System**: Configure both warning and blocking limits per customer
- **Warning Limit**: Non-blocking threshold that triggers user notifications
- **Blocking Limit**: Hard limit that prevents order confirmation without approval
- **Dynamic Due Amount Calculation**: Automatically calculates total outstanding exposure from:
  - Posted invoice balances (credit - debit)
  - Unpaid sales orders
  - Draft invoices from sales orders

### 2. Multi-Level Approval Workflow
Sales orders exceeding blocking limits require approval from:
1. **Sales Manager**: First-level approval
2. **Finance/Account Manager**: Final approval authority

### 3. Overdue Invoice Detection (Enhanced Feature)
- **Automatic Detection**: System automatically detects customers with overdue invoices
- **Visual Warning**: Red alert banner displayed on sales orders for customers with overdue invoices
- **Warning Integration**: Triggers warning wizard even if credit limits are not exceeded
- **Smart Notifications**: Customized messages based on combination of overdue invoices and credit limits

### 4. Three-Tier Control System
The module implements three levels of control:

#### Scenario 1: Normal Processing
- **Condition**: `(amount_due + order_total) ≤ blocking_limit` AND no overdue invoices
- **Action**: Order confirms normally without any intervention
- **Approvals Required**: 0

#### Scenario 2: Warning (Soft Block)
Triggers in any of these situations:
- **2A**: `warning_limit ≤ amount_due < blocking_limit`
- **2B**: Customer has overdue invoices (even if limits not exceeded) ⭐ NEW
- **2C**: Customer has overdue invoices AND warning limit exceeded

**Action**: Display warning wizard with customized messages:
- "Customer has overdue invoices, Do You want to continue?"
- "Customer has overdue invoices and warning limit exceeded, Do You want to continue?"
- "Customer warning limit exceeded, Do You want to continue?"

**Approvals Required**: 0 (user confirmation only)

#### Scenario 3: Hard Block
- **Condition**: `(amount_due + order_total) > blocking_limit`
- **Action**: Prevents confirmation, requires approval workflow
- **Approvals Required**: 2 (Sales Manager + Finance Manager)

### 5. Email Notification System
- Automatic emails sent to appropriate approvers with direct Odoo links
- Different templates for sales and finance approval stages
- Rejection notifications sent back to sales team
- Dynamic URL generation for easy access to orders

### 6. Visual Indicators
- **Yellow Alert**: Displayed when credit blocking limit is exceeded
- **Red Alert**: Displayed when customer has overdue invoices ⭐ NEW
- **Status Badges**: New order states for tracking approval progress
- **Credit Information Panel**: Displays comprehensive credit info on sales order form ⭐ NEW (v2.1)

## Technical Details

### New Sale Order States
- `sales_approval`: Waiting for Sales Manager approval
- `finance_approval`: Waiting for Finance Manager approval
- `approved`: Final approval obtained, ready for confirmation
- `reject`: Rejected by approval authority

### New Fields

#### res.partner (Customer)
- `credit_check` (Boolean): Activate credit limit feature
- `credit_warning` (Monetary): Warning threshold amount
- `credit_blocking` (Monetary): Blocking threshold amount
- `amount_due` (Monetary, Computed): Total outstanding amount
- `has_overdue_invoices` (Boolean, Computed): Detects overdue invoices ⭐ NEW
- `overdue_amount` (Monetary, Computed): Total amount of overdue invoices ⭐ NEW (v2.1)

#### res.company
- `accountant_email` (Char): Finance team email for notifications

#### sale.order
- `has_overdue_invoices` (Boolean, Related): Customer's overdue status ⭐ NEW
- `overdue_amount` (Monetary, Related): Total overdue amount ⭐ NEW (v2.1)
- `customer_warning_limit` (Monetary, Related): Customer's warning limit ⭐ NEW (v2.1)
- `customer_payment_term` (Many2one, Related): Customer's payment term ⭐ NEW (v2.1)
- `is_credit_limit_approval` (Boolean, Computed): Indicates if approval needed
- `is_credit_limit_final_approved` (Boolean): Final approval flag

### Overdue Invoice Detection Logic ⭐ NEW

The system searches for invoices with the following criteria:
- Status: `posted` (confirmed invoices)
- Payment State: `not_paid` or `partial` (unpaid or partially paid)
- Invoice Type: `out_invoice` or `out_refund` (customer invoices)
- Due Date: Less than today's date

```python
overdue_invoices = self.env['account.move'].search([
    ('partner_id', '=', rec.id),
    ('state', '=', 'posted'),
    ('payment_state', 'in', ['not_paid', 'partial']),
    ('move_type', 'in', ['out_invoice', 'out_refund']),
    ('invoice_date_due', '<', today),
], limit=1)
```

## Configuration

### Step 1: Enable Credit Check for Customer
1. Navigate to **Contacts**
2. Select a customer
3. Enable **Active Credit** checkbox
4. Set **Warning Amount** (e.g., $10,000)
5. Set **Blocking Amount** (e.g., $15,000)

### Step 2: Configure Company Settings
1. Navigate to **Settings → General Settings → Companies**
2. Edit your company
3. Set **Accountant email** for finance team notifications

### Step 3: Assign Security Groups
Ensure users have appropriate access rights:
- **ERP Manager** (`base.group_erp_manager`): Can initiate approval workflow
- **Sales Manager** (`sales_team.group_sale_manager`): First-level approval
- **Account Manager** (`account.group_account_manager`): Final approval

## Workflow Examples

### Example 1: Customer with Overdue Invoices (New Scenario) ⭐

**Customer**: ABC Corp
- Credit Warning: $10,000
- Credit Blocking: $15,000
- Current Due: $5,000
- **Has overdue invoice from last month: $2,000**

**New Order**: $3,000

**Result**:
1. Red alert banner appears: "Warning: This customer has overdue invoices!"
2. User clicks "Confirm"
3. Warning wizard appears: "Customer has overdue invoices, Do You want to continue?"
4. User clicks "Yes" → Order confirms

**Total Due After Confirmation**: $8,000 (still below warning limit)

### Example 2: Overdue Invoices + Warning Limit Exceeded ⭐

**Customer**: XYZ Corp
- Credit Warning: $10,000
- Credit Blocking: $15,000
- Current Due: $9,000
- **Has overdue invoice: $3,000**

**New Order**: $2,000

**Result**:
1. Red alert banner: "Warning: This customer has overdue invoices!"
2. User clicks "Confirm"
3. Warning wizard: "Customer has overdue invoices and warning limit exceeded, Do You want to continue?"
4. User clicks "Yes" → Order confirms

**Total Due After Confirmation**: $11,000 (warning limit exceeded)

### Example 3: Hard Block with Approval Workflow

**Customer**: DEF Corp
- Credit Blocking: $15,000
- Current Due: $14,000

**New Order**: $3,000

**Result**:
1. User clicks "Confirm"
2. System blocks: "Can not confirm... exceeds customer's credit limit by $2,000"
3. ERP Manager clicks "Credit Limit Approval" button
4. Order state → `sales_approval`
5. Email sent to Sales Manager
6. Sales Manager clicks "Approve"
7. Order state → `finance_approval`
8. Email sent to Finance Manager
9. Finance Manager clicks "Approve"
10. Order state → `approved`
11. User can now click "Confirm" → Order state → `sale`

## User Interface

### Sales Order Form View Alerts

#### Credit Limit Alert (Yellow)
```
⚠️ Customer Blocking Limit is $15,000.00
   Customer Due Amount is $14,000.00
```

#### Overdue Invoice Alert (Red) ⭐ NEW
```
⚠️ Warning: This customer has overdue invoices!
```

#### Customer Credit Information Panel ⭐ NEW (v2.1)
Displayed automatically below customer field when `credit_check` is enabled:

```
┌─────────────────────────────────────────────────┐
│  Customer Credit Information                     │
├─────────────────────────────────────────────────┤
│  Customer Warning Limit:    $10,000.00          │
│  Customer Blocking Limit:   $15,000.00          │
│  Amount Due:                $8,500.00            │
│  Overdue Amount:            $2,500.00  (red)    │
│  Customer Payment Term:     30 Net Days          │
└─────────────────────────────────────────────────┘
```

**Features**:
- Only visible when customer has credit check enabled
- Shows all credit-related information in one place
- Overdue amount displayed in red when > 0
- Payment term shows configured customer payment conditions
- All fields are read-only (informative only)

### Buttons

#### "Credit Limit Approval" Button
- **Visible**: Draft/Sent states when blocking limit exceeded
- **Access**: ERP Manager only
- **Action**: Initiates approval workflow

#### "Approve" Button (Sales Manager)
- **Visible**: `sales_approval` state only
- **Access**: Sales Manager
- **Action**: Advances to finance approval

#### "Approve" Button (Finance Manager)
- **Visible**: `finance_approval` state only
- **Access**: Account Manager
- **Action**: Final approval, allows confirmation

#### "Reject" Buttons
- Available to both Sales and Finance managers
- Sends rejection email to salesperson
- Transitions order to `reject` state

## Dependencies

- `sale_management`: Core Odoo sales module

## Security

### Access Rights
- `warning.wizard`: Accessible to all authenticated users

### Button-Level Security
- Credit Limit Approval: ERP Manager only
- Sales Approval: Sales Manager only
- Finance Approval: Account Manager only

## Installation

1. Copy module to Odoo addons directory
2. Update Apps List
3. Install "Sale Account Manager Customer Credit Limit Approval"
4. Configure customer credit limits
5. Set company accountant email

## Technical Modifications

### Version 2.1 (Latest) ⭐

#### Modified Files

**1. models/res_partner.py**
- **Line 15**: Added `overdue_amount` field (Monetary, Computed)
- **Lines 46-61**: Added `_compute_overdue_amount()` method
  - Calculates total amount of all overdue invoices
  - Sums `amount_residual` from overdue invoices
  - Returns monetary value

**2. models/sale_order.py**
- **Line 30**: Added `customer_warning_limit` related field
- **Line 34**: Added `overdue_amount` related field
- **Line 35**: Added `customer_payment_term` related field
  - Links to customer's configured payment term
  - Displays payment conditions on sales order

**3. views/sale_order.xml**
- **Lines 39-48**: Added "Customer Credit Information" panel
  - Displays below partner field
  - Shows: Warning Limit, Blocking Limit, Amount Due, Overdue Amount, Payment Term
  - Only visible when `partner_id.credit_check == True`
  - Overdue amount shown in red (CSS class: `text-danger`)
  - All fields read-only (informative only)
- **Lines 55-56**: Added invisible fields for proper field loading

### Version 2.0 ⭐

#### Modified Files

**1. models/res_partner.py**
- **Line 14**: Added `has_overdue_invoices` field
- **Lines 28-43**: Added `_compute_has_overdue_invoices()` method
  - Searches for posted invoices past due date
  - Checks unpaid/partially paid status
  - Returns boolean flag

**2. models/sale_order.py**
- **Line 32**: Added `has_overdue_invoices` related field
- **Lines 93-114**: Enhanced `action_confirm()` logic
  - Added condition: `(partner_id.has_overdue_invoices and partner_id.credit_check)`
  - Implemented smart message selection based on situation
  - Three different warning messages for different scenarios

**3. views/sale_order.xml**
- **Lines 22-27**: Added red alert banner for overdue invoices
  - Uses Font Awesome exclamation triangle icon
  - Visible only in draft/sent states
  - CSS class: `alert-danger`
- **Line 43**: Added invisible field `has_overdue_invoices`

## Version History

### Version 2.1 (2024) ⭐
- ⭐ Added Customer Credit Information panel on sales order form
- ⭐ Added overdue amount calculation and display
- ⭐ Added customer warning limit display on order
- ⭐ Added customer payment term display on order
- ⭐ Enhanced visibility of credit information for sales team
- ⭐ Improved UX with consolidated credit information

### Version 2.0 (2024) ⭐
- ⭐ Added overdue invoice detection
- ⭐ Enhanced warning wizard with overdue invoice checks
- ⭐ Added visual red alert banner for overdue invoices
- ⭐ Implemented smart warning messages based on multiple conditions
- ⭐ Extended warning scenario to include customers with payment delays

### Version 1.0 (Initial Release)
- Credit limit configuration per customer
- Multi-level approval workflow
- Email notifications
- Warning and blocking thresholds
- Due amount calculation

## Author

Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

## License

OPL-1 (Odoo Proprietary License v1.0)

## Support

For issues or questions, please contact your system administrator or Odoo support.

---

**Module Name**: sale_account_manager_customer_credit_limit_approval
**Version**: 18.0.1.0.0
**Category**: Sales
**Auto Install**: No
