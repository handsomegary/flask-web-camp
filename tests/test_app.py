"""Integration checks for the camp app using isolated, temporary databases."""

import html
import tempfile
import unittest
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from app import Tasks, app as default_app, create_app, db


def tearDownModule():
    """Release the demonstration app's import-time SQLite connection too."""
    with default_app.app_context():
        db.session.remove()
        db.engine.dispose()


class PageForms(HTMLParser):
    """Read public form actions and CSRF values as a browser would."""

    def __init__(self, source):
        super().__init__()
        self.tokens = []
        self.delete_actions = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("name") == "csrf_token":
            self.tokens.append(attributes.get("value", ""))
        if tag == "form":
            action = attributes.get("action", "")
            if action.startswith("/delete_task/"):
                self.delete_actions.append(action)


class TodoAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory(prefix="flask-camp-test-")
        self.addCleanup(self.temp_directory.cleanup)
        self.apps = []
        self.addCleanup(self.close_database_handles)
        self.instance_path = str(Path(self.temp_directory.name).resolve())
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "test-session-key-only",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///tasks.db",
            "WTF_CSRF_ENABLED": True,
        }
        self.app = self.make_app()
        self.client = self.app.test_client()

    def make_app(self):
        application = create_app(self.config, instance_path=self.instance_path)
        self.apps.append(application)
        return application

    def close_database_handles(self):
        # Close SQLite handles before TemporaryDirectory removes files on Windows.
        for application in self.apps:
            with application.app_context():
                db.session.remove()
                db.engine.dispose()

    def get_token(self, client=None):
        response = (client or self.client).get("/todo")
        self.assertEqual(response.status_code, 200)
        forms = PageForms(response.get_data(as_text=True))
        self.assertTrue(forms.tokens, "The add form must contain a CSRF token.")
        return forms.tokens[0]

    def add_task(self, name, client=None):
        selected_client = client or self.client
        response = selected_client.post(
            "/todo", data={"todo": name, "csrf_token": self.get_token(selected_client)}
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/todo")
        return response

    def delete_actions(self, client=None):
        response = (client or self.client).get("/todo")
        self.assertEqual(response.status_code, 200)
        return PageForms(response.get_data(as_text=True)).delete_actions

    def delete_task(self, action, client=None):
        selected_client = client or self.client
        return selected_client.post(
            action, data={"csrf_token": self.get_token(selected_client)}
        )

    def test_empty_home_and_todo_are_ready_without_manual_database_setup(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("0 件待辦", home.get_data(as_text=True))
        listing = self.client.get("/todo")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(PageForms(listing.get_data(as_text=True)).delete_actions, [])
        self.assertTrue(Path(self.instance_path, "tasks.db").is_file())

    def test_add_list_delete_and_refresh_do_not_duplicate_tasks(self):
        self.add_task("讀一章 Python")
        self.add_task("完成 Flask 練習")
        for _ in range(2):
            listing = self.client.get("/todo").get_data(as_text=True)
            self.assertIn("讀一章 Python", listing)
            self.assertIn("完成 Flask 練習", listing)
            self.assertEqual(len(PageForms(listing).delete_actions), 2)
        self.assertIn("2 件待辦", self.client.get("/").get_data(as_text=True))

        removed = self.delete_task(self.delete_actions()[0])
        self.assertEqual(removed.status_code, 303)
        self.assertEqual(removed.headers["Location"], "/todo")
        listing = self.client.get("/todo").get_data(as_text=True)
        self.assertNotIn("讀一章 Python", listing)
        self.assertIn("完成 Flask 練習", listing)
        self.assertEqual(len(PageForms(listing).delete_actions), 1)

    def test_tasks_and_deletions_persist_when_the_app_restarts(self):
        self.add_task("保留下來的任務")
        self.add_task("刪掉的任務")
        self.assertEqual(self.delete_task(self.delete_actions()[1]).status_code, 303)

        restarted_client = self.make_app().test_client()
        listing = restarted_client.get("/todo").get_data(as_text=True)
        self.assertIn("保留下來的任務", listing)
        self.assertNotIn("刪掉的任務", listing)
        self.assertEqual(len(PageForms(listing).delete_actions), 1)
        self.add_task("重新啟動後新增", restarted_client)
        self.assertIn("2 件待辦", restarted_client.get("/").get_data(as_text=True))

    def test_oldest_task_is_next_and_deletion_advances_to_the_following_task(self):
        # Explicit dates also exercise stable ordering for tasks created at one instant.
        oldest = datetime(2025, 1, 1, 9)
        newer = datetime(2025, 1, 2, 9)
        with self.app.app_context():
            db.session.add_all(
                [
                    Tasks(task_name="較新的任務", date_added=newer),
                    Tasks(task_name="最早的第一件", date_added=oldest),
                    Tasks(task_name="同時建立的第二件", date_added=oldest),
                ]
            )
            db.session.commit()

        home = self.client.get("/").get_data(as_text=True)
        self.assertIn("最早的第一件", home)
        self.assertNotIn("較新的任務", home)
        listing = self.client.get("/todo").get_data(as_text=True)
        self.assertLess(listing.index("最早的第一件"), listing.index("同時建立的第二件"))
        self.assertLess(listing.index("同時建立的第二件"), listing.index("較新的任務"))

        for next_name in ("同時建立的第二件", "較新的任務"):
            self.assertEqual(self.delete_task(self.delete_actions()[0]).status_code, 303)
            self.assertIn(next_name, self.client.get("/").get_data(as_text=True))
        self.assertEqual(self.delete_task(self.delete_actions()[0]).status_code, 303)
        self.assertIn("0 件待辦", self.client.get("/").get_data(as_text=True))

    def test_blank_and_oversized_tasks_show_errors_without_creating_rows(self):
        for invalid_name in ("", " \t\n ", "任" * 201, "x" * 1000):
            with self.subTest(name=repr(invalid_name[:20])):
                response = self.client.post(
                    "/todo",
                    data={"todo": invalid_name, "csrf_token": self.get_token()},
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('id="task-errors"', response.get_data(as_text=True))
                self.assertEqual(self.delete_actions(), [])

    def test_task_whitespace_is_trimmed_and_the_200_character_limit_is_accepted(self):
        self.add_task(" \t讀一章 Python\n ")
        self.add_task("  " + "任" * 200 + "  ")
        listing = self.client.get("/todo").get_data(as_text=True)
        self.assertIn("<h3>讀一章 Python</h3>", listing)
        self.assertIn("<h3>" + "任" * 200 + "</h3>", listing)
        self.assertEqual(len(PageForms(listing).delete_actions), 2)

    def test_user_content_is_escaped_on_task_pages_and_profile(self):
        dangerous_name = '<script>alert("xss")</script>'
        escaped_name = html.escape(dangerous_name).replace("&quot;", "&#34;")
        self.add_task(dangerous_name)
        for path in ("/", "/todo"):
            with self.subTest(path=path):
                page = self.client.get(path).get_data(as_text=True)
                self.assertNotIn(dangerous_name, page)
                self.assertIn(escaped_name, page)
        profile_name = '<img src=x onerror="alert(1)">'
        response = self.client.get("/user/" + quote(profile_name, safe=""))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(profile_name, response.get_data(as_text=True))
        self.assertIn("&lt;img", response.get_data(as_text=True))

    def test_missing_and_tampered_csrf_tokens_are_rejected_for_add_and_delete(self):
        valid_token = self.get_token()
        for invalid_token in (None, "invalid-token", valid_token + "tampered"):
            with self.subTest(token=invalid_token):
                data = {"todo": "不應該新增"}
                if invalid_token is not None:
                    data["csrf_token"] = invalid_token
                self.assertEqual(self.client.post("/todo", data=data).status_code, 400)
                self.assertEqual(self.delete_actions(), [])

        self.add_task("保護這件任務")
        action = self.delete_actions()[0]
        for data in ({}, {"csrf_token": "invalid-token"}):
            self.assertEqual(self.client.post(action, data=data).status_code, 400)
            self.assertEqual(len(self.delete_actions()), 1)
        self.assertEqual(self.delete_task(action).status_code, 303)

    def test_a_csrf_token_cannot_be_reused_by_a_different_browser_session(self):
        first_session_token = self.get_token()
        other_client = self.app.test_client()
        self.get_token(other_client)
        rejected = other_client.post(
            "/todo", data={"todo": "另一個瀏覽器", "csrf_token": first_session_token}
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(self.delete_actions(), [])
        self.add_task("另一個瀏覽器", other_client)
        self.assertEqual(len(self.delete_actions()), 1)

    def test_get_cannot_delete_and_missing_tasks_return_404(self):
        self.add_task("不讓連結刪除")
        action = self.delete_actions()[0]
        self.assertEqual(self.client.get(action).status_code, 405)
        self.assertEqual(len(self.delete_actions()), 1)
        missing = self.delete_task("/delete_task/999999")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(len(self.delete_actions()), 1)
        self.assertEqual(self.client.get("/unknown-page").status_code, 404)

    def test_profile_and_pages_use_served_static_assets(self):
        for path in ("/", "/todo", "/user/Flask%20Learner"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                page = response.get_data(as_text=True)
                self.assertIn('href="/static/style.css"', page)
                self.assertIn('href="/static/favicon.svg"', page)
        profile = self.client.get("/user/Flask%20Learner").get_data(as_text=True)
        self.assertIn("Flask Learner", profile)
        for path in ("/static/style.css", "/static/favicon.svg"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)

    def test_init_db_is_idempotent_and_keeps_existing_tasks(self):
        self.add_task("資料不能被重建清掉")
        runner = self.app.test_cli_runner()
        for _ in range(2):
            result = runner.invoke(args=["init-db"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(len(self.delete_actions()), 1)
            self.assertIn("資料不能被重建清掉", self.client.get("/todo").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
