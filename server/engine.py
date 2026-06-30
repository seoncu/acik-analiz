#!/usr/bin/env python3
"""
Açık Analiz — Native Veri Motoru (FastAPI + DuckDB)
====================================================
Maksimum kapasite: veriyi native DuckDB ile (disk-destekli, streaming) işler →
milyarlarca hücre. RAM ile değil, disk ile sınırlıdır.

Çalışma modeli:
  • Bu motor, arayüzü (index.html + api-bridge.js) AYNI kökenden (http://127.0.0.1:8765)
    sunar → tarayıcı mixed-content engeline takılmaz.
  • Başlatıcı (.command/.bat) en güncel dosyaları GitHub'dan çekip bu motoru çalıştırır →
    kullanıcılar her açılışta güncel sürümü alır.

Uçlar: /api/health /api/process /api/process-multi /api/upload /api/set-filters
       /api/aggregate /api/filtered-stats /api/sample /api/sql /api/sql-pivot
       /api/download-processed
"""
import io
import os
import json
import time
import tempfile
import hashlib

import duckdb
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
DUCK_PATH = os.path.join(tempfile.gettempdir(), "acikanaliz_engine.duckdb")

app = FastAPI(title="Açık Analiz Motoru")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Tek bağlantı (tek kullanıcı, yerel). Diske yazar → RAM'i aşan veride spilling.
con = duckdb.connect(DUCK_PATH)
con.execute("PRAGMA threads=4")

STATE = {"headers": [], "numeric": {}, "filter_sql": "", "rows": 0}


# ---------------------------------------------------------------- yardımcılar
def q(name: str) -> str:
    """SQL tanımlayıcı (sütun adı) güvenli tırnaklama."""
    return '"' + str(name).replace('"', '""') + '"'


def lit(s: str) -> str:
    """SQL string literal."""
    return "'" + str(s).replace("'", "''") + "'"


def mask_expr(col: str, mode: str) -> str:
    """Bir sütun için maskeleme SQL ifadesi (çıktı sütunu aynı adla)."""
    c = q(col)
    if mode == "hash":
        return ("CASE WHEN " + c + " IS NULL OR " + c + "='' THEN " + c +
                " ELSE 'MASK_' || upper(substr(md5(CAST(" + c + " AS VARCHAR)),1,8)) END AS " + c)
    if mode == "partial":
        return ("CASE WHEN " + c + " IS NULL OR length(CAST(" + c + " AS VARCHAR))<=3 THEN '***' "
                "ELSE substr(CAST(" + c + " AS VARCHAR),1,1) || repeat('*', length(CAST(" + c +
                " AS VARCHAR))-2) || substr(CAST(" + c + " AS VARCHAR), length(CAST(" + c +
                " AS VARCHAR)), 1) END AS " + c)
    # 'none' (ve bilinmeyen) → olduğu gibi
    return c


def detect_numeric(table: str, cols):
    """Her sütun için sayısal mı tespit.
    KİMLİK/kod sütunlarını (telefon, TCKN, ID) HARİÇ tutar — yoksa DOUBLE'a cast'lenince
    baştaki sıfır kaybolur, 11+ hanede hassasiyet bozulur (…0000), binlik ayraç eklenir.
    """
    out = {}
    for c in cols:
        cc = q(c)
        cv = "CAST(" + cc + " AS VARCHAR)"
        row = con.execute(
            "SELECT "
            "count(*) FILTER (WHERE " + cc + " IS NOT NULL AND " + cv + "<>'') AS ne, "
            "count(*) FILTER (WHERE TRY_CAST(replace(" + cv + ",',','.') AS DOUBLE) IS NOT NULL "
            "AND " + cv + "<>'') AS num, "
            # kimlik-benzeri: '+' ile başlar, baştaki sıfır+rakam, ya da 11+ haneli saf rakam
            "count(*) FILTER (WHERE regexp_matches(" + cv + ", '^(\\+|0[0-9]|[0-9]{11,}$)')) AS ident "
            "FROM " + table
        ).fetchone()
        ne, num, ident = (row[0] or 0), (row[1] or 0), (row[2] or 0)
        out[c] = (ne > 0 and num / ne >= 0.8 and ident == 0)
    return out


def num_col(col: str) -> str:
    """Sayısal kolonu Türkçe-ondalık farkındalığıyla DOUBLE'a çeviren ifade."""
    return "TRY_CAST(replace(CAST(" + q(col) + " AS VARCHAR),',','.') AS DOUBLE)"


