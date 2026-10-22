"""
Banking Risk & Customer Analysis - SQL Project
Builds a small banking database (SQLite) and answers business questions with SQL.
Run:  python banking_sql_project.py
Creates banking.db and results.md next to this file.
"""
import sqlite3, random, os
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "banking.db")
OUT = os.path.join(HERE, "results.md")
random.seed(42)

SCHEMA = """
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT,
    state         TEXT,
    credit_score  INTEGER,
    annual_income INTEGER,
    join_date     TEXT
);
CREATE TABLE accounts (
    account_id   INTEGER PRIMARY KEY,
    customer_id  INTEGER REFERENCES customers(customer_id),
    account_type TEXT,          -- Checking / Savings
    open_date    TEXT
);
CREATE TABLE transactions (
    txn_id     INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(account_id),
    txn_date   TEXT,
    txn_type   TEXT,            -- Deposit / Withdrawal / Fee
    amount     REAL
);
CREATE TABLE loans (
    loan_id      INTEGER PRIMARY KEY,
    customer_id  INTEGER REFERENCES customers(customer_id),
    loan_type    TEXT,          -- Auto / Personal / Mortgage
    loan_amount  INTEGER,
    status       TEXT,          -- Approved / Denied
    default_risk TEXT           -- Low / Medium / High
);
"""

STATES = ["MN", "MD", "PA", "SD", "TX", "NY"]

def build():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    base = date(2022, 1, 1)
    # customers
    for i in range(1, 61):
        score = random.randint(540, 820)
        income = random.randint(28, 120) * 1000
        con.execute("INSERT INTO customers VALUES (?,?,?,?,?,?)",
                    (i, f"Customer{i}", random.choice(STATES), score, income,
                     str(base + timedelta(days=random.randint(0, 900)))))
    # accounts
    aid = 1
    for cid in range(1, 61):
        for t in (["Checking", "Savings"] if random.random() < 0.6 else ["Checking"]):
            con.execute("INSERT INTO accounts VALUES (?,?,?,?)",
                        (aid, cid, t, str(base + timedelta(days=random.randint(0, 900)))))
            aid += 1
    n_acc = aid - 1
    # transactions
    for tid in range(1, 701):
        a = random.randint(1, n_acc)
        kind = random.choices(["Deposit", "Withdrawal", "Fee"], [45, 48, 7])[0]
        amt = {"Deposit": random.randint(100, 3000),
               "Withdrawal": random.randint(20, 1500),
               "Fee": random.choice([5, 10, 12, 25, 35])}[kind]
        con.execute("INSERT INTO transactions VALUES (?,?,?,?,?)",
                    (tid, a, str(date(2025, 1, 1) + timedelta(days=random.randint(0, 540))), kind, float(amt)))
    # loans: risk and approval driven by credit score and income-to-loan ratio
    lid = 1
    for cid in range(1, 61):
        if random.random() < 0.75:
            row = con.execute("SELECT credit_score, annual_income FROM customers WHERE customer_id=?", (cid,)).fetchone()
            score, income = row
            amount = random.randint(8, 60) * 1000
            ratio = amount / income
            if score >= 700 and ratio < 0.5:
                risk, status = "Low", "Approved"
            elif score >= 640 and ratio < 0.7:
                risk = "Medium"; status = "Approved" if random.random() < 0.8 else "Denied"
            else:
                risk = "High"; status = "Denied" if random.random() < 0.85 else "Approved"
            con.execute("INSERT INTO loans VALUES (?,?,?,?,?,?)",
                        (lid, cid, random.choice(["Auto", "Personal", "Mortgage"]), amount, status, risk))
            lid += 1
    con.commit()
    return con

