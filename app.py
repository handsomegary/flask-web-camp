"""A complete version of the Flask camp's profile and SQLite todo app."""

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask, flash, redirect, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect, FlaskForm
from flask_wtf.csrf import CSRFError
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


db = SQLAlchemy()
csrf = CSRFProtect()


class Tasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(200), nullable=False)
    date_added = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Tasks {self.id} {self.task_name!r}>"


class TodoForm(FlaskForm):
    todo = StringField(
        "想做些什麼？",
        filters=[lambda value: value.strip() if value else value],
        validators=[
            DataRequired(message="請輸入待辦事項。"),
            Length(max=200, message="待辦事項最多 200 個字。"),
        ],
    )
    submit = SubmitField("新增待辦")


class DeleteForm(FlaskForm):
    submit = SubmitField("刪除")


def _local_secret(instance_path):
    """Keep local sessions valid across restarts without a key in source control."""
    secret_path = Path(instance_path) / ".secret_key"
    try:
        with secret_path.open("x", encoding="utf-8") as stream:
            secret = secrets.token_hex(32)
            stream.write(secret)
            return secret
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip()


def create_app(test_config=None, *, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///tasks.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = _local_secret(app.instance_path)

    db.init_app(app)
    csrf.init_app(app)
    with app.app_context():
        db.create_all()

    @app.get("/")
    def home():
        next_task = db.session.scalar(
            db.select(Tasks).order_by(Tasks.date_added, Tasks.id).limit(1)
        )
        task_count = db.session.scalar(db.select(db.func.count(Tasks.id)))
        return render_template("index.html", todo=next_task, task_count=task_count)

    @app.get("/user/<name>")
    def user(name):
        return render_template("user.html", name=name)

    @app.route("/todo", methods=["GET", "POST"])
    def todo():
        form = TodoForm()
        if form.validate_on_submit():
            db.session.add(Tasks(task_name=form.todo.data))
            db.session.commit()
            flash("已新增一筆待辦事項。", "success")
            return redirect(url_for("todo"), code=303)
        tasks = db.session.scalars(
            db.select(Tasks).order_by(Tasks.date_added, Tasks.id)
        ).all()
        status = 400 if form.is_submitted() else 200
        return render_template(
            "todo.html", form=form, delete_form=DeleteForm(), todos=tasks
        ), status

    @app.post("/delete_task/<int:id>")
    def delete_task(id):
        task = db.get_or_404(Tasks, id)
        db.session.delete(task)
        db.session.commit()
        flash("已刪除待辦事項。", "success")
        return redirect(url_for("todo"), code=303)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template(
            "error.html",
            code=400,
            title="表單已過期",
            message="請重新開啟待辦清單後再試一次。",
        ), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template(
            "error.html",
            code=404,
            title="找不到這個頁面或待辦事項",
            message="它可能已經被刪除，或網址不正確。",
        ), 404

    @app.cli.command("init-db")
    def init_db():
        """Create missing database tables without deleting existing tasks."""
        db.create_all()
        click.echo("Database tables are ready.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
