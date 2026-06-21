/*auto generated raw_loans table with zero entries, to be populated by the data pipeline*/
CREATE TABLE IF NOT EXISTS accepted_loans (
    loan_status             SMALLINT,
    issue_d                 TEXT,
    id                      NUMERIC,
    loan_amnt               NUMERIC,
    term                    INTEGER,
    int_rate                NUMERIC,
    installment             NUMERIC,
    grade                   TEXT,
    sub_grade               TEXT,
    emp_length              INTEGER,
    home_ownership          TEXT,
    annual_inc              NUMERIC,
    verification_status     TEXT,
    purpose                 TEXT,
    addr_state              TEXT,
    dti                     NUMERIC,
    fico_range_low          NUMERIC,
    fico_range_high         NUMERIC,
    delinq_2yrs             NUMERIC,
    inq_last_6mths          NUMERIC,
    open_acc                NUMERIC,
    pub_rec                 NUMERIC,
    revol_bal               NUMERIC,
    total_rev_hi_lim        NUMERIC,
    revol_util              NUMERIC,
    total_acc               NUMERIC,
    mort_acc                NUMERIC,
    pub_rec_bankruptcies     NUMERIC,
    tax_liens               NUMERIC,
    earliest_cr_line                    TEXT,
    credit_utilization                  NUMERIC,
    months_since_earliest_credit_line   INTEGER
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
      CASE
        WHEN lower(trim(loan_status)) = 'fully paid'                THEN 0
        WHEN lower(trim(loan_status)) IN ('charged off', 'default') THEN 1
      END::SMALLINT,
      issue_d,
      NULLIF(TRIM(id),                   '')::NUMERIC,
      NULLIF(TRIM(loan_amnt),            '')::NUMERIC,
      NULLIF(REGEXP_REPLACE(term,        '[^0-9]', '', 'g'), '')::INTEGER,
      NULLIF(TRIM(int_rate),             '')::NUMERIC,
      NULLIF(TRIM(installment),          '')::NUMERIC,
      grade,
      sub_grade,
      CASE
        WHEN emp_length = '10+ years' THEN 10
        WHEN emp_length = '< 1 year'  THEN 0
        ELSE NULLIF(REGEXP_REPLACE(emp_length, '[^0-9]', '', 'g'), '')::INTEGER
      END::INTEGER,
      home_ownership,
      NULLIF(TRIM(annual_inc),           '')::NUMERIC,
      verification_status,
      purpose,
      addr_state,
      NULLIF(TRIM(dti),                  '')::NUMERIC,
      NULLIF(TRIM(fico_range_low),       '')::NUMERIC,
      NULLIF(TRIM(fico_range_high),      '')::NUMERIC,
      NULLIF(TRIM(delinq_2yrs),          '')::NUMERIC,
      NULLIF(TRIM(inq_last_6mths),       '')::NUMERIC,
      NULLIF(TRIM(open_acc),             '')::NUMERIC,
      NULLIF(TRIM(pub_rec),              '')::NUMERIC,
      NULLIF(TRIM(revol_bal),            '')::NUMERIC,
      NULLIF(TRIM(total_rev_hi_lim),     '')::NUMERIC,
      NULLIF(TRIM(revol_util),           '')::NUMERIC,
      NULLIF(TRIM(total_acc),            '')::NUMERIC,
      NULLIF(TRIM(mort_acc),             '')::NUMERIC,
      NULLIF(TRIM(pub_rec_bankruptcies), '')::NUMERIC,
      NULLIF(TRIM(tax_liens),            '')::NUMERIC,
      earliest_cr_line
    FROM stg_accepted_loans
    WHERE lower(trim(loan_status)) IN ('charged off', 'default', 'fully paid');

    /*Remove rows where 70% or more columns are null - IS NULL works on all typed columns*/
    DELETE FROM accepted_loans
    WHERE (
      CASE WHEN loan_status          IS NULL THEN 1 ELSE 0 END +
      CASE WHEN issue_d              IS NULL OR BTRIM(issue_d) = '' THEN 1 ELSE 0 END +
      CASE WHEN id                   IS NULL THEN 1 ELSE 0 END +
      CASE WHEN loan_amnt            IS NULL THEN 1 ELSE 0 END +
      CASE WHEN term                 IS NULL THEN 1 ELSE 0 END +
      CASE WHEN int_rate             IS NULL THEN 1 ELSE 0 END +
      CASE WHEN installment          IS NULL THEN 1 ELSE 0 END +
      CASE WHEN grade                IS NULL OR BTRIM(grade) = '' THEN 1 ELSE 0 END +
      CASE WHEN sub_grade            IS NULL OR BTRIM(sub_grade) = '' THEN 1 ELSE 0 END +
      CASE WHEN emp_length           IS NULL THEN 1 ELSE 0 END +
      CASE WHEN home_ownership       IS NULL OR BTRIM(home_ownership) = '' THEN 1 ELSE 0 END +
      CASE WHEN annual_inc           IS NULL THEN 1 ELSE 0 END +
      CASE WHEN verification_status  IS NULL OR BTRIM(verification_status) = '' THEN 1 ELSE 0 END +
      CASE WHEN purpose              IS NULL OR BTRIM(purpose) = '' THEN 1 ELSE 0 END +
      CASE WHEN addr_state           IS NULL OR BTRIM(addr_state) = '' THEN 1 ELSE 0 END +
      CASE WHEN dti                  IS NULL THEN 1 ELSE 0 END +
      CASE WHEN fico_range_low       IS NULL THEN 1 ELSE 0 END +
      CASE WHEN fico_range_high      IS NULL THEN 1 ELSE 0 END +
      CASE WHEN delinq_2yrs          IS NULL THEN 1 ELSE 0 END +
      CASE WHEN inq_last_6mths       IS NULL THEN 1 ELSE 0 END +
      CASE WHEN open_acc             IS NULL THEN 1 ELSE 0 END +
      CASE WHEN pub_rec              IS NULL THEN 1 ELSE 0 END +
      CASE WHEN revol_bal            IS NULL THEN 1 ELSE 0 END +
      CASE WHEN total_rev_hi_lim     IS NULL THEN 1 ELSE 0 END +
      CASE WHEN revol_util           IS NULL THEN 1 ELSE 0 END +
      CASE WHEN total_acc            IS NULL THEN 1 ELSE 0 END +
      CASE WHEN mort_acc             IS NULL THEN 1 ELSE 0 END +
      CASE WHEN pub_rec_bankruptcies IS NULL THEN 1 ELSE 0 END +
      CASE WHEN tax_liens            IS NULL THEN 1 ELSE 0 END +
      CASE WHEN earliest_cr_line     IS NULL OR BTRIM(earliest_cr_line) = '' THEN 1 ELSE 0 END
    )::NUMERIC / 30 >= 0.70;

    UPDATE accepted_loans
    SET
      credit_utilization = CASE
        WHEN NULLIF(total_rev_hi_lim, 0) IS NULL THEN NULL
        ELSE ROUND(revol_bal / NULLIF(total_rev_hi_lim, 0), 4)
      END,
      months_since_earliest_credit_line = CASE
        WHEN issue_d IS NULL OR earliest_cr_line IS NULL THEN NULL
        ELSE (
          EXTRACT(YEAR FROM age(
            to_date(issue_d, 'Mon-YYYY'),
            to_date(earliest_cr_line, 'Mon-YYYY')
          )) * 12
          + EXTRACT(MONTH FROM age(
            to_date(issue_d, 'Mon-YYYY'),
            to_date(earliest_cr_line, 'Mon-YYYY')
          ))
        )::INT
    END;
  END IF;
END $$;
