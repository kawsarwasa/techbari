# TechBari Inventory Phase 1 — v1.1.0

Inventory Phase 1 introduces the stock engine used by future Purchase, Online Order, POS and Return modules.

## Architecture

`Product -> ProductVariant/SKU -> InventoryBalance -> Warehouse`

Every physical or reserved stock change writes a `StockMovement` ledger entry. `ProductVariant.stock_quantity` remains only as a backward-compatible available-stock cache for the existing catalog/storefront; inventory balances are authoritative.

## Database entities

- `Warehouse`
- `InventoryBalance`
- `StockMovement`
- `StockAdjustment`
- `StockTransfer`
- `StockTransferItem`

## Warehouse stock

Each `(warehouse, variant)` has one unique balance with:

- on-hand quantity
- reserved quantity
- available quantity = on hand - reserved
- low-stock threshold

## Stock movement ledger

Supported movement types include:

- Opening Stock
- Purchase In
- Online Sale Out
- POS Sale Out
- Sales Return In
- Purchase Return Out
- Adjustment In / Out
- Transfer In / Out
- Damage / Loss Out
- Reserve / Release
- Reserved Stock Sold

Movement rows store SKU/product snapshots, before/after state, reference, note, actor and timestamp. The application model blocks editing/deleting individual ledger rows.

## Atomic services

`inventory.services` provides transaction-safe operations using `transaction.atomic()` and row locking with `select_for_update()`:

- `post_movement(...)`
- `adjust_stock(...)`
- `transfer_stock(...)`
- `reserve_stock(...)`
- `release_reserved_stock(...)`
- `issue_reserved_stock(...)`

Negative stock and transferring reserved stock are rejected.

## Existing catalog stock migration

Migration `inventory.0002_import_catalog_opening_stock` creates the default `MAIN` warehouse and imports every existing `ProductVariant.stock_quantity` as opening stock without changing the catalog quantity. Existing low-stock alert values are copied to the warehouse/SKU balance.

New catalog variants automatically receive an inventory balance. Legacy catalog stock-field edits are reconciled through auditable inventory movements instead of bypassing the ledger.

## Dashboard routes

- `/dashboard/inventory/` — balances and thresholds
- `/dashboard/warehouses/` — warehouse management
- `/dashboard/warehouses/add/` — add/edit warehouse
- `/dashboard/stock-adjustment/` — counted-stock adjustment
- `/dashboard/stock-transfer/` — multi-SKU warehouse transfer
- `/dashboard/inventory/movements/` — movement ledger
- `/dashboard/inventory/low-stock/` — low/out-of-stock report

## Apply locally

```powershell
python manage.py migrate
python manage.py check
python manage.py test catalog inventory
python manage.py runserver
```

Do not run a destructive catalog reseed. The inventory migration imports current variant stock automatically.

## Next phase

Serial / IMEI / Warranty tracking should build on `Warehouse`, `InventoryBalance` and `StockMovement`. Purchase, Sales Order, POS and Returns should call the inventory service layer rather than writing stock fields directly.
