# Banking Risk & Customer Analysis - SQL Results

Database: 60 customers, accounts, 700 transactions, and loans (SQLite). All data is synthetic, generated for practice.


## 1. Approval rate by default-risk level
*Which risk tiers does the bank approve, and how often?*

```sql
SELECT default_risk,
       COUNT(*) AS loans,
       SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
       ROUND(100.0 * SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_pct
FROM loans
GROUP BY default_risk
ORDER BY approval_pct DESC;
```

```
| default_risk | loans | approved | approval_pct |
|--------------|-------|----------|--------------|
| Low          | 8     | 8        | 100.0        |
| Medium       | 11    | 8        | 72.7         |
| High         | 25    | 4        | 16.0         |
```


## 2. Average credit score and income by loan outcome (JOIN)
*Do approved borrowers really have stronger credit and income?*

```sql
SELECT l.status,
       COUNT(*) AS loans,
       ROUND(AVG(c.credit_score), 0) AS avg_credit_score,
       ROUND(AVG(c.annual_income), 0) AS avg_income
FROM loans l
JOIN customers c ON c.customer_id = l.customer_id
GROUP BY l.status;
```

```
| status   | loans | avg_credit_score | avg_income |
|----------|-------|------------------|------------|
| Approved | 20    | 717.0            | 80700.0    |
| Denied   | 24    | 656.0            | 66917.0    |
```


## 3. Customer credit tiers (CASE)
*How many customers fall in each credit tier, and how much do they earn?*

```sql
SELECT CASE WHEN credit_score >= 740 THEN 'Excellent (740+)'
            WHEN credit_score >= 670 THEN 'Good (670-739)'
            WHEN credit_score >= 580 THEN 'Fair (580-669)'
            ELSE 'Poor (<580)' END AS credit_tier,
       COUNT(*) AS customers,
       ROUND(AVG(annual_income), 0) AS avg_income
FROM customers
GROUP BY credit_tier
ORDER BY MIN(credit_score) DESC;
```

```
| credit_tier      | customers | avg_income |
|------------------|-----------|------------|
| Excellent (740+) | 15        | 75400.0    |
| Good (670-739)   | 15        | 62000.0    |
| Fair (580-669)   | 21        | 81476.0    |
| Poor (<580)      | 9         | 80667.0    |
```


## 4. Top 5 largest approved loans (RANK window function + subquery)
*Who holds the largest approved loans, and how do they rank?*

```sql
SELECT * FROM (
    SELECT c.name, l.loan_type, l.loan_amount, c.credit_score,
           RANK() OVER (ORDER BY l.loan_amount DESC) AS size_rank
    FROM loans l
    JOIN customers c ON c.customer_id = l.customer_id
    WHERE l.status = 'Approved'
) WHERE size_rank <= 5
ORDER BY size_rank, name;
```

```
| name       | loan_type | loan_amount | credit_score | size_rank |
|------------|-----------|-------------|--------------|-----------|
| Customer4  | Auto      | 53000       | 584          | 1         |
| Customer30 | Mortgage  | 52000       | 774          | 2         |
| Customer6  | Personal  | 50000       | 798          | 3         |
| Customer27 | Mortgage  | 48000       | 701          | 4         |
| Customer7  | Auto      | 44000       | 641          | 5         |
```


## 5. Monthly deposits vs withdrawals (aggregation + date)
*How does cash flow change month to month?*

```sql
SELECT substr(txn_date, 1, 7) AS month,
       ROUND(SUM(CASE WHEN txn_type='Deposit' THEN amount ELSE 0 END), 0) AS deposits,
       ROUND(SUM(CASE WHEN txn_type='Withdrawal' THEN amount ELSE 0 END), 0) AS withdrawals,
       ROUND(SUM(CASE WHEN txn_type='Deposit' THEN amount
                      WHEN txn_type='Withdrawal' THEN -amount ELSE 0 END), 0) AS net_flow
FROM transactions
GROUP BY month
ORDER BY month
LIMIT 12;
```

```
| month   | deposits | withdrawals | net_flow |
|---------|----------|-------------|----------|
| 2025-01 | 22778.0  | 8081.0      | 14697.0  |
| 2025-02 | 39611.0  | 12730.0     | 26881.0  |
| 2025-03 | 23364.0  | 10397.0     | 12967.0  |
| 2025-04 | 25107.0  | 13448.0     | 11659.0  |
| 2025-05 | 31910.0  | 16016.0     | 15894.0  |
| 2025-06 | 18791.0  | 10243.0     | 8548.0   |
| 2025-07 | 18928.0  | 11707.0     | 7221.0   |
| 2025-08 | 20912.0  | 16143.0     | 4769.0   |
| 2025-09 | 29529.0  | 7353.0      | 22176.0  |
| 2025-10 | 29299.0  | 21202.0     | 8097.0   |
| 2025-11 | 27369.0  | 17151.0     | 10218.0  |
| 2025-12 | 39879.0  | 18743.0     | 21136.0  |
```


## 6. Customers with the most fees (CTE + HAVING)
*Which customers pay the most in account fees and may be at risk of leaving?*

```sql
WITH fees AS (
    SELECT a.customer_id, COUNT(*) AS fee_count, SUM(t.amount) AS total_fees
    FROM transactions t
    JOIN accounts a ON a.account_id = t.account_id
    WHERE t.txn_type = 'Fee'
    GROUP BY a.customer_id
    HAVING COUNT(*) >= 2
)
SELECT c.name, f.fee_count, f.total_fees
FROM fees f
JOIN customers c ON c.customer_id = f.customer_id
ORDER BY f.total_fees DESC
LIMIT 5;
```

```
| name       | fee_count | total_fees |
|------------|-----------|------------|
| Customer45 | 3         | 72.0       |
| Customer37 | 2         | 60.0       |
| Customer44 | 2         | 60.0       |
| Customer51 | 3         | 60.0       |
| Customer48 | 2         | 47.0       |
```


## 7. High-risk customers who were still approved (filtering + ratio)
*Which approved loans are the riskiest and need monitoring?*

```sql
SELECT c.name, c.credit_score, c.annual_income, l.loan_type, l.loan_amount,
       ROUND(100.0 * l.loan_amount / c.annual_income, 1) AS loan_to_income_pct
FROM loans l
JOIN customers c ON c.customer_id = l.customer_id
WHERE l.status = 'Approved'
  AND l.default_risk = 'High'
ORDER BY loan_to_income_pct DESC;
```

```
| name       | credit_score | annual_income | loan_type | loan_amount | loan_to_income_pct |
|------------|--------------|---------------|-----------|-------------|--------------------|
| Customer30 | 774          | 46000         | Mortgage  | 52000       | 113.0              |
| Customer9  | 682          | 28000         | Mortgage  | 22000       | 78.6               |
| Customer4  | 584          | 103000        | Auto      | 53000       | 51.5               |
| Customer14 | 562          | 86000         | Mortgage  | 38000       | 44.2               |
```


## 8. Loan type performance
*Which loan products are largest and riskiest?*

```sql
SELECT loan_type,
       COUNT(*) AS loans,
       ROUND(AVG(loan_amount), 0) AS avg_amount,
       SUM(CASE WHEN default_risk='High' THEN 1 ELSE 0 END) AS high_risk_loans
FROM loans
GROUP BY loan_type
ORDER BY avg_amount DESC;
```

```
| loan_type | loans | avg_amount | high_risk_loans |
|-----------|-------|------------|-----------------|
| Mortgage  | 17    | 34706.0    | 11              |
| Auto      | 14    | 33214.0    | 8               |
| Personal  | 13    | 33000.0    | 6               |
```
