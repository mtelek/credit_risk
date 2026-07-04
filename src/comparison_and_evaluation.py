import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, roc_auc_score
from log_regression import OUTPUTS_DIR

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
