# User Access Studio: how-to

This document is the operational guide for administrators. The
listing page in `static/description/index.html` is the marketing
view. Both are kept in sync but this one carries the depth.

## Install

`eh_access_studio` depends only on `base`, `mail`, `web`. No optional
packages are required at runtime; the YAML import wizard uses the
`PyYAML` package that ships with Odoo. Install via the Apps menu like
any other Odoo module, or with the standard CLI:

```
odoo-bin -d <db> -i eh_access_studio --stop-after-init
```

After install you have:

* A new top-level menu **Access Studio**.
* Two privilege groups: **Access Studio: User** (read-only) and
  **Access Studio: Manager** (full access).
* A daily scheduled action that deactivates expired profiles.

## Concepts

A **profile** is a named bundle of access overlays applied to a list
of users. A profile owns child rule lines:

| Line type | Hides |
| --- | --- |
| Hidden Menus | menus and submenus |
| Field Rules | fields (invisible / read-only / required) per model |
| Model Rules | per-model toggles for create / edit / delete / archive / duplicate / import / export / spreadsheet / add property, plus toolbar reports / server actions / view types |
| Node Rules | individual buttons, notebook tabs, kanban links, search filters and group-by entries |
| Chatter Rules | per-model chatter widget removal |
| Domain Rules | per-model record-rule overlay with smart placeholders |

Plus profile-level toggles: `hide_chatter`, `hide_send_message`,
`hide_log_note`, `hide_schedule_activity`, `hide_import`,
`hide_export`, `hide_spreadsheet`, `hide_add_property`,
`disable_login`, `disable_debug_mode`, `readonly`.

## Three layers of enforcement

1. **UI hide.** Hidden menus, fields, buttons, tabs, filters and
   chatter. Removes UI surface, does not block the ORM. Use for
   clutter reduction and least-confusion UX.
2. **Per-model toggles.** Hide the create / edit / delete / import /
   export buttons. Drop reports and server actions from the toolbar.
   Hide entire view types. Still UI-only.
3. **Domain Access.** Strict ORM-level gates. AND-ed onto Odoo's
   stock record rules. Blocks server code, the API and any other
   interaction path, not just the UI.

Pick the layer that matches the rule's purpose. Mixing layers is fine
and often correct.

## Smart placeholders

Recognised in the right-value of a domain leaf:

| Placeholder | Resolves to |
| --- | --- |
| `__uid__` | current user id |
| `__cid__` | current company id |
| `__company_ids__` | list of allowed company ids |
| `__today__` | today (date) |
| `__yesterday__` | today minus 1 day |
| `__tomorrow__` | today plus 1 day |
| `__week_start__` ... `__week_end__` | ISO week boundaries |
| `__month_start__` ... `__month_end__` | calendar month boundaries |
| `__quarter_start__` ... `__quarter_end__` | quarter boundaries |
| `__year_start__` ... `__year_end__` | calendar year boundaries |
| `__last_7_days__` ... `__last_365_days__` | rolling windows |

Resolution happens at evaluation time, against the current user, the
current company and today's date. The unit-tested implementation lives
at `tools/domain_resolver.py`.

## Cookbook

### Hide all menus except a single app for a user

1. Create a profile, add the user.
2. Open `Hide Menus`. Add every top-level menu except the one you
   want them to keep.

### Make a user read-only across the system

1. Create a profile, add the user.
2. Tick **Read-Only Mode**.

The system rejects this if the user is in `base.group_system` or
`base.group_erp_manager`. Administrators are never locked out.

### Restrict a sales user to records they own

1. Create a profile, add the user.
2. Open `Domain Access`. Add a row for `sale.order`.
3. Tick **Read** and **Edit** rights, leave **Delete** off.
4. Tick **Apply Filter** and set the domain to:
   ```python
   [("user_id", "=", "__uid__")]
   ```

The user can now see and edit only their own orders. The ORM enforces
the rule, so the API and server code respect it too.

### Time-bound auditor profile

1. Create a profile, add the auditor user.
2. Set **Active From** to today and **Active Until** to the end of the
   audit window.
3. Configure the rules.

A daily cron deactivates the profile once the date passes. The
deactivation is logged in the profile's chatter.

### Block sign-in temporarily

1. Create a profile, add the user.
2. Tick **Disable Login** (on the **Global** tab).

The user is denied at the credential check. A message is posted on the
profile's chatter for audit. Administrators are exempt.

## Quick start: profile templates

`Access Studio -> New from Template` opens a wizard that builds a
fresh profile from a vetted starting point. Four templates ship:

| Template | What you get |
| --- | --- |
| Read-only across the system | Read-Only Mode on. The user can browse but cannot create / edit / delete anywhere. Administrators are exempt. |
| Sales rep: own records only | Domain rule on the chosen model (default `sale.order`) restricting read / edit to records where `user_id` is the current user. Hides Export. |
| Vendor / contractor | Settings menu hidden, Import / Export / Spreadsheet hidden, developer mode disabled, plus a domain rule on `sale.order` for own records. |
| Auditor | Read-Only Mode on, developer mode disabled, time-bounded with an Active Until date. |

Templates are a starting point, not a contract. After the wizard
creates the profile, edit any of the rules normally.

## Health check

`Access Studio -> Profiles -> Action -> Access Studio: health check`
(cog menu on the list view) scans the active configuration and
surfaces:

* profiles with no users assigned (likely orphan)
* profiles with no rules and no global toggles (no-op)
* profiles whose Active Until date has passed but are still active
  (cron has not run, or it failed)
* domain rules whose stored domain does not parse (will fail closed
  at runtime)

Run after a YAML import or any external configuration change.

## Conflict report

`Access Studio -> Profiles -> Action -> Access Studio: conflict
report` flags every user / model pair where two active profiles
disagree on a domain rule. Use to rationalise overlapping profiles
before they confuse end users.

## YAML import / export

`Configuration -> Import / Export` opens a wizard. Export selects a
list of profiles, generates a YAML payload that is downloadable.
Import parses an uploaded YAML and upserts profiles by name. Existing
profiles with the same name are updated; missing profiles are created;
nothing else is touched.

Round-trip tested in `tests/test_yaml_wizard.py`. Payload size capped
at 1 MB to keep the import path memory-safe.

## Troubleshooting

**A user reports "I can't see X" but no profile lists X as hidden.**
Open the profile and click **Summary** in the form header. The
notification lists every active rule and global toggle. Often the
issue is a `hide_export` / `hide_import` global flag the admin
forgot.

**A profile that should apply does not.** Check the cache. The active-
profile cache is keyed on `(uid, cid)` and invalidated on profile
write. If you imported via SQL or external tooling without going
through the ORM, run any tiny edit on the profile to bump the cache.

**A user in two profiles gets unexpected rights.** Run the **conflict
report** server action from the Profiles list view. It surfaces every
user / model pair where two active profiles disagree on a domain rule.

## Engineering rules followed

The module follows the ten engineering rules of the ERP Heritage
suite, documented in `docs/CONTRIBUTING_PROCESS.md`:

* No silent fallbacks. Errors are logged with stack trace.
* Plain Python where possible. The placeholder resolver runs without
  Odoo loaded; 18 unit tests cover every sentinel.
* Atomic counters via SQL where applicable.
* Per-record savepoints in cron loops.
* Strict equality on cache keys.
* Schema-first XML where applicable.
* `ValidationError` in `@api.constrains`, `UserError` in actions.
* Privilege groups, not direct upstream group references.
* Tests cover the bug, not just the feature.
* No vendor names in code or docs that are user-facing.

## Contact

Support, training, custom extensions: `info@erpheritage.com.au`.
