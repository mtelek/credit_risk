import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, roc_auc_score
from log_regression import OUTPUTS_DIR
import pandas as pd
import numpy as np

def plot_roc_curve(logreg, xgb_model, x_test, y_test):
	# Predicted probabilities
	lr_prob = logreg.predict_proba(x_test)[:, 1]
	xgb_prob = xgb_model.predict_proba(x_test)[:, 1]

	# ROC coordinates
	lr_fpr, lr_tpr, _ = roc_curve(y_test, lr_prob)
	xgb_fpr, xgb_tpr, _ = roc_curve(y_test, xgb_prob)

	# AUC values
	lr_auc = roc_auc_score(y_test, lr_prob)
	xgb_auc = roc_auc_score(y_test, xgb_prob)

	# Plot
	plt.figure(figsize=(6, 6))
	plt.plot(lr_fpr, lr_tpr, label=f"Logistic Regression (AUC = {lr_auc:.3f})")
	plt.plot(xgb_fpr, xgb_tpr, label=f"XGBoost (AUC = {xgb_auc:.3f})")
	plt.plot([0, 1], [0, 1], "k--", label="Random")

	plt.xlabel("False Positive Rate")
	plt.ylabel("True Positive Rate")
	plt.title("ROC Curve Comparison")
	plt.legend()

	plt.savefig(OUTPUTS_DIR / "roc_comparison.png", dpi=300)
	plt.close()

def plot_decile_ks(model, x_test, y_test):
    # Predicted probability of default
    prob = model.predict_proba(x_test)[:, 1]

    # Build DataFrame
    df = pd.DataFrame({
        "prob": prob,
        "target": y_test
    })

    # Highest PD first (riskiest customers)
    df = df.sort_values("prob", ascending=False).reset_index(drop=True)

    # Split into 10 equal-sized groups
    df["decile"] = pd.qcut(df.index, 10, labels=False) + 1

    # Calculate goods/bads per decile
    ks_table = (
        df.groupby("decile")
          .agg(
              bad=("target", "sum"),
              total=("target", "count")
          )
          .reset_index()
    )

    ks_table["good"] = ks_table["total"] - ks_table["bad"]
    # Cumulative percentages
    ks_table["cum_bad"] = ks_table["bad"].cumsum() / ks_table["bad"].sum()
    ks_table["cum_good"] = ks_table["good"].cumsum() / ks_table["good"].sum()
    # KS
    ks_table["KS"] = np.abs(ks_table["cum_bad"] - ks_table["cum_good"])

    # Plot
    plt.figure(figsize=(8,5))
    plt.plot(ks_table["decile"], ks_table["cum_bad"], marker="o", label="Bad loans")
    plt.plot(ks_table["decile"], ks_table["cum_good"], marker="o", label="Good loans")
    max_idx = ks_table["KS"].idxmax()

    plt.vlines(
        ks_table.loc[max_idx, "decile"],
        ks_table.loc[max_idx, "cum_good"],
        ks_table.loc[max_idx, "cum_bad"],
        colors="red",
        linestyles="--",
        label=f"KS = {ks_table.loc[max_idx,'KS']:.3f}"
    )

    plt.xlabel("Risk Decile (1 = Highest PD)")
    plt.ylabel("Cumulative Percentage")
    plt.title("KS Decile Chart")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUTS_DIR / "ks_decile_chart.png", dpi=300)
    plt.close()
