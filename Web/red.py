from datetime import timedelta
from flask import jsonify
import joblib
import pandas as pd
import requests
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import bcrypt

model = joblib.load("freshcast_xgb_model.joblib")
label_encoder = joblib.load("product_label_encoder.joblib")


df = pd.read_csv("freshcast_dataset.csv")
df['date'] = pd.to_datetime(df['date'])
df.sort_values(['product', 'date'], inplace=True)


def get_weather_forecast(start_date, end_date):
    response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&daily=rain_sum&daily=temperature_2m_mean&start_date={start_date}&end_date={end_date}")
    weather_data = response.json()
    return weather_data


def forecast(product):
    if product not in df['product'].unique():
        return jsonify({"error": "Product not found"}), 404
    
    product_df = df[df['product'] == product].copy()
    product_df = product_df.sort_values('date').tail(10).copy()

    forecast_dates = [
    (product_df['date'].max() + timedelta(days=i+1)).strftime("%Y-%m-%d")
    for i in range(7)
]

    weather = get_weather_forecast(str(forecast_dates[0]), str(forecast_dates[-1]))
    input_data_list = []
    
    for i in range(7):
        input_data = {}
        input_data["temperature"] = weather["daily"]["temperature_2m_mean"][i]
        input_data["rainfall_mm"] = weather["daily"]["rain_sum"][i]
        date_i = pd.to_datetime(weather["daily"]["time"][i])
        input_data["day_of_week"] = date_i.dayofweek
        input_data["month"] = date_i.month
        input_data["product_id"] = label_encoder.transform([product])[0]
        input_data["sales_lag_1"] = product_df.iloc[-1]['sales']
        input_data["sales_lag_2"] = product_df.iloc[-2]['sales']
        input_data["sales_lag_3"] = product_df.iloc[-3]['sales']
        input_data["is_holiday"] = 0

        input_data_list.append(input_data)

    predictions = []

    for i in range(7):
        input_df = pd.DataFrame([input_data_list[i]])[['product_id', 'temperature', 'rainfall_mm', 'is_holiday', 'day_of_week', 'month', 'sales_lag_1', 'sales_lag_2', 'sales_lag_3']]
        pred = model.predict(input_df)[0]
        predictions.append(round(pred))

        # Update lag features for next prediction
        input_data['sales_lag_3'] = input_data['sales_lag_2']
        input_data['sales_lag_2'] = input_data['sales_lag_1']
        input_data['sales_lag_1'] = pred

        input_data['day_of_week'] = (input_data['day_of_week'] + 1) % 7

    return {
        "product": product,
        "dates": [pd.to_datetime(d).strftime("%Y-%m-%d") for d in forecast_dates],
        "predicted": predictions,
        "total": sum(predictions)
    }
    
def forecast_past(product):
    if product not in df['product'].unique():
        return jsonify({"error": "Product not found"}), 404

    product_df = df[df['product'] == product].copy()
    product_df['date'] = pd.to_datetime(product_df['date'])
    product_df = product_df.sort_values('date')

    # Need at least 10 days of data to generate 7 lagged predictions
    if len(product_df) < 10:
        return jsonify({"error": "Not enough data to generate past forecast"}), 400

    past_df = product_df.tail(10).reset_index(drop=True)

    predicted = []
    actual = []
    dates = []

    for i in range(3, 10):
        row = past_df.iloc[i]
        date_i = pd.to_datetime(row['date'])
        dates.append(date_i.strftime("%Y-%m-%d"))
        actual.append(int(row['sales']))

        input_data = {
            'product_id': label_encoder.transform([product])[0],
            'temperature': row['temperature'],
            'rainfall_mm': row['rainfall_mm'],
            'is_holiday': row['is_holiday'],
            'day_of_week': date_i.dayofweek,
            'month': date_i.month,
            'sales_lag_1': past_df.iloc[i-1]['sales'],
            'sales_lag_2': past_df.iloc[i-2]['sales'],
            'sales_lag_3': past_df.iloc[i-3]['sales']
        }

        input_df = pd.DataFrame([input_data])[[
            'product_id', 'temperature', 'rainfall_mm', 'is_holiday',
            'day_of_week', 'month', 'sales_lag_1', 'sales_lag_2', 'sales_lag_3'
        ]]

        pred = model.predict(input_df)[0]
        predicted.append(round(pred))

    return {
        "product": product,
        "dates": dates,
        "actual": actual,
        "predicted": predicted,
        "total_actual": sum(actual),
        "total_predicted": sum(predicted),
        "accuracy": round(100 - abs(((sum(actual) - sum(predicted)) / sum(actual)) * 100), 2),
        "diff": abs(sum(actual) - sum(predicted)),
        "average": round(sum(actual) / len(actual), 2)
    }
    
    
def addUser(name, email, password, users):
    user = {
        "name": name,
        "email": email,
        "password": bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    }

    result = users.insert_one(user)
    user["_id"] = result.inserted_id
    return user