# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Test a running local Wrangler preview; pass --double-opt-in when enabled.

Use --persist-to to match an isolated Wrangler local database, if applicable.
"""

import argparse
import hashlib
import http.client
import json
import re
import sqlite3
import subprocess
import tempfile
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / "scambio-site"
WRANGLER = SITE / "node_modules/.bin/wrangler"
SUFFIX = uuid.uuid4().hex[:12]
COUNT = 0
PERSIST_TO = None


def request(path, *, method="GET", data=None, headers=None, chunked=False):
    connection = http.client.HTTPConnection("127.0.0.1", 8787, timeout=10)
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    base = {
        "Origin": "https://scambio.app",
        "Content-Type": "application/json",
        "Sec-Fetch-Site": "same-origin",
        "CF-Connecting-IP": "192.0.2.120",
    }
    base.update(headers or {})
    ip = int(base["CF-Connecting-IP"].rsplit(".", 1)[1])
    base["CF-Connecting-IP"] = f"2001:db8:{SUFFIX[:4]}:{SUFFIX[4:8]}::{ip:x}"
    base = {key: value for key, value in base.items() if value is not None}
    connection.request(method, path, body=body, headers=base, encode_chunked=chunked)
    response = connection.getresponse()
    status, response_headers, content = (
        response.status,
        dict(response.getheaders()),
        response.read(),
    )
    connection.close()
    lower = {key.lower(): value for key, value in response_headers.items()}
    assert lower["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in lower["content-security-policy"]
    assert "unsafe-inline" not in lower["content-security-policy"]
    assert lower["strict-transport-security"] == "max-age=31536000"
    assert "camera=()" in lower["permissions-policy"]
    global COUNT
    COUNT += 1
    return status, lower, content


def sql(command):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql") as source:
        source.write(command)
        source.flush()
        result = subprocess.run(
            [
                str(WRANGLER),
                "d1",
                "execute",
                "scambio-waitlist",
                "--local",
                "--file",
                source.name,
                "--json",
                *(["--persist-to", PERSIST_TO] if PERSIST_TO else []),
            ],
            cwd=SITE,
            capture_output=True,
            text=True,
            check=True,
        )
    return json.loads(result.stdout)[0]["results"]


def row(email):
    return sql(
        "SELECT * FROM waitlist WHERE email = '" + email.replace("'", "''") + "'"
    )[0]


def token_for(record):
    directory = SITE / ".wrangler/tmp/email"
    for path in directory.rglob("*.txt"):
        match = re.search(
            r"https://scambio.app/api/confirm\?t=([a-f0-9]{64})", path.read_text()
        )
        if (
            match
            and hashlib.sha256(match[1].encode()).hexdigest() == record["token_hash"]
        ):
            return match[1]
    raise AssertionError("No simulated email matches the stored token hash")


def signup(email, lang="en"):
    return {
        "email": email,
        "computer": ["Mac"],
        "phone": ["Android"],
        "consent": True,
        "lang": lang,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--double-opt-in", action="store_true")
    parser.add_argument("--persist-to")
    args = parser.parse_args()
    global PERSIST_TO
    PERSIST_TO = args.persist_to
    config = tomllib.loads((SITE / "wrangler.toml").read_text())
    assert "migrations_dir" not in config["d1_databases"][0]
    assert "send_email" not in config
    assert config["vars"]["DOUBLE_OPT_IN"] == "false"
    # Migration preserves all existing fields and requires fresh confirmation.
    db = sqlite3.connect(":memory:")
    db.executescript((SITE / "schema.sql").read_text())
    db.execute(
        "INSERT INTO waitlist VALUES (?,?,?,?,?,?,?,?)",
        ("legacy@example.test", "Mac", "Android", None, "en", "old", "old", "old"),
    )
    migrations = sorted((SITE / "migrations").glob("*.sql"))
    for migration in migrations[:2]:
        db.executescript(migration.read_text())
    assert db.execute(
        "SELECT status, consent_at, token_hash FROM waitlist"
    ).fetchone() == ("legacy_unconfirmed", "old", None)
    for status in ("pending", "confirmed"):
        db.execute(
            "INSERT INTO waitlist VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                status + "@example.test",
                "Linux",
                "iPhone",
                "Device",
                "it",
                "consent",
                "created",
                "updated",
                status,
                "hash" if status == "pending" else None,
                123456 if status == "pending" else None,
                "confirmed" if status == "confirmed" else None,
            ),
        )
    before = db.execute("SELECT * FROM waitlist ORDER BY email").fetchall()
    db.execute("INSERT INTO waitlist_daily_quota VALUES ('2026-10-08', 12)")
    db.executescript(migrations[2].read_text())
    assert db.execute("SELECT * FROM waitlist ORDER BY email").fetchall() == before
    assert db.execute("SELECT count FROM waitlist_daily_quota").fetchone() == (12,)
    db.execute("UPDATE waitlist SET status='unconfirmed' WHERE status='pending'")
    for command in (
        "UPDATE waitlist SET status='invalid'",
        "UPDATE waitlist SET token_hash='duplicate'",
    ):
        try:
            db.execute(command)
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Migration lost a constraint: " + command)
    db.close()
    print("PASS migration preserves all records, quota and constraints", flush=True)
    endpoint = "/api/waitlist"
    for origin in (
        None,
        "http://localhost.attacker.example",
        "https://www.scambio.app",
        "http://localhost:8788",
        "http://localhost:8787",
    ):
        assert (
            request(endpoint, method="POST", data={}, headers={"Origin": origin})[0]
            == 403
        )
    assert (
        request(
            endpoint, method="POST", data={}, headers={"Sec-Fetch-Site": "cross-site"}
        )[0]
        == 403
    )
    assert (
        request(
            endpoint, method="POST", data={}, headers={"Content-Type": "text/plain"}
        )[0]
        == 415
    )
    assert request(endpoint, method="GET")[0] == 405
    assert (
        request(
            endpoint,
            method="POST",
            data=b"x" * 4097,
            headers={"CF-Connecting-IP": "192.0.2.121"},
        )[0]
        == 413
    )
    assert (
        request(
            endpoint,
            method="POST",
            data=iter([b"x" * 3000, b"x" * 1097]),
            chunked=True,
            headers={"CF-Connecting-IP": "192.0.2.122"},
        )[0]
        == 413
    )
    assert (
        request(
            endpoint,
            method="POST",
            data=b"null",
            headers={"CF-Connecting-IP": "192.0.2.123"},
        )[0]
        == 400
    )
    print("PASS origin, content type, streaming body limit and headers", flush=True)
    for index in range(6):
        status = request(
            endpoint,
            method="POST",
            data={"website": "bot"},
            headers={"CF-Connecting-IP": "192.0.2.124"},
        )[0]
        assert status == (200 if index < 5 else 429), (index, status)
    print("PASS Cloudflare rate limit", flush=True)
    for index, invalid in enumerate(
        (
            {"consent": False},
            {"email": "invalid"},
            {"computer": []},
            {"phone": ["invalid"]},
            {"device": []},
        )
    ):
        assert (
            request(
                endpoint,
                method="POST",
                data={**signup("invalid@example.test"), **invalid},
                headers={"CF-Connecting-IP": f"192.0.2.{150 + index}"},
            )[0]
            == 422
        )
    for index, status in enumerate(
        ("legacy_unconfirmed", "unconfirmed", "pending", "confirmed")
    ):
        email = f"spec05-{SUFFIX}-{status}@example.test"
        old_token = hashlib.sha256(email.encode()).hexdigest()
        old_hash = hashlib.sha256(old_token.encode()).hexdigest()
        sql(f"""INSERT INTO waitlist
            (email, computer, phone, device, lang, consent_at, created_at, updated_at,
             status, token_hash, token_expires, confirmed_at)
            VALUES ('{email}', 'Linux', 'iPhone', 'Old device', 'it',
              'old', 'old', 'old',
              '{status}', {repr(old_hash) if status == "pending" else "NULL"},
              {4102444800 if status == "pending" else "NULL"},
              {"'old'" if status == "confirmed" else "NULL"})""")
        before = row(email)
        emails_before = set((SITE / ".wrangler/tmp/email").rglob("*.txt"))
        result = request(
            endpoint,
            method="POST",
            data=signup(email),
            headers={"CF-Connecting-IP": f"192.0.2.{140 + index}"},
        )
        assert result[0] == 200
        assert json.loads(result[2]) == {"ok": True, "confirm": args.double_opt_in}
        after = row(email)
        if status == "confirmed":
            assert after == before
        else:
            assert after["status"] == (
                "pending" if args.double_opt_in else "unconfirmed"
            )
            assert after["computer"] == "Mac" and after["phone"] == "Android"
            assert after["lang"] == "en" and after["device"] is None
            assert after["created_at"] == "old" and after["consent_at"] != "old"
            assert after["confirmed_at"] is None
            if args.double_opt_in:
                assert token_for(after) != old_token
            else:
                assert after["token_hash"] is None and after["token_expires"] is None
        if status == "confirmed" or not args.double_opt_in:
            assert set((SITE / ".wrangler/tmp/email").rglob("*.txt")) == emails_before
        if status == "pending":
            assert "expired" in request("/api/confirm?t=" + old_token)[1]["location"]
    print(
        "PASS existing states, token invalidation and immutable confirmed rows",
        flush=True,
    )
    for index, lang in enumerate(("en", "it", "de")):
        email = f"spec05-{SUFFIX}-{lang}@example.test"
        payload = signup(email, lang)
        headers = {"CF-Connecting-IP": f"192.0.2.{130 + index}"}
        emails_before = set((SITE / ".wrangler/tmp/email").rglob("*.txt"))
        initial = request(endpoint, method="POST", data=payload, headers=headers)
        assert initial[0] == 200
        assert json.loads(initial[2]) == {"ok": True, "confirm": args.double_opt_in}
        record = row(email)
        if not args.double_opt_in:
            assert record["status"] == "unconfirmed" and record["confirmed_at"] is None
            assert record["token_hash"] is None and record["token_expires"] is None
            payload["computer"] = ["Linux", "Mac"]
            assert (
                request(endpoint, method="POST", data=payload, headers=headers)[2]
                == initial[2]
            )
            assert row(email)["computer"] == "Mac,Linux"
            assert set((SITE / ".wrangler/tmp/email").rglob("*.txt")) == emails_before
            continue
        assert record["status"] == "pending" and record["confirmed_at"] is None
        first = token_for(record)
        assert first not in json.dumps(record)
        assert (
            request(endpoint, method="POST", data=payload, headers=headers)[2]
            == initial[2]
        )
        second = token_for(row(email))
        assert first != second
        assert "expired" in request("/api/confirm?t=" + first)[1]["location"]
        result = request("/api/confirm?t=" + second)
        assert result[0] == 302 and result[1]["location"].endswith(
            "success&lang=" + lang
        )
        assert result[1]["referrer-policy"] == "no-referrer"
        confirmed = row(email)
        assert confirmed["status"] == "confirmed" and confirmed["confirmed_at"]
        assert confirmed["token_hash"] is None and confirmed["token_expires"] is None
        assert "expired" in request("/api/confirm?t=" + second)[1]["location"]
        emails_before = set((SITE / ".wrangler/tmp/email").rglob("*.txt"))
        payload["computer"], payload["lang"] = ["Linux"], "de"
        assert (
            request(endpoint, method="POST", data=payload, headers=headers)[2]
            == initial[2]
        )
        assert row(email) == confirmed
        assert set((SITE / ".wrangler/tmp/email").rglob("*.txt")) == emails_before
    print(
        "PASS signup, replacement and confirmation behavior in en/it/de",
        flush=True,
    )
    email = f"spec05-{SUFFIX}-expired@example.test"
    assert (
        request(
            endpoint,
            method="POST",
            data=signup(email),
            headers={"CF-Connecting-IP": "192.0.2.134"},
        )[0]
        == 200
    )
    if args.double_opt_in:
        token = token_for(row(email))
        sql(f"UPDATE waitlist SET token_expires = 1 WHERE email = '{email}'")
        assert "expired" in request("/api/confirm?t=" + token)[1]["location"]
        assert row(email)["status"] == "pending"
        print("PASS expired token", flush=True)
    quota = sql(
        "SELECT day, count FROM waitlist_daily_quota ORDER BY day DESC LIMIT 1"
    )[0]
    try:
        sql(f"UPDATE waitlist_daily_quota SET count=1000 WHERE day='{quota['day']}'")
        assert (
            request(
                endpoint,
                method="POST",
                data=signup(email),
                headers={"CF-Connecting-IP": "192.0.2.135"},
            )[0]
            == 429
        )
    finally:
        sql(
            f"UPDATE waitlist_daily_quota SET count={quota['count']} "
            f"WHERE day='{quota['day']}'"
        )
    print("PASS global daily quota", flush=True)
    # Inject immutable assets directly: Wrangler's file watcher is asynchronous.
    subprocess.run(
        ["node", "--input-type=module"],
        cwd=SITE,
        input=r"""
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source = await readFile('./src/worker.js', 'utf8');
const {default: worker} = await import('data:text/javascript;base64,' +
  Buffer.from(source).toString('base64'));
