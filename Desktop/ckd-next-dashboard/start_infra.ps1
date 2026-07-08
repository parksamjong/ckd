# CKD-NEXT 인프라 시작 스크립트 (PowerShell)
# 1. Docker (Kafka + Redis) 기동
# 2. PostgreSQL CDC 트리거 설치
# 3. Python 패키지 설치

$PYTHON = "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
$PSQL   = "C:\Program Files\PostgreSQL\14\bin\psql.exe"
$DIR    = $PSScriptRoot

Write-Host "=== CKD-NEXT 인프라 기동 ===" -ForegroundColor Cyan

# 1. Docker Compose
Write-Host "`n[1/4] Docker Compose 기동..." -ForegroundColor Yellow
Set-Location $DIR
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker 기동 실패. Docker Desktop이 실행 중인지 확인하세요." -ForegroundColor Red
    exit 1
}

# Kafka 준비 대기
Write-Host "Kafka/Redis 준비 중 (20초)..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# 2. PostgreSQL CDC 트리거 설치
Write-Host "`n[2/4] PostgreSQL CDC 트리거 설치..." -ForegroundColor Yellow
if (Test-Path $PSQL) {
    $env:PGPASSWORD = "1234"
    & $PSQL -h 127.0.0.1 -p 5432 -U postgres -d ckd_next -f "$DIR\cdc_setup.sql"
} else {
    Write-Host "psql 미설치 — Python으로 CDC 트리거 설치" -ForegroundColor Yellow
    & $PYTHON -c @"
import psycopg2
sql = open(r'$DIR\cdc_setup.sql').read()
conn = psycopg2.connect(host='127.0.0.1',port=5432,database='ckd_next',user='postgres',password='1234')
conn.autocommit = True
conn.cursor().execute(sql)
conn.close()
print('CDC 트리거 설치 완료')
"@
}

# 3. Python 패키지 설치
Write-Host "`n[3/4] Python 패키지 설치..." -ForegroundColor Yellow
& $PYTHON -m pip install aiokafka==0.11.0 redis==5.0.7 --quiet

# 4. 프로세스 기동
Write-Host "`n[4/4] CDC 브릿지 + Kafka Consumer 기동..." -ForegroundColor Yellow
Start-Process $PYTHON -ArgumentList "$DIR\cdc_kafka_bridge.py" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process $PYTHON -ArgumentList "$DIR\kafka_consumer.py" -WindowStyle Minimized

Write-Host "`n=== 인프라 기동 완료 ===" -ForegroundColor Green
Write-Host "Kafka UI  : http://localhost:8080" -ForegroundColor Cyan
Write-Host "Redis UI  : http://localhost:8081" -ForegroundColor Cyan
Write-Host "Dashboard : http://localhost:8765" -ForegroundColor Cyan
Write-Host "Infra API : http://localhost:8765/api/infra/status" -ForegroundColor Cyan
