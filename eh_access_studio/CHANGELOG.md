# User Access Studio CHANGELOG

Module: `eh_access_studio`. License LGPL-3.0 or later.

## v18.0.1.0.0 (May 2026, initial release)

### Capabilities
- Hide menus and submenus from navigation.
- Hide fields per-model: invisible / read-only with force-save / required.
- Hide individual buttons, notebook tabs, kanban links, search filters
  and group-by entries by technical name.
- Hide chatter system-wide, per-model, or per-individual-button (Send
  Message / Log Note / Schedule Activity).
- Per-model toggles for create / edit / delete / archive / duplicate /
  import / export / spreadsheet / add property; hidden view types;
  hidden report and server actions.
- Per-model record rules (Domain Access) with smart placeholder
  resolution. Sentinels: `__uid__`, `__cid__`, `__company_ids__`,
  `__today__`, `__yesterday__`, `__tomorrow__`, `__week_start__`,
  `__week_end__`, `__month_start__`, `__month_end__`,
  `__quarter_start__`, `__quarter_end__`, `__year_start__`,
  `__year_end__`, `__last_7_days__`, `__last_30_days__`,
  `__last_90_days__`, `__last_365_days__`.
- Time-bound profiles with `date_from` / `date_until`. Daily cron
  deactivates expired profiles in bulk.
- Disable login per profile, enforced at the credential check. Audit
  message posted on the profile chatter on denial.
- Disable developer mode per profile, enforced via web-client URL
  strip in a controller override.
- Profile-level `readonly` mode (admins exempt by constraint).

### Operations
- Four-template quick-start wizard: read-only, own-records, vendor /
  portal, auditor.
- Health-check action: flags orphan, no-op, expired and unparseable
  profiles.
- Conflict-report action: flags users in two profiles with
  contradictory domain rules on the same model.
- Diagnostic / Summary action: plain-English explanation of every
  rule on a profile.
- Test-plan action: lists target users for ad-hoc impersonation in a
  private browser window.
- Profile duplication action.
- YAML import / export wizard with idempotent re-import (upserts by
  name). 1 MB payload cap.

### Performance and safety
- Five `@tools.ormcache`-decorated methods keyed on
  `(uid, cid, today_iso, model_name)`: `_get_active_profile_ids`,
  `_model_line_ids_for`, `_chatter_visibility_for`,
  `_eh_access_field_rules`, `_eh_access_node_rules`. All sit in the
  default cache category (Odoo 18's ormcache categories are not
  extensible; per-method clear is not exposed by the framework).
- Invalidation via `registry.clear_cache()` (default category only)
  plus a single `registry.signal_changes()` for cross-worker
  propagation. Categories outside the default (assets, templates,
  routing, groups) stay warm.
- Cron deactivation skips per-row invalidation via an
  `eh_access_studio_skip_invalidate` context flag, then fires one
  invalidation + signal at the end of the batch regardless of size.
- Parameterised SQL only. No `.format()` or `% (...)` with values.
- `psycopg2.errors.UndefinedTable` caught in cache lookups so the
  first-install path does not crash before model tables exist.
- Fail-closed on unparseable Domain Access filters: returns
  `[("id", "=", False)]` instead of granting access.
- Admin-in-readonly profile rejected at constraint level. Access
  Studio configuration menu is exempt from any rule that targets it.
- Domain Access bypass for our own configuration tables to keep
  admins out of self-imposed lockouts.

### Schema
- Models: `eh.access.profile` (mail.thread + activity), `eh.access.field`,
  `eh.access.model`, `eh.access.node`, `eh.access.chatter`,
  `eh.access.domain`, plus the abstract `eh.access.line.mixin` for
  CRUD-driven cache invalidation.
- Wizards: `eh.access.yaml.wizard`, `eh.access.template.wizard`.
- Privilege groups: `Access Studio: User` (read-only),
  `Access Studio: Manager` (full).

### Listing and docs
- Heritage dark-and-mint listing page with DM Sans / DM Mono
  typography.
- HOWTO guide with cookbook, three-layer enforcement explainer,
  troubleshooting and engineering-rule cross-reference.
- Four sample YAML files in `docs/examples/` matching the four
  template scenarios.
- Positioning one-pager in `docs/POSITIONING.md`.
- i18n template seeded in `i18n/eh_access_studio.pot`.

### Tests
- 18 standalone resolver tests (no Odoo loaded), runnable via
  `python3 tools/test_domain_resolver.py`.
- 12 Odoo test suites covering: profile lifecycle, hide menu, hide
  field, domain rules, disable login, fail-closed, caching, YAML
  round-trip, conflict and diagnostic, template wizard, health
  check.

### Compliance
- License LGPL-3.0 or later.
- Apps Store: name 22 chars, banner 880x440, icon 140x140, no
  external links, English only, contact `info@erpheritage.com.au`.
- Originality position recorded in
  `../docs/ORIGINALITY_AND_LICENSING.md`.
