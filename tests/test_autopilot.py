import unittest
from sqlcli.autopilot import rule_based_sql_generator


class AutopilotTests(unittest.TestCase):
    def test_generates_create_database(self):
        result = rule_based_sql_generator("create database store")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("CREATE DATABASE IF NOT EXISTS `store`", sql)

    def test_generates_create_table_with_columns(self):
        result = rule_based_sql_generator("create table students with id, first name, email, age int")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("CREATE TABLE IF NOT EXISTS `students`", sql)
        self.assertIn("`first_name` VARCHAR", sql)
        self.assertIn("`email` VARCHAR", sql)
        self.assertIn("`age` INT", sql)

    def test_generates_foreign_keys(self):
        result = rule_based_sql_generator("create table orders with user id, total amount, foreign key to users")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)", sql)

    def test_generates_select_with_where(self):
        result = rule_based_sql_generator("show all records from users where age >= 18")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("SELECT * FROM `users` WHERE age >= 18 LIMIT 50;", sql)

    def test_generates_count(self):
        result = rule_based_sql_generator("count records in orders")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertEqual(sql, "SELECT COUNT(*) AS `total_count` FROM `orders`;")

    def test_generates_top_n_ranking(self):
        result = rule_based_sql_generator("top 5 highest salary in employees")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("SELECT * FROM `employees` ORDER BY `salary` DESC LIMIT 5;", sql)

    def test_generates_duplicates(self):
        result = rule_based_sql_generator("find duplicate emails in users")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("SELECT `emails`, COUNT(*) AS `duplicate_count` FROM `users` GROUP BY `emails` HAVING `duplicate_count` > 1", sql)

    def test_generates_join(self):
        result = rule_based_sql_generator("join orders with customers")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("SELECT * FROM `orders` INNER JOIN `customers` ON `orders`.`customer_id` = `customers`.`id` LIMIT 50;", sql)

    def test_generates_add_column(self):
        result = rule_based_sql_generator("add column phone varchar(20) to users")
        self.assertIsNotNone(result)
        sql, cat, exp = result
        self.assertIn("ALTER TABLE `users` ADD COLUMN `phone` VARCHAR(20);", sql)


if __name__ == "__main__":
    unittest.main()
