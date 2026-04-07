# Period Filter Widget

JavaScript/OWL widget для фільтрації періодів в звіті Journal Items Balance.

## 📁 Структура

```
static/src/
├── js/
│   ├── period_filter_button.js       ← OWL Component (dropdown logic)
│   └── period_filter_integration.js  ← ListController patch
├── xml/
│   └── period_filter_widget.xml      ← Templates (UI)
└── scss/
    └── period_filter_widget.scss     ← Styles
```

## 🎯 Як це працює

### 1. **OWL Component** (`period_filter_button.js`)
- Створює dropdown кнопку "Period"
- Обробляє вибір періоду (This Year, This Month, Last Month, Custom)
- Для Custom показує modal з date picker
- Викликає `applyPeriod(start, end)` → оновлює context

### 2. **Controller Integration** (`period_filter_integration.js`)
- Патчить `ListController.prototype`
- В `setup()` додає `this.PeriodFilterButton = PeriodFilterButton`
- Тільки для моделі `bio.account.move.line.report`

### 3. **Template** (`period_filter_widget.xml`)
- **PeriodFilterButton**: Dropdown з опціями
- **Custom Modal**: Date picker для довільного періоду
- **ListView extension**: Додає button через `t-set-slot="control-panel-additional-actions"`

### 4. **View Integration** (NO `js_class` needed!)
- Template розширює `web.ListView`
- Перевіряє `t-if="PeriodFilterButton"` (додається патчем)
- Рендерить `<t t-component="PeriodFilterButton"/>`

## 🔄 Flow: Вибір періоду → SQL filtering

```
User clicks "This Month"
    ↓
PeriodFilterWidget.onThisMonth()
    ↓
applyPeriod('2026-03-01', '2026-03-15')
    ↓
action.doAction(..., additionalContext: {period_start, period_end})
    ↓
Python: search() override reads context
    ↓
SET LOCAL bio.period_start = '2026-03-01'
SET LOCAL bio.period_end = '2026-03-15'
    ↓
SQL: current_setting('bio.period_start')
    ↓
FAST filtering at database level! ⚡
```

## 🎨 UI Elements

### Dropdown Menu:
```
┌─────────────────────────┐
│ 📅 Period ▼            │
├─────────────────────────┤
│ 📅 This Year           │
│ 📅 This Month          │
│ 📅 Last Month          │
├─────────────────────────┤
│ ➕ Custom Period...    │
├─────────────────────────┤
│ 🔗 Advanced (Wizard)   │
└─────────────────────────┘
```

### Custom Modal:
```
┌────────────────────────────────┐
│ 📅 Select Custom Period    ✕  │
├────────────────────────────────┤
│ From Date: [2026-01-01] 📆    │
│ To Date:   [2026-03-15] 📆    │
│                                │
│ ℹ️  Dates will be passed to   │
│    SQL via session variables  │
├────────────────────────────────┤
│           [Cancel] [Apply]     │
└────────────────────────────────┘
```

## 🧪 Testing

### Manual Testing:

1. **Install module** (або upgrade якщо вже встановлено):
   ```bash
   odoo-bin -u bio_account_balance
   ```

2. **Clear browser cache** (важливо для assets!):
   - Hard refresh: Ctrl+Shift+R (або Cmd+Shift+R on Mac)
   - Або відкрити DevTools → Application → Clear storage

3. **Open report**:
   - Accounting → Reporting → Audit Reports → Journal Items Balance

4. **Check for Period button**:
   - Should see "📅 Period" button in control panel (near search bar)
   - Click → dropdown з періодами
   - Select "This Month" → list reloads з filtered data
   - Select "Custom Period..." → modal opens
   - Choose dates → Apply → list reloads

### Browser Console Testing:

```javascript
// Check if widget loaded
odoo.define.modules['bio_account_balance/static/src/js/period_filter_widget']

// Check registry
odoo.__DEBUG__.services['registry'].category('views').get('bio_account_move_line_report_list')
```

## 🐛 Troubleshooting

### Widget not showing?

1. **Check assets loaded**:
   - Open DevTools → Network → filter "period_filter"
   - Should see 3 files loaded (JS, XML, SCSS)

2. **Check console for errors**:
   - Press F12 → Console tab
   - Look for JavaScript errors

3. **Check view uses correct js_class**:
   ```xml
   <tree ... js_class="bio_account_move_line_report_list">
   ```

4. **Restart Odoo server**:
   ```bash
   sudo systemctl restart odoo
   ```

5. **Update module + clear assets**:
   ```bash
   odoo-bin -u bio_account_balance --dev=all
   ```

### Dropdown not working?

- Check Dropdown/DropdownItem imports
- Check OWL version (should be OWL 2 for Odoo 16)
- Check browser console for component errors

### Period not applying?

- Check `applyPeriod()` method
- Check `action.doAction()` call
- Check Python `search()` override receives context
- Check SQL `current_setting()` reads session variables

## 📚 References

- [Odoo OWL Documentation](https://github.com/odoo/owl)
- [Odoo Web Framework](https://www.odoo.com/documentation/16.0/developer/reference/frontend/framework_overview.html)
- [JavaScript Framework](https://www.odoo.com/documentation/16.0/developer/reference/frontend/javascript_reference.html)

## 🔗 Related Files

- `models/account_move_line_report.py` - Python search() override
- `views/account_move_line_report_views.xml` - Tree view з js_class
- `wizard/period_filter_wizard.py` - Alternative wizard approach

---

**Built with ❤️ using OWL 2 for Odoo 16**
