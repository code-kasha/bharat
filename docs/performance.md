# Performance

Measured on 26 September 2026 with the bundled 155,599-office database on a Windows laptop, in-process through Django's test client (no network). Values are medians of 30 requests after one warm-up; "queries" counts database queries per request.

| Request | Median | p95 | Queries |
| --- | ---: | ---: | ---: |
| PIN lookup, API or page (`110001`, 23 offices) | 2.3 ms | 2.9 ms | 3 |
| Home page / dataset metadata | 1 ms | 1.5 ms | 1 |
| Search `market`, API or page (140 matches) | 78 ms | 81 ms | 2–3 |
| Search with no matches (`zzqx`) | 49 ms | 59 ms | 2 |
| Search `an` (64,904 matches) | 95 ms | 113 ms | 2 |
| State filter (`Kerala`) | 39 ms | 44 ms | 2 |
| States list | 18 ms | 20 ms | 2 |
| Districts list (all states) | 202 ms | 215 ms | 2 |
| Districts for one state | 31 ms | 36 ms | 2 |
| Full export, one request | 1.2 s (42.9 MB; 1.4 MB gzip) | | 3 |

PIN lookups use the PIN index. Search scans the table because substring matching (`LIKE '%term%'`) cannot use an index; at this size that stays under about 0.1 s. The all-states districts list groups the whole table on each request. A composite `(state, district)` index was measured on a copy of the database to cut that query from about 92 ms to 0.5 ms (page count from 109 ms to 15 ms), but it adds 4.4 MB to `db.sqlite3`, so it is not included.

## Design notes

The lookup page costs one HTTP request and three database queries: the dataset label, the result count and one page of 25 offices. It declares an inline icon so browsers skip `/favicon.ico`; that path answers with a cached empty response for browsers that request it anyway.

The design deliberately keeps one directory snapshot, no user accounts, and no runtime dependency on the upstream API. SQLite runs in WAL mode, so reads continue during a replacement. Writers use immediate transactions, so concurrent fetches are serialized. PIN lookup uses an indexed exact match. Place search uses substring matching; it is not fuzzy search.
