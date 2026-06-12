-- auto generated raw_loans table with zero entries, to be populated by the data pipeline
CREATE TABLE IF NOT EXISTS accepted_loans (
    loan_status             TEXT,
    issue_d                 TEXT,
    id                      TEXT,
    loan_amnt               TEXT,
    term                    TEXT,
    int_rate                TEXT,
    installment             TEXT,
    grade                   TEXT,
    sub_grade               TEXT,
    emp_length              TEXT,
    home_ownership          TEXT,
    annual_inc              TEXT,
    verification_status     TEXT,
    purpose                 TEXT,
    addr_state              TEXT,
    dti                     TEXT,
    fico_range_low          TEXT,
    fico_range_high         TEXT,
    delinq_2yrs             TEXT,
    inq_last_6mths          TEXT,
    open_acc                TEXT,
    pub_rec                 TEXT,
    revol_bal               TEXT,
    total_rev_hi_lim        TEXT,
    revol_util              TEXT,
    total_acc               TEXT,
    mort_acc                TEXT,
    pub_ec_bankruptcies     TEXT,
    tax_liens               TEXT,
    earliest_cr_line        TEXT
);

/*Populate accepted_loans from staging table. In a real pipeline, this would be done in batches with transformations and error handling, but for simplicity we are doing it in one step here.*/
INSERT INTO accepted_loans (
loan_status, issue_d, id, loan_amnt, term, int_rate, installment, grade, sub_grade,
emp_length, home_ownership, annual_inc, verification_status, purpose, addr_state, dti,
fico_range_low, fico_range_high, delinq_2yrs, inq_last_6mths, open_acc, pub_rec,
revol_bal, total_rev_hi_lim, revol_util, total_acc, mort_acc, pub_ec_bankruptcies,
tax_liens, earliest_cr_line
)
SELECT loan_status, issue_d, id, loan_amnt, term, int_rate, installment, grade, sub_grade,
emp_length, home_ownership, annual_inc, verification_status, purpose, addr_state, dti,
fico_range_low, fico_range_high, delinq_2yrs, inq_last_6mths, open_acc, pub_rec,
revol_bal, total_rev_hi_lim, revol_util, total_acc, mort_acc, pub_rec_bankruptcies,
tax_liens, earliest_cr_line FROM stg_accepted_loans;

