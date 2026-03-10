# CR Electronic Invoice Credit Limit

This module extends the Costa Rican Electronic Invoice module (`l10n_cr_cr_electronic_invoice`) to limit the creation of credit notes so that their total amount doesn't exceed the original invoice amount.

## Features

- Automatically computes the total amount of credit notes created for each invoice
- Prevents creation of credit notes that would cause the total credit amount to exceed the original invoice amount
- Shows the total credit notes amount on the invoice form view
- Provides clear error messages when limits are exceeded

## Functionality

### Credit Note Limitation
The module implements a constraint that checks:
1. When creating a credit note, it calculates the total amount of all existing credit notes for the same original invoice
2. It adds the current credit note amount to this total
3. If this sum exceeds the original invoice amount, it raises a validation error

### Computed Fields
- `credit_note_total`: Shows the total amount of credit notes created for an invoice

## Installation

1. Add the module to your Odoo addons path
2. Update the apps list
3. Install the "CR Electronic Invoice Credit Limit" module

## Configuration

No additional configuration is required. The module works automatically once installed.

## Usage

1. When creating a credit note from an invoice, the system will automatically check if the total credit amount would exceed the original invoice
2. If the limit would be exceeded, a validation error is shown with details
3. On the invoice form view, you can see the total amount of credit notes already created

## Technical Details

The module extends:
- `account.move` model with computation and constraint methods
- `account.move.line` model with additional validation
- Invoice form view to display credit note totals

## Error Handling

When a credit note exceeds the allowed limit, a detailed error message is displayed showing:
- The total credit notes amount that would result
- The original invoice amount
- The current credit note amount
- The original invoice reference