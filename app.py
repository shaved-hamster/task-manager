import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-key-change-before-deploy")

database_url = os.environ.get("DATABASE_URL", "sqlite:///task_manager.db")

# Налаштування драйвера для PostgreSQL
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg2://",
        1
    )

elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1
    )

elif database_url.startswith("postgresql+psycopg://"):
    database_url = database_url.replace(
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Увійдіть, щоб переглянути цю сторінку."


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    tasks = db.relationship("Task", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(
            Task.is_completed.asc(), Task.created_at.desc()
        ).all()
    else:
        tasks = []
    return render_template("index.html", tasks=tasks)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Заповніть усі поля.", "error")
        elif len(password) < 6:
            flash("Пароль має містити щонайменше 6 символів.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Це ім'я користувача вже зайняте.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Користувач із такою поштою вже зареєстрований.", "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Обліковий запис створено. Вітаємо!", "success")
            return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Ви успішно увійшли.", "success")
            return redirect(url_for("index"))
        flash("Неправильна пошта або пароль.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Ви вийшли з облікового запису.", "success")
    return redirect(url_for("index"))


@app.route("/tasks/add", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Введіть назву завдання.", "error")
        else:
            task = Task(title=title, description=description, user_id=current_user.id)
            db.session.add(task)
            db.session.commit()
            flash("Завдання додано.", "success")
            return redirect(url_for("index"))

    return render_template("task_form.html", page_title="Нове завдання", task=None)


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Введіть назву завдання.", "error")
        else:
            task.title = title
            task.description = description
            db.session.commit()
            flash("Зміни збережено.", "success")
            return redirect(url_for("index"))

    return render_template("task_form.html", page_title="Редагувати завдання", task=task)


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.is_completed = not task.is_completed
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Завдання видалено.", "success")
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {"status": "ok"}


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
