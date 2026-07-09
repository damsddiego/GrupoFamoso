# Odoo Power BI Connector

**Company:** Infintor Solutions

This Odoo module exposes a secure, token-based API endpoint for Power BI integration.

## Features
- API endpoint returns  data in JSON format.
- Access protected by Bearer token (managed via Odoo backend UI).
- UI for managing tokens (create, activate, deactivate, assign to user).
- Permission group for API token management.

## Usage
1. Install this module.
2. Assign users to the **Power BI API Managerr** group.
3. Go to **Power BI API > API Tokens** to create/manage tokens.
4. Create Model records and assighn models and fields.

## Endpoint Example

```
GET http://<your-odoo-server>/api/tables
Authorization: Bearer <token>
```

## Security
- Only tokens marked as "Active" will work.
- Each token is linked to a user for auditing.

---