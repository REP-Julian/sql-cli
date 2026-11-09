"""Comprehensive SQL knowledge base aligned with W3Schools and MySQL standards."""

from __future__ import annotations

import difflib
import re
import textwrap
from dataclasses import dataclass


@dataclass(frozen=True)
class SQLTopic:
    key: str
    name: str
    category: str
    syntax: str
    summary: str
    example: str
    notes: str = ""
    difficulty: str = "Beginner"
    challenge: str = ""
    solution: str = ""


TOPICS: dict[str, SQLTopic] = {
    # --- SQL BASICS ---
    "syntax": SQLTopic(
        key="syntax",
        name="SQL Syntax",
        category="Basics",
        syntax="SELECT column1, column2 FROM table_name WHERE condition;",
        summary="SQL statements consist of keywords, identifiers (table/column names), and clauses ending with a semicolon (;). SQL keywords are case-insensitive, but writing them in UPPERCASE is standard practice.",
        example="SELECT id, name FROM users WHERE active = 1;",
        notes="Statements end with a semicolon (;). In MySQL, identifiers can be wrapped in backticks (`table_name`).",
    ),
    "select": SQLTopic(
        key="select",
        name="SQL Select",
        category="Basics",
        syntax="SELECT column1, column2, ... FROM table_name;\nSELECT * FROM table_name;",
        summary="The SELECT statement reads data from one or more database tables and returns a tabular result set. Use * to select all columns.",
        example="SELECT id, name, email FROM customers;\nSELECT * FROM products;",
        notes="Avoid SELECT * in production when you only need specific columns; selecting only needed columns saves bandwidth and memory.",
    ),
    "select-distinct": SQLTopic(
        key="select-distinct",
        name="SQL Select Distinct",
        category="Basics",
        syntax="SELECT DISTINCT column1, column2 FROM table_name;",
        summary="SELECT DISTINCT eliminates duplicate rows from the query result, returning only unique values for the specified columns.",
        example="SELECT DISTINCT country FROM customers ORDER BY country;",
        notes="Distinct evaluates all selected columns together: if you select two columns, it returns unique combinations of both.",
    ),
    "where": SQLTopic(
        key="where",
        name="SQL Where",
        category="Basics",
        syntax="SELECT column1 FROM table_name WHERE condition;\nUPDATE table_name SET col = val WHERE condition;\nDELETE FROM table_name WHERE condition;",
        summary="The WHERE clause filters records to include only those satisfying the given condition. Used in SELECT, UPDATE, and DELETE statements.",
        example="SELECT * FROM employees WHERE salary >= 50000 AND department = 'Engineering';",
        notes="Strings in conditions must be enclosed in single quotes ('text'). Numbers do not use quotes.",
    ),
    "order-by": SQLTopic(
        key="order-by",
        name="SQL Order By",
        category="Basics",
        syntax="SELECT column1 FROM table_name ORDER BY column1 [ASC|DESC], column2 [ASC|DESC];",
        summary="ORDER BY sorts the returned records. ASC (default) sorts in ascending order (A-Z, 0-9), DESC sorts in descending order (Z-A, 9-0).",
        example="SELECT name, salary FROM employees ORDER BY department ASC, salary DESC;",
        notes="You can sort by multiple columns, or by column position (e.g., ORDER BY 1, 2).",
    ),
    "and-or-not": SQLTopic(
        key="and-or-not",
        name="SQL And, Or, Not",
        category="Basics",
        syntax="SELECT * FROM table_name WHERE condition1 AND (condition2 OR condition3);\nSELECT * FROM table_name WHERE NOT condition;",
        summary="Logical operators combine filters: AND requires all conditions to be true; OR requires at least one condition to be true; NOT inverts a condition.",
        example="SELECT * FROM products WHERE (category = 'Electronics' OR category = 'Office') AND price < 100 AND NOT discontinued = 1;",
        notes="Always use parentheses () when combining AND and OR to avoid operator precedence confusion.",
    ),
    "insert-into": SQLTopic(
        key="insert-into",
        name="SQL Insert Into",
        category="DML (Data Manipulation)",
        syntax="INSERT INTO table_name (col1, col2, col3) VALUES (val1, val2, val3);\nINSERT INTO table_name (col1, col2) VALUES (v1, v2), (v3, v4);",
        summary="INSERT INTO inserts new rows into a database table. You can insert a single record or multiple records in one batch.",
        example="INSERT INTO students (name, email, age) VALUES ('Alice', 'alice@example.com', 20), ('Bob', 'bob@example.com', 22);",
        notes="Auto-increment primary keys should generally be omitted from the column list; MySQL will populate them automatically.",
    ),
    "null-values": SQLTopic(
        key="null-values",
        name="SQL Null Values",
        category="Basics",
        syntax="SELECT * FROM table_name WHERE column_name IS NULL;\nSELECT * FROM table_name WHERE column_name IS NOT NULL;",
        summary="NULL represents missing, unknown, or undefined data. Because NULL is not a value, you cannot compare it with = or !=; you MUST use IS NULL or IS NOT NULL.",
        example="SELECT name, phone FROM customers WHERE phone IS NULL;\nSELECT name, phone FROM customers WHERE phone IS NOT NULL;",
        notes="Comparing column = NULL always evaluates to UNKNOWN/FALSE in SQL. Always use IS NULL or IS NOT NULL.",
    ),
    "update": SQLTopic(
        key="update",
        name="SQL Update",
        category="DML (Data Manipulation)",
        syntax="UPDATE table_name SET col1 = val1, col2 = val2 WHERE condition;",
        summary="UPDATE modifies existing records in a table. It requires a SET clause with one or more column assignments, and normally a WHERE condition.",
        example="UPDATE products SET price = 19.99, stock = stock - 1 WHERE id = 101;",
        notes="CRITICAL: Omitting the WHERE clause updates ALL rows in the table! SQLCLI requires a WHERE clause for safety.",
    ),
    "delete": SQLTopic(
        key="delete",
        name="SQL Delete",
        category="DML (Data Manipulation)",
        syntax="DELETE FROM table_name WHERE condition;",
        summary="DELETE removes specific records from a table matching the WHERE condition.",
        example="DELETE FROM sessions WHERE expired_at < NOW();",
        notes="Omitting WHERE deletes every row in the table! Use TRUNCATE TABLE table_name; if you want to reset a whole table quickly.",
    ),
    "select-top-limit": SQLTopic(
        key="select-top-limit",
        name="SQL Select Top / Limit",
        category="Basics",
        syntax="-- MySQL / MariaDB / PostgreSQL / SQLite:\nSELECT * FROM table_name LIMIT count [OFFSET skip];\n-- SQL Server / MS Access:\nSELECT TOP count * FROM table_name;",
        summary="Restricts the number of rows returned. MySQL uses the LIMIT clause at the end of the query (with optional OFFSET for pagination).",
        example="SELECT * FROM logs ORDER BY created_at DESC LIMIT 10 OFFSET 20;",
        notes="MySQL syntax: LIMIT 10 (first 10 rows); LIMIT 10 OFFSET 20 (skip 20, take 10).",
    ),

    # --- AGGREGATE FUNCTIONS ---
    "aggregate-functions": SQLTopic(
        key="aggregate-functions",
        name="SQL Aggregate Functions",
        category="Aggregates",
        syntax="SELECT COUNT(col), SUM(col), AVG(col), MIN(col), MAX(col) FROM table_name [WHERE condition];",
        summary="Aggregate functions calculate a single summary result from multiple row values. They ignore NULL values (except COUNT(*)).",
        example="SELECT COUNT(*) AS total_items, AVG(price) AS avg_price, MIN(price) AS lowest, MAX(price) AS highest FROM products WHERE in_stock = 1;",
        notes="Aggregate functions cannot be used directly in a WHERE clause; use a HAVING clause with GROUP BY, or a subquery.",
    ),
    "min-max": SQLTopic(
        key="min-max",
        name="SQL Min() and Max()",
        category="Aggregates",
        syntax="SELECT MIN(column_name) FROM table_name WHERE condition;\nSELECT MAX(column_name) FROM table_name WHERE condition;",
        summary="MIN() returns the smallest value in the selected column; MAX() returns the largest value. Works on numbers, dates, and strings.",
        example="SELECT MIN(price) AS cheapest, MAX(price) AS priciest FROM products;",
        notes="Works on text alphabetically (A is MIN, Z is MAX) and dates chronologically (oldest is MIN, newest is MAX).",
    ),
    "count": SQLTopic(
        key="count",
        name="SQL Count()",
        category="Aggregates",
        syntax="SELECT COUNT(*) FROM table_name;\nSELECT COUNT(column_name) FROM table_name;\nSELECT COUNT(DISTINCT column_name) FROM table_name;",
        summary="COUNT(*) returns total rows including NULLs. COUNT(column) returns rows where column is NOT NULL. COUNT(DISTINCT column) counts distinct non-null values.",
        example="SELECT COUNT(*) AS total_orders, COUNT(shipped_at) AS delivered_orders, COUNT(DISTINCT customer_id) AS active_customers FROM orders;",
        notes="COUNT(*) is optimized by database query planners and does not examine column values.",
    ),
    "sum-avg": SQLTopic(
        key="sum-avg",
        name="SQL Sum() and Avg()",
        category="Aggregates",
        syntax="SELECT SUM(column_name) FROM table_name WHERE condition;\nSELECT AVG(column_name) FROM table_name WHERE condition;",
        summary="SUM() computes the total sum of a numeric column. AVG() computes the average value (arithmetic mean) of a numeric column, ignoring NULLs.",
        example="SELECT department, SUM(salary) AS total_payroll, ROUND(AVG(salary), 2) AS average_salary FROM employees GROUP BY department;",
        notes="AVG ignores NULL values; if 4 rows have values (10, 20, 30, NULL), AVG is (10+20+30)/3 = 20.",
    ),

    # --- FILTERING & PATTERNS ---
    "like-wildcards": SQLTopic(
        key="like-wildcards",
        name="SQL Like & Wildcards",
        category="Filtering",
        syntax="SELECT * FROM table_name WHERE column_name LIKE pattern;\n-- % matches zero or more characters\n-- _ matches exactly one character",
        summary="LIKE searches for a specified pattern in a column. Wildcard % matches any sequence of characters; wildcard _ matches any single character.",
        example="SELECT * FROM users WHERE email LIKE '%@gmail.com';\nSELECT * FROM codes WHERE code LIKE 'A_9%';",
        notes="LIKE 'a%' (starts with a), LIKE '%a' (ends with a), LIKE '%or%' (contains 'or'), LIKE '_r%' (second character is 'r'). MySQL LIKE is case-insensitive by default in utf8mb4_general_ci.",
    ),
    "in": SQLTopic(
        key="in",
        name="SQL In Operator",
        category="Filtering",
        syntax="SELECT * FROM table_name WHERE column_name IN (value1, value2, ...);\nSELECT * FROM table_name WHERE column_name IN (SELECT col FROM other_table);",
        summary="IN allows you to specify multiple values in a WHERE clause as a shorthand for multiple OR conditions. It can also accept a subquery.",
        example="SELECT * FROM customers WHERE country IN ('Philippines', 'Japan', 'Singapore');",
        notes="Use NOT IN to exclude a list of values. Beware: if the list in NOT IN contains a NULL value, the query returns no rows.",
    ),
    "between": SQLTopic(
        key="between",
        name="SQL Between Operator",
        category="Filtering",
        syntax="SELECT * FROM table_name WHERE column_name BETWEEN val1 AND val2;",
        summary="BETWEEN selects values within a given range. The values can be numbers, text, or dates. BETWEEN is inclusive (both begin and end values are included).",
        example="SELECT * FROM products WHERE price BETWEEN 10.00 AND 50.00;\nSELECT * FROM orders WHERE order_date BETWEEN '2026-01-01' AND '2026-12-31';",
        notes="BETWEEN val1 AND val2 is equivalent to (column >= val1 AND column <= val2).",
    ),
    "aliases": SQLTopic(
        key="aliases",
        name="SQL Aliases (AS)",
        category="Syntax",
        syntax="SELECT column_name AS alias_name FROM table_name;\nSELECT t1.col, t2.col FROM table1 AS t1 JOIN table2 AS t2 ON t1.id = t2.t1_id;",
        summary="Aliases give a table or a column a temporary name to make queries more readable, or to name calculated/aggregated columns in query results.",
        example="SELECT CONCAT(first_name, ' ', last_name) AS full_name, salary * 12 AS annual_salary FROM employees AS e;",
        notes="The AS keyword is optional in SQL, but writing it explicitly is recommended for clarity.",
    ),

    # --- JOINS ---
    "joins": SQLTopic(
        key="joins",
        name="SQL Joins Overview",
        category="Joins",
        syntax="SELECT columns FROM table1 JOIN_TYPE table2 ON table1.common_col = table2.common_col;",
        summary="A JOIN clause combines rows from two or more tables based on a related column between them. Supported join types: INNER, LEFT, RIGHT, FULL, and CROSS.",
        example="SELECT orders.id, customers.name, orders.amount FROM orders INNER JOIN customers ON orders.customer_id = customers.id;",
        notes="Always qualify column names with table name or alias when joining tables with matching column names.",
    ),
    "inner-join": SQLTopic(
        key="inner-join",
        name="SQL Inner Join",
        category="Joins",
        syntax="SELECT columns FROM table1 INNER JOIN table2 ON table1.id = table2.table1_id;",
        summary="INNER JOIN returns records that have matching values in both tables. If a row in table1 has no match in table2, it is omitted from the result.",
        example="SELECT o.order_id, c.customer_name, o.order_date FROM orders AS o INNER JOIN customers AS c ON o.customer_id = c.customer_id;",
        notes="INNER JOIN is the default join type; typing simply JOIN is identical to INNER JOIN.",
    ),
    "left-join": SQLTopic(
        key="left-join",
        name="SQL Left Join",
        category="Joins",
        syntax="SELECT columns FROM table1 LEFT JOIN table2 ON table1.id = table2.table1_id;",
        summary="LEFT JOIN (or LEFT OUTER JOIN) returns ALL records from the left table, and the matched records from the right table. Missing right table values return NULL.",
        example="SELECT c.name, o.order_id, o.amount FROM customers AS c LEFT JOIN orders AS o ON c.id = o.customer_id;",
        notes="Use LEFT JOIN when you want to keep all parent records even if they have no child records (e.g. customers with 0 orders).",
    ),
    "right-join": SQLTopic(
        key="right-join",
        name="SQL Right Join",
        category="Joins",
        syntax="SELECT columns FROM table1 RIGHT JOIN table2 ON table1.id = table2.table1_id;",
        summary="RIGHT JOIN (or RIGHT OUTER JOIN) returns ALL records from the right table, and the matched records from the left table. Unmatched left columns return NULL.",
        example="SELECT e.name AS employee, d.dept_name FROM employees AS e RIGHT JOIN departments AS d ON e.dept_id = d.id;",
        notes="RIGHT JOIN is rarely used; most developers rewrite RIGHT JOINs as LEFT JOINs by swapping table order for readability.",
    ),
    "full-join": SQLTopic(
        key="full-join",
        name="SQL Full Join",
        category="Joins",
        syntax="-- MySQL emulation via UNION:\nSELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id\nUNION\nSELECT * FROM t1 RIGHT JOIN t2 ON t1.id = t2.id;",
        summary="FULL OUTER JOIN returns all records when there is a match in either left or right table. In MySQL, FULL JOIN is not natively supported, so it is emulated using LEFT JOIN UNION RIGHT JOIN.",
        example="SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON c.id = o.customer_id\nUNION\nSELECT c.name, o.id FROM customers c RIGHT JOIN orders o ON c.id = o.customer_id;",
        notes="In PostgreSQL and SQL Server, FULL OUTER JOIN syntax is native.",
    ),
    "self-join": SQLTopic(
        key="self-join",
        name="SQL Self Join",
        category="Joins",
        syntax="SELECT A.col, B.col FROM table_name A, table_name B WHERE condition;\n-- Or with explicit JOIN:\nSELECT A.col, B.col FROM table_name A JOIN table_name B ON A.id = B.parent_id;",
        summary="A self join is a regular join in which a table is joined with itself. Table aliases are mandatory to distinguish the two instances.",
        example="SELECT e.name AS employee, m.name AS manager FROM employees e LEFT JOIN employees m ON e.manager_id = m.id;",
        notes="Ideal for hierarchical data like employee-manager relationships or category sub-categories.",
    ),

    # --- SET OPERATIONS & GROUPING ---
    "union": SQLTopic(
        key="union",
        name="SQL Union and Union All",
        category="Sets",
        syntax="SELECT col1, col2 FROM table1\nUNION\nSELECT col1, col2 FROM table2;\n\nSELECT col1, col2 FROM table1\nUNION ALL\nSELECT col1, col2 FROM table2;",
        summary="UNION combines the result-set of two or more SELECT queries into one. UNION eliminates duplicates; UNION ALL keeps duplicate rows and is faster.",
        example="SELECT city, country FROM customers\nUNION\nSELECT city, country FROM suppliers ORDER BY city;",
        notes="Rules for UNION: each SELECT statement must have the same number of columns, in the same order, with compatible data types.",
    ),
    "group-by": SQLTopic(
        key="group-by",
        name="SQL Group By",
        category="Aggregates",
        syntax="SELECT column1, COUNT(*) FROM table_name GROUP BY column1;",
        summary="GROUP BY groups rows that have the same values into summary rows (e.g. 'find the number of customers in each country'). Typically used with aggregate functions.",
        example="SELECT status, COUNT(*) AS count, SUM(amount) AS total_revenue FROM orders GROUP BY status;",
        notes="Every non-aggregated column in the SELECT list must appear in the GROUP BY clause under standard SQL and MySQL ONLY_FULL_GROUP_BY mode.",
    ),
    "having": SQLTopic(
        key="having",
        name="SQL Having",
        category="Aggregates",
        syntax="SELECT column1, COUNT(*) FROM table_name GROUP BY column1 HAVING aggregate_condition;",
        summary="The HAVING clause filters groups created by GROUP BY. It was added to SQL because the WHERE keyword cannot be used with aggregate functions.",
        example="SELECT department, AVG(salary) AS avg_sal FROM employees GROUP BY department HAVING AVG(salary) > 60000;",
        notes="WHERE filters individual rows BEFORE grouping. HAVING filters groups AFTER aggregation.",
    ),
    "exists": SQLTopic(
        key="exists",
        name="SQL Exists",
        category="Advanced",
        syntax="SELECT column_name FROM table_name WHERE EXISTS (SELECT 1 FROM other_table WHERE condition);",
        summary="EXISTS tests for the existence of any record in a subquery. It returns TRUE if the subquery returns one or more records.",
        example="SELECT name FROM suppliers WHERE EXISTS (SELECT 1 FROM products WHERE products.supplier_id = suppliers.id AND products.price < 20);",
        notes="EXISTS stops scanning as soon as the first matching row is found, making it faster than IN for large subqueries.",
    ),
    "any-all": SQLTopic(
        key="any-all",
        name="SQL Any and All",
        category="Advanced",
        syntax="SELECT column_name FROM table_name WHERE col operator ANY (SELECT col FROM table WHERE condition);\nSELECT column_name FROM table_name WHERE col operator ALL (SELECT col FROM table WHERE condition);",
        summary="ANY returns TRUE if any subquery values meet the condition. ALL returns TRUE if all subquery values meet the condition.",
        example="SELECT name FROM products WHERE price > ANY (SELECT price FROM competitors);\nSELECT name FROM products WHERE price > ALL (SELECT price FROM competitors);",
        notes="Common operators used with ANY/ALL: =, <>, !=, >, >=, <, <=.",
    ),
    "case": SQLTopic(
        key="case",
        name="SQL Case",
        category="Syntax",
        syntax="CASE\n    WHEN condition1 THEN result1\n    WHEN condition2 THEN result2\n    ELSE result\nEND",
        summary="CASE goes through conditions and returns a value when the first condition is met (like an IF-THEN-ELSE statement). If no condition is met, it returns the ELSE value.",
        example="SELECT order_id, amount,\nCASE\n    WHEN amount >= 1000 THEN 'VIP'\n    WHEN amount >= 500 THEN 'Regular'\n    ELSE 'Bronze'\nEND AS customer_tier\nFROM orders;",
        notes="If there is no ELSE part and no conditions are true, CASE returns NULL.",
    ),
    "null-functions": SQLTopic(
        key="null-functions",
        name="SQL Null Functions (IFNULL, COALESCE)",
        category="Functions",
        syntax="SELECT IFNULL(column_name, fallback_value) FROM table_name;\nSELECT COALESCE(col1, col2, col3, default_value) FROM table_name;",
        summary="IFNULL() returns a fallback value if expression is NULL. COALESCE() evaluates the arguments in order and returns the first non-NULL value.",
        example="SELECT name, IFNULL(discount, 0) AS discount FROM products;\nSELECT name, COALESCE(phone, mobile, email, 'No Contact') AS preferred_contact FROM users;",
        notes="COALESCE is standard ANSI SQL and works across all database engines. IFNULL is MySQL-specific.",
    ),

    # --- DATABASE DDL & SCHEMA ---
    "create-db": SQLTopic(
        key="create-db",
        name="SQL Create DB",
        category="DDL (Data Definition)",
        syntax="CREATE DATABASE [IF NOT EXISTS] database_name [CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci];",
        summary="CREATE DATABASE creates a new SQL database schema.",
        example="CREATE DATABASE IF NOT EXISTS my_shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\nUSE my_shop;",
        notes="After creating a database, switch to it with USE database_name; before creating tables.",
    ),
    "drop-db": SQLTopic(
        key="drop-db",
        name="SQL Drop DB",
        category="DDL (Data Definition)",
        syntax="DROP DATABASE [IF EXISTS] database_name;",
        summary="DROP DATABASE deletes an existing database and permanently removes all tables, views, stored procedures, and data inside it.",
        example="DROP DATABASE IF EXISTS test_db;",
        notes="DANGER: This action cannot be undone! Make sure to take a backup first.",
    ),
    "create-table": SQLTopic(
        key="create-table",
        name="SQL Create Table",
        category="DDL (Data Definition)",
        syntax="CREATE TABLE [IF NOT EXISTS] table_name (\n    column1 datatype constraints,\n    column2 datatype constraints,\n    PRIMARY KEY (column1)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;",
        summary="CREATE TABLE creates a new table in the selected database, defining column names, data types, and integrity constraints.",
        example="CREATE TABLE users (\n    id INT AUTO_INCREMENT PRIMARY KEY,\n    username VARCHAR(50) NOT NULL UNIQUE,\n    email VARCHAR(100) NOT NULL,\n    age INT DEFAULT 18,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;",
        notes="Always specify a PRIMARY KEY. InnoDB is the recommended MySQL storage engine for foreign keys and transactions.",
    ),
    "drop-table": SQLTopic(
        key="drop-table",
        name="SQL Drop Table",
        category="DDL (Data Definition)",
        syntax="DROP TABLE [IF EXISTS] table_name;",
        summary="DROP TABLE deletes a table definition and all its data, indexes, triggers, and constraints permanently.",
        example="DROP TABLE IF EXISTS old_logs;",
        notes="To empty the data without deleting the table structure, use TRUNCATE TABLE table_name; instead.",
    ),
    "alter-table": SQLTopic(
        key="alter-table",
        name="SQL Alter Table",
        category="DDL (Data Definition)",
        syntax="ALTER TABLE table_name ADD column_name datatype;\nALTER TABLE table_name DROP COLUMN column_name;\nALTER TABLE table_name MODIFY COLUMN column_name new_datatype;\nALTER TABLE table_name RENAME TO new_table_name;",
        summary="ALTER TABLE adds, deletes, or modifies columns in an existing table, as well as adding and dropping constraints and indexes.",
        example="ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL AFTER email;\nALTER TABLE users MODIFY COLUMN username VARCHAR(80) NOT NULL;",
        notes="In MySQL, use AFTER column_name to place a newly added column in a specific position.",
    ),
    "constraints": SQLTopic(
        key="constraints",
        name="SQL Constraints",
        category="Constraints",
        syntax="CREATE TABLE table_name (\n    id INT NOT NULL AUTO_INCREMENT,\n    code VARCHAR(10) UNIQUE,\n    age INT CHECK (age >= 18),\n    status VARCHAR(20) DEFAULT 'pending',\n    PRIMARY KEY (id),\n    FOREIGN KEY (user_id) REFERENCES users(id)\n);",
        summary="Constraints specify rules for data in a table: NOT NULL, UNIQUE, PRIMARY KEY, FOREIGN KEY, CHECK, and DEFAULT. They ensure database integrity.",
        example="ALTER TABLE employees ADD CONSTRAINT chk_salary CHECK (salary > 0);",
        notes="Constraints prevent invalid data from ever being written to the database.",
    ),
    "primary-key": SQLTopic(
        key="primary-key",
        name="SQL Primary Key",
        category="Constraints",
        syntax="-- Column constraint:\nid INT AUTO_INCREMENT PRIMARY KEY,\n-- Table constraint (composite):\nPRIMARY KEY (order_id, product_id)",
        summary="PRIMARY KEY uniquely identifies each record in a table. Primary keys must contain UNIQUE values and cannot contain NULL values. Each table can have only ONE primary key.",
        example="CREATE TABLE products (\n    product_id INT AUTO_INCREMENT PRIMARY KEY,\n    product_name VARCHAR(100) NOT NULL\n);",
        notes="A composite primary key is made up of two or more columns combined together.",
    ),
    "foreign-key": SQLTopic(
        key="foreign-key",
        name="SQL Foreign Key",
        category="Constraints",
        syntax="FOREIGN KEY (parent_id) REFERENCES parent_table(id) [ON DELETE CASCADE] [ON UPDATE CASCADE]",
        summary="A FOREIGN KEY is a field (or collection of fields) that refers to the PRIMARY KEY in another table. It prevents actions that would destroy links between tables.",
        example="CREATE TABLE orders (\n    order_id INT AUTO_INCREMENT PRIMARY KEY,\n    customer_id INT NOT NULL,\n    order_date DATE NOT NULL,\n    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE\n);",
        notes="ON DELETE CASCADE deletes child records automatically when the parent is deleted. ON DELETE RESTRICT blocks parent deletion.",
    ),
    "check-default": SQLTopic(
        key="check-default",
        name="SQL Check and Default Constraints",
        category="Constraints",
        syntax="column_name datatype CHECK (condition)\ncolumn_name datatype DEFAULT default_value",
        summary="CHECK limits the values that can be placed in a column. DEFAULT sets a default value for a column when no value is specified in an INSERT.",
        example="CREATE TABLE staff (\n    id INT PRIMARY KEY,\n    age INT CHECK (age >= 18 AND age <= 70),\n    role VARCHAR(30) DEFAULT 'Associate',\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);",
        notes="MySQL 8.0+ enforces CHECK constraints. In earlier versions, CHECK syntax was parsed but ignored.",
    ),
    "create-index": SQLTopic(
        key="create-index",
        name="SQL Create Index",
        category="DDL (Data Definition)",
        syntax="CREATE [UNIQUE] INDEX index_name ON table_name (column1, column2);\nDROP INDEX index_name ON table_name;",
        summary="Indexes are used to retrieve data from the database more quickly. The users cannot see the indexes, they are just used to speed up searches and queries.",
        example="CREATE INDEX idx_customers_email ON customers (email);\nCREATE INDEX idx_orders_customer_date ON orders (customer_id, order_date DESC);",
        notes="Indexes speed up SELECT queries with WHERE and JOIN, but slow down INSERT, UPDATE, and DELETE because the index must also be updated.",
    ),
    "auto-increment": SQLTopic(
        key="auto-increment",
        name="SQL Auto Increment",
        category="Constraints",
        syntax="column_name INT AUTO_INCREMENT PRIMARY KEY",
        summary="AUTO_INCREMENT allows a unique number to be generated automatically when a new record is inserted into a table. Often used as primary keys.",
        example="CREATE TABLE items (\n    item_id INT AUTO_INCREMENT PRIMARY KEY,\n    item_name VARCHAR(50) NOT NULL\n);\nALTER TABLE items AUTO_INCREMENT = 1000; -- Start at 1000",
        notes="In SQL Server, the keyword is IDENTITY(1,1). In PostgreSQL, use SERIAL or GENERATED ALWAYS AS IDENTITY.",
    ),
    "views": SQLTopic(
        key="views",
        name="SQL Views",
        category="DDL (Data Definition)",
        syntax="CREATE [OR REPLACE] VIEW view_name AS\nSELECT columns FROM table WHERE condition;\nDROP VIEW view_name;",
        summary="A VIEW is a virtual table based on the result-set of an SQL statement. It contains rows and columns just like a real table, but queries the underlying tables dynamically.",
        example="CREATE OR REPLACE VIEW active_customers AS\nSELECT id, name, email FROM customers WHERE active = 1;",
        notes="Views simplify complex queries, encapsulate business logic, and can restrict direct access to sensitive columns.",
    ),
    "stored-procedures": SQLTopic(
        key="stored-procedures",
        name="SQL Stored Procedures",
        category="Advanced",
        syntax="DELIMITER //\nCREATE PROCEDURE procedure_name (IN param1 datatype, OUT param2 datatype)\nBEGIN\n    -- SQL statements\nEND //\nDELIMITER ;\nCALL procedure_name(arg1, @out_arg);",
        summary="A stored procedure is prepared SQL code that you can save and reuse over and over again with input and output parameters.",
        example="DELIMITER //\nCREATE PROCEDURE GetCustomerOrders(IN cust_id INT)\nBEGIN\n    SELECT * FROM orders WHERE customer_id = cust_id;\nEND //\nDELIMITER ;\nCALL GetCustomerOrders(5);",
        notes="DELIMITER temporarily changes MySQL's statement delimiter from ; to // so the procedure body can contain semicolons.",
    ),

    # --- SECURITY & BEST PRACTICES ---
    "sql-injection": SQLTopic(
        key="sql-injection",
        name="SQL Injection & Prepared Statements",
        category="Security",
        syntax="-- VULNERABLE string interpolation:\n-- query = f\"SELECT * FROM users WHERE user = '{input_user}' AND pass = '{input_pass}'\"\n\n-- SECURE parameterized query in Python:\ncursor.execute(\"SELECT * FROM users WHERE user = %s AND pass = %s\", (input_user, input_pass))",
        summary="SQL Injection (SQLi) is a security vulnerability where an attacker can execute malicious SQL statements by manipulating unvalidated user input.",
        example="-- Always use parameterized queries / prepared statements:\ncursor.execute(\"SELECT * FROM accounts WHERE account_id = %s\", (account_id,))",
        notes="NEVER concatenate or format user input directly into SQL strings. Always use prepared statements with parameter placeholders (%s in MySQL connector, ? in SQLite/ODBC).",
    ),

    # --- REFERENCES & DATA TYPES ---
    "data-types": SQLTopic(
        key="data-types",
        name="SQL Data Types Reference",
        category="Reference",
        syntax="INT, VARCHAR(n), TEXT, DATE, DATETIME, TIMESTAMP, DECIMAL(p,s), BOOLEAN",
        summary="MySQL Data Types:\n- Numeric: INT, TINYINT, SMALLINT, MEDIUMINT, BIGINT, DECIMAL(p,s), FLOAT, DOUBLE\n- String: VARCHAR(n), CHAR(n), TEXT, MEDIUMTEXT, LONGTEXT, ENUM, JSON\n- Date/Time: DATE ('YYYY-MM-DD'), DATETIME ('YYYY-MM-DD HH:MM:SS'), TIMESTAMP, TIME, YEAR\n- Binary: BLOB, LONGBLOB, BINARY, VARBINARY",
        example="CREATE TABLE demo (\n    id INT AUTO_INCREMENT PRIMARY KEY,\n    price DECIMAL(10, 2) NOT NULL,\n    description TEXT,\n    is_published BOOLEAN DEFAULT FALSE,\n    created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n);",
        notes="DECIMAL(10, 2) has 10 total digits with 2 after the decimal point (e.g. 99999999.99). Ideal for money.",
    ),
    "mysql-functions": SQLTopic(
        key="mysql-functions",
        name="MySQL Built-in Functions Reference",
        category="Reference",
        syntax="-- String: CONCAT(), SUBSTRING(), LOWER(), UPPER(), LENGTH(), TRIM(), REPLACE()\n-- Numeric: ROUND(), FLOOR(), CEIL(), ABS(), MOD(), RAND()\n-- Date: NOW(), CURDATE(), DATEDIFF(), DATE_ADD(), DATE_SUB(), DATE_FORMAT()",
        summary="MySQL provides extensive built-in functions for manipulating strings, numeric calculations, dates, control flow, and aggregations.",
        example="SELECT CONCAT(first_name, ' ', UPPER(last_name)) AS full_name,\n       DATEDIFF(NOW(), hire_date) AS days_with_company,\n       ROUND(salary * 1.10, 2) AS raised_salary\nFROM employees;",
        notes="To format a date: DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s').",
    ),
    "quick-ref": SQLTopic(
        key="quick-ref",
        name="SQL Quick Reference Cheat Sheet",
        category="Reference",
        syntax="SELECT col FROM tbl WHERE cond GROUP BY col HAVING agg_cond ORDER BY col [ASC|DESC] LIMIT n;",
        summary="Standard clause order in an SQL query:\n1. SELECT (columns)\n2. FROM (tables / joins)\n3. WHERE (row filters)\n4. GROUP BY (grouping)\n5. HAVING (group filters)\n6. ORDER BY (sorting)\n7. LIMIT / OFFSET (pagination)",
        example="SELECT department, COUNT(*) AS count\nFROM employees\nWHERE status = 'Active'\nGROUP BY department\nHAVING count >= 5\nORDER BY count DESC\nLIMIT 5;",
        notes="Execution order behind the scenes: FROM -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY -> LIMIT.",
    ),

    # --- ADVANCED QUERYING, WINDOW FUNCTIONS & OPTIMIZATION ---
    "window-functions": SQLTopic(
        key="window-functions",
        name="SQL Window Functions (OVER / PARTITION BY)",
        category="Advanced",
        syntax="SELECT column1, ROW_NUMBER() OVER (PARTITION BY group_col ORDER BY order_col DESC) AS rank_num\nFROM table_name;",
        summary="Window functions perform calculations across a set of table rows related to the current row without collapsing them into a single row like GROUP BY does.",
        example="SELECT id, name, department, salary,\n       RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dept_rank\nFROM employees;",
        notes="Common window functions: ROW_NUMBER(), RANK(), DENSE_RANK(), LEAD(), LAG(). Available in MySQL 8.0+ and SQLite 3.25+.",
        difficulty="Advanced",
        challenge="Write a query using ROW_NUMBER() or RANK() to rank records by a numeric column partitioned by category.",
        solution="SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY score DESC) AS rank_in_cat FROM records;",
    ),
    "cte": SQLTopic(
        key="cte",
        name="SQL Common Table Expressions (WITH CTE)",
        category="Advanced",
        syntax="WITH cte_name AS (\n    SELECT col1, col2 FROM table_name WHERE condition\n)\nSELECT * FROM cte_name;",
        summary="A Common Table Expression (CTE) defines a temporary named result set within a single query scope, making complex nested queries clean and readable.",
        example="WITH high_earners AS (\n    SELECT department, AVG(salary) AS avg_dept_sal\n    FROM employees GROUP BY department\n)\nSELECT e.name, e.salary, h.avg_dept_sal\nFROM employees e\nJOIN high_earners h ON e.department = h.department\nWHERE e.salary > h.avg_dept_sal;",
        notes="CTEs can be recursive (WITH RECURSIVE) for hierarchies, bill of materials, and category trees.",
        difficulty="Advanced",
        challenge="Define a CTE named 'filtered_data' that filters active records, then query all records from it.",
        solution="WITH filtered_data AS (\n    SELECT * FROM students WHERE gpa >= 3.5\n)\nSELECT * FROM filtered_data ORDER BY gpa DESC;",
    ),
    "transactions": SQLTopic(
        key="transactions",
        name="SQL Transactions (ACID, Commit, Rollback)",
        category="TCL (Transaction Control)",
        syntax="START TRANSACTION;\nUPDATE accounts SET balance = balance - 100 WHERE id = 1;\nUPDATE accounts SET balance = balance + 100 WHERE id = 2;\nCOMMIT; -- or ROLLBACK on error;",
        summary="Transactions bundle multiple SQL operations into a single atomic unit of work following ACID properties. Rollback safely recovers from errors.",
        example="START TRANSACTION;\nUPDATE inventory SET stock = stock - 1 WHERE product_id = 42;\nINSERT INTO orders (product_id, quantity) VALUES (42, 1);\nCOMMIT;",
        notes="In MySQL InnoDB, transactions guarantee Atomicity and Consistency. DDL statements (like CREATE/DROP TABLE) trigger implicit commits.",
        difficulty="Advanced",
        challenge="Draft a transaction that updates a status column on record 1 and inserts a change log entry, followed by COMMIT.",
        solution="START TRANSACTION;\nUPDATE users SET status = 'active' WHERE id = 1;\nINSERT INTO audit_logs (action, target_id) VALUES ('activate', 1);\nCOMMIT;",
    ),
    "subqueries": SQLTopic(
        key="subqueries",
        name="SQL Subqueries (Scalar & Correlated)",
        category="Advanced",
        syntax="SELECT * FROM table1 WHERE col1 > (SELECT AVG(col1) FROM table1);\nSELECT * FROM (SELECT col1, COUNT(*) AS cnt FROM table1 GROUP BY col1) AS derived_table;",
        summary="A subquery is a nested query evaluated within an outer SQL statement. Can return single scalar values, lists, or derived tables.",
        example="SELECT name, salary FROM employees WHERE salary > (SELECT AVG(salary) FROM employees);",
        notes="Derived tables in the FROM clause require an alias (e.g. AS temp). Correlated subqueries evaluate once per outer row.",
        difficulty="Intermediate",
        challenge="Find all records with a value higher than the overall average using a nested subquery.",
        solution="SELECT * FROM students WHERE gpa > (SELECT AVG(gpa) FROM students);",
    ),
    "explain-plans": SQLTopic(
        key="explain-plans",
        name="SQL Explain & Query Execution Plans",
        category="Advanced",
        syntax="EXPLAIN SELECT * FROM table_name WHERE indexed_col = 'val';\nEXPLAIN FORMAT=JSON SELECT ...;",
        summary="EXPLAIN exposes the internal query execution plan, displaying index hits, table access types (const, ref, range, ALL), and estimated rows examined.",
        example="EXPLAIN SELECT e.name, d.department_name\nFROM employees e\nJOIN departments d ON e.dept_id = d.id\nWHERE e.status = 'active';",
        notes="Check the 'type' column: 'const' and 'ref' use indexes; 'ALL' indicates a slow full table scan.",
        difficulty="Advanced",
        challenge="Prepend EXPLAIN to your query to inspect whether indexes are being utilized.",
        solution="EXPLAIN SELECT * FROM students WHERE id = 1;",
    ),
    "json-querying": SQLTopic(
        key="json-querying",
        name="SQL JSON Functions (Extract, Contains, ->)",
        category="Functions",
        syntax="SELECT JSON_EXTRACT(json_col, '$.key') FROM table_name;\nSELECT json_col->'$.key' AS quoted_val, json_col->>'$.key' AS unquoted_val FROM table_name;",
        summary="Modern MySQL and SQLite support native JSON data types with path-based extraction (-> and ->>) and search functions.",
        example="SELECT id, data->>'$.profile.email' AS user_email\nFROM user_profiles\nWHERE JSON_CONTAINS(data, '\"admin\"', '$.roles');",
        notes="Use ->> to automatically strip surrounding JSON quotes from extracted string values. Supported in MySQL 5.7+.",
        difficulty="Intermediate",
        challenge="Extract the 'name' field from a JSON document column using the ->> arrow operator.",
        solution="SELECT id, metadata->>'$.name' AS item_name FROM items;",
    ),
    "coalesce": SQLTopic(
        key="coalesce",
        name="SQL COALESCE & Fallbacks",
        category="Functions",
        syntax="SELECT COALESCE(col1, col2, col3, 'Default Value') FROM table_name;",
        summary="COALESCE evaluates arguments sequentially and returns the first non-NULL value found. Standard ANSI SQL replacement for missing data.",
        example="SELECT name, COALESCE(phone, mobile, email, 'No contact provided') AS primary_contact\nFROM users;",
        notes="IFNULL(a, b) is MySQL-specific; COALESCE(a, b, c, ...) is universal ANSI SQL and accepts unlimited fallback arguments.",
        difficulty="Intermediate",
        challenge="Select records displaying a contact column with a fallback default string when NULL.",
        solution="SELECT id, name, COALESCE(email, 'no-email@domain.com') AS contact FROM students;",
    ),
    "truncate-table": SQLTopic(
        key="truncate-table",
        name="SQL Truncate Table",
        category="DDL (Data Definition)",
        syntax="TRUNCATE TABLE table_name;",
        summary="TRUNCATE quickly deletes all rows from a table and resets auto-increment counters. Significantly faster than DELETE without WHERE.",
        example="TRUNCATE TABLE staging_logs;",
        notes="TRUNCATE is a DDL operation in MySQL that executes an implicit COMMIT. It cannot be rolled back.",
        difficulty="Beginner",
        challenge="Write a statement that quickly resets a table and clears all records.",
        solution="TRUNCATE TABLE temp_records;",
    ),
    "upsert-on-duplicate": SQLTopic(
        key="upsert-on-duplicate",
        name="SQL Upsert (INSERT ... ON DUPLICATE KEY UPDATE)",
        category="DML (Data Manipulation)",
        syntax="INSERT INTO table_name (id, col1, col2) VALUES (1, 'val1', 'val2')\nON DUPLICATE KEY UPDATE col1 = VALUES(col1), col2 = VALUES(col2);",
        summary="Upsert inserts a new row, or atomically updates the existing row if a primary or unique key collision occurs.",
        example="INSERT INTO page_views (page_url, view_count) VALUES ('/home', 1)\nON DUPLICATE KEY UPDATE view_count = view_count + 1;",
        notes="In MySQL 8.0.19+, you can alias row values: INSERT INTO tbl (a,b) VALUES (1,2) AS new ON DUPLICATE KEY UPDATE b = new.b.",
        difficulty="Intermediate",
        challenge="Write an upsert statement that inserts a counter row or increments the counter on duplicate key.",
        solution="INSERT INTO metrics (metric_name, counter) VALUES ('logins', 1) ON DUPLICATE KEY UPDATE counter = counter + 1;",
    ),
    "regex-patterns": SQLTopic(
        key="regex-patterns",
        name="SQL Regular Expressions (REGEXP / RLIKE)",
        category="Filtering",
        syntax="SELECT * FROM table_name WHERE column_name REGEXP 'pattern';",
        summary="REGEXP (or RLIKE) filters rows matching POSIX regular expressions, providing sophisticated text searching beyond standard LIKE wildcards.",
        example="SELECT * FROM customers WHERE email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$';",
        notes="Use ^ for start of string, $ for end of string, [0-9] for digits, and + for one or more occurrences.",
        difficulty="Intermediate",
        challenge="Filter rows where a text column starts with a capital letter followed by digits.",
        solution="SELECT * FROM products WHERE sku REGEXP '^[A-Z][0-9]+';",
    ),
    "conditional-agg": SQLTopic(
        key="conditional-agg",
        name="SQL Conditional Aggregation (Pivot Technique)",
        category="Aggregates",
        syntax="SELECT group_col,\n       SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved_count,\n       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_count\nFROM table_name GROUP BY group_col;",
        summary="Conditional aggregation embeds CASE statements inside aggregate functions (SUM, COUNT, AVG) to pivot row values into columns in a single table scan.",
        example="SELECT department, COUNT(*) AS total_staff,\n       SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) AS female_count,\n       SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) AS male_count\nFROM employees GROUP BY department;",
        notes="Far faster than running multiple separate queries with different WHERE clauses.",
        difficulty="Intermediate",
        challenge="Count total records and high-score records (score >= 80) in a single GROUP BY query.",
        solution="SELECT category, COUNT(*) AS total, SUM(CASE WHEN score >= 80 THEN 1 ELSE 0 END) AS high_scores FROM exams GROUP BY category;",
    ),
    "indexing-strategies": SQLTopic(
        key="indexing-strategies",
        name="SQL Indexing Strategies & Performance",
        category="DDL (Data Definition)",
        syntax="CREATE INDEX idx_col1_col2 ON table_name (col1, col2);\nCREATE UNIQUE INDEX idx_uniq_col ON table_name (col);",
        summary="Indexes create B-Tree lookup structures that speed up SELECT queries, WHERE filters, and JOIN conditions by orders of magnitude.",
        example="CREATE INDEX idx_orders_customer_date ON orders (customer_id, order_date DESC);",
        notes="In composite indexes (A, B), queries filtering on (A) or (A, B) utilize the index, but filtering on (B) alone cannot (leftmost prefix rule).",
        difficulty="Advanced",
        challenge="Create a composite index on a table spanning two frequently queried columns.",
        solution="CREATE INDEX idx_students_course_gpa ON students (course, gpa DESC);",
    ),

    # --- DDL, DML, DCL, TCL FOUNDATIONS & TAXONOMY ---
    "ddl": SQLTopic(
        key="ddl",
        name="SQL DDL (Data Definition Language)",
        category="DDL (Data Definition)",
        syntax="-- Core DDL Statements:\nCREATE DATABASE | TABLE | INDEX | VIEW | TRIGGER ...;\nALTER TABLE ... ADD | DROP | MODIFY ...;\nDROP DATABASE | TABLE | VIEW | TRIGGER ...;\nTRUNCATE TABLE ...;\nRENAME TABLE ...;",
        summary="Data Definition Language (DDL) defines, alters, and removes database structure (tables, schemas, indexes, views, triggers). In MySQL, DDL statements commit implicitly.",
        example="CREATE TABLE student_grades (\n    id INT AUTO_INCREMENT PRIMARY KEY,\n    student_name VARCHAR(100) NOT NULL,\n    grade DECIMAL(4,2) NOT NULL\n) ENGINE=InnoDB;\nALTER TABLE student_grades ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        notes="DDL operations commit immediately in MySQL and cannot be rolled back inside a transaction.",
        difficulty="Beginner",
        challenge="Write a DDL statement to create a table 'products' with an id and name column.",
        solution="CREATE TABLE products (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL);",
    ),
    "dml": SQLTopic(
        key="dml",
        name="SQL DML (Data Manipulation Language)",
        category="DML (Data Manipulation)",
        syntax="-- Core DML Statements:\nINSERT INTO table_name (cols) VALUES (...);\nUPDATE table_name SET col = val WHERE condition;\nDELETE FROM table_name WHERE condition;\nREPLACE INTO table_name (...) VALUES (...);\nINSERT INTO ... ON DUPLICATE KEY UPDATE ...;",
        summary="Data Manipulation Language (DML) manages data inside tables: adding records (INSERT), updating values (UPDATE), deleting rows (DELETE), and upserting data.",
        example="INSERT INTO students (first_name, last_name, age, course) VALUES ('Julian', 'Agustino', 20, 'IT');\nUPDATE students SET gpa = 3.9 WHERE first_name = 'Julian';\nDELETE FROM students WHERE age < 16;",
        notes="Always use a WHERE clause with UPDATE and DELETE to prevent accidental table-wide modifications. DML can be committed or rolled back.",
        difficulty="Beginner",
        challenge="Write a DML statement to insert a new student record.",
        solution="INSERT INTO students (first_name, course) VALUES ('Alice', 'Computer Science');",
    ),
    "dcl": SQLTopic(
        key="dcl",
        name="SQL DCL (Data Control Language)",
        category="DCL (Data Control)",
        syntax="-- Core DCL Statements:\nGRANT privilege_list ON db.table TO 'user'@'host';\nREVOKE privilege_list ON db.table FROM 'user'@'host';\nCREATE USER 'user'@'host' IDENTIFIED BY 'password';\nDROP USER 'user'@'host';\nALTER USER 'user'@'host' IDENTIFIED BY 'new_password';\nSHOW GRANTS FOR 'user'@'host';",
        summary="Data Control Language (DCL) manages authentication, permissions, database access rights, roles, and administrative security boundaries.",
        example="CREATE USER 'dev_app'@'localhost' IDENTIFIED BY 'StrongPass#2026';\nGRANT SELECT, INSERT, UPDATE ON agustino_db.* TO 'dev_app'@'localhost';\nFLUSH PRIVILEGES;\nSHOW GRANTS FOR 'dev_app'@'localhost';",
        notes="DCL enforces the Principle of Least Privilege: only grant the minimal permissions required for an application or user to function.",
        difficulty="Intermediate",
        challenge="Grant SELECT permissions on table 'students' to 'report_user'@'localhost'.",
        solution="GRANT SELECT ON students TO 'report_user'@'localhost'; FLUSH PRIVILEGES;",
    ),
    "tcl": SQLTopic(
        key="tcl",
        name="SQL TCL (Transaction Control Language)",
        category="TCL (Transaction Control)",
        syntax="-- Core TCL Statements:\nSTART TRANSACTION; -- or BEGIN\nCOMMIT; -- Save all mutations permanently\nROLLBACK; -- Undo all mutations\nSAVEPOINT savepoint_name; -- Intermediate checkpoint\nROLLBACK TO SAVEPOINT savepoint_name;\nSET autocommit = 0 | 1;",
        summary="Transaction Control Language (TCL) manages database transactions to enforce ACID properties (Atomicity, Consistency, Isolation, Durability) for multi-step mutations.",
        example="START TRANSACTION;\nUPDATE student_accounts SET balance = balance - 100 WHERE id = 1;\nUPDATE student_accounts SET balance = balance + 100 WHERE id = 2;\nCOMMIT;",
        notes="If any step in a transaction fails, execute ROLLBACK to restore the database to its pristine pre-transaction state.",
        difficulty="Intermediate",
        challenge="Write a transaction skeleton that updates two rows and commits.",
        solution="START TRANSACTION; UPDATE accounts SET bal = bal - 50 WHERE id = 1; UPDATE accounts SET bal = bal + 50 WHERE id = 2; COMMIT;",
    ),

    # --- EXTENDED DDL TOPICS ---
    "rename-table": SQLTopic(
        key="rename-table",
        name="SQL Rename Table",
        category="DDL (Data Definition)",
        syntax="RENAME TABLE old_table_name TO new_table_name;\n-- Multiple tables in one atomic statement:\nRENAME TABLE t1 TO t1_backup, t2 TO t1;",
        summary="RENAME TABLE renames one or more database tables atomically in MySQL. Excellent for zero-downtime table swapping during database migrations.",
        example="RENAME TABLE students TO students_archive, students_staging TO students;",
        notes="Executed atomically: other clients cannot access tables in an intermediate state while renaming. DDL operation.",
        difficulty="Beginner",
        challenge="Rename a temporary table 'temp_users' to 'users_v2'.",
        solution="RENAME TABLE temp_users TO users_v2;",
    ),
    "drop-index": SQLTopic(
        key="drop-index",
        name="SQL Drop Index",
        category="DDL (Data Definition)",
        syntax="DROP INDEX index_name ON table_name;\n-- Or via ALTER TABLE:\nALTER TABLE table_name DROP INDEX index_name;",
        summary="DROP INDEX deletes an existing index from a table to reclaim disk space or reduce INSERT/UPDATE overhead when an index is no longer needed.",
        example="DROP INDEX idx_customer_email ON customers;",
        notes="Dropping unused indexes speeds up write operations (INSERT, UPDATE, DELETE). In SQLite, syntax is DROP INDEX index_name;.",
        difficulty="Intermediate",
        challenge="Write a statement to drop the index 'idx_orders_date' on table 'orders'.",
        solution="DROP INDEX idx_orders_date ON orders;",
    ),
    "drop-view": SQLTopic(
        key="drop-view",
        name="SQL Drop View",
        category="DDL (Data Definition)",
        syntax="DROP VIEW [IF EXISTS] view_name [, view_name2];",
        summary="DROP VIEW permanently deletes one or more views from the database without affecting the underlying base tables.",
        example="DROP VIEW IF EXISTS active_students_view;",
        notes="IF EXISTS prevents errors if the view does not exist. Does not delete any real data.",
        difficulty="Beginner",
        challenge="Safely drop a view named 'monthly_sales_summary' if it exists.",
        solution="DROP VIEW IF EXISTS monthly_sales_summary;",
    ),
    "triggers": SQLTopic(
        key="triggers",
        name="SQL Triggers (CREATE TRIGGER)",
        category="DDL (Data Definition)",
        syntax="CREATE TRIGGER trigger_name\nBEFORE|AFTER INSERT|UPDATE|DELETE ON table_name\nFOR EACH ROW\nBEGIN\n    -- SQL logic using NEW.col or OLD.col\nEND;",
        summary="A trigger is a stored database program that executes automatically in response to specified mutation events (INSERT, UPDATE, DELETE) on a table.",
        example="CREATE TRIGGER trg_audit_student_update\nAFTER UPDATE ON students\nFOR EACH ROW\nBEGIN\n    INSERT INTO audit_log (student_id, old_gpa, new_gpa, updated_at)\n    VALUES (OLD.student_id, OLD.gpa, NEW.gpa, NOW());\nEND;",
        notes="NEW refers to new row values (INSERT/UPDATE); OLD refers to existing row values (UPDATE/DELETE). SQLite and MySQL InnoDB both support triggers.",
        difficulty="Advanced",
        challenge="Draft a trigger that logs an entry after a row is deleted.",
        solution="CREATE TRIGGER trg_user_delete AFTER DELETE ON users FOR EACH ROW BEGIN INSERT INTO user_deletions (deleted_user_id, deleted_at) VALUES (OLD.id, NOW()); END;",
    ),
    "drop-trigger": SQLTopic(
        key="drop-trigger",
        name="SQL Drop Trigger",
        category="DDL (Data Definition)",
        syntax="DROP TRIGGER [IF EXISTS] trigger_name;",
        summary="DROP TRIGGER deletes a trigger from the database schema.",
        example="DROP TRIGGER IF EXISTS trg_audit_student_update;",
        notes="Requires TRIGGER privilege in MySQL.",
        difficulty="Beginner",
        challenge="Drop a trigger named 'audit_tracker' safely.",
        solution="DROP TRIGGER IF EXISTS audit_tracker;",
    ),

    # --- EXTENDED DML TOPICS ---
    "replace-into": SQLTopic(
        key="replace-into",
        name="SQL Replace Into",
        category="DML (Data Manipulation)",
        syntax="REPLACE INTO table_name (id, col1, col2) VALUES (1, 'val1', 'val2');",
        summary="MySQL extension to standard SQL. If an existing row has matching PRIMARY or UNIQUE key, MySQL deletes the old row and inserts the new row in a single atomic action.",
        example="REPLACE INTO app_config (setting_key, setting_value) VALUES ('theme', 'dark_obsidian');",
        notes="Unlike INSERT ... ON DUPLICATE KEY UPDATE, REPLACE INTO deletes the old row first, which means auto-increment IDs may advance and foreign keys with CASCADE may trigger.",
        difficulty="Intermediate",
        challenge="Use REPLACE INTO to set or overwrite a config key 'maintenance_mode' to 'false'.",
        solution="REPLACE INTO settings (key_name, value) VALUES ('maintenance_mode', 'false');",
    ),
    "insert-into-select": SQLTopic(
        key="insert-into-select",
        name="SQL Insert Into Select",
        category="DML (Data Manipulation)",
        syntax="INSERT INTO target_table (col1, col2)\nSELECT col1, col2 FROM source_table WHERE condition;",
        summary="Copies data from one table directly into another table. Extremely efficient for table archiving, backups, ETL batch runs, and migrations without moving data through the client application.",
        example="INSERT INTO graduated_students (student_id, name, final_gpa)\nSELECT student_id, first_name, gpa FROM students WHERE credits >= 120;",
        notes="Data types in the source SELECT must be compatible with target columns. Target table must already exist.",
        difficulty="Intermediate",
        challenge="Copy inactive users into an archive table using INSERT INTO SELECT.",
        solution="INSERT INTO users_archive (id, username, email) SELECT id, username, email FROM users WHERE status = 'inactive';",
    ),
    "bulk-insert": SQLTopic(
        key="bulk-insert",
        name="SQL Bulk Batch Insert",
        category="DML (Data Manipulation)",
        syntax="INSERT INTO table_name (col1, col2)\nVALUES\n    (v1, v2),\n    (v3, v4),\n    (v5, v6);",
        summary="Inserting multiple rows in a single INSERT statement reduces network roundtrips, transaction overhead, and index rebuild passes by up to 50x compared to single-row inserts.",
        example="INSERT INTO courses (course_code, course_title, credits) VALUES\n    ('CS101', 'Intro to Computer Science', 3),\n    ('CS201', 'Data Structures & Algorithms', 4),\n    ('CS301', 'Database Systems', 3);",
        notes="Governed by MySQL's max_allowed_packet setting (usually 16MB-64MB). Recommended batch size is 500 to 2,000 rows per statement.",
        difficulty="Beginner",
        challenge="Write a single INSERT statement that creates 3 categories at once.",
        solution="INSERT INTO categories (name) VALUES ('Tech'), ('Design'), ('Marketing');",
    ),

    # --- DCL (DATA CONTROL LANGUAGE) TOPICS ---
    "grant": SQLTopic(
        key="grant",
        name="SQL DCL Grant (Privileges)",
        category="DCL (Data Control)",
        syntax="GRANT privilege_list ON database_name.table_name TO 'username'@'host';\nFLUSH PRIVILEGES;",
        summary="Data Control Language (DCL) statement that assigns database permissions (SELECT, INSERT, UPDATE, DELETE, ALL PRIVILEGES) to specific database users or roles.",
        example="GRANT SELECT, INSERT, UPDATE ON agustino_db.* TO 'app_user'@'localhost';\nFLUSH PRIVILEGES;",
        notes="Host specifies allowed connection origins: 'localhost' (local machine only), '%' (any IP address), or specific CIDR subnet. Always execute FLUSH PRIVILEGES; in MySQL after manual grant modifications.",
        difficulty="Intermediate",
        challenge="Grant read-only SELECT permissions on all tables in 'reports_db' to user 'analyst'@'localhost'.",
        solution="GRANT SELECT ON reports_db.* TO 'analyst'@'localhost'; FLUSH PRIVILEGES;",
    ),
    "revoke": SQLTopic(
        key="revoke",
        name="SQL DCL Revoke (Remove Privileges)",
        category="DCL (Data Control)",
        syntax="REVOKE privilege_list ON database_name.table_name FROM 'username'@'host';\nFLUSH PRIVILEGES;",
        summary="DCL statement that revokes previously assigned database permissions from a user or role to enforce principle of least privilege.",
        example="REVOKE DELETE, DROP ON agustino_db.* FROM 'junior_dev'@'%';\nFLUSH PRIVILEGES;",
        notes="To revoke all permissions simultaneously: REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'username'@'host';.",
        difficulty="Intermediate",
        challenge="Revoke DROP privileges on database 'production_db' from user 'developer'@'%' .",
        solution="REVOKE DROP ON production_db.* FROM 'developer'@'%'; FLUSH PRIVILEGES;",
    ),
    "create-user": SQLTopic(
        key="create-user",
        name="SQL DCL Create User",
        category="DCL (Data Control)",
        syntax="CREATE USER 'username'@'host' IDENTIFIED BY 'password';\n-- With password expiration policy:\nCREATE USER 'username'@'host' IDENTIFIED WITH caching_sha2_password BY 'pass' PASSWORD EXPIRE INTERVAL 90 DAY;",
        summary="DCL account administration statement that registers a new database authentication credential with host routing restrictions and security policies.",
        example="CREATE USER 'bi_dashboard'@'192.168.1.%' IDENTIFIED BY 'StrongP@ssw0rd2026!';",
        notes="In MySQL 8.0+, caching_sha2_password is the default secure authentication plugin. Avoid using '%' for root administrative accounts.",
        difficulty="Intermediate",
        challenge="Create a new local user 'api_worker' with a strong password.",
        solution="CREATE USER 'api_worker'@'localhost' IDENTIFIED BY 'SecretApi#2026';",
    ),
    "drop-user": SQLTopic(
        key="drop-user",
        name="SQL DCL Drop User",
        category="DCL (Data Control)",
        syntax="DROP USER [IF EXISTS] 'username'@'host' [, 'username2'@'host'];",
        summary="DCL account management command that completely removes a user account and revokes all its granted privileges.",
        example="DROP USER IF EXISTS 'old_contractor'@'%';",
        notes="In MySQL, dropping a user automatically drops all privilege records in mysql.user and table grant tables.",
        difficulty="Beginner",
        challenge="Safely drop an obsolete user account 'test_runner'@'localhost'.",
        solution="DROP USER IF EXISTS 'test_runner'@'localhost';",
    ),
    "alter-user": SQLTopic(
        key="alter-user",
        name="SQL DCL Alter User (Password & Policy)",
        category="DCL (Data Control)",
        syntax="ALTER USER 'username'@'host' IDENTIFIED BY 'new_password';\n-- Account locking:\nALTER USER 'username'@'host' ACCOUNT LOCK; -- or UNLOCK",
        summary="DCL command to modify user credentials, reset forgotten passwords, rotate secrets, and lock or unlock compromised accounts.",
        example="ALTER USER 'root'@'localhost' IDENTIFIED BY 'NewSecurePass#2026';",
        notes="Used frequently in XAMPP / MariaDB configuration to establish root passwords or enable native password plugins.",
        difficulty="Intermediate",
        challenge="Update the password for 'app_user'@'localhost' and unlock the account.",
        solution="ALTER USER 'app_user'@'localhost' IDENTIFIED BY 'Fresh#Password2026' ACCOUNT UNLOCK;",
    ),
    "show-grants": SQLTopic(
        key="show-grants",
        name="SQL DCL Show Grants (Audit Privileges)",
        category="DCL (Data Control)",
        syntax="SHOW GRANTS FOR 'username'@'host';\nSHOW GRANTS; -- current active connection",
        summary="DCL security audit command that displays all permissions, roles, and administrative grants assigned to a database user account.",
        example="SHOW GRANTS FOR 'root'@'localhost';\nSHOW GRANTS FOR CURRENT_USER();",
        notes="Essential security auditing tool for verifying that service accounts operate under least-privilege principles.",
        difficulty="Beginner",
        challenge="Inspect the grants and privileges of the current connected session.",
        solution="SHOW GRANTS FOR CURRENT_USER();",
    ),
    "roles-rbac": SQLTopic(
        key="roles-rbac",
        name="SQL DCL Roles & RBAC (Role-Based Access)",
        category="DCL (Data Control)",
        syntax="CREATE ROLE 'role_name';\nGRANT privilege_list ON db.* TO 'role_name';\nGRANT 'role_name' TO 'username'@'host';\nSET DEFAULT ROLE ALL TO 'username'@'host';",
        summary="Roles allow grouping database privileges into named profiles (e.g. read_only, developer, data_analyst) and granting the entire profile to multiple users at once.",
        example="CREATE ROLE 'reporting_read_only';\nGRANT SELECT ON sales_db.* TO 'reporting_read_only';\nGRANT 'reporting_read_only' TO 'analyst1'@'%', 'analyst2'@'%';\nSET DEFAULT ROLE 'reporting_read_only' TO 'analyst1'@'%';",
        notes="Supported in MySQL 8.0+. When a user connects, roles must be activated (SET ROLE) or assigned as default (SET DEFAULT ROLE).",
        difficulty="Advanced",
        challenge="Create a role named 'db_reader' with SELECT privileges and assign it to a user.",
        solution="CREATE ROLE 'db_reader'; GRANT SELECT ON *.* TO 'db_reader'; GRANT 'db_reader' TO 'viewer'@'localhost';",
    ),

    # --- TCL (TRANSACTION CONTROL LANGUAGE) TOPICS ---
    "rollback": SQLTopic(
        key="rollback",
        name="SQL TCL Rollback (Undo Uncommitted Changes)",
        category="TCL (Transaction Control)",
        syntax="ROLLBACK;\nROLLBACK TO [SAVEPOINT] savepoint_name;",
        summary="Transaction Control Language (TCL) command that aborts the current transaction and reverts all database mutations made since the last COMMIT or SAVEPOINT.",
        example="START TRANSACTION;\nUPDATE student_accounts SET balance = balance - 500 WHERE student_id = 1;\n-- Error occurs or check fails:\nROLLBACK;\n-- Balance remains unaltered",
        notes="ROLLBACK only affects transactional storage engines (like MySQL InnoDB or SQLite). Non-transactional engines (MyISAM) cannot be rolled back.",
        difficulty="Intermediate",
        challenge="Begin a transaction, delete an erroneous record, then execute ROLLBACK to restore state.",
        solution="START TRANSACTION; DELETE FROM temp_logs WHERE id = 99; ROLLBACK;",
    ),
    "savepoint": SQLTopic(
        key="savepoint",
        name="SQL TCL Savepoint (Partial Rollback)",
        category="TCL (Transaction Control)",
        syntax="SAVEPOINT savepoint_name;\nROLLBACK TO SAVEPOINT savepoint_name;\nRELEASE SAVEPOINT savepoint_name;",
        summary="TCL checkpoint command that creates intermediate savepoints inside an ongoing transaction, enabling partial rollback without cancelling the entire transaction.",
        example="START TRANSACTION;\nINSERT INTO orders (id, total) VALUES (101, 250);\nSAVEPOINT after_order;\nINSERT INTO shipments (order_id, carrier) VALUES (101, 'Express');\n-- If shipment fails, roll back to checkpoint:\nROLLBACK TO SAVEPOINT after_order;\nCOMMIT; -- Order 101 is still preserved!",
        notes="RELEASE SAVEPOINT removes a checkpoint without executing a rollback.",
        difficulty="Advanced",
        challenge="Set a savepoint named 'step1' inside a transaction and roll back to it.",
        solution="START TRANSACTION; UPDATE accounts SET balance = balance - 10 WHERE id = 1; SAVEPOINT step1; UPDATE accounts SET balance = balance - 9999 WHERE id = 1; ROLLBACK TO SAVEPOINT step1; COMMIT;",
    ),
    "autocommit": SQLTopic(
        key="autocommit",
        name="SQL TCL Autocommit Mode",
        category="TCL (Transaction Control)",
        syntax="SET autocommit = 0; -- Disable automatic commits\nSET autocommit = 1; -- Enable automatic commits (default)\nSELECT @@autocommit;",
        summary="Controls whether MySQL commits every individual SQL statement automatically. Disabling autocommit begins an implicit transaction until COMMIT or ROLLBACK is explicitly called.",
        example="SET autocommit = 0;\nUPDATE inventory SET quantity = quantity - 1 WHERE item_id = 5;\nUPDATE orders SET status = 'shipped' WHERE order_id = 12;\nCOMMIT;\nSET autocommit = 1;",
        notes="In autocommit=1 (default), every single DML statement commits immediately upon execution.",
        difficulty="Beginner",
        challenge="Check current autocommit status and temporarily turn it off.",
        solution="SELECT @@autocommit; SET autocommit = 0;",
    ),
    "transaction-isolation": SQLTopic(
        key="transaction-isolation",
        name="SQL TCL Transaction Isolation Levels",
        category="TCL (Transaction Control)",
        syntax="SET [GLOBAL|SESSION] TRANSACTION ISOLATION LEVEL\n    READ UNCOMMITTED |\n    READ COMMITTED |\n    REPEATABLE READ |\n    SERIALIZABLE;",
        summary="Configures the strictness of transaction boundaries to balance concurrency performance against concurrency anomalies (Dirty Reads, Non-repeatable Reads, Phantom Reads).",
        example="SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;\nSELECT @@transaction_isolation;",
        notes="MySQL InnoDB defaults to REPEATABLE READ (using MVCC and Next-Key Locking to eliminate phantom reads). PostgreSQL defaults to READ COMMITTED.",
        difficulty="Advanced",
        challenge="Query the current session transaction isolation level.",
        solution="SELECT @@transaction_isolation;",
    ),

    # --- CONSTRAINTS & INTEGRITY EXTENSIONS ---
    "unique-constraint": SQLTopic(
        key="unique-constraint",
        name="SQL Unique Constraint",
        category="Constraints",
        syntax="CREATE TABLE tbl (\n    id INT,\n    email VARCHAR(255) UNIQUE\n);\n-- Add to existing table:\nALTER TABLE table_name ADD CONSTRAINT uq_col_name UNIQUE (column_name);",
        summary="Ensures that all values in a column or combination of columns are unique across the table. Unlike PRIMARY KEY, UNIQUE constraints permit NULL values (and multiple NULLs in MySQL/PostgreSQL).",
        example="ALTER TABLE students ADD CONSTRAINT uq_student_email UNIQUE (email);",
        notes="MySQL automatically creates a B-Tree index to enforce UNIQUE constraints.",
        difficulty="Beginner",
        challenge="Add a unique constraint to column 'sku' on table 'products'.",
        solution="ALTER TABLE products ADD CONSTRAINT uq_product_sku UNIQUE (sku);",
    ),
    "on-delete-cascade": SQLTopic(
        key="on-delete-cascade",
        name="SQL Foreign Key Cascading (ON DELETE / UPDATE CASCADE)",
        category="Constraints",
        syntax="FOREIGN KEY (parent_id) REFERENCES parent_table(id)\n    ON DELETE CASCADE\n    ON UPDATE CASCADE;\n-- Options: CASCADE | SET NULL | RESTRICT | NO ACTION",
        summary="Controls automated referential integrity behavior when a referenced parent row is deleted or updated. CASCADE automatically deletes or updates child rows.",
        example="CREATE TABLE enrollments (\n    enrollment_id INT PRIMARY KEY AUTO_INCREMENT,\n    student_id INT,\n    course_id INT,\n    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE\n);",
        notes="ON DELETE CASCADE is powerful but dangerous: deleting one customer could delete all their orders, order items, invoices, and payment receipts! Use RESTRICT or SET NULL when records should be preserved.",
        difficulty="Intermediate",
        challenge="Define a foreign key with ON DELETE CASCADE linking 'comments.post_id' to 'posts.id'.",
        solution="ALTER TABLE comments ADD CONSTRAINT fk_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;",
    ),
    "not-null": SQLTopic(
        key="not-null",
        name="SQL Not Null Constraint",
        category="Constraints",
        syntax="CREATE TABLE tbl (id INT NOT NULL, name VARCHAR(100) NOT NULL);\nALTER TABLE table_name MODIFY column_name data_type NOT NULL;",
        summary="Enforces that a column cannot store NULL values, guaranteeing that every inserted or updated record provides explicit data.",
        example="ALTER TABLE students MODIFY first_name VARCHAR(100) NOT NULL;",
        notes="Before altering an existing column to NOT NULL, ensure no existing rows contain NULL, or the ALTER TABLE statement will fail.",
        difficulty="Beginner",
        challenge="Modify a column 'username' on table 'users' to disallow NULL values.",
        solution="ALTER TABLE users MODIFY username VARCHAR(50) NOT NULL;",
    ),

    # --- FUNCTIONS & LOGIC EXTENSIONS ---
    "string-functions": SQLTopic(
        key="string-functions",
        name="SQL String Functions (CONCAT, SUBSTR, LENGTH, TRIM)",
        category="Functions",
        syntax="SELECT CONCAT(first_name, ' ', last_name) AS full_name,\n       UPPER(code), LOWER(email), LENGTH(summary),\n       SUBSTRING(phone, 1, 3) AS area_code,\n       TRIM(comment)\nFROM table_name;",
        summary="Core SQL string manipulation functions for formatting, extracting substrings, measuring character length, changing case, and cleaning whitespace.",
        example="SELECT CONCAT_WS(', ', last_name, first_name) AS formatted_name,\n       UPPER(course) AS course_upper,\n       CHAR_LENGTH(course) AS course_name_len\nFROM students;",
        notes="LENGTH() returns byte length; CHAR_LENGTH() returns character count (critical for UTF-8 / multi-byte characters). CONCAT_WS() concatenates with a separator.",
        difficulty="Beginner",
        challenge="Concatenate student first and last names with a space as 'full_name'.",
        solution="SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM students;",
    ),
    "date-time-functions": SQLTopic(
        key="date-time-functions",
        name="SQL Date & Time Functions (NOW, DATEDIFF, DATE_ADD)",
        category="Functions",
        syntax="SELECT NOW(), CURDATE(), CURTIME();\nSELECT DATE_ADD(created_at, INTERVAL 7 DAY) AS expires_at;\nSELECT DATEDIFF(end_date, start_date) AS days_between;\nSELECT DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') AS formatted_date;",
        summary="Functions for retrieving current time, computing date differences, calculating offsets and deadlines with INTERVAL, and formatting timestamps for display.",
        example="SELECT student_id, first_name,\n       DATE_FORMAT(NOW(), '%W, %M %e, %Y') AS current_report_date\nFROM students;",
        notes="DATEDIFF(expr1, expr2) returns (expr1 - expr2) in days. In MySQL, DATE_SUB(date, INTERVAL n DAY) subtracts days.",
        difficulty="Intermediate",
        challenge="Calculate rows where created_at is within the past 30 days.",
        solution="SELECT * FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY);",
    ),
    "math-functions": SQLTopic(
        key="math-functions",
        name="SQL Math Functions (ROUND, CEIL, FLOOR, ABS, MOD)",
        category="Functions",
        syntax="SELECT ROUND(col, 2), CEIL(col), FLOOR(col), ABS(col), MOD(col, 2) FROM table_name;",
        summary="Standard mathematical operations for precision rounding, absolute values, remainder calculations (modulo), and power exponents.",
        example="SELECT first_name, gpa, ROUND(gpa, 1) AS rounded_gpa, CEIL(gpa) AS gpa_ceiling FROM students;",
        notes="ROUND(val, d) rounds to d decimal places. CEIL() rounds up to next integer; FLOOR() rounds down.",
        difficulty="Beginner",
        challenge="Select numeric scores rounded to 1 decimal place.",
        solution="SELECT id, ROUND(score, 1) AS rounded_score FROM exam_results;",
    ),
    "cross-join": SQLTopic(
        key="cross-join",
        name="SQL Cross Join (Cartesian Product)",
        category="Joins",
        syntax="SELECT * FROM table1 CROSS JOIN table2;\nSELECT * FROM table1, table2; -- Equivalent comma syntax",
        summary="CROSS JOIN produces a Cartesian product matching every row in the first table with every row in the second table (N * M rows returned).",
        example="SELECT s.size_name, c.color_name FROM sizes s CROSS JOIN colors c;",
        notes="Rarely used without filters because 10,000 rows x 10,000 rows yields 100,000,000 rows. Excellent for matrix generation (e.g. sizes x colors).",
        difficulty="Intermediate",
        challenge="Generate all combinations of sizes and colors using CROSS JOIN.",
        solution="SELECT * FROM sizes CROSS JOIN colors;",
    ),
}

