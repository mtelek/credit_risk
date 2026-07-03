from pathlib import Path
import pandas as pd
import scorecardpy as sc
import pickle
from time import perf_counter
import numpy as np
from sklearn.linear_model import LogisticRegression
import statsmodels.api as sm
import re
from dataset_init import _cache_key
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp
from environment import load_db_config

OUTPUTS_DIR = Path("/app/outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

BINS_CACHE_PATH = "/app/data/cache/bins_cache.pkl"
TRAIN_WOE = "/app/data/cache/train_woe.pkl"
TEST_WOE = "/app/data/cache/test_woe.pkl"
WOE_KEY_PATH = "/app/data/keywoe_cache.key"

def apply_woe(train, test, y, force_recompute):
	woe_key_path = Path(WOE_KEY_PATH)
	woe_key = _cache_key(sorted(train.columns.tolist()), y)

	if (not force_recompute and Path(BINS_CACHE_PATH).exists() and Path(TRAIN_WOE).exists() and Path(TEST_WOE).exists() and woe_key_path.exists() and woe_key_path.read_text() == woe_key):
		with open(BINS_CACHE_PATH, "rb") as f:
			bins = pickle.load(f)

		train_woe = pd.read_pickle(TRAIN_WOE)
		test_woe = pd.read_pickle(TEST_WOE)

		print("[INFO] Loaded cached WOE + bins.")
	else:
		print("[INFO] Recomputing WOE...")
		bins = sc.woebin(train, y=y, check_cate_num=False)
		train_woe = sc.woebin_ply(train, bins)
		test_woe = sc.woebin_ply(test, bins)

		with open(BINS_CACHE_PATH, "wb") as f:
			pickle.dump(bins, f)

		train_woe.to_pickle(TRAIN_WOE)
		test_woe.to_pickle(TEST_WOE)
		woe_key_path.write_text(woe_key)
		print("[INFO] Saved WOE + bins cache.")

	y_train = train_woe[y].astype(int)
	y_test = test_woe[y].astype(int)

	x_train = train_woe.drop(columns=[y])
	x_test = test_woe.drop(columns=[y])

	return y_train, x_train, y_test, x_test, bins

def get_iv_table(bins):
	iv_table = pd.DataFrame(
		{
			"variable": list(bins.keys()),
			"iv": [b["total_iv"].iloc[0] for b in bins.values()],
		}
	).sort_values("iv", ascending=False)

	return iv_table

def variable_check(bins, x_train, x_test, corr_thrshold=0.8, iv_threshold=0.02):
	iv_table = get_iv_table(bins)
	iv_table.to_csv(OUTPUTS_DIR / "iv_table.csv", index=False)

	keep_vars = iv_table.loc[iv_table.iv >= iv_threshold, "variable"]
	keep_cols = [f"{c}_woe" for c in keep_vars]
	dropped_low_iv = [c for c in x_train.columns if c not in keep_cols]
	print(f"[INFO] Removed {len(dropped_low_iv)} low-IV variables: {dropped_low_iv}")

	x_train = x_train[keep_cols]
	x_test = x_test[keep_cols]

	corr = x_train.corr().abs()
	upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
	
	to_drop = []
	for col in upper.columns:

		correlated = upper.index[upper[col] > corr_thrshold].tolist()

		for other in correlated:

			iv_col = iv_table.loc[
				iv_table.variable == col.replace("_woe", ""),"iv"].iloc[0]

			iv_other = iv_table.loc[
				iv_table.variable == other.replace("_woe", ""),"iv"].iloc[0]

			if iv_col >= iv_other:
				to_drop.append(other)
			else:
				to_drop.append(col)

	to_drop = list(set(to_drop))
	x_train = x_train.drop(columns=to_drop)
	x_test = x_test.drop(columns=to_drop)
	
	print(f"[INFO] Removed {len(to_drop)} highly correlated variables: {to_drop}")
	return x_train, x_test

def evaluate_model(model, x, y, label="dataset"):
	y_pred_proba = model.predict_proba(x)[:, 1]

	auc = roc_auc_score(y, y_pred_proba)
	gini = 2 * auc - 1

	y_arr = np.asarray(y)
	pos = y_pred_proba[y_arr == 1]
	neg = y_pred_proba[y_arr == 0]
	ks = ks_2samp(pos, neg).statistic

	eval_table = pd.DataFrame({
		"Dataset": [label],
		"AUC": [auc],
		"Gini": [gini],
		"KS": [ks]
	})
	return eval_table

def save_coefficients(model, x_train):
	coef_df = pd.DataFrame({
		"variable": [re.sub("_woe$", "", col) for col in x_train.columns],
		"coefficient": model.coef_[0]
	}).sort_values("coefficient", ascending=False)

	coef_df.to_csv(OUTPUTS_DIR / "logreg_coefficients.csv", index=False)

	return coef_df

def log_regression(train, test):
	#Loade env variables
	cfg = load_db_config()
	#Apply WoE to train and test data
	step_start = perf_counter()
	y = "loan_status"
	y_train, x_train, y_test, x_test, bins = apply_woe(train, test, y, cfg['force_recompute'])
	print(f"[TIMING] apply_woe: {perf_counter() - step_start:.2f}s")
 
	#Variable check - IV calculation, remove low IV vars, correlation matrix, remove one var from highly correlated vars
	x_train, x_test = variable_check(bins, x_train, x_test)

	#Model with Logistic Regression
	step_start = perf_counter()
	logreg = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
	logreg.fit(x_train, y_train)
	print(f"[TIMING] logreg.fit: {perf_counter() - step_start:.2f}s")

	#Train statsmodels Logit model and export coefficient significance summary (coef + p-values)
	x_train_sm = sm.add_constant(x_train)
	sm_model = sm.Logit(y_train, x_train_sm).fit()
	summary_df = pd.DataFrame({
		"coef": sm_model.params,
		"p_value": sm_model.pvalues,
	}).sort_values("coef", ascending=False)
	summary_df.to_csv(OUTPUTS_DIR / "logit_stats.csv")

	#Check coefficients make business sense
	coef_df = save_coefficients(logreg, x_train)

	if cfg['debug_eda'] == True:
		negative_coefs = coef_df[coef_df['coefficient'] < 0]
		if not negative_coefs.empty:
			print("\n[INFO] Unexpected negative coefficients — investigate:")
			print(negative_coefs.to_string(index=False))
		else:
			print("\n[INFO] All coefficients positive — consistent with WOE convention.")

		key_vars = ['dti', 'annual_inc', 'int_rate']
		for var in key_vars:
			if var in bins:
				print(f"\n{var}:")
				print(bins[var][['bin', 'count_distr', 'badprob', 'woe']])
 
	#Evaluate model
	train_metrics = evaluate_model(logreg, x_train, y_train, label="Train")
	test_metrics = evaluate_model(logreg, x_test,  y_test,  label="Test")
 
	return	bins, logreg, x_train, y_train, x_test, y_test, train_metrics, test_metrics
