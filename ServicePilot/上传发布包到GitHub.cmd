@echo off
setlocal
set "GIT_HOME=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git"
set "GIT_EXE=%GIT_HOME%\cmd\git.exe"
set "PATH=%GIT_HOME%\cmd;%GIT_HOME%\mingw64\bin;%GIT_HOME%\usr\bin;%SystemRoot%\System32;%SystemRoot%;%PATH%"
if not exist "%GIT_EXE%" goto gitmissing
"%SystemRoot%\System32\chcp.com" 65001 >nul
title ServicePilot GitHub Upload
cd /d "%~dp0artifacts\deployment\20261014-234248\source"
if errorlevel 1 goto missing
if not exist ".git" goto missing
set "GCM_TRACE="
set "GIT_TRACE="
set "GIT_TRACE_CURL="
set "HTTPS_PROXY=http://127.0.0.1:7890"
set "HTTP_PROXY=http://127.0.0.1:7890"
set "UPLOAD_LOG=%~dp0artifacts\deployment\20261014-234248\upload-result.log"
if /i "%~1"=="--self-test" goto selftest
echo Upload target: zhangzhenting6666-design/servicepilot
echo This uses GitHub DEVICE login. No popup window is required.
echo Open https://github.com/login/device in your logged-in browser.
echo Enter the one-time code printed BELOW and approve with the correct account.
echo Do NOT send passwords, login codes, tokens or DeepSeek keys in chat.
echo.
"%GIT_EXE%" -c http.proxy=http://127.0.0.1:7890 credential-manager github login --username zhangzhenting6666-design --device --no-ui
if errorlevel 1 goto authfailed
echo GitHub login completed. Uploading the prepared allowlisted release...
"%GIT_EXE%" -c http.proxy=http://127.0.0.1:7890 -c credential.interactive=false -c credential.username=zhangzhenting6666-design push -u origin main > "%UPLOAD_LOG%" 2>&1
if errorlevel 1 goto uploadfailed
type "%UPLOAD_LOG%"
echo.
echo UPLOAD SUCCEEDED. Please reply: uploaded.
echo The developer will independently verify the remote commit.
goto keepopen
:authfailed
echo.
echo LOGIN FAILED. The terminal stays open. Share only the error, never login codes.
goto keepopen
:uploadfailed
type "%UPLOAD_LOG%"
echo.
echo UPLOAD FAILED. Error log saved to:
echo %UPLOAD_LOG%
goto keepopen
:missing
echo PREPARED RELEASE NOT FOUND. Return to the developer chat.
goto keepopen
:gitmissing
echo BUNDLED GIT NOT FOUND. Return to the developer chat.
goto keepopen
:selftest
"%GIT_EXE%" --version
if errorlevel 1 exit /b 1
"%GIT_EXE%" credential-manager --version
if errorlevel 1 exit /b 1
"%GIT_EXE%" rev-parse --short HEAD
"%GIT_EXE%" remote get-url origin
exit /b %errorlevel%
:keepopen
echo.
echo This window stays open. You can close it with the X after checking the result.
"%SystemRoot%\System32\cmd.exe" /k
