import unittest
from sqlcli.knowledge import (
    TOPICS,
    adapt_query_to_schema,
    filter_topics,
    format_topic_card,
    get_categories,
    get_topic_challenge,
    list_topics,
    lookup_topic,
)


class KnowledgeTests(unittest.TestCase):
    def test_all_core_w3_topics_present(self):
        topics = list_topics()
        expected = [
            "syntax", "select", "select-distinct", "where", "order-by",
            "and-or-not", "insert-into", "null-values", "update", "delete",
            "select-top-limit", "aggregate-functions", "min-max", "count",
            "sum-avg", "like-wildcards", "in", "between", "aliases",
            "joins", "inner-join", "left-join", "right-join", "full-join",
            "self-join", "union", "group-by", "having", "exists",
            "any-all", "case", "null-functions", "stored-procedures",
            "create-db", "drop-db", "create-table", "drop-table",
            "alter-table", "constraints", "primary-key", "foreign-key",
            "check-default", "create-index", "auto-increment", "views",
            "sql-injection", "data-types", "mysql-functions", "quick-ref",
            "window-functions", "cte", "transactions", "subqueries",
            "explain-plans", "json-querying", "coalesce", "truncate-table",
            "upsert-on-duplicate", "regex-patterns", "conditional-agg",
            "indexing-strategies",
        ]
        for key in expected:
            with self.subTest(key=key):
                self.assertIn(key, TOPICS)

    def test_lookup_topic_by_key_and_synonyms(self):
        self.assertIsNotNone(lookup_topic("create-table"))
        self.assertIsNotNone(lookup_topic("create table"))
        self.assertIsNotNone(lookup_topic("table"))
        self.assertIsNotNone(lookup_topic("joins"))
        self.assertIsNotNone(lookup_topic("inner join"))
        self.assertIsNotNone(lookup_topic("group by"))
        self.assertIsNotNone(lookup_topic("data types"))
        self.assertIsNotNone(lookup_topic("window functions"))
        self.assertIsNotNone(lookup_topic("cte"))
        self.assertIsNotNone(lookup_topic("transactions"))
        self.assertIsNotNone(lookup_topic("explain"))
        # DDL, DML, DCL, TCL lookups
        self.assertIsNotNone(lookup_topic("ddl"))
        self.assertIsNotNone(lookup_topic("dml"))
        self.assertIsNotNone(lookup_topic("dcl"))
        self.assertIsNotNone(lookup_topic("tcl"))
        self.assertIsNotNone(lookup_topic("grant"))
        self.assertIsNotNone(lookup_topic("revoke"))
        self.assertIsNotNone(lookup_topic("create user"))
        self.assertIsNotNone(lookup_topic("rollback"))
        self.assertIsNotNone(lookup_topic("savepoint"))
        self.assertIsNotNone(lookup_topic("triggers"))
        self.assertIsNotNone(lookup_topic("unique constraint"))

    def test_format_topic_card_contains_metadata(self):
        topic = lookup_topic("create-table")
        card = format_topic_card(topic)
        self.assertIn("SQL Create Table", card)
        self.assertIn("Syntax:", card)
        self.assertIn("Example:", card)

    def test_filter_topics(self):
        basics = filter_topics(category="Basics")
        self.assertTrue(len(basics) > 0)
        for t in basics:
            self.assertEqual(t.category, "Basics")

        ddl_topics = filter_topics(category="DDL")
        self.assertTrue(len(ddl_topics) >= 5)

        dml_topics = filter_topics(category="DML")
        self.assertTrue(len(dml_topics) >= 4)

        dcl_topics = filter_topics(category="DCL")
        self.assertTrue(len(dcl_topics) >= 5)

        tcl_topics = filter_topics(category="TCL")
        self.assertTrue(len(tcl_topics) >= 4)

        filtered = filter_topics(query="window")
        self.assertTrue(any(t.key == "window-functions" for t in filtered))

    def test_get_categories_contains_ddl_dml_dcl_tcl(self):
        cats = get_categories()
        self.assertIn("DDL (Data Definition)", cats)
        self.assertIn("DML (Data Manipulation)", cats)
        self.assertIn("DCL (Data Control)", cats)
        self.assertIn("TCL (Transaction Control)", cats)
        self.assertIn("Constraints", cats)
        self.assertIn("Basics", cats)

    def test_adapt_query_to_schema(self):
        query = "SELECT DISTINCT country FROM customers ORDER BY country;"
        adapted = adapt_query_to_schema(query, "students", ["student_id", "first_name", "gpa"])
        self.assertIn("`students`", adapted)
        self.assertIn("`first_name`", adapted)

    def test_get_topic_challenge(self):
        topic = lookup_topic("cte")
        prompt, solution = get_topic_challenge(topic)
        self.assertTrue(len(prompt) > 0)
        self.assertTrue("WITH" in solution or "SELECT" in solution)


if __name__ == "__main__":
    unittest.main()