const valid = {version: '1.2.3', deb: 'scambio_1.2.3_all.deb', sha256: 'a'.repeat(64)};
async function request(data, method = 'GET') {
  return worker.fetch(new Request('https://scambio.app/download/scambio.deb', {method}),
    {ASSETS: {fetch: async () => Response.json(data)}});
}
for (const method of ['GET', 'HEAD']) {
  const response = await request(valid, method);
  assert.equal(response.status, 302);
  assert.equal(response.headers.get('location'), '/scambio_1.2.3_all.deb');
  assert.equal(response.headers.get('cache-control'), 'no-cache');
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
}
assert.equal((await request(valid, 'POST')).status, 405);
for (const [field, value] of [
    ['deb', '//evil.example/file.deb'], ['deb', '../file.deb'],
    ['version', '1.2.3/../x'], ['sha256', 'bad']]) {
  assert.equal((await request({...valid, [field]: value})).status, 503);
}
const local = new Request('http://localhost:8787/api/waitlist', {method: 'POST',
  headers: {'Origin': 'http://localhost:8787', 'Content-Type': 'application/json'},
  body: JSON.stringify({website: 'bot'})});
assert.equal((await worker.fetch(local, {ALLOW_LOCAL_ORIGIN: 'true',
  WAITLIST_LIMITER: {limit: async () => ({success: true})}})).status, 200);
