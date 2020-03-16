import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cash = db.execute("SELECT cash FROM users WHERE id = :id",
                      id=session["user_id"])
    shares = db.execute(
        "SELECT symbol, SUM(shares) as Total FROM transaction_history WHERE id = :id GROUP BY symbol", id=session["user_id"])
    portfolio = []
    for holding in shares:
        shareInfo = lookup(holding["symbol"])
        portfolio.append({"name": shareInfo["name"], "symbol": holding["symbol"], "shares": holding["Total"],
                          "price": shareInfo["price"], "total": shareInfo["price"] * holding["Total"]})

    portfolioValue = 0
    for x in portfolio:
        portfolioValue += x["total"]
    portfolioValue += cash[0]["cash"]

    return render_template("index.html", portfolio=portfolio, cash=usd(cash[0]["cash"]), portfolioValue=usd(portfolioValue))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("must provide company symbol", 400)

        if not (shares % 1 == 0):
            return apology("must provide an integer number of shares", 400)

        if lookup(symbol) == None:
            return apology("invalid symbol", 400)

        stockInfo = lookup(symbol)
        price = stockInfo["price"]

        cash = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        if cash[0]["cash"] >= price * shares:
            db.execute("INSERT INTO transaction_history (id, symbol, shares, price, timestamp) VALUES (:id, :symbol, :shares, :price, CURRENT_TIMESTAMP)",
                       id=session["user_id"], symbol=symbol, shares=shares, price=price)
            db.execute("UPDATE users SET cash = cash - (:price * :shares) WHERE id = :id",
                       id=session["user_id"], price=price, shares=shares)
            return redirect("/")

        elif cash[0]["cash"] < price * shares:
            return apology("can't afford", 400)

    if request.method == "GET":
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    username = request.args.get('username')
    """Return true if username available, else false, in JSON format"""
    existing = db.execute(
        "SELECT * FROM users WHERE username=:username", username=username)
    if existing:
        return "False"
    elif len(username) != 0:
        return "True"

    # need to take input of username and store in a variable username
    # query database 'users' to see if there is any user.username = username
    # return true to username if there ISN'T and false if there IS
    # use ajax to change register such that it calls this route when someone types in an input username
    # if this function returns false, dynamically display a JS alert saying it's taken
    # if this function returns true, then actually submit the form to the database, creating a new user


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transaction_history_list = db.execute(
        "SELECT symbol, shares, price, timestamp FROM transaction_history WHERE id = :id", id=session["user_id"])
    return render_template("history.html", transaction_history_list=transaction_history_list)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        symbol = request.form.get("symbol")

        if lookup(symbol) == None:
            return apology("invalid symbol", 400)

        stockInfo = lookup(symbol)
        name = stockInfo['name']
        price = stockInfo['price']
        symbol = stockInfo['symbol']

        return render_template("quoted.html", companyName=name, symbol=symbol, latestPrice=price)

    if request.method == "GET":
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        # Ensure username was submitted
        if not username or username == "":
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide both password AND confirmation", 400)

        # Ensure the confirmation password matches the original password
        if not (request.form.get("password") == request.form.get("confirmation")):
            return apology("passwords did not match", 400)

        hashWord = generate_password_hash(request.form.get("password"))
        # once confident in input validity, store username and hashed version of password in database
        db.execute("INSERT into users (username, hash) VALUES (:username, :hashW)",
                   username=username, hashW=hashWord)
        # rows = db.execute("SELECT * FROM users WHERE username = :username AND hash = :hashW", username=username, hashW=hashWord)
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username", username=username)
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        # Redirect user to home page
        return redirect("/")

    if request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        symbols = db.execute(
            "SELECT symbol FROM transaction_history WHERE id=:id GROUP BY symbol", id=session["user_id"])
        return render_template("sell.html", symbols=symbols)

    if request.method == "POST":
        symbol = request.form.get("fourLetters")
        sharesToSell = int(request.form.get("NOshares")[0])
        stockInfo = lookup(symbol)
        price = stockInfo['price']

        if not symbol:
            return apology("must choose company symbol", 403)
        if not sharesToSell:
            return apology("must choose integer number of shares to sell", 403)

        db.execute("INSERT INTO transaction_history VALUES (:id, :symbol, :shares, :price, CURRENT_TIMESTAMP)",
                   id=session["user_id"], symbol=symbol, shares=int((-1 * sharesToSell)), price=price)

        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