# Synonyms for easy keyword search
SYNONYMS: dict[str, str] = {
    "syntax": "syntax",
    "select": "select",
    "distinct": "select-distinct",
    "where": "where",
    "order": "order-by",
    "order by": "order-by",
    "sort": "order-by",
    "and": "and-or-not",
    "or": "and-or-not",
    "not": "and-or-not",
    "insert": "insert-into",
    "insert into": "insert-into",
    "null": "null-values",
    "null values": "null-values",
    "is null": "null-values",
    "update": "update",
    "delete": "delete",
    "top": "select-top-limit",
    "limit": "select-top-limit",
    "offset": "select-top-limit",
    "aggregate": "aggregate-functions",
    "min": "min-max",
    "max": "min-max",
    "count": "count",
    "sum": "sum-avg",
    "avg": "sum-avg",
    "like": "like-wildcards",
    "wildcards": "like-wildcards",
    "in": "in",
    "between": "between",
    "alias": "aliases",
    "aliases": "aliases",
    "as": "aliases",
    "join": "joins",
    "joins": "joins",
    "inner join": "inner-join",
    "left join": "left-join",
    "right join": "right-join",
    "full join": "full-join",
    "self join": "self-join",
    "union": "union",
    "union all": "union",
    "group by": "group-by",
    "group": "group-by",
    "having": "having",
    "exists": "exists",
    "any": "any-all",
    "all": "any-all",
    "case": "case",
    "ifnull": "null-functions",
    "coalesce": "null-functions",
    "stored procedure": "stored-procedures",
    "procedure": "stored-procedures",
    "create db": "create-db",
    "create database": "create-db",
    "drop db": "drop-db",
    "drop database": "drop-db",
    "create table": "create-table",
    "table": "create-table",
    "drop table": "drop-table",
    "alter table": "alter-table",
    "alter": "alter-table",
    "constraints": "constraints",
    "constraint": "constraints",
    "primary key": "primary-key",
    "foreign key": "foreign-key",
    "check": "check-default",
    "default": "check-default",
    "index": "create-index",
    "create index": "create-index",
    "auto increment": "auto-increment",
    "auto_increment": "auto-increment",
    "view": "views",
    "views": "views",
    "injection": "sql-injection",
    "sql injection": "sql-injection",
    "prepared statements": "sql-injection",
    "data types": "data-types",
    "types": "data-types",
    "functions": "mysql-functions",
    "mysql functions": "mysql-functions",
    "cheat sheet": "quick-ref",
    "quick ref": "quick-ref",
    "window": "window-functions",
    "window functions": "window-functions",
    "over": "window-functions",
    "partition by": "window-functions",
    "rank": "window-functions",
    "row number": "window-functions",
    "cte": "cte",
    "with": "cte",
    "common table expression": "cte",
    "transaction": "transactions",
    "transactions": "transactions",
    "commit": "transactions",
    "rollback": "transactions",
    "subquery": "subqueries",
    "subqueries": "subqueries",
    "nested query": "subqueries",
    "explain": "explain-plans",
    "execution plan": "explain-plans",
    "json": "json-querying",
    "json extract": "json-querying",
    "coalesce": "coalesce",
    "truncate": "truncate-table",
    "truncate table": "truncate-table",
    "upsert": "upsert-on-duplicate",
    "on duplicate key": "upsert-on-duplicate",
    "regex": "regex-patterns",
    "regexp": "regex-patterns",
    "rlike": "regex-patterns",
    "conditional aggregation": "conditional-agg",
    "pivot": "conditional-agg",
    "composite index": "indexing-strategies",
    "index performance": "indexing-strategies",
    "ddl": "ddl",
    "data definition": "ddl",
    "data definition language": "ddl",
    "dml": "dml",
    "data manipulation": "dml",
    "data manipulation language": "dml",
    "dcl": "dcl",
    "data control": "dcl",
    "data control language": "dcl",
    "tcl": "tcl",
    "transaction control": "tcl",
    "transaction control language": "tcl",
    "grant": "grant",
    "privilege": "grant",
    "privileges": "grant",
    "revoke": "revoke",
    "user": "create-user",
    "create user": "create-user",
    "drop user": "drop-user",
    "alter user": "alter-user",
    "password": "alter-user",
    "show grants": "show-grants",
    "role": "roles-rbac",
    "roles": "roles-rbac",
    "rbac": "roles-rbac",
    "savepoint": "savepoint",
    "checkpoint": "savepoint",
    "autocommit": "autocommit",
    "isolation": "transaction-isolation",
    "isolation level": "transaction-isolation",
    "rename": "rename-table",
    "rename table": "rename-table",
    "drop index": "drop-index",
    "drop view": "drop-view",
    "trigger": "triggers",
    "triggers": "triggers",
    "create trigger": "triggers",
    "drop trigger": "drop-trigger",
    "replace": "replace-into",
    "replace into": "replace-into",
    "insert into select": "insert-into-select",
    "copy table": "insert-into-select",
    "bulk insert": "bulk-insert",
    "batch insert": "bulk-insert",
    "unique": "unique-constraint",
    "unique constraint": "unique-constraint",
    "cascade": "on-delete-cascade",
    "on delete cascade": "on-delete-cascade",
    "foreign key cascade": "on-delete-cascade",
    "not null": "not-null",
    "string functions": "string-functions",
    "concat": "string-functions",
    "substr": "string-functions",
    "date functions": "date-time-functions",
    "datetime": "date-time-functions",
    "now": "date-time-functions",
    "math functions": "math-functions",
    "round": "math-functions",
    "cross join": "cross-join",
    "cartesian": "cross-join",
}


