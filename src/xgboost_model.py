from xgboost import XGBClassifier
from log_regression import evaluate_model

def train_xgboost(x_train, y_train, x_test, y_test):
	model = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=42)
	model.fit(x_train, y_train)
	
	train_metrics = evaluate_model(model, x_train, y_train, label="Train")
	test_metrics = evaluate_model(model, x_test, y_test, label="Test")
	
	return model, train_metrics, test_metrics