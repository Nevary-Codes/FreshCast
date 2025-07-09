from bson import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, url_for
import pandas as pd
import joblib
from datetime import timedelta
from red import forecast, forecast_past, addUser
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from flask_login import login_manager, login_user, LoginManager, login_required
import bcrypt
from models import User

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

load_dotenv()
uri = os.getenv("MONGO_URI")
client = MongoClient(uri)
db = client["FreshCast"]
users = db["Users"]


@login_manager.user_loader
def load_user(user_id):
    user_data = users.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
    
        if not (name and email and password):
            return redirect(url_for("register"))

        user_data = addUser(name, email, password, users)
        
        if "error" in user_data:
            return redirect(url_for("register"))
        login_user(user_data)
        return redirect(url_for("dashboard"))

    # GET request: render the register page
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = users.find_one({"email": email})
        if user and bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            user = User(user)
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    df = pd.read_csv("freshcast_dataset.csv")
    past_forecasts = []
    for i in df["product"].unique():
        past_forecasts.append(forecast_past(i))
        
    return render_template("dashboard.html", past_forecasts=past_forecasts)


@app.route("/overview")
@login_required
def overview():
    df = pd.read_csv("freshcast_dataset.csv")
    max_product = df.groupby("product")["sales"].sum().idxmax()
    max_sales = df.groupby("product")["sales"].sum().max()
    
    future = forecast(max_product)
    past = forecast_past(max_product)
    
    return render_template("overview.html", future=future, past=past, max_sales=max_sales, max_product=max_product)


@app.route("/forecasts")
@login_required
def forecasts():
    selected_product = request.args.get("product", default="Milk (1L)")
    df = pd.read_csv("freshcast_dataset.csv")
    all_products = df["product"].unique()

    past = forecast_past(selected_product)
    future = forecast(selected_product)

    return render_template("forecasts.html", selected_product=selected_product, all_products=all_products, past=past, future=future)


@app.route("/inventory")
@login_required
def inventory():
    df = pd.read_csv("freshcast_dataset.csv")

    df["date"] = pd.to_datetime(df["date"])

    end_date = df["date"].max()
    start_date = end_date - timedelta(days=6)

    recent_df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

    recent_sales = recent_df.groupby("product")["sales"].sum()
    forecasts = []
    for i in recent_sales.keys():
        fore = forecast(i)
        fore["total_sales"] = recent_sales[i]
        forecasts.append(fore)
    return render_template("inventory.html", forecasts=forecasts)

from flask_login import logout_user


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


if __name__ == '__main__':
    app.run(debug=True)