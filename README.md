# SQLCLI Workbench

**SQLCLI helps you explore a MySQL database from a simple terminal window.** It works with MySQL/MariaDB from XAMPP and can suggest SQL as you type. The optional AI helper runs on your computer with Ollama.

You don't need to know Git or use AI to get started. Follow the steps below, one at a time.

Examples use placeholder names only. Your database records are not included in this guide or uploaded to GitHub.

## What you need

- **Windows**
- **Python 3.10 or newer** — [Download Python](https://www.python.org/downloads/windows/). During setup, check **Add Python to PATH**.
- **XAMPP** — [Download XAMPP](https://www.apachefriends.org/download.html). You need this to run your database.
- **Ollama** — optional. You only need it if you want to use the AI helper.

## First-time setup

### 1. Download SQLCLI

On this GitHub page, choose **Code**, then **Download ZIP**. Open the downloaded ZIP and extract its folder somewhere easy to find, such as `C:\sqlCLI`.

### 2. Set up SQLCLI

Open the extracted folder and double-click **`setup.bat`**. Follow the on-screen questions. Setup installs the Python packages SQLCLI needs and creates a separate environment for this project.

If Python or XAMPP is missing, setup can open its official download page. Install the missing program, then run `setup.bat` again. Ollama and its AI model are optional. Setup checks your CPU and available memory, then recommends a model size that fits the computer's current headroom. It asks before changing the model saved in `.env`.

The first setup needs internet to download Python packages. After setup, you can use SQLCLI with XAMPP offline. The AI model also needs internet to download, but can be used offline after it is installed.

### 3. Start your database

Open the **XAMPP Control Panel** and click **Start** next to **MySQL**. Keep MySQL running while you use SQLCLI.

### 4. Open SQLCLI

In File Explorer, open the SQLCLI folder. Click the address bar at the top, type `powershell`, and press **Enter**. In the PowerShell window, copy and run:

```powershell
.\.venv\Scripts\sqlcli.exe
```

You should see a prompt that starts with `sqlcli`. If it says **MySQL is offline**, start MySQL in XAMPP, then type `:connect` at the SQLCLI prompt.

## Find your database and tables

Commands that start with `:` are SQLCLI commands. Type one and press **Enter**:

```text
:databases
```

This shows the databases you can access. Choose a name from the list, then replace `your_database_name` below with it:

```text
:use your_database_name
:tables
```

`:use` selects the database. `:tables` then shows its tables. Replace `your_table_name` with a table name from that list:

Tip: after connecting, type `:use ` and press **Tab** to complete a database name SQLCLI can access. Type `:databases` to refresh the available database names.

```text
:describe your_table_name
:sample your_table_name
```

To see up to 10 rows from that table, you can also type this SQL query:

```sql
SELECT * FROM your_table_name LIMIT 10;
```

If the prompt says **no database**, select one with `:use your_database_name` first.

## SQLCLI commands and SQL are different

- SQLCLI commands start with a colon, like `:tables`. They do **not** need a semicolon.
- SQL statements do not start with a colon. They must end with a semicolon (`;`).

For example:

```text
:count your_table_name
```

```sql
SELECT * FROM your_table_name LIMIT 10;
```

Press **Tab** to see suggestions for SQLCLI commands, database names, SQL words, tables, columns, and functions. Suggestions change with the SQL you're writing: after `FROM` SQLCLI offers tables, and after `WHERE` it offers columns from the tables in your query. Date and time functions are included too. For example, type `CUR` for `CURDATE` or `CURTIME`, or type `INTERVAL ` to see units such as `DAY`, `MONTH`, and `YEAR`.

```sql
SELECT CURRENT_DATE(), CURRENT_TIME(), NOW();
```

Type `:help` to see all commands. If SQLCLI says **Waiting for ;**, finish the SQL statement with `;`. Press **Ctrl+C** to cancel an unfinished line.

## Handy commands

| Type this | It does this |
|---|---|
| `:databases` | Shows databases you can access |
| `:use your_database_name` | Selects a database (replace with your database's name) |
| `:tables` | Lists tables in the selected database |
| `:describe your_table_name` | Shows the columns in a table |
| `:sample your_table_name` | Previews up to 10 rows |
| `:sample your_table_name 5` | Previews up to 5 rows |
| `:count your_table_name` | Counts rows in a table |
| `:refresh` | Reloads database, table, and column suggestions |
| `:help` | Shows help |
| `:quit` | Closes SQLCLI |

To save a query's results as a new CSV file, use `:export`:

```text
:export results.csv SELECT * FROM your_table_name LIMIT 10;
```

The CSV is saved in the folder where SQLCLI is running. SQLCLI won't overwrite an existing file.

## Optional AI helper

The AI helper is optional. It uses Ollama on your own computer. Downloading a model needs internet; after it is installed, you can ask for SQL without internet.

### Choosing an AI model for your computer

The setup program checks the number of CPU cores, current CPU use, total RAM, and currently available RAM. It recommends the largest of these small Qwen models that is predicted to keep RAM use below 80%:

| Model | A good starting point | Download size (approx.) |
| --- | --- | --- |
| `qwen3.5:0.8b` | Older or lower-spec computers, including computers with only 1–2 CPU cores | 1.2–1.3 GB |
| `qwen3.5:2b` | A modest or midrange computer when the 4B model does not fit safely | 2.7–3.1 GB |
| `qwen3.5:4b` | A midrange computer with enough free memory and at least 3 CPU cores | 3.3–4.0 GB |

Smaller models need less memory and are usually quicker on older CPUs, but may make less accurate SQL suggestions. The installer uses the current free RAM as well as the computer's total RAM, so it can recommend a smaller model when many other programs are open. It skips optional AI setup if no listed model currently fits the safety check. You can rerun `setup.bat` later, after closing programs, to check again. Model sizes are listed in the [official Ollama Qwen3.5 library](https://ollama.com/library/qwen3.5).

Check that Ollama is ready:

```text
:ollama status
```

If it is stopped, start it from inside SQLCLI:

```text
:ollama start
```

Then ask a question in plain language:

```text
:ask show the latest 10 records
```

If SQLCLI says the model is missing, connect to the internet and type `:ollama pull`. If AI says it is disabled, type `:ai on`.

**`:ask` only suggests SQL; it never runs the query for you.** Read the suggestion before copying it into SQLCLI. SQLCLI asks you to confirm data-changing commands. Keep a backup before changing important data.

When AI is on, it can understand obvious spelling mistakes in `:ask` requests. If a SQL statement returns a syntax, unknown-column, ambiguous-column, or missing-table error, SQLCLI can offer a corrected version. It shows the suggestion first and runs it only if you type `YES`; data-changing SQL still displays a warning.

To help protect your computer, SQLCLI checks CPU use and available RAM before an AI request. It pauses before starting a request if CPU use is already 80% or higher, or if loading the selected model is predicted to bring RAM use to 80% or higher. The Qwen3.5 4B model gets a 4.5 GB working-memory allowance, including Ollama overhead. Ollama is limited to one request at a time and at most two CPU threads per request. Close other programs and try again later if AI is paused. These checks reduce load, but cannot enforce a hard real-time CPU ceiling or measure temperature; stop using local AI if the computer becomes too hot or unresponsive.

## If something goes wrong

- **“MySQL is offline”** — start MySQL in XAMPP, then type `:connect` inside SQLCLI.
- **“No database selected”** — type `:databases`, then `:use` followed by a database name from the list.
- **“Table not found”** — make sure you selected the right database, then type `:tables` and check the spelling.
- **“Access denied”** — check the MySQL user name and password in `.env` inside the SQLCLI folder. Many XAMPP setups use user `root` and a blank password, but yours may differ.
- **“Ollama unavailable”** — type `:ollama start`, then `:ollama status`.
- **“AI paused to protect your laptop”** — close other programs and try again when CPU and projected RAM use are below 80%. If this happens often, rerun `setup.bat` and choose a smaller recommended model such as `qwen3.5:2b` or `qwen3.5:0.8b`.
- **Python is not recognized** — install Python 3.10 or newer, select **Add Python to PATH**, and run `setup.bat` again.

## Your settings and files

SQLCLI reads database settings from `.env` in the project folder. Setup creates `.env` from `.env.example` if needed and keeps an existing `.env` unchanged. If your MySQL password is not blank, add it to `MYSQL_PASSWORD` in `.env`.

**Never upload `.env` to GitHub.** It may contain your database password. The project ignores `.env`, the Python environment, Ollama, and downloaded model files. `.env.example` contains safe example settings.

Python plugins can add commands and suggestions. See [plugins/README.md](plugins/README.md) for an example. SQLCLI runs plugin code when it starts, so only use plugins you trust.

## License

SQLCLI is licensed under the MIT License. See [LICENSE](LICENSE).
