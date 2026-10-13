# Flask 網站實作營

將 2022 Flask 網站實作營的練習整理成可直接執行的網站：個人介紹頁、首頁的下一筆待辦，以及使用 SQLite 儲存的待辦清單。

本機執行只需 Python、pip 安裝的套件，以及瀏覽器。SQLite 隨 Python 提供，不需要另外安裝資料庫伺服器，也不需要 Node.js。

## 已完成的課程功能

- Flask 路由與 Jinja2 模板，首頁、個人介紹頁及共用導覽列。
- 個人介紹頁與本機 CSS，並依螢幕寬度調整版面。
- Flask-WTF 表單：新增待辦、空白檢查、最多 200 個字、CSRF 保護。
- SQLite 資料保存：任務名稱、編號及建立時間；清單依建立時間排序，時間顯示為 UTC。
- 刪除待辦使用帶有 CSRF 保護的 POST 表單。
- 首頁顯示下一筆待辦及總筆數，並提供空清單與錯誤頁面。

課程最後的實作範圍是新增、查詢與刪除待辦。此版本沿用這個範圍；尚未加入任務編輯、完成狀態或帳號登入。所有使用者共用同一份清單，適合本機練習與示範。

## 執行環境

建議使用 Python 3.11 或更新版本。本機驗證使用 Python 3.14.4；安裝環境中的 SQLAlchemy 2.1.4 要求 Python 3.11 以上。

主要套件固定於 `requirements.txt`：

| 套件 | 版本 |
| --- | --- |
| Flask | 3.1.3 |
| Flask-SQLAlchemy | 3.1.1 |
| Flask-WTF | 1.3.0 |
| SQLAlchemy | 2.1.4 |

## Windows / PowerShell 快速開始

先下載這個 repo，或用 Git 取得：

```powershell
git clone https://github.com/handsomegary/flask-web-camp.git
cd flask-web-camp
```

私人 repo 需要以有存取權的 GitHub 帳號登入。接著建立虛擬環境、安裝套件並啟動：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

若電腦使用 `py` 啟動器，可將第一行改成 `py -3 -m venv .venv`。若 PowerShell 不允許執行啟用腳本，直接呼叫虛擬環境內的 Python 即可：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

開啟 [http://127.0.0.1:5000](http://127.0.0.1:5000)，或 [http://localhost:5000](http://localhost:5000)。按 `Ctrl+C` 停止伺服器。

| 網址 | 功能 |
| --- | --- |
| `/` | 首頁及下一筆待辦 |
| `/user/Gary` | 個人介紹；網址中的名稱會傳入頁面 |
| `/todo` | 新增、查看及刪除待辦 |

## 資料庫與設定

首次啟動會自動建立 `instance/tasks.db` 和資料表，從空清單開始。之後重新啟動會保留已新增的資料。需要手動建立缺少的資料表時，可以執行：

```powershell
python -m flask --app app init-db
```

此指令不會刪除現有待辦；原課程的 `python create_db.py` 也保留相同用途。未啟用虛擬環境時，將 `python` 改成 `.\.venv\Scripts\python.exe`。

應用程式採用 `create_app()` 工廠建立 Flask 實例。本機預設會產生並保存 `instance/.secret_key`，供表單與 session 使用；它與資料庫都已被 `.gitignore` 排除。

如需自行指定設定，在啟動前手動設定環境變數：

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:DATABASE_URL = "sqlite:///tasks.db"
python app.py
```

`SECRET_KEY` 應在同一個環境中保持固定；上述指令適合首次產生。相對 SQLite 路徑會以 `instance` 資料夾為基準。程式直接讀取環境變數，不會自動載入 `.env`，也不需要 `python-dotenv`。

Repo 只包含程式、測試與說明，不包含原課程 PDF、圖片素材或既有資料庫。介面使用本機 CSS，可在沒有外部 CDN 的情況下使用。

## 測試

安裝套件後，在專案根目錄執行 Python 標準函式庫的測試工具：

```powershell
python -m unittest discover -s tests -v
```

未啟用虛擬環境時：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions 會在 push 和 pull request 時，以 Python 3.11 與 3.14 執行同一組測試。

## GitHub 與網站上線

推送至 GitHub repo 是保存與分享原始碼；網站仍需執行中的 Python 環境。[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) 提供靜態 HTML、CSS、JavaScript 網站，無法執行這個 Flask 後端。

如要讓其他人透過網路使用，後續需要支援 Python / WSGI 的主機，並安排固定的 `SECRET_KEY` 與持久化資料庫。本版先完成本機執行與 repo，不包含上線設定。`python app.py` 是本機開發啟動方式；正式部署請參考 [Flask 部署文件](https://flask.palletsprojects.com/en/stable/deploying/)。