def build_col_stats(where=""):
    """Tüm çıktı sütunları için col_stats sözlüğü (frontend kontratı)."""
    w = (" WHERE " + where) if where else ""
    stats = {}
    total = con.execute("SELECT count(*) FROM veri" + w).fetchone()[0]
    for c in STATE["headers"]:
        cc = q(c)
        ne, empt = con.execute(
            "SELECT count(*) FILTER (WHERE " + cc + " IS NOT NULL AND CAST(" + cc + " AS VARCHAR)<>''), "
            "count(*) FILTER (WHERE " + cc + " IS NULL OR CAST(" + cc + " AS VARCHAR)='') FROM veri" + w
        ).fetchone()
        uniq = con.execute("SELECT count(DISTINCT " + cc + ") FROM veri" + w).fetchone()[0]
        # freq: en sık 200 değer
        freq = {}
        for v, cnt in con.execute(
            "SELECT CAST(" + cc + " AS VARCHAR) v, count(*) c FROM veri" + w +
            " GROUP BY 1 ORDER BY c DESC LIMIT 200"
        ).fetchall():
            if v is not None:
                freq[v] = cnt
        s = {"count": int(ne or 0), "empty": int(empt or 0), "uniqueCount": int(uniq or 0),
             "freq": freq, "isNumeric": bool(STATE["numeric"].get(c))}
        if s["isNumeric"]:
            x = num_col(c)
            r = con.execute(
                "SELECT count(" + x + "), sum(" + x + "), avg(" + x + "), stddev_samp(" + x + "), "
                "min(" + x + "), max(" + x + "), median(" + x + "), "
                "quantile_cont(" + x + ",0.25), quantile_cont(" + x + ",0.75) FROM veri" + w
            ).fetchone()
            s["numCount"] = int(r[0] or 0)
            s["sum"] = float(r[1] or 0)
            s["mean"] = float(r[2] or 0)
            s["std"] = float(r[3] or 0)
            s["min"] = float(r[4]) if r[4] is not None else 0
            s["max"] = float(r[5]) if r[5] is not None else 0
            s["median"] = float(r[6]) if r[6] is not None else 0
            s["p25"] = float(r[7]) if r[7] is not None else 0
            s["p75"] = float(r[8]) if r[8] is not None else 0
        stats[c] = s
    return stats, int(total or 0)


def make_veri_from_src(mask_config: dict):
    """_src tablosundan maskelenmiş 'veri' tablosunu kur; STATE'i güncelle."""
    src_cols = [d[0] for d in con.execute("DESCRIBE _src").fetchall()]
    out_headers, exprs = [], []
    for c in src_cols:
        mode = (mask_config or {}).get(c, "none")
        if mode == "remove":
            continue
        out_headers.append(c)
        exprs.append(mask_expr(c, mode))
    con.execute("DROP TABLE IF EXISTS veri")
    con.execute("CREATE TABLE veri AS SELECT " + ", ".join(exprs) + " FROM _src")
    STATE["headers"] = out_headers
    STATE["numeric"] = detect_numeric("veri", out_headers)
    STATE["filter_sql"] = ""
    STATE["rows"] = con.execute("SELECT count(*) FROM veri").fetchone()[0]


def rows_as_dicts(sql):
    rel = con.execute(sql)
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def _read_into_src(path, delimiter):
    delim = "\\t" if delimiter in ("\t", "\\t", "tsv") else (delimiter or ",")
    con.execute("DROP TABLE IF EXISTS _src")
    con.execute(
        "CREATE TABLE _src AS SELECT * FROM read_csv(" + lit(path) +
        ", header=true, all_varchar=true, delim=" + lit(delim) +
        ", quote='\"', escape='\"', sample_size=-1, ignore_errors=true)"
    )


# ---------------------------------------------------------------- statik UI
@app.get("/")
def index():
    p = os.path.join(HERE, "index.html")
    if os.path.exists(p):
        return FileResponse(p)
    return HTMLResponse("<h3>index.html bulunamadı. Başlatıcı en güncel arayüzü indirememiş olabilir.</h3>")


@app.get("/api-bridge.js")
def bridge():
    p = os.path.join(HERE, "api-bridge.js")
    if os.path.exists(p):
        return FileResponse(p, media_type="application/javascript")
    return PlainTextResponse("// api-bridge.js yok", media_type="application/javascript")


@app.get("/server/api-bridge.js")
def bridge2():
    return bridge()


# ---------------------------------------------------------------- API
@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "DuckDB", "duckdb": duckdb.__version__,
            "rows": STATE["rows"], "cols": len(STATE["headers"])}