QUERIES = [
("1. Approval rate by default-risk level",
 "Which risk tiers does the bank approve, and how often?",
 """SELECT default_risk,
       COUNT(*) AS loans,
       SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
       ROUND(100.0 * SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_pct
FROM loans
GROUP BY default_risk
ORDER BY approval_pct DESC;"""),

("2. Average credit score and income by loan outcome (JOIN)",
 "Do approved borrowers really have stronger credit and income?",
 """SELECT l.status,
       COUNT(*) AS loans,
       ROUND(AVG(c.credit_score), 0) AS avg_credit_score,
       ROUND(AVG(c.annual_income), 0) AS avg_income
FROM loans l
JOIN customers c ON c.customer_id = l.customer_id
GROUP BY l.status;"""),

("3. Customer credit tiers (CASE)",
 "How many customers fall in each credit tier, and how much do they earn?",
 """SELECT CASE WHEN credit_score >= 740 THEN 'Excellent (740+)'
            WHEN credit_score >= 670 THEN 'Good (670-739)'
            WHEN credit_score >= 580 THEN 'Fair (580-669)'
            ELSE 'Poor (<580)' END AS credit_tier,
       COUNT(*) AS customers,
       ROUND(AVG(annual_income), 0) AS avg_income
FROM customers
GROUP BY credit_tier
ORDER BY MIN(credit_score) DESC;"""),

("4. Top 5 largest approved loans (RANK window function + subquery)",
 "Who holds the largest approved loans, and how do they rank?",
 """SELECT * FROM (
    SELECT c.name, l.loan_type, l.loan_amount, c.credit_score,
           RANK() OVER (ORDER BY l.loan_amount DESC) AS size_rank
    FROM loans l
    JOIN customers c ON c.customer_id = l.customer_id
    WHERE l.status = 'Approved'
) WHERE size_rank <= 5
ORDER BY size_rank, name;"""),

("5. Monthly deposits vs withdrawals (aggregation + date)",
 "How does cash flow change month to month?",
 """SELECT substr(txn_date, 1, 7) AS month,
       ROUND(SUM(CASE WHEN txn_type='Deposit' THEN amount ELSE 0 END), 0) AS deposits,
       ROUND(SUM(CASE WHEN txn_type='Withdrawal' THEN amount ELSE 0 END), 0) AS withdrawals,
       ROUND(SUM(CASE WHEN txn_type='Deposit' THEN amount
                      WHEN txn_type='Withdrawal' THEN -amount ELSE 0 END), 0) AS net_flow
FROM transactions
GROUP BY month
ORDER BY month
LIMIT 12;"""),

("6. Customers with the most fees (CTE + HAVING)",
 "Which customers pay the most in account fees and may be at risk of leaving?",
 """WITH fees AS (
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
LIMIT 5;"""),

("7. High-risk customers who were still approved (filtering + ratio)",
 "Which approved loans are the riskiest and need monitoring?",
 """SELECT c.name, c.credit_score, c.annual_income, l.loan_type, l.loan_amount,
       ROUND(100.0 * l.loan_amount / c.annual_income, 1) AS loan_to_income_pct
FROM loans l
JOIN customers c ON c.customer_id = l.customer_id
WHERE l.status = 'Approved'
  AND l.default_risk = 'High'
ORDER BY loan_to_income_pct DESC;"""),

("8. Loan type performance",
 "Which loan products are largest and riskiest?",
 """SELECT loan_type,
       COUNT(*) AS loans,
       ROUND(AVG(loan_amount), 0) AS avg_amount,
       SUM(CASE WHEN default_risk='High' THEN 1 ELSE 0 END) AS high_risk_loans
FROM loans
GROUP BY loan_type
ORDER BY avg_amount DESC;"""),
]

def fmt(headers, rows):
    if not rows:
        return "(no rows)"
    cols = list(zip(*([headers] + [[str(x) for x in r] for r in rows])))
    w = [max(len(c) for c in col) for col in cols]
    line = lambda r: "| " + " | ".join(str(x).ljust(w[i]) for i, x in enumerate(r)) + " |"
    return "\n".join([line(headers), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows])

def main():
    con = build()
    md = ["# Banking Risk & Customer Analysis - SQL Results\n",
          "Database: 60 customers, accounts, 700 transactions, and loans (SQLite). All data is synthetic, generated for practice.\n"]
    for title, question, sql in QUERIES:
        cur = con.execute(sql)
        headers = [d[0] for d in cur.description]
        rows = cur.fetchall()
        table = fmt(headers, rows)
        print("\n" + title + "\n" + question + "\n" + table)
        md.append(f"\n## {title}\n*{question}*\n\n```sql\n{sql}\n```\n\n```\n{table}\n```\n")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("\nDone. Saved banking.db and results.md in:", HERE)

if __name__ == "__main__":
    main()
