from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    u_id = (session.get("user_id"))

    sum_data = db.execute("SELECT * FROM users WHERE id = :id", id=u_id)
    trans_data = db.execute("SELECT * FROM trans WHERE user_id = :id", id=u_id)
    port_data = db.execute("SELECT * FROM port WHERE user_id = :id", id=u_id)

    #sum transactions and cash
    cash_total = round(sum_data[0]["cash"], 2)
    port_total = 0
    for i in port_data:
        stock_data = lookup(i["symbol"])
        i["currprice"] = round(stock_data["price"], 2)
        i["gainloss"] = round((((stock_data["price"] * i["shares"]) - i["total"]) / i["total"]) * 100, 2)
        port_total += i["currprice"] * i["shares"]
    total = round(cash_total + port_total, 2)
    total_gain = round((((cash_total + port_total) - 10000) / 10000) * 100, 2)

    return render_template("home.html", total=total, cash_total = cash_total, total_gain = total_gain, stocks=port_data)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        u_id = (session.get("user_id"))

        #validate inputs
        if not request.form.get("ticker"):
            return apology("please enter a ticker")
        elif not request.form.get("quantity"):
            return apology("please enter a quantity")
        elif int(request.form.get("quantity")) < 1:
            return apology("please enter a quantity greater than 0")

        # query database for stock
        stock = request.form.get("ticker")
        stock_data = lookup(stock)
        if not stock_data:
            return apology("Invalid stock name")

        #pre-format fields
        stock = stock.upper()
        price = stock_data["price"]
        quantity = int(request.form.get("quantity"))
        total = price * quantity

        # check user funds
        funds = db.execute("SELECT cash FROM users WHERE id = :id", id=u_id)
        funds = funds[0]["cash"]
 if total > funds:
            return apology("insufficient funds")

        dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        #log transaction
        db.execute("INSERT INTO trans (user_id, symbol, shares, price, total, buy_sell, datetime) VALUES (:id, :sym, :sh, :pr, :tot, 'BUY', :dt)", id=u_id, sym=stock, sh=quantity, pr=price, tot=total, dt=dt)

        #update portfolio
        if db.execute("SELECT symbol FROM port WHERE user_id = :id AND symbol = :stock", id=u_id, stock=stock):
            db.execute("UPDATE port SET shares = shares + :sh, last_price = :pr, total = total + :tot WHERE user_id = :id AND symbol = :stock", id=u_id, stock=stock, sh=quantity, pr=price, tot=total)
        else:
            db.execute("INSERT INTO port (user_id, symbol, shares, last_price, total) VALUES (:id, :sym, :sh, :pr, :tot)", id=u_id, sym=stock, sh=quantity, pr=price, tot=total)

        #exe new cash balance
        db.execute("UPDATE users SET cash = :newcash WHERE id = :id", newcash=funds-total, id=u_id)

        # redirect user to index page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    u_id = (session.get("user_id"))

    sum_data = db.execute("SELECT * FROM users WHERE id = :id", id=u_id)
    trans_data = db.execute("SELECT * FROM trans WHERE user_id = :id", id=u_id)
    port_data = db.execute("SELECT * FROM port WHERE user_id = :id", id=u_id)       