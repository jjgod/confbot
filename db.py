#!/usr/bin/env python
# db migrationer

import sqlite3, datetime, glob, sys, re, os

DBNAME = "bot.db"

def insert_entry(db, entry):
    db.execute("INSERT INTO log VALUES (?, ?, ?)", (entry["time"], entry["sender"], entry["msg"]))

def import_log(db, log):
    line_re = re.compile("^([0-9]+-[0-9]+-[0-9]+) ([0-9]+:[0-9]+:[0-9]+) <([^>]+)> (.+)$")
    log_re = re.compile("^([0-9]+-[0-9]+-[0-9]+) ([0-9]+:[0-9]+:[0-9]+) \*\*\* (.+)$")
    entry = None

    for line in open(log):
        m = line_re.match(line)
        if m:
            if entry:
                insert_entry(db, entry)

            entry = {}
            entry["time"] = datetime.datetime.strptime("%s %s" % (m.group(1), m.group(2)), "%Y-%m-%d %H:%M:%S")
            entry["sender"] = m.group(3).strip()
            entry["msg"] = m.group(4)
        else:
            if not log_re.match(line) and entry and not line[:-1].startswith("The bot is started"):
                entry["msg"] += "\n" + line[:-1]

    if entry:
        insert_entry(db, entry)

if len(sys.argv) < 2:
    print "usage: %s [init | import [file]]" % sys.argv[0]
    sys.exit(-1)

if sys.argv[1] == 'init':
    if os.path.isfile(DBNAME):
        os.unlink(DBNAME)

    db = sqlite3.connect(DBNAME)
    c = db.cursor()
    c.executescript("""BEGIN TRANSACTION;
CREATE TABLE "nick" (
"id" TEXT ,
"nick" TEXT );
CREATE TABLE "log" (
        "time" timestamp DEFAULT NULL,
        "sender" TEXT DEFAULT NULL,
        "msg" TEXT DEFAULT NULL);
CREATE INDEX "id_index" ON "nick" ("id");
CREATE INDEX "nick_index" ON "nick" ("nick");
COMMIT;""")
    db.commit()
    c.close()
    db.close()

if sys.argv[1] == "import":
    db = sqlite3.connect(DBNAME)
    cur = db.cursor()

    if len(sys.argv) > 2:
        import_log(cur, sys.argv[2])
    else:
        for log in glob.glob("2009*.log"):
            import_log(cur, log)

    db.commit()
    cur.close()
    db.close()