def lookup_topic(query: str) -> SQLTopic | None:
    """Find a SQL topic by exact key, name, synonym, or fuzzy match."""
    normalized = query.strip().lower().replace("_", " ").replace("-", " ")
    if not normalized:
        return None

    # Exact synonym or key match
    if normalized in SYNONYMS:
        key = SYNONYMS[normalized]
        if key in TOPICS:
            return TOPICS[key]

    for key, topic in TOPICS.items():
        if normalized == key or normalized == topic.name.lower():
            return topic

    # Prefix match
    for key, topic in TOPICS.items():
        if topic.name.lower().startswith(normalized) or key.startswith(normalized):
            return topic

    # Word containment match
    for key, topic in TOPICS.items():
        if normalized in topic.name.lower() or normalized in key:
            return topic

    # Fuzzy match against topic names and keys
    candidates = list(TOPICS.keys()) + [t.name.lower() for t in TOPICS.values()]
    matches = difflib.get_close_matches(normalized, candidates, n=1, cutoff=0.6)
    if matches:
        match = matches[0]
        for key, topic in TOPICS.items():
            if match == key or match == topic.name.lower():
                return topic

    return None


def list_topics() -> list[str]:
    """Return all topic keys for completion and help."""
    return sorted(TOPICS.keys())


def search_topics(query: str) -> list[SQLTopic]:
    """Search topics by keyword across key, name, summary, and syntax."""
    q = query.lower().strip()
    results: list[SQLTopic] = []
    for topic in TOPICS.values():
        if q in topic.key or q in topic.name.lower() or q in topic.summary.lower() or q in topic.syntax.lower():
            results.append(topic)
    return results


