# User Access Studio: positioning

A one-page summary you can paste into a sales conversation, an RFP
response or an internal architecture brief. Every claim here is
verifiable against the source in this repository.

## The problem

Configuring access in Odoo is fragmented. To restrict what one user
sees, an admin opens at least four screens: groups, ir.rule, ir.ui.menu
visibility groups, ir.model.access. The same change often crosses
three or four of these. The result: production access setups that
nobody fully understands, that drift from the documented intent, and
that customers want a single place to manage.

## The Heritage answer

User Access Studio. One LGPL-3 module on Odoo 18 Community.
Depends only on `base`, `mail`, `web`. Around 1,800 lines of model
and wizard code. Stock Odoo domain widget, no fork. Five
`@tools.ormcache`-decorated methods keyed on
`(uid, cid, today, model_name)` for hot-path lookups. Cache
invalidation uses `registry.clear_cache()` (default category only)
plus `signal_changes()` for cross-worker propagation; cron uses bulk
invalidation. Parameterised SQL only. All errors logged with stack
trace, fall-back permissive on view render so a misconfigured rule
never breaks the UI.

## What an admin can do in one screen

* Hide menus, fields, buttons, notebook tabs, kanban links, search
  filters, group-by entries, chatter (system-wide, per-model and
  per-individual-button).
* Per-model toggles for create, edit, delete, archive, duplicate,
  import, export, spreadsheet, add property, hidden view types,
  hidden reports, hidden server actions.
* Per-model record rules (Domain Access) with smart placeholders that
  resolve at evaluation time: `__uid__`, `__cid__`, `__company_ids__`,
  `__today__`, `__week_start__`, `__month_start__`,
  `__quarter_start__`, `__year_start__`, `__last_7_days__` and the
  matching end-of-period and rolling-window values.
* Time-bound profiles with daily cron deactivation.
* Disable login per profile (with audit log on the profile chatter).
* Disable developer mode for the profile (URL-strip via controller).

## What a manager can do in one click

* Quick-start a new profile from a template: read-only viewer, sales
  rep with own records, vendor / contractor portal, time-bound
  auditor.
* Run a health check that flags orphan, no-op, expired and
  unparseable profiles.
* Run a conflict report that flags users in two profiles with
  contradictory domain rules.
* Export profiles to YAML for version control. Re-import is
  idempotent.

## Architecture commitments

| Concern | User Access Studio approach |
| --- | --- |
| Module count | One. |
| Domain editor | Stock Odoo widget. |
| SQL safety | Parameterised SQL only. No `.format()`, no `% (...)`. |
| Cache invalidation | `registry.clear_cache()` (default category only) + `signal_changes()`. Cron uses bulk invalidation. |
| View cache key | Shared by profile, not by user. |
| HTTP coupling | `self.env.companies` only. Models never read HTTP. |
| Error handling | Logged with stack trace, permissive fallback in view render so a misconfigured rule never breaks the UI. |
| Smart placeholders | Explicit sentinels (`__uid__`, `__cid__`, `__today__`, etc.). |
| Test coverage | 18 standalone tests + 12 Odoo test suites. |
| Originality posture | Documented in `docs/ORIGINALITY_AND_LICENSING.md`. |
| License | LGPL-3.0 or later. |

## Risk posture

* **Copyright**: original work. Stock Odoo APIs only. Posture
  documented per-module in `docs/ORIGINALITY_AND_LICENSING.md`.
* **Security**: parameterised SQL, fail-closed on unparseable
  domains, admin lockout impossible, audit log on denied logins.
* **Performance**: ormcaches keyed on `(uid, cid, today, model)`;
  cross-worker invalidation via the registry signaling sequence;
  bulk invalidation in cron.
* **Upgradability**: no fork of Odoo internals. Stock domain widget,
  stock `_postprocess_tag_*` hooks, stock `_compute_domain` extension
  point. Survives Odoo minor upgrades without rebase work.

## Pricing

USD 199 per database. Three months of free support included. Paid
extension available. LGPL-3, so customers retain the source and can
extend without licence fees.

Contact `info@erpheritage.com.au` for procurement, training, or
custom extensions.
