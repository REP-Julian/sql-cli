"""Conservative classification of SQL statements before interactive execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SQLSafety:
    verb: str | None
    requires_confirmation: bool
    missing_where: bool
    multiple_statements: bool = False


_MUTATING = {
    "DELETE", "UPDATE", "INSERT", "REPLACE", "LOAD", "CALL", "CREATE", "ALTER",
    "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE",
}
_WHERE_REQUIRED = {"DELETE", "UPDATE"}


def _tokens(sql: str) -> list[tuple[str, int, bool]]:
    """Return SQL words with nesting depth; skip literals and comments."""
    tokens: list[tuple[str, int, bool]] = []
    depth = 0
    index = 0
    size = len(sql)
    while index < size:
        char = sql[index]
        following = sql[index + 1] if index + 1 < size else ""
        if char in "'\"":
            quote = char
            index += 1
            while index < size:
                if sql[index] == "\\":
                    index += 2
                elif sql[index] == quote:
                    if index + 1 < size and sql[index + 1] == quote:
                        index += 2
                    else:
                        index += 1
                        break
                else:
                    index += 1
            continue
        if char == "`":
            index += 1
            identifier = []
            while index < size:
                if sql[index] == "`":
                    if index + 1 < size and sql[index + 1] == "`":
                        identifier.append("`")
                        index += 2
                    else:
                        index += 1
                        break
                else:
                    identifier.append(sql[index])
                    index += 1
            tokens.append(("".join(identifier).upper(), depth, True))
            continue
        if char == "#" or (char == "-" and following == "-" and (index + 2 == size or sql[index + 2].isspace())):
            newline = sql.find("\n", index)
            index = size if newline == -1 else newline + 1
            continue
        if char == "/" and following == "*":
            end = sql.find("*/", index + 2)
            mysql_executable = index + 2 < size and sql[index + 2] == "!"
            mariadb_executable = (
                index + 3 < size
                and sql[index + 2:index + 4].upper() == "M!"
            )
            if mysql_executable or mariadb_executable:
                # MySQL (/*! ... */) and MariaDB (/*M! ... */) execute
                # version comments, so scan their contents as SQL.
                body_start = index + (4 if mariadb_executable else 3)
                version_end = body_start
                while version_end < size and sql[version_end].isdigit():
                    version_end += 1
                if version_end > body_start and version_end < size and sql[version_end].isspace():
                    body_start = version_end
                body_end = size if end == -1 else end
                tokens.extend(
                    (word, depth + nested_depth, quoted)
                    for word, nested_depth, quoted in _tokens(sql[body_start:body_end])
                )
            index = size if end == -1 else end + 2
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            index += 1
            continue
        if char == ";":
            tokens.append((";", depth, False))
            index += 1
            continue
        if char.isalpha() or char in "_$":
            end = index + 1
            while end < size and (sql[end].isalnum() or sql[end] in "_$"):
                end += 1
            tokens.append((sql[index:end].upper(), depth, False))
            index = end
            continue
        index += 1
    return tokens


def inspect_sql(sql: str) -> SQLSafety:
    tokens = _tokens(sql)
    nonempty_sections = 0
    has_content = False
    for word, _, _ in tokens:
        if word == ";":
            nonempty_sections += int(has_content)
            has_content = False
        else:
            has_content = True
    nonempty_sections += int(has_content)
    multiple_statements = nonempty_sections > 1
    top_level = [(word, position) for position, (word, depth, quoted) in enumerate(tokens) if depth == 0 and not quoted]
    if not top_level:
        return SQLSafety(None, False, False, multiple_statements)

    first = top_level[0][0]
    verb_position = 0
    if first == "WITH":
        main = next(
            ((word, position) for word, position in top_level[1:] if word in _MUTATING | {"SELECT"}),
            (None, -1),
        )
        verb, verb_position = main
    else:
        verb = first

    if verb is None:
        return SQLSafety(None, False, False, multiple_statements)

    main_words = [word for word, position in top_level if position >= verb_position]
    missing_where = verb in _WHERE_REQUIRED and "WHERE" not in main_words[1:]
    special_select = verb == "SELECT" and any(
        pair in zip(main_words, main_words[1:])
        for pair in (("INTO", "OUTFILE"), ("INTO", "DUMPFILE"), ("FOR", "UPDATE"))
    )
    return SQLSafety(verb, verb in _MUTATING or special_select, missing_where, multiple_statements)