def format_topic_card(topic: SQLTopic) -> str:
    """Format a SQLTopic as a clear readable guide."""
    border = "-" * 68
    lines = [
        f"\n+{border}+",
        f"|  {topic.name:<64}|",
        f"|  Category: {topic.category:<54}|",
        f"+{border}+",
        "|  Summary:                                                          |",
    ]
    # Word wrap summary
    import textwrap
    for line in textwrap.wrap(topic.summary, width=64):
        lines.append(f"|  {line:<64}|")

    lines.append(f"+{border}+")
    lines.append("|  Syntax:                                                           |")
    for s_line in topic.syntax.splitlines():
        lines.append(f"|    {s_line:<62}|")

    lines.append(f"+{border}+")
    lines.append("|  Example:                                                          |")
    for e_line in topic.example.splitlines():
        lines.append(f"|    {e_line:<62}|")

    if topic.notes:
        lines.append(f"+{border}+")
        lines.append("|  Notes:                                                            |")
        for n_line in textwrap.wrap(topic.notes, width=64):
            lines.append(f"|  {n_line:<64}|")

    lines.append(f"+{border}+\n")
    return "\n".join(lines)


def get_categories() -> list[str]:
    """Return all unique topic categories sorted alphabetically."""
    return sorted({topic.category for topic in TOPICS.values()})