console.log('PASS relative redirect, manifest tampering and explicit local origin');
const app = await readFile('./public/app.js', 'utf8');
const COPY = JSON.parse(await readFile('./public/copy.json', 'utf8'));
const submit = app.slice(app.indexOf('  form.addEventListener("submit"'),
  app.indexOf('  /* mock state change:'));
for (const cur of ['en', 'it', 'de']) {
  for (const confirm of [false, true]) {
    let handler, finished;
    const complete = new Promise(resolve => { finished = resolve; });
    const title = {setAttribute(key, value) { this[key] = value; }};
    const text = {setAttribute: title.setAttribute};
    const done = {hidden: true, querySelector: tag => tag === 'h3' ? title : text,
      focus() { this.focused = true; }};
    const nodes = {done, email: {value: 'ui@example.test'}, device: {value: ''},
      website: {value: ''}, consent: {checked: true}, 'form-err': {textContent: ''},
      submit: {set disabled(value) { if (!value) finished(); }}};
    const form = {hidden: false,
      addEventListener: (name, callback) => {handler = callback;}};
    vm.runInNewContext(submit, {form, COPY, cur, $: id => nodes[id],
      checks: () => [], document: {documentElement: {lang: cur}},
      get: (obj, path) => path.split('.').reduce((value, key) => value[key], obj),
      FormData: class {
        getAll(name) {return [name === 'computer' ? 'Mac' : 'Android'];}},
      fetch: async () => ({ok: true, json: async () => ({ok: true, confirm})})});
    handler({preventDefault() {}});
    await complete;
    const prefix = confirm ? 'confirm_' : 'success_';
    assert.equal(title.textContent, COPY[cur].form[prefix + 'title']);
    assert.equal(text.textContent, COPY[cur].form[prefix + 'text']);
    assert.equal(title['data-k'], 'form.' + prefix + 'title');
    assert.equal(text['data-k'], 'form.' + prefix + 'text');
    assert.notEqual(COPY[cur].form.success_title, COPY[cur].form.confirm_title);
    assert.ok(COPY[cur].form.success_text);
    assert.ok(form.hidden && !done.hidden && done.focused);
    assert.equal(nodes['form-err'].textContent, '');
  }
}
console.log('PASS frontend success copy in both modes and en/it/de');
""",
        text=True,
        check=True,
    )
    print(
        f"PASS {COUNT} HTTP assertions; only local D1 and simulated emails", flush=True
    )


if __name__ == "__main__":
    main()
