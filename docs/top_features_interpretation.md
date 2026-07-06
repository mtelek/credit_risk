# Top 5 Most Predictive Features

Before interpreting the final model, it is worth noting that the pipeline first filtered out weak variables. The variables removed for low IV were: addr_state, revol_util, revol_bal, pub_rec_bankruptcies, emp_length, tax_liens, total_acc, delinq_2yrs, pub_rec, open_acc, purpose, credit_utilization, and months_since_earliest_credit_line. The variables removed for high correlation were: int_rate, sub_grade, and fico_range_low. This kept the final model focused on the strongest, least redundant signals.

Based on the logistic regression coefficients and information value (IV) outputs, the strongest retained predictors of default are:

1. Grade
   - This was one of the strongest signals in the model and is a direct proxy for borrower credit quality.
   - Lower grades are associated with higher expected default risk, which is consistent with how lenders normally underwrite loans.

2. Annual income
   - Borrowers with lower income tend to have less financial buffer, making repayment stress more likely.
   - This makes business sense because income level is a core indicator of repayment capacity.

3. Home ownership
   - Borrowers who rent or have less stable housing arrangements often face greater financial volatility.
   - This feature is useful because housing status can reflect stability and overall financial resilience.

4. Term
   - Longer loan terms are linked to higher default probability.
   - This makes sense because longer repayment periods increase exposure to income shocks and changing financial conditions.

5. Debt-to-income ratio (DTI)
   - A higher DTI means a borrower already has a larger share of income committed to debt payments.
   - This is a strong business signal because borrowers with less repayment capacity are more likely to miss payments.

Overall, these retained features reflect the core drivers of credit risk: weaker borrower quality, lower repayment capacity, greater financial instability, and longer repayment exposure.
