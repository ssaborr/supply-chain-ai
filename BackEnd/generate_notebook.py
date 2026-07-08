import json

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# ARIMA Model Evaluation\n",
    "This notebook evaluates the performance of the ARIMA model used for demand forecasting on historical product sales."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import pandas as pd\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "from statsmodels.tsa.arima.model import ARIMA\n",
    "from pymongo import MongoClient\n",
    "from sklearn.metrics import mean_absolute_error, mean_squared_error\n",
    "\n",
    "# 1. Load data from MongoDB\n",
    "client = MongoClient('mongodb://localhost:27017')\n",
    "db = client['smart_supply_chain']\n",
    "query = {'product_id': 191, 'sales': {'$ne': None}}\n",
    "records = list(db['forecasts'].find(query))\n",
    "client.close()\n",
    "\n",
    "df = pd.DataFrame([{\n",
    "    'ds': pd.to_datetime(r['date']),\n",
    "    'y': float(r['sales'])\n",
    "} for r in records])\n",
    "\n",
    "df = df.sort_values(by='ds').reset_index(drop=True)\n",
    "df = df.groupby('ds').agg({'y': 'sum'}).reset_index()\n",
    "df_ts = df.set_index('ds').asfreq('D', fill_value=0.0)\n",
    "print(f'Total historical data points: {len(df_ts)}')"
   ]
  },
  {
   "cell_type": "markdown",
   "source": [
    "## Train-Test Split\n",
    "We split the data, keeping the last 30 days of sales as the test set to evaluate forecast accuracy."
   ],
   "metadata": {}
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "test_days = 30\n",
    "train_data = df_ts.iloc[:-test_days]\n",
    "test_data = df_ts.iloc[-test_days:]\n",
    "print(f'Train set: {len(train_data)} days, Test set: {len(test_data)} days')"
   ]
  },
  {
   "cell_type": "markdown",
   "source": [
    "## Fit ARIMA Model\n",
    "We fit the ARIMA(1, 1, 1)x(1, 0, 1, 7) model on the training set."
   ],
   "metadata": {}
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "model = ARIMA(train_data['y'], order=(1, 1, 1), seasonal_order=(1, 0, 1, 7))\n",
    "model_fit = model.fit()\n",
    "print(model_fit.summary())"
   ]
  },
  {
   "cell_type": "markdown",
   "source": [
    "## Forecast and Evaluate Accuracy Metrics\n",
    "We generate predictions on the test set timeframe and compute Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and Mean Absolute Percentage Error (MAPE)."
   ],
   "metadata": {}
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "predictions = model_fit.forecast(steps=test_days)\n",
    "predictions = predictions.clip(lower=0.0)\n",
    "\n",
    "# Compute metrics\n",
    "mae = mean_absolute_error(test_data['y'], predictions)\n",
    "rmse = np.sqrt(mean_squared_error(test_data['y'], predictions))\n",
    "mape = np.mean(np.abs((test_data['y'] - predictions) / (test_data['y'] + 1e-5))) * 100\n",
    "\n",
    "print('ARIMA Evaluation Metrics:')\n",
    "print(f'  MAE:  {mae:.2f} units')\n",
    "print(f'  RMSE: {rmse:.2f} units')\n",
    "print(f'  MAPE: {mape:.2f}%')"
   ]
  },
  {
   "cell_type": "markdown",
   "source": [
    "## Plot Actual vs Forecasted values"
   ],
   "metadata": {}
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "plt.figure(figsize=(12, 6))\n",
    "plt.plot(train_data.index[-60:], train_data['y'].iloc[-60:], label='Historical Sales (Last 60 Days)', color='green')\n",
    "plt.plot(test_data.index, test_data['y'], label='Actual Sales (Test Set)', color='blue')\n",
    "plt.plot(test_data.index, predictions, label='ARIMA Forecast', color='orange', linestyle='--')\n",
    "plt.title('ARIMA Demand Forecast Validation')\n",
    "plt.xlabel('Date')\n",
    "plt.ylabel('Sales Volume')\n",
    "plt.legend()\n",
    "plt.grid(True)\n",
    "plt.show()"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.11.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

with open(r'c:\Users\Sabor\Desktop\project\arima_model_evaluation.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)
print("Notebook generated successfully!")
