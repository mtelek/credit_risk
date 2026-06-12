/*auto generated raw_loans table with zero entries, to be populated by the data pipeline*/
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
    pub_rec_bankruptcies     TEXT,
    tax_liens               TEXT,
    earliest_cr_line        TEXT
);

/*Populate accepted_loans from staging table only once, when accepted_loans is empty*/
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM accepted_loans LIMIT 1) THEN
    INSERT INTO accepted_loans (
      loan_status, issue_d, id, loan_amnt, term, int_rate, installment, grade, sub_grade,
      emp_length, home_ownership, annual_inc, verification_status, purpose, addr_state, dti,
      fico_range_low, fico_range_high, delinq_2yrs, inq_last_6mths, open_acc, pub_rec,
      revol_bal, total_rev_hi_lim, revol_util, total_acc, mort_acc, pub_rec_bankruptcies,
      tax_liens, earliest_cr_line
    )
    SELECT
      loan_status, issue_d, id, loan_amnt, term, int_rate, installment, grade, sub_grade,
      emp_length, home_ownership, annual_inc, verification_status, purpose, addr_state, dti,
      fico_range_low, fico_range_high, delinq_2yrs, inq_last_6mths, open_acc, pub_rec,
      revol_bal, total_rev_hi_lim, revol_util, total_acc, mort_acc, pub_rec_bankruptcies,
      tax_liens, earliest_cr_line
    FROM stg_accepted_loans;

    /*Remove rows where 70% or more columns are empty/null*/
    DELETE FROM accepted_loans a
    WHERE (
      SELECT COUNT(*) FILTER (WHERE COALESCE(BTRIM(v), '') = '')
      FROM jsonb_each_text(to_jsonb(a)) AS t(k, v)
    )::NUMERIC
    /
    (
      SELECT COUNT(*)
      FROM jsonb_object_keys(to_jsonb(a))
    ) >= 0.70;

    ALTER TABLE accepted_loans
      ALTER COLUMN id TYPE NUMERIC USING NULLIF(TRIM(id), '')::NUMERIC,
      ALTER COLUMN loan_amnt TYPE NUMERIC USING NULLIF(TRIM(loan_amnt), '')::NUMERIC,
      ALTER COLUMN int_rate TYPE NUMERIC USING NULLIF(TRIM(int_rate), '')::NUMERIC,
      ALTER COLUMN installment TYPE NUMERIC USING NULLIF(TRIM(installment), '')::NUMERIC,
      ALTER COLUMN annual_inc TYPE NUMERIC USING NULLIF(TRIM(annual_inc), '')::NUMERIC,
      ALTER COLUMN dti TYPE NUMERIC USING NULLIF(TRIM(dti), '')::NUMERIC,
      ALTER COLUMN fico_range_low TYPE NUMERIC USING NULLIF(TRIM(fico_range_low), '')::NUMERIC,
      ALTER COLUMN fico_range_high TYPE NUMERIC USING NULLIF(TRIM(fico_range_high), '')::NUMERIC,
      ALTER COLUMN delinq_2yrs TYPE NUMERIC USING NULLIF(TRIM(delinq_2yrs), '')::NUMERIC,
      ALTER COLUMN inq_last_6mths TYPE NUMERIC USING NULLIF(TRIM(inq_last_6mths), '')::NUMERIC,
      ALTER COLUMN open_acc TYPE NUMERIC USING NULLIF(TRIM(open_acc), '')::NUMERIC,
      ALTER COLUMN pub_rec TYPE NUMERIC USING NULLIF(TRIM(pub_rec), '')::NUMERIC,
      ALTER COLUMN revol_bal TYPE NUMERIC USING NULLIF(TRIM(revol_bal), '')::NUMERIC,
      ALTER COLUMN total_rev_hi_lim TYPE NUMERIC USING NULLIF(TRIM(total_rev_hi_lim), '')::NUMERIC,
      ALTER COLUMN revol_util TYPE NUMERIC USING NULLIF(TRIM(revol_util), '')::NUMERIC,
      ALTER COLUMN total_acc TYPE NUMERIC USING NULLIF(TRIM(total_acc), '')::NUMERIC,
      ALTER COLUMN mort_acc TYPE NUMERIC USING NULLIF(TRIM(mort_acc), '')::NUMERIC,
      ALTER COLUMN pub_rec_bankruptcies TYPE NUMERIC USING NULLIF(TRIM(pub_rec_bankruptcies), '')::NUMERIC,
      ALTER COLUMN tax_liens TYPE NUMERIC USING NULLIF(TRIM(tax_liens), '')::NUMERIC,
      ALTER COLUMN term TYPE INTEGER USING NULLIF(REGEXP_REPLACE(term, '[^0-9]', '', 'g'), '')::INTEGER,
      ALTER COLUMN emp_length TYPE INTEGER USING CASE
        WHEN emp_length = '10+ years' THEN 10
        WHEN emp_length = '< 1 year' THEN 0
        ELSE NULLIF(REGEXP_REPLACE(emp_length, '[^0-9]', '', 'g'), '')::INTEGER
      END;
  END IF;
END $$;
