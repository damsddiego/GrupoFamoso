# Sales Commission OMAX - Enhanced Version

This module extends the functionality of the Sales Commission OMAX module to allow commission calculations based on the number of days an invoice has been outstanding.

## New Features

### Commission by Days
The module now allows you to configure different commission percentages based on the number of days between the invoice date and due date:

- 0-30 days
- 31-60 days
- 61-90 days
- 90+ days

## Configuration

1. Go to Sales > Sales Commission > Sales Commission
2. Create a new commission or edit an existing one
3. Select "Standard" as the Commission Type
4. Check the "Commission by Days" box
5. Fill in the commission percentages for each day range:
   - 0-30 Days Commission %
   - 31-60 Days Commission %
   - 61-90 Days Commission %
   - 90+ Days Commission %

## How It Works

When an invoice is validated or paid (depending on your commission configuration), the system will:
1. Calculate the difference in days between the invoice date and due date
2. Apply the corresponding commission percentage based on the day range
3. Generate the commission analysis line with the calculated amount

## Example

If you configure:
- 0-30 days: 5%
- 31-60 days: 3%
- 61-90 days: 2%
- 90+ days: 1%

And an invoice has a due date 45 days after the invoice date, the system will apply a 3% commission.

## Notes

- The "Commission by Days" feature only works with "Standard" commission type
- If "Commission by Days" is enabled, the standard commission percentage field is hidden
- At least one commission percentage must be set when "Commission by Days" is enabled