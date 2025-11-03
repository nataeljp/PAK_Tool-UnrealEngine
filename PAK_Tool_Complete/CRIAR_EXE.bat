@echo off
chcp 65001 >nul
title PAK Tool v3 - Gerador de Executavel
color 0A

echo.
echo ========================================
echo   PAK TOOL V3 - GERADOR DE EXECUTAVEL
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado!
    echo Instale Python 3.11 de: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo OK

echo.
echo [2/4] Instalando dependencias...
echo (Isso pode levar 1-2 minutos)
pip install pyuepak cryptography Pillow pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ERRO ao instalar dependencias!
    pause
    exit /b 1
)
echo OK

echo.
echo [3/4] Gerando executavel com PyInstaller...
echo (Isso pode levar 3-4 minutos)
echo.

pyinstaller --name="PAK_Tool" --onefile --windowed --icon=NONE --clean --noconfirm --hidden-import=cryptography --hidden-import=cryptography.hazmat --hidden-import=cryptography.hazmat.primitives --hidden-import=cryptography.hazmat.backends --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=PIL.ImageTk --collect-all=cryptography --collect-all=PIL pak_tool_gui.py

if errorlevel 1 (
    echo.
    echo ERRO ao gerar executavel!
    pause
    exit /b 1
)

echo.
echo [4/4] Organizando arquivos...

if not exist "PAK_Tool_EXE" mkdir PAK_Tool_EXE
copy dist\PAK_Tool.exe PAK_Tool_EXE\ >nul
copy LEIA-ME.txt PAK_Tool_EXE\ >nul 2>&1

echo.
echo ========================================
echo   EXECUTAVEL CRIADO COM SUCESSO!
echo ========================================
echo.
echo Localizacao: PAK_Tool_EXE\PAK_Tool.exe
echo.
echo Tamanho: 
dir PAK_Tool_EXE\PAK_Tool.exe | find "PAK_Tool.exe"
echo.
echo NOVIDADES DA VERSAO 3:
echo  - Adicionar arquivos ao PAK
echo  - Substituir arquivos existentes
echo  - Deletar arquivos do PAK
echo  - Editor de texto integrado
echo  - Visualizador de imagens
echo  - Status visual de modificacoes
echo.
echo TESTE AGORA: Entre na pasta PAK_Tool_EXE e execute PAK_Tool.exe
echo.
pause
