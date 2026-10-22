# AI---Microproject-
# SecureBank AI Fraud Detection Platform

An AI-powered financial security dashboard that detects suspicious transactions, explains fraud predictions, and supports fraud analysis through a conversational AI assistant.

## Key Features

- **AI-Powered Fraud Detection:** Uses an XGBoost machine learning model to classify transactions based on fraud risk.
- **Real-Time Risk Scoring:** Assigns each transaction a risk score between 0 and 1.
- **Behavioral Analysis:** Analyzes transaction velocity, device fingerprints, location deviations, merchant categories, and spending patterns.
- **Explainable AI:** Provides SHAP-style feature attribution to help administrators understand why a transaction was flagged.
- **Gemini AI Assistant:** Enables natural-language queries about suspicious transactions and their risk assessments.
- **Interactive Dashboard:** Displays transaction queues, risk distribution charts, and model performance metrics.
- **Batch CSV Prediction:** Supports uploading CSV files for bulk transaction risk analysis.
- **Admin Authentication:** Restricts dashboard access through an administrative authentication layer.
- **Fraud Investigation Support:** Combines risk scores, feature-level explanations, and conversational AI to assist human decision-making.
- **Performance-Oriented Scoring:** Designed for low-latency transaction analysis, with a reported inference time of under 42 milliseconds.

## Technology Stack

- **Machine Learning:** XGBoost
- **Explainable AI:** SHAP-style feature attribution
- **Conversational AI:** Google Gemini
- **Frontend:** Web-based interactive dashboard
- **Data Processing:** Transaction feature analysis and CSV processing
- **Security:** Admin authentication

## Project Highlights

- Integrates machine learning, explainable AI, and conversational AI in a unified platform.
- Converts fraud predictions into understandable information for administrators.
- Supports both individual transaction review and bulk CSV analysis.
- Provides visual insights into transaction risk and model performance.
- Emphasizes transparency, usability, and efficient fraud investigation.

## Future Enhancements

- Integration with live payment-processing systems.
- Automated model retraining using confirmed fraud outcomes.
- Concept-drift detection and continuous model monitoring.
- Advanced fraud-ring detection using graph-based machine learning.
- Enhanced model validation and production deployment.

## Responsible Use

Fraud risk scores are decision-support signals and should be validated through appropriate human review. Real financial data should be handled securely and in accordance with applicable privacy requirements.