@app.post("/api/process")
async def process(file: UploadFile = File(...), mask_config: str = Form("{}"), delimiter: str = Form(",")):
    t0 = time.time()
    try:
        data = await file.read()
        tmp = os.path.join(tempfile.gettempdir(), "acikanaliz_input_" + str(int(t0)) + ".csv")
        with open(tmp, "wb") as f:
            f.write(data)
        _read_into_src(tmp, delimiter)
        make_veri_from_src(json.loads(mask_config or "{}"))
        col_stats, total = build_col_stats()
        sample_rows = rows_as_dicts("SELECT * FROM veri USING SAMPLE 5000 ROWS")
        preview_rows = rows_as_dicts("SELECT * FROM veri LIMIT 20")
        try:
            os.remove(tmp)
        except Exception:
            pass
        return {"ok": True, "rows": total, "cols": len(STATE["headers"]),
                "cells": total * len(STATE["headers"]), "headers": STATE["headers"],
                "delimiter": delimiter, "processing_time": round(time.time() - t0, 2),
                "col_stats": col_stats, "sample_rows": sample_rows, "preview_rows": preview_rows}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/process-multi")
async def process_multi(files: list[UploadFile] = File(...), mask_config: str = Form("{}"),
                        delimiter: str = Form(","), labels: str = Form("[]")):
    t0 = time.time()
    try:
        # Dosyaları tek tek _src'ye birleştir (yatay/MERGE — alt alta)
        con.execute("DROP TABLE IF EXISTS _src")
        first = True
        for uf in files:
            data = await uf.read()
            tmp = os.path.join(tempfile.gettempdir(), "acikanaliz_m_" + str(int(time.time() * 1000)) + ".csv")
            with open(tmp, "wb") as f:
                f.write(data)
            delim = "\\t" if delimiter in ("\t", "\\t", "tsv") else (delimiter or ",")
            sub = ("SELECT * FROM read_csv(" + lit(tmp) + ", header=true, all_varchar=true, delim=" +
                   lit(delim) + ", quote='\"', escape='\"', sample_size=-1, ignore_errors=true)")
            if first:
                con.execute("CREATE TABLE _src AS " + sub)
                first = False
            else:
                # union by name → eksik sütunlar NULL
                con.execute("INSERT INTO _src BY NAME " + sub)
            try:
                os.remove(tmp)
            except Exception:
                pass
        make_veri_from_src(json.loads(mask_config or "{}"))
        col_stats, total = build_col_stats()
        sample_rows = rows_as_dicts("SELECT * FROM veri USING SAMPLE 5000 ROWS")
        preview_rows = rows_as_dicts("SELECT * FROM veri LIMIT 20")
        return {"ok": True, "rows": total, "cols": len(STATE["headers"]),
                "cells": total * len(STATE["headers"]), "headers": STATE["headers"],
                "delimiter": delimiter, "processing_time": round(time.time() - t0, 2),
                "col_stats": col_stats, "sample_rows": sample_rows, "preview_rows": preview_rows}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    return await process(file=file, mask_config="{}", delimiter=",")


def build_filter_sql(filters: dict) -> str:
    """Frontend filtre nesnesinden WHERE ifadesi (best-effort)."""
    parts = []
    for col, f in (filters or {}).items():
        if col not in STATE["headers"]:
            continue
        cc = q(col)
        if isinstance(f, dict):
            if STATE["numeric"].get(col):
                x = num_col(col)
                if f.get("minVal") not in (None, ""):
                    parts.append(x + " >= " + str(float(f["minVal"])))
                if f.get("maxVal") not in (None, ""):
                    parts.append(x + " <= " + str(float(f["maxVal"])))
            inc = f.get("includeValues") or []
            exc = f.get("excludeValues") or []
            if inc:
                parts.append("CAST(" + cc + " AS VARCHAR) IN (" + ",".join(lit(str(v)) for v in inc) + ")")
            if exc:
                parts.append("CAST(" + cc + " AS VARCHAR) NOT IN (" + ",".join(lit(str(v)) for v in exc) + ")")
    return " AND ".join(parts)


@app.post("/api/set-filters")
async def set_filters(req: Request):
    body = await req.json()
    STATE["filter_sql"] = build_filter_sql(body.get("filters") or {})
    return {"ok": True, "where": STATE["filter_sql"]}


