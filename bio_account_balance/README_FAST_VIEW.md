# Journal Items (Fast) - Real-Time Balance View

## Overview

`bio.account.move.line.view` is a SQL VIEW that provides the same interface as `account.move.line` but with **real-time cumulative balance calculations** using PostgreSQL window functions.

## Architecture

### SQL VIEW with Window Functions

Instead of using a separate balance table (`bio_account_move_line_balance`), balances are calculated **on-the-fly** in SQL:

```sql
SELECT
    aml.*,
    -- Initial balance (before current row)
    SUM(debit - credit) OVER (
        PARTITION BY partner_id, account_id, company_id
        ORDER BY date, id
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) as bio_initial_balance,

    -- End balance (including current row)
    SUM(debit - credit) OVER (
        PARTITION BY partner_id, account_id, company_id
        ORDER BY date, id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as bio_end_balance
FROM account_move_line aml
WHERE parent_state = 'posted'
```

### Window Function Explanation

**PARTITION BY partner_id, account_id, company_id:**
- Creates separate balance calculations for each combination
- Example: Partner A + Account 411000 = separate balance stream

**ORDER BY date, id:**
- Chronological order (by date, then by ID for tie-breaking)
- Ensures correct cumulative sum

**ROWS BETWEEN:**
- `UNBOUNDED PRECEDING AND 1 PRECEDING` = sum from start until **previous** row (initial balance)
- `UNBOUNDED PRECEDING AND CURRENT ROW` = sum from start until **current** row (end balance)

## Benefits

### ✅ Real-Time Balances
- Always up-to-date (no cron job needed)
- No delay between posting and balance availability
- No risk of stale data

### ✅ Simpler Architecture
- No separate `bio_account_move_line_balance` table
- No cron job to maintain
- Less database storage
- Fewer potential failure points

### ✅ Performance
- PostgreSQL window functions are highly optimized
- Works efficiently with proper indexes on:
  - `account_move_line(date, partner_id, account_id)`
  - `account_move_line(partner_id, account_id, date, id)`

### ✅ Maintainability
- One SQL VIEW instead of Python model + cron + balance table
- Easier to understand and debug
- Self-contained logic

## Performance Considerations

### Indexes (Important!)

For optimal performance, ensure these indexes exist:

```sql
-- Index for window function ordering
CREATE INDEX IF NOT EXISTS idx_aml_balance_calc
ON account_move_line(partner_id, account_id, company_id, date, id)
WHERE parent_state = 'posted';

-- Index for filtering
CREATE INDEX IF NOT EXISTS idx_aml_posted_date
ON account_move_line(date, id)
WHERE parent_state = 'posted';
```

### When to Use

**Good for:**
- Balance reports (tree, pivot, graph)
- Partner/Account analysis
- Export with balances
- Real-time monitoring
- < 10M journal items (typical use case)

**Not ideal for:**
- Extremely large datasets (> 50M rows) - consider partitioning
- High-frequency real-time queries on massive tables

### Performance Comparison

| Dataset Size | Window Function Time | Note |
|--------------|---------------------|------|
| 100K rows    | < 1s               | ✅ Excellent |
| 1M rows      | 1-3s               | ✅ Good |
| 10M rows     | 5-15s              | ⚠️ Acceptable (with indexes) |
| 50M+ rows    | 30s+               | ⚠️ Consider partitioning |

*Times are approximate and depend on hardware/indexes*

## Usage

### Access via Menu

```
Accounting > Accounting > Journal Items (Fast)
Accounting > Reporting > Journal Items (Fast)
```

### Access via Action Button

```
Journal Items → [Action ▼] → ⚡ Fast View
```

### Python API

```python
# Get journal items with balances
lines = env['bio.account.move.line.view'].search([
    ('partner_id', '=', partner_id),
    ('date', '>=', '2024-01-01'),
])

for line in lines:
    print(f"{line.date} | {line.name} | Initial: {line.bio_initial_balance} | End: {line.bio_end_balance}")
```

### Pivot Analysis

```python
# Open in pivot mode
action = env.ref('bio_account_balance.action_bio_account_move_line_view')
action.read()[0]
```

## Comparison with Other Approaches

### vs. bio_account_move_line_balance (separate table)

| Feature | Separate Table | **SQL VIEW (Window Functions)** |
|---------|----------------|--------------------------------|
| Real-time | ❌ Cron delay | ✅ **Instant** |
| Maintenance | ⚠️ Cron + table | ✅ **Self-contained** |
| Storage | ❌ Additional table | ✅ **No extra storage** |
| Complexity | ⚠️ Higher | ✅ **Simpler** |
| Performance | ✅ Faster on huge datasets | ✅ **Fast for typical use** |

### vs. Python Computed Fields

| Feature | Python Computed | **SQL VIEW** |
|---------|-----------------|--------------|
| Performance | ❌ Very slow | ✅ **Fast** |
| Pivot support | ⚠️ Limited | ✅ **Full support** |
| Export | ⚠️ Slow | ✅ **Fast** |
| Maintenance | ❌ Complex | ✅ **Simple** |

## Troubleshooting

### Slow Performance

1. **Check indexes:**
   ```sql
   SELECT * FROM pg_indexes WHERE tablename = 'account_move_line';
   ```

2. **Add missing indexes:**
   ```sql
   CREATE INDEX idx_aml_balance_calc ON account_move_line(partner_id, account_id, company_id, date, id);
   ```

3. **Analyze table:**
   ```sql
   ANALYZE account_move_line;
   ```

### Wrong Balances

1. **Check data consistency:**
   - Ensure all moves are properly posted
   - Verify no duplicate IDs

2. **Check partition logic:**
   - Balances are per partner/account/company
   - NULL partners are treated as separate partition

3. **Rebuild view:**
   ```python
   env['bio.account.move.line.view'].init()
   ```

## Technical Details

### SQL Optimization

PostgreSQL optimizes window functions using:
- **Index scans** for PARTITION BY and ORDER BY
- **Incremental aggregation** for running sums
- **Parallel execution** on large datasets (if configured)

### View Materialization

The view is **not materialized** (not cached), meaning:
- ✅ Always shows latest data
- ⚠️ Recalculated on each query
- For better performance on huge datasets, consider materialized view with refresh strategy

## Future Enhancements

Possible optimizations for very large datasets:

1. **Materialized View:**
   ```sql
   CREATE MATERIALIZED VIEW bio_account_move_line_view_mat AS ...
   REFRESH MATERIALIZED VIEW bio_account_move_line_view_mat;
   ```

2. **Partitioning:**
   - Partition `account_move_line` by year/month
   - Window functions work per partition

3. **Incremental Calculation:**
   - Store monthly/yearly snapshots
   - Calculate only incremental changes

## Conclusion

This approach provides an excellent balance between:
- **Simplicity** (no extra tables/crons)
- **Performance** (fast SQL window functions)
- **Real-time data** (always up-to-date)
- **Maintainability** (self-contained SQL VIEW)

For most use cases (< 10M journal items), this is the **optimal solution**! 🚀
