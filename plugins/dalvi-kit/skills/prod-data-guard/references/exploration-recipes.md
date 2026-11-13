# Structure-only exploration recipes

Every recipe here prints structure, counts or shape, never a field value. Adapt
it to the client you have. Bind parameters (`$1`, `?`, `@table`) through the
client instead of pasting names into SQL.

## Contents

- [Learn a field's meaning without printing it](#learn-a-fields-meaning-without-printing-it)
- [PostgreSQL](#postgresql)
- [MySQL and MariaDB](#mysql-and-mariadb)
- [SQL Server](#sql-server)
- [SQLite](#sqlite)
- [REST and JSON APIs](#rest-and-json-apis)
- [CSV and spreadsheets](#csv-and-spreadsheets)

## Learn a field's meaning without printing it

Documentation, schema comments, an API spec or the application's source settle
meaning best. When none of them does, measure the field's shape. Each check
returns only numbers:

- filled versus empty;
- distinct values versus rows: close to the row count means an identifier or
  free text; a handful means a category;
- minimum and maximum length;
- how many values match a pattern: contains `@`, digits only, a date, contains
  a space (names and free text do);
- how many values also appear in a column you already understand, such as the
  name or id column of a people table: a high overlap means the field points
  to a person.

```sql
-- Illustrative names: is accounts.owner a category, a code or a person?
select count(*)                                              as total_rows
     , count(a.owner)                                        as filled
     , count(distinct a.owner)                               as distinct_values
     , min(length(a.owner))                                  as min_len
     , max(length(a.owner))                                  as max_len
     , sum(case when a.owner like '% %' then 1 else 0 end)   as with_space
     , sum(case when a.owner like '%@%' then 1 else 0 end)   as with_at_sign
     , sum(case when a.owner in (select s.full_name from staff s)
                then 1 else 0 end)                           as matches_a_staff_name
from accounts a;
```

If the result points to a person or to free text, the field holds personal
data: don't group by it and don't print it. If it stays ambiguous, ask.

**Statistics are data, not structure.** PostgreSQL `pg_stats`
(`most_common_vals`, `histogram_bounds`), MySQL histograms in
`information_schema.column_statistics` and SQL Server `DBCC SHOW_STATISTICS`
contain real values from the table.

## PostgreSQL

Open a read-only transaction with a timeout:

```sql
begin transaction read only;
set local statement_timeout = '15s';
```

Context: who you are and whether the session is really read-only.

```sql
select current_database()                                as database_name
     , current_user                                      as role_name
     , current_setting('server_version_num')::integer    as server_version_num
     , current_setting('transaction_read_only')          as transaction_read_only;
```

Relations in one schema (`$1` = schema). `reltuples` is the planner's estimate,
so this does not scan any table:

```sql
select c.relname                                          as object_name
     , case c.relkind
         when 'r' then 'table'     when 'p' then 'partitioned table'
         when 'v' then 'view'      when 'm' then 'materialized view'
         when 'f' then 'foreign table'
       end                                                as kind
     , c.reltuples::bigint                                as estimated_rows
     , c.relrowsecurity                                   as rls_enabled
     , pg_catalog.has_table_privilege(c.oid, 'SELECT')    as can_select
     , pg_catalog.obj_description(c.oid, 'pg_class')      as comment
from pg_catalog.pg_class c
join pg_catalog.pg_namespace n on n.oid = c.relnamespace
where n.nspname = $1
  and c.relkind in ('r', 'p', 'v', 'm', 'f')
order by c.relname;
```

Columns with their comments, constraints, and the triggers a write would fire
(`$1` = `'schema.table'`):

```sql
select a.attname                                              as column_name
     , pg_catalog.format_type(a.atttypid, a.atttypmod)        as data_type
     , a.attnotnull                                           as not_null
     , pg_catalog.col_description(a.attrelid, a.attnum)       as comment
from pg_catalog.pg_attribute a
where a.attrelid = to_regclass($1) and a.attnum > 0 and not a.attisdropped
order by a.attnum;

select conname, contype, pg_catalog.pg_get_constraintdef(oid)
from pg_catalog.pg_constraint where conrelid = to_regclass($1);

select tgname, tgenabled, pg_catalog.pg_get_triggerdef(oid)
from pg_catalog.pg_trigger where tgrelid = to_regclass($1) and not tgisinternal;
```

Never call a function or procedure you discovered while exploring, and never
run `EXPLAIN ANALYZE` on an unknown query: it executes the statement. Planning
can contact remote servers through foreign tables.

The context and relations queries are modified versions of queries in the
`schema-exploration` skill of
[timescale/pg-aiguide](https://github.com/timescale/pg-aiguide), commit
`1aef6e4` (Apache-2.0): columns removed and renamed, reformatted. See `LICENSE`
and `NOTICE` in this skill's folder.

## MySQL and MariaDB

```sql
start transaction read only;
set session max_execution_time = 15000;   -- MySQL, milliseconds, SELECT only
-- MariaDB: set session max_statement_time = 15;   (seconds)

select table_name, table_rows as estimated_rows, table_comment
from information_schema.tables
where table_schema = ? order by table_name;

select column_name, column_type, is_nullable, column_key, column_comment
from information_schema.columns
where table_schema = ? and table_name = ? order by ordinal_position;

select trigger_name, action_timing, event_manipulation
from information_schema.triggers
where event_object_schema = ? and event_object_table = ?;
```

For InnoDB, `table_rows` is an estimate.

## SQL Server

SQL Server has no read-only transaction. Use a login with read-only rights, or
`ApplicationIntent=ReadOnly` against a readable secondary, and set
`SET LOCK_TIMEOUT 15000;`.

```sql
select s.name as schema_name, t.name as table_name, sum(p.rows) as row_count
from sys.tables t
join sys.schemas s on s.schema_id = t.schema_id
join sys.partitions p on p.object_id = t.object_id and p.index_id in (0, 1)
group by s.name, t.name order by s.name, t.name;

select c.name as column_name, ty.name as data_type, c.max_length, c.is_nullable,
       ep.value as description
from sys.columns c
join sys.types ty on ty.user_type_id = c.user_type_id
left join sys.extended_properties ep
  on ep.major_id = c.object_id and ep.minor_id = c.column_id and ep.name = 'MS_Description'
where c.object_id = object_id(@table) order by c.column_id;

select name, is_disabled from sys.triggers where parent_id = object_id(@table);
```

## SQLite

Open the file read-only: `sqlite3.connect("file:<path>?mode=ro", uri=True)` in
Python, or `sqlite3 -readonly <path>` in the shell.

```sql
select type, name from sqlite_schema where type in ('table', 'view', 'trigger') order by type, name;
pragma table_info('<table>');        -- columns, types, not null, primary key
pragma foreign_key_list('<table>');
pragma index_list('<table>');
select count(*) from "<table>";      -- exact count; cheap on small files
```

The `sql` column of `sqlite_schema` holds the DDL, including `CHECK`
constraints and trigger bodies.

## REST and JSON APIs

- Read the API's documentation or OpenAPI spec first: it settles meaning.
- Explore with `GET` only, and check the docs for `GET`s with side effects
  (mark as read, audit "viewed", token rotation).
- Ask for the smallest page the API allows (`limit=1`, `per_page=1`,
  `range=0-0`) and pipe the response straight into the shape printer, without
  saving it to disk:

```python
# shape.py: print key paths and value types of the JSON on stdin, never values.
import json, re, sys

KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,40}$")

def shape(node, path, out):
    if isinstance(node, dict):
        # Keys that are not identifier-like (e-mails, names, ids) are data: collapse them.
        if len(node) > 30 or any(not KEY.match(str(k)) for k in node):
            out.setdefault(path, set()).add(f"map({len(node)} keys)")
            for v in node.values():
                shape(v, path + "{*}", out)
            return
        out.setdefault(path, set()).add("object")
        for k, v in node.items():
            shape(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        out.setdefault(path, set()).add(f"array(len {len(node)})")
        for item in node:
            shape(item, path + "[]", out)
    else:
        out.setdefault(path, set()).add(type(node).__name__)

out = {}
shape(json.load(sys.stdin), "$", out)
for p, types in out.items():
    print(p, "|".join(sorted(types)))
```

`curl -s <url> | python -I shape.py` prints lines like `$.data[].manager object`
and `$.data[].manager.name str`: enough to see that a field is a person, without
seeing who.

## CSV and spreadsheets

An input file with personal data gets the same treatment as the database:
header and counts, not rows. `head`, `cat` and opening the file in a viewer
print rows.

```python
# csv_shape.py <file> [delimiter]: header and per-column counts, never values.
import csv, re, sys

path, delim = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else ";")
with open(path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=delim))
header, body = rows[0], rows[1:]
print(f"columns: {len(header)} | data rows: {len(body)} | "
      f"rows with wrong column count: {sum(len(r) != len(header) for r in body)}")
classes = {"int": r"^-?\d+$", "decimal": r"^-?\d+[.,]\d+$",
           "date": r"^\d{4}-\d{2}-\d{2}|^\d{2}/\d{2}/\d{4}", "has @": r"@", "has space": r" "}
for i, name in enumerate(header):
    vals = [r[i] for r in body if i < len(r) and r[i] != ""]
    counts = {k: sum(bool(re.search(p, v)) for v in vals) for k, p in classes.items()}
    lens = [len(v) for v in vals] or [0]
    print(f"{name!r}: filled {len(vals)}, distinct {len(set(vals))}, "
          f"len {min(lens)}-{max(lens)}, {counts}")
```

Duplicated keys show up as `distinct` lower than `filled` on the key column.
Leading zeros lost to a spreadsheet show up as a length range that is too wide
on a fixed-length code.