@app.post("/api/aggregate")
async def aggregate(req: Request):
    body = await req.json()
    x = body.get("x")
    ys = body.get("y") or []
    agg = (body.get("agg") or "count").lower()
    sort = (body.get("sort") or "desc").lower()
    limit = int(body.get("limit") or 15)
    if not x or x not in STATE["headers"]:
        return {"labels": [], "datasets": []}
    w = (" WHERE " + STATE["filter_sql"]) if STATE["filter_sql"] else ""
    sel = [q(x) + " AS _lbl", "count(*) AS _n"]
    dnames = []
    for y in ys:
        if y not in STATE["headers"]:
            continue
        xx = num_col(y)
        if agg == "sum":
            sel.append("sum(" + xx + ")")
        elif agg in ("avg", "mean"):
            sel.append("avg(" + xx + ")")
        elif agg == "min":
            sel.append("min(" + xx + ")")
        elif agg == "max":
            sel.append("max(" + xx + ")")
        elif agg == "median":
            sel.append("median(" + xx + ")")
        elif agg == "std":
            sel.append("stddev_samp(" + xx + ")")
        else:
            sel.append("count(" + xx + ")")
        dnames.append(y)
    order = "_n DESC" if sort == "desc" else ("_n ASC" if sort == "asc" else "_lbl")
    sql = ("SELECT " + ", ".join(sel) + " FROM veri" + w + " GROUP BY 1 ORDER BY " + order +
           " LIMIT " + str(limit))
    rel = con.execute(sql)
    rows = rel.fetchall()
    labels = [("" if r[0] is None else str(r[0])) for r in rows]
    counts = [int(r[1] or 0) for r in rows]
    datasets = []
    if not dnames:  # sadece sayım
        datasets.append({"label": "Sayı", "data": counts})
    else:
        for i, name in enumerate(dnames):
            datasets.append({"label": name, "data": [float(r[2 + i]) if r[2 + i] is not None else 0 for r in rows]})
    return {"labels": labels, "datasets": datasets, "_counts": counts, "fullLabels": labels}


@app.post("/api/filtered-stats")
async def filtered_stats(req: Request):
    body = await req.json()
    where = build_filter_sql(body.get("filters") or {})
    col_stats, total = build_col_stats(where)
    return {"ok": True, "col_stats": col_stats, "rowCount": total}


@app.post("/api/sample")
async def sample(req: Request):
    body = await req.json()
    n = int(body.get("n") or 1000)
    off = int(body.get("offset") or 0)
    rows = rows_as_dicts("SELECT * FROM veri LIMIT " + str(n) + " OFFSET " + str(off))
    return {"ok": True, "rows": rows}


@app.post("/api/sql")
async def run_sql(req: Request):
    body = await req.json()
    sql = (body.get("sql") or "").strip()
    if not sql:
        return JSONResponse({"error": "Boş sorgu"}, status_code=400)
    try:
        rel = con.execute(sql)
        cols = [d[0] for d in rel.description] if rel.description else []
        data = rel.fetchall()
        rows = [[(None if v is None else v) for v in r] for r in data[:100000]]
        return {"columns": cols, "rows": rows,
                "totalDataRows": STATE["rows"], "totalDataCols": len(STATE["headers"])}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/sql-pivot")
async def sql_pivot(req: Request):
    body = await req.json()
    row_dim = body.get("rowDim")
    col_dim = body.get("colDim") or ""
    value_fields = body.get("valueFields") or []
    where = body.get("where") or ""
    order_dir = body.get("orderDir") or "ASC"
    if not row_dim:
        return JSONResponse({"error": "Satır boyutu yok"}, status_code=400)
    w = (" WHERE " + where) if where else ""
    try:
        # Grup-bazlı mod (frontend bunu sorunsuz render eder)
        sel = [q(row_dim), "count(*) AS _n"]
        for vf in value_fields:
            col = vf.get("col")
            for ag in (vf.get("aggs") or ["sum"]):
                if col not in STATE["headers"]:
                    continue
                xx = num_col(col)
                fn = {"mean": "avg", "avg": "avg", "sum": "sum", "min": "min",
                      "max": "max", "median": "median", "std": "stddev_samp",
                      "count": "count"}.get(ag, "sum")
                alias = q(col + "_" + ag)
                sel.append(fn + "(" + (xx if ag != "count" else "*") + ") AS " + alias)
        sql = ("SELECT " + ", ".join(sel) + " FROM veri" + w + " GROUP BY 1 ORDER BY " +
               q(row_dim) + " " + ("DESC" if order_dir.upper() == "DESC" else "ASC"))
        rel = con.execute(sql)
        cols = [d[0] for d in rel.description]
        rows = [list(r) for r in rel.fetchall()]
        return {"columns": cols, "rows": rows, "mode": "groupby"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/download-processed")
def download_processed(format: str = "csv"):
    if not STATE["headers"]:
        return JSONResponse({"error": "İşlenmiş veri yok"}, status_code=400)
    out = os.path.join(tempfile.gettempdir(), "acikanaliz_masked." + ("xlsx" if format == "xlsx" else "csv"))
    try:
        if format == "xlsx":
            con.execute("INSTALL excel; LOAD excel;")
            con.execute("COPY veri TO " + lit(out) + " WITH (FORMAT xlsx, HEADER true)")
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            con.execute("COPY veri TO " + lit(out) + " WITH (FORMAT csv, HEADER true)")
            media = "text/csv"
        return FileResponse(out, media_type=media, filename=os.path.basename(out))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    print("=" * 56)
    print("  Açık Analiz Motoru — http://127.0.0.1:%d" % PORT)
    print("  DuckDB %s · Tarayıcı otomatik açılacak" % duckdb.__version__)
    print("  Durdurmak için: Ctrl+C")
    print("=" * 56)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
