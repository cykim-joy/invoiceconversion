@echo off
chcp 65001 > nul
title 택배요청서 변환 대시보드

echo.
echo  ========================================
echo   📦 택배요청서 변환 대시보드 시작 중...
echo  ========================================
echo.

:: Python 설치 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo  [오류] Python이 설치되어 있지 않습니다.
    echo  https://python.org 에서 설치 후 다시 실행해주세요.
    pause
    exit /b
)

:: 패키지 설치 확인 (streamlit 또는 google_auth_oauthlib 없으면 자동 설치)
python -c "import streamlit, google_auth_oauthlib" > nul 2>&1
if errorlevel 1 (
    echo  필요한 패키지를 설치합니다. 잠시만 기다려주세요...
    echo.
    pip install -r requirements.txt
    echo.
)

:: 앱 실행
echo  브라우저가 자동으로 열립니다.
echo  종료하려면 이 창을 닫으세요.
echo.

python -m streamlit run app.py --server.headless false

pause