def filter_topics(category: str = "", query: str = "", difficulty: str = "") -> list[SQLTopic]:
    """Filter topics by category, search query, and difficulty level."""
    cat = category.strip().lower()
    q = query.strip().lower()
    diff = difficulty.strip().lower()

    matches: list[SQLTopic] = []
    for topic in TOPICS.values():
        if cat and cat != "all categories" and cat != "all":
            top_cat = topic.category.lower()
            if top_cat != cat and not top_cat.startswith(cat) and f"({cat})" not in top_cat:
                continue
        if diff and diff != "all levels" and diff != "all" and topic.difficulty.lower() != diff:
            continue
        if q:
            searchable = f"{topic.key} {topic.name} {topic.category} {topic.summary} {topic.syntax} {topic.notes}".lower()
            if q not in searchable:
                continue
        matches.append(topic)
    return matches


def get_topic_challenge(topic: SQLTopic) -> tuple[str, str]:
    """Return (challenge_prompt, solution_sql) for interactive practice missions."""
    if topic.challenge and topic.solution:
        return topic.challenge, topic.solution
    
    # Sensible defaults for topics without custom challenge fields
    prompt = f"Mission: Formulate and execute a '{topic.name}' query using your active database table."
    solution = topic.example
    return prompt, solution


def adapt_query_to_schema(query: str, table_name: str, columns: list[str]) -> str:
    """Intelligently adapt a generic example query to the active table and its actual columns."""
    if not table_name or not columns:
        return query

    # Target table identifier wrapped in backticks
    target_tbl = f"`{table_name}`"

    generic_tables = [
        "table_name", "customers", "products", "employees", "users",
        "orders", "students", "sessions", "codes", "logs", "items", "t1",
        "activities", "departments", "accounts", "staging_import_logs", "user_settings",
        "staging_logs", "records", "metrics", "visitor_stats", "exams"
    ]

    adapted = query
    # Replace generic table names
    for gt in generic_tables:
        pattern = r"\b" + re.escape(gt) + r"\b"
        adapted = re.sub(pattern, target_tbl, adapted, flags=re.IGNORECASE)

    # Column mapping placeholders
    col0 = f"`{columns[0]}`"
    col1 = f"`{columns[1]}`" if len(columns) > 1 else col0
    col2 = f"`{columns[2]}`" if len(columns) > 2 else col1
    col3 = f"`{columns[3]}`" if len(columns) > 3 else col2

    generic_cols = {
        "column1": col0,
        "column2": col1,
        "column3": col2,
        "column_name": col0,
        "col1": col0,
        "col2": col1,
        "col3": col2,
        "col": col0,
    }
    for gc, actual in generic_cols.items():
        pattern = r"\b" + re.escape(gc) + r"\b"
        adapted = re.sub(pattern, actual, adapted, flags=re.IGNORECASE)

    # Substitute common tutorial column names if they don't exist in active table
    common_placeholders = [
        "country", "department", "salary", "price", "email", "phone",
        "stock", "active", "created_at", "order_date", "balance", "points",
        "shipped_at", "in_stock", "expired_at"
    ]
    col_names_lower = [c.lower() for c in columns]
    for ph in common_placeholders:
        if ph not in col_names_lower:
            replacement = col1 if len(columns) > 1 else col0
            pattern = r"\b" + re.escape(ph) + r"\b"
            adapted = re.sub(pattern, replacement, adapted, flags=re.IGNORECASE)

    return adapted

