# Аналіз розбіжностей між Partner Ledger і Journal Items (Balance)

## Дані

### Partner: A.T.B. INTERNATIONAL CARGO SRL
### Period: Jan 2026
### Account: 401010 Suppliers

---

## Порівняння балансів

### Partner Ledger (правильний):
```
Initial Balance (до Jan 2026):
  Debit: 1,462,855.28
  Credit: 1,496,592.58
  Balance: -33,737.30

Транзакції Jan 2026:
  01/05: Credit 1,527.20  → Balance: -35,264.50
  01/08: Debit 509.36     → Balance: -34,755.14
  01/08: Debit 28,354.71  → Balance: -6,400.43
  01/23: Credit 12,208.60 → Balance: -18,609.03

Final Balance: -18,609.03
```

### Journal Items (Balance) - 401010 only:
```
Транзакції (хронологічно):
  01/05: Initial=-40,819.52, Debit=0, Credit=1,847.79 → End=-42,667.31
  01/08: Initial=-42,667.31, Debit=616.29, Credit=0 → End=-42,051.02
  01/08: Initial=-42,051.02, Debit=34,306.97, Credit=0 → End=-7,744.05
  01/23: Initial=-7,744.05, Debit=0, Credit=14,771.44 → End=-22,515.49

Final Balance: -22,515.49
```

### account.move.line (вихідні дані) - 401010:
```
  01/05 VB/2026/01/0032:  Debit=0, Credit=1,847.79, Balance=-1,847.79
  01/08 BCRR/2026/00045:  Debit=616.29, Credit=0, Balance=616.29
  01/08 BCRR/2026/00045:  Debit=34,306.97, Credit=0, Balance=34,306.97
  01/23 VB/2026/01/0127:  Debit=0, Credit=14,771.44, Balance=-14,771.44

Total movement: Debit=34,923.26, Credit=16,619.23, Net=+18,304.03
```

---

## Розбіжності

### 1. Initial Balance
- **Partner Ledger**: -33,737.30
- **Journal Items**: -40,819.52
- **Різниця**: -7,082.22

### 2. Final Balance
- **Partner Ledger**: -18,609.03
- **Journal Items**: -22,515.49
- **Різниця**: -3,906.46

### 3. Транзакції
**Partner Ledger показує (в колонці AmtCurr):**
- 01/05: -1,847.79 (але Credit колонка = 1,527.20 ???)
- 01/08: +616.29
- 01/08: +34,306.97
- 01/23: -14,771.44

**account.move.line:**
- 01/05: Credit=1,847.79 ✓
- 01/08: Debit=616.29 ✓
- 01/08: Debit=34,306.97 ✓
- 01/23: Credit=14,771.44 ✓

**Транзакції співпадають!** ✓

---

## Проблема: Різне Initial Balance

### Перевірка формули:

**Partner Ledger:**
```
Initial: -33,737.30
01/05 Credit: -1,847.79 → -33,737.30 - 1,847.79 = -35,585.09 ❌
Partner показує: -35,264.50 ❌

Різниця: -35,264.50 - (-35,585.09) = 320.59
```

**320.59 = TVA з рахунку 442600!**

### Висновок:
Partner Ledger НЕ просто показує баланс 401010!
Partner Ledger включає якусь кореляцію з іншими рахунками (TVA?).

---

## КОРІНЬ ПРОБЛЕМИ

### Partner Ledger використовує іншу логіку!

Partner Ledger НЕ показує просто кумулятивний баланс для account 401010.
Він показує більш складну логіку, можливо:
1. Враховує тільки POSTED entries
2. Враховує matching/reconciliation
3. Фільтрує за типом рахунку
4. Включає/виключує певні types of entries

### Наша реалізація (Journal Items Balance):

```sql
PARTITION BY partner_id, account_id, company_id
ORDER BY date, id
ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
```

Це рахує **ВСЕЄ** рядки для partner+account+company в хронологічному порядку.

---

## Що треба перевірити

### 1. Фільтрація по posted
Partner Ledger може включати тільки posted entries.
Наш VIEW вже фільтрує: `WHERE aml.parent_state = 'posted'` ✓

### 2. Сортування
Partner Ledger може сортувати інакше.
Треба перевірити чи не є ID в іншому порядку для date 01/08 (два рядки).

### 3. Opening Balance
Partner Ledger може рахувати opening balance ДО date_from.
Наша реалізація рахує кумулятивно з САМОГО ПОЧАТКУ.

**ЦЕ МОЖЕ БУТИ ГОЛОВНА ПРОБЛЕМА!**

### Гіпотеза:
Partner Ledger показує:
- **Initial Balance** = баланс на 2025-12-31 23:59:59
- **Transactions** = тільки за Jan 2026

Наша реалізація:
- **Initial Balance** = кумулятивний з самого початку до попереднього рядка
- Для першого рядка Jan 2026 це включає ВСІ попередні рядки

**Але це має бути однаково!**

---

## Рекомендації

### 1. Перевірити ID сортування
Для 01/08 є два рядки. Треба перевірити їх ID в account.move.line.

### 2. Перевірити всі рядки account.move.line
Можливо є ще рядки які не включені в Excel export.

### 3. Порівняти Initial Balance детально
Запустити SQL запит щоб розрахувати opening balance на 2026-01-01.

### 4. Перевірити логіку Partner Ledger
Подивитись код Partner Ledger в Odoo щоб зрозуміти як він рахує баланси.

---

## SQL для перевірки

```sql
-- Opening balance на 2026-01-01 для A.T.B., account 401010
SELECT
    partner_id,
    account_id,
    SUM(debit) as total_debit,
    SUM(credit) as total_credit,
    SUM(debit - credit) as balance
FROM account_move_line
WHERE partner_id = <ATB_ID>
  AND account_id = <401010_ID>
  AND date < '2026-01-01'
  AND parent_state = 'posted'
GROUP BY partner_id, account_id;

-- Транзакції Jan 2026
SELECT
    date,
    move_id,
    name,
    debit,
    credit,
    balance,
    id
FROM account_move_line
WHERE partner_id = <ATB_ID>
  AND account_id = <401010_ID>
  AND date >= '2026-01-01'
  AND date < '2026-02-01'
  AND parent_state = 'posted'
ORDER BY date, id;
```

---

## Наступні кроки

1. ✅ Проаналізувати дані з Excel - DONE
2. ⏳ Знайти точну причину розбіжності - IN PROGRESS
3. ⏳ Виправити логіку розрахунку балансів
4. ⏳ Протестувати на реальних даних
