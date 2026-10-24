#!/usr/bin/env bash

set -e
mkdir -p demo

cat > demo/app.jsonl <<'EOF'
{"timestamp": "2024-03-01T09:00:00", "level": "INFO", "source": "auth", "message": "user logged in"}
{"timestamp": "2024-03-01T09:05:00", "level": "ERROR", "source": "payments", "message": "card declined"}
{"timestamp": "2024-03-01T09:10:00", "level": "ERROR", "source": "payments", "message": "gateway timeout"}
{"timestamp": "2024-03-01T09:15:00", "level": "WARNING", "source": "auth", "message": "слишком много попыток"}
{"timestamp": "2024-03-01T09:20:00", "level": "CRITICAL", "source": "база", "message": "нет соединения"}
{"timestamp": "2024-03-01T09:25:00", "level": "ERROR", "source": "auth", "message": "token expired"}
{"timestamp": "2024-03-01T09:30:00", "level": "DEBUG", "source": "web", "message": "GET /index"}
{"timestamp": "2024-03-01T12:30:00+03:00", "level": "INFO", "source": "web", "message": "GET /about"}
EOF

cat > demo/app.csv <<'EOF'
timestamp,level,source,message
2024-03-01T09:00:00,INFO,auth,user logged in
2024-03-01T09:05:00,ERROR,payments,card declined
2024-03-01T09:10:00,ERROR,payments,gateway timeout
2024-03-01T09:15:00,WARNING,auth,слишком много попыток
2024-03-01T09:20:00,CRITICAL,база,нет соединения
2024-03-01T09:25:00,ERROR,auth,token expired
2024-03-01T09:30:00,DEBUG,web,GET /index
2024-03-01T12:30:00+03:00,INFO,web,GET /about
EOF


head -n 6 demo/app.jsonl > demo/broken.jsonl
echo '{oops' >> demo/broken.jsonl
sed -n 8p demo/app.jsonl >> demo/broken.jsonl


printf 'timestamp,level,source,message\n2024-03-01T09:00:00,INFO,auth,ok\n2024-03-01T09:05:00,INFO,auth,ok\n32/13/2024,INFO,auth,ok\n' > demo/bad_date.csv

: > demo/empty.jsonl


for s in c b; do
    printf '{"timestamp": "2024-03-02T10:00:00", "level": "ERROR", "source": "%s", "message": "x"}\n' "$s"
done > demo/ties_a.jsonl
for s in a d e f g; do
    printf '{"timestamp": "2024-03-02T11:00:00", "level": "ERROR", "source": "%s", "message": "x"}\n' "$s"
done > demo/ties_b.jsonl

printf 'ERROR db disk is full\nINFO web all good\n' > demo/events.log

echo "demo/ is ready"
