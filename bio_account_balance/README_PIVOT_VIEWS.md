# Balance Pivot Views - Usage Guide

## 📊 Two Pivot Options Available

After installing `bio_account_balance`, you have **TWO pivot views** for balance analysis:

---

## 1️⃣ Universal Pivot (Standard + Batch SQL)

**Menu:** `Accounting > Journal Items`

### ✅ Use When:
- Need **flexible date filtering** (custom periods, exact dates)
- Need **all filters** (journal, move, partner, account, etc.)
- Want to **group by any field** (date, partner, account, journal, etc.)
- Need **precise balance** for ANY filtered period

### 🚀 Performance:
- **Optimized with batch SQL** (1 query instead of N)
- Fast for most use cases (~1-5 seconds for 1000+ partners)

### 📌 Features:
- ✅ Full Odoo flexibility - all filters work
- ✅ Any date range (2024-01-15 to 2024-03-20)
- ✅ Group by ANY field (partner, account, journal, date, etc.)
- ✅ Accurate opening/closing for filtered period

### Example Use Cases:
```
✓ "Show partner balances for Q1 2024"
✓ "Filter by specific journal and show daily balances"
✓ "Opening/closing balance for exact date range 2024-02-15 to 2024-02-28"
✓ "Group by partner + account + month with custom filters"
```

### Fields Available:
- `bio_opening_by_partner` - Opening balance (first line in filtered period)
- `bio_closing_by_partner` - Closing balance (last line in filtered period)
- All standard account.move.line fields (debit, credit, balance, etc.)

---

## 2️⃣ Fast Monthly Pivot (SQL VIEW)

**Menu:** `Accounting > Reporting > Monthly Balance (Fast)`

### ✅ Use When:
- Need **super fast** monthly/yearly analysis
- **Monthly granularity** is sufficient (not daily)
- Want **quick overview** without heavy calculations
- Analyzing **trends over time** (months, years)

### 🚀 Performance:
- **~100x faster** than standard pivot!
- Pre-calculated data - instant response
- Perfect for large datasets (10k+ partners)

### 📌 Features:
- ✅ Lightning fast - no calculations needed
- ✅ Pre-aggregated by month
- ✅ Perfect for trends/reports
- ⚠️ Monthly granularity only (cannot filter by day)
- ⚠️ Limited filters (partner, account, year, month only)

### Example Use Cases:
```
✓ "Show monthly balance trends for 2024"
✓ "Compare partner balances across months"
✓ "Yearly balance overview"
✓ "Quick monthly report for management"
```

### Fields Available:
- `opening_balance` - Balance at start of month
- `closing_balance` - Balance at end of month
- `balance_change` - Difference (closing - opening)
- Dimensions: `partner_id`, `account_id`, `year`, `month`, `company_id`

---

## 🤔 Which One Should I Use?

### Decision Tree:

```
Do you need custom date ranges (not just months)?
├─ YES → Use Universal Pivot (account.move.line)
└─ NO → Do you need to filter by journal/move/etc?
    ├─ YES → Use Universal Pivot
    └─ NO → Do you only need monthly/yearly overview?
        ├─ YES → Use Fast Monthly Pivot ⚡
        └─ NO → Use Universal Pivot
```

### Quick Comparison:

| Feature | Universal Pivot | Fast Monthly Pivot |
|---------|----------------|-------------------|
| **Speed** | Fast (batch SQL) | ⚡ **Super Fast** (pre-calculated) |
| **Date Flexibility** | ✅ Any range | ⚠️ Months only |
| **Filters** | ✅ All filters | ⚠️ Limited (partner, account, year, month) |
| **Grouping** | ✅ Any field | ⚠️ Fixed dimensions |
| **Use Case** | Detailed analysis | Quick overview |
| **Best For** | Accounting work | Management reports |

---

## 💡 Pro Tips

### Universal Pivot:
1. **Always filter by date** - improves performance
2. **Use batch optimization** - automatically enabled when grouping by partner
3. **Combine filters** - partner + account + date for precise analysis

### Fast Monthly Pivot:
1. **Default view** shows current year (fast!)
2. **Great for graphs** - visualize balance trends over time
3. **Export to Excel** - pre-calculated data perfect for reports
4. **Use filters** - "Current Year", "Last Year", "Positive/Negative Balance"

---

## 🛠️ Technical Details

### Universal Pivot - How It Works:
```python
# When grouping by partner_id:
# - ONE SQL query for ALL partners (batch optimization)
# - Finds first/last lines within filtered period
# - Sums balances across accounts

# Result: N partners = 1 SQL query (instead of N queries!)
```

### Fast Monthly Pivot - How It Works:
```sql
-- PostgreSQL VIEW pre-calculates:
-- 1. Group lines by partner/account/month
-- 2. Find first line of each month (opening)
-- 3. Find last line of each month (closing)
-- 4. Store results in VIEW for instant access

-- Result: No Python calculations, pure SQL speed! ⚡
```

---

## 🐛 Troubleshooting

### "Monthly pivot shows empty data"
- Ensure module is updated: `./odoo-bin -u bio_account_balance`
- Check posted moves exist
- SQL VIEW should be created automatically on install

### "Universal pivot is slow"
- Add date filter (improves query performance)
- Reduce number of groups (fewer rows = faster)
- Batch SQL activates only when grouping by `partner_id`

### "Balances don't match"
- **Universal pivot** shows balance for **filtered period**
- **Monthly pivot** shows balance for **entire month**
- Different periods = different balances (this is expected!)

---

## 📚 Related Documentation

- **ODOO-834** - Main ticket for balance calculations
- **account_move_line.py** - Source code for batch SQL optimization
- **monthly_balance_view.py** - Source code for SQL VIEW

---

**Questions?** Check module source code or contact development team.

ODOO-834 | Biosphera Accounting Module
