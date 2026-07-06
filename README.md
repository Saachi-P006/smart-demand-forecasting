# 📦 SmartDemand: AI-Powered Supply Chain Demand Forecasting

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python">
  <img src="https://img.shields.io/badge/Streamlit-Web%20App-red?logo=streamlit">
  <img src="https://img.shields.io/badge/XGBoost-Machine%20Learning-green">
  <img src="https://img.shields.io/badge/Docker-Containerized-blue?logo=docker">
  <img src="https://img.shields.io/badge/PyTest-Tested-success">
  <img src="https://img.shields.io/badge/License-MIT-yellow">
</p>

---

<p align="center">
  <img src="screenshots/Screenshot 2026-07-06 235900.png" width="900">
</p>

---

# 📖 Overview

**SmartDemand** is an AI-powered supply chain demand forecasting platform designed to help retailers and businesses optimize inventory planning through machine learning.

The application predicts future product demand, identifies inventory risks such as overstocking and stock shortages, generates business recommendations, and enables analysts to review forecasts before they are finalized through a Human-in-the-Loop workflow.

Built with scalability and modularity in mind, SmartDemand combines machine learning, data engineering, interactive dashboards, Docker deployment, and automated testing into a production-style application.

---

# ✨ Key Features

## 📈 AI Demand Forecasting

- Machine Learning based demand prediction using XGBoost
- Historical sales analysis
- Time-series forecasting
- Chunk-based processing for large datasets
- Forecast confidence tracking

---

## 📦 Inventory Intelligence

- Overstock detection
- Understock detection
- Inventory risk scoring
- Smart reorder recommendations
- Inventory optimization insights

---

## 👨‍💼 Human-in-the-Loop Review

- Review queue for forecasts
- Approve / Reject workflow
- Reviewer feedback system
- Bulk approval support
- Manual validation before deployment

---

## 📊 Interactive Dashboards

- Business insights dashboard
- Forecast visualization
- Inventory analytics
- Risk monitoring
- Performance metrics

---

## 🚨 Smart Alerts

- Inventory alerts
- Business notifications
- Email alert system
- Critical stock warnings

---

## ⚙️ Engineering Features

- Modular architecture
- Feature engineering pipeline
- Docker support
- Unit testing with PyTest
- Memory-efficient processing
- Easily extendable project structure

---

# 🧠 Machine Learning Workflow

```text
Raw Business Data
        │
        ▼
Data Cleaning & Preprocessing
        │
        ▼
Feature Engineering
        │
        ▼
Model Training (XGBoost)
        │
        ▼
Demand Forecast Generation
        │
        ▼
Inventory Risk Analysis
        │
        ▼
Human Review & Validation
        │
        ▼
Business Dashboard
```

---

# 🏗️ Project Structure

```text
SmartDemand
│
├── data/
│   ├── raw/
│   ├── load_data.py
│   └── processing.py
│
├── features/
│   └── feature_engineering.py
│
├── frontend/
│   ├── components/
│   └── pages/
│
├── models/
│   ├── train.py
│   ├── feedback.py
│   ├── metrics.json
│   └── ...
│
├── tests/
│
├── utils/
│
├── screenshots/
│
├── app.py
├── main.py
├── Dockerfile
├── requirements.txt
└── README.md
```

---

# 📊 Data Sources

The forecasting model leverages multiple business signals including:

- 📦 Product Catalog
- 🛒 Historical Sales
- 🌦️ Weather Data
- 💰 Promotions
- 🏪 Store Capacity
- 🚚 Supplier Lead Time
- 📉 Product Returns
- 👥 Customer Segments
- 🌐 Web Traffic Signals
- 🗓️ Business Events Calendar
- 💲 Competitor Pricing
- 📊 Demand Volatility

---

# 🛠️ Tech Stack

| Category | Technologies |
|-----------|--------------|
| Programming Language | Python |
| Machine Learning | XGBoost, Scikit-learn |
| Data Processing | Pandas, NumPy |
| Visualization | Plotly |
| Web Framework | Streamlit |
| Testing | PyTest |
| Deployment | Docker |

---

# 🚀 Getting Started

## Clone the repository

```bash
git clone https://github.com/Saachi-P006/smart-demand-forecasting.git
```

## Navigate into the project

```bash
cd smart-demand-forecasting
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run the application

```bash
streamlit run app.py
```

---

# 🐳 Docker

## Build Docker Image

```bash
docker build -t smart-demand .
```

## Run Docker Container

```bash
docker run -p 8501:8501 smart-demand
```

---

# 🧪 Run Tests

```bash
pytest
```

---

# 📸 Application Screenshots

## 🏠 Home Dashboard

Displays the overall demand forecasting dashboard.

![Home Dashboard](screenshots/Screenshot%202026-07-06%20235900.png)

---

## 📈 Forecast Dashboard

Shows machine learning based demand forecasts.

![Forecast Dashboard](screenshots/Screenshot%202026-07-07%20001052.png)

---

## 👨‍💼 Reviewer Dashboard

Human-in-the-loop review interface for validating forecasts.

![Reviewer Dashboard](screenshots/Screenshot%202026-07-07%20001257.png)

---

## 📊 Admin Dashboard

Administrative dashboard for monitoring forecasting performance.

![Admin Dashboard](screenshots/Screenshot%202026-07-07%20001448.png)

---

## 🚨 Inventory Alerts

Displays inventory risks and alert notifications.

![Inventory Alerts](screenshots/Screenshot%202026-07-07%20001553.png)

---

## 💼 Business Insights

Business analytics dashboard.

![Business Insights](screenshots/Screenshot%202026-07-07%20001925.png)

---

## 📉 Model Performance

Model metrics and forecasting evaluation.

![Model Performance](screenshots/Screenshot%202026-07-07%20002053.png)

---

# 📈 Future Enhancements

- Real-time forecasting
- Explainable AI (SHAP)
- Cloud deployment (AWS / Azure)
- REST API integration
- User authentication
- Automated model retraining
- CI/CD pipeline
- Database integration

---

# 🎯 Skills Demonstrated

- Machine Learning
- Demand Forecasting
- Data Engineering
- Feature Engineering
- Inventory Analytics
- Human-in-the-Loop AI
- Streamlit Development
- Docker Containerization
- Software Testing
- Modular Software Architecture

---

# 👩‍💻 Author

**Saachi Patwari**

Second-Year Information Technology Student  
Cummins College of Engineering, Pune

GitHub: https://github.com/Saachi-P006

---

## ⭐ If you found this project interesting, consider giving it a star!
