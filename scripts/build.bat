@echo off
chcp 65001 >nul
echo ========================================
echo  掌柜 BizMaster - 生产构建
echo ========================================
echo.

REM 环境变量：国内镜像源 + 项目内缓存目录（避免沙箱/GitHub 下载限制）
set "ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/"
set "ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/"
set "ELECTRON_CACHE=%~dp0..\electron\.cache"
set "ELECTRON_BUILDER_CACHE=%~dp0..\electron\.cache"
REM 禁用代码签名证书自动发现（避免下载 winCodeSign 时解压失败）
set "CSC_IDENTITY_AUTO_DISCOVERY=false"
REM 代码签名（自签名证书；若购买商业证书，替换 certs\ecom-agent.pfx 与密码即可）
if exist "%~dp0..\certs\ecom-agent.pfx" (
    set "CSC_LINK=%~dp0..\certs\ecom-agent.pfx"
    set "CSC_KEY_PASSWORD=EcomAgent2026!"
)

REM Step 0: 预取 winCodeSign 工具（Windows 无管理员权限时 7-Zip 解压符号链接会失败，需 -snl 跳过）
if not exist "%~dp0..\electron\.cache\winCodeSign\winCodeSign-2.6.0" (
    echo [0/4] 预取 winCodeSign 工具...
    if not exist "%~dp0..\electron\.cache\winCodeSign" mkdir "%~dp0..\electron\.cache\winCodeSign"
    curl -L -o "%~dp0..\electron\.cache\winCodeSign\wcs.7z" "https://npmmirror.com/mirrors/electron-builder-binaries/winCodeSign-2.6.0/winCodeSign-2.6.0.7z"
    if %ERRORLEVEL% neq 0 (
        echo winCodeSign 下载失败！
        pause
        exit /b 1
    )
    mkdir "%~dp0..\electron\.cache\winCodeSign\winCodeSign-2.6.0"
    "%~dp0..\electron\node_modules\7zip-bin\win\x64\7za.exe" x -snl -y "%~dp0..\electron\.cache\winCodeSign\wcs.7z" "-o%~dp0..\electron\.cache\winCodeSign\winCodeSign-2.6.0" >nul
)

REM Step 1: 构建前端
echo [1/4] 构建前端...
cd /d "%~dp0..\frontend"
call npm run build
if %ERRORLEVEL% neq 0 (
    echo 前端构建失败！
    pause
    exit /b 1
)

REM Step 2: 构建后端
echo [2/4] 构建后端 exe...
cd /d "%~dp0..\backend"
call python -m PyInstaller pyinstaller.spec --noconfirm
if %ERRORLEVEL% neq 0 (
    echo 后端构建失败！
    pause
    exit /b 1
)

REM Step 3: 复制后端 exe
echo [3/4] 复制后端到 Electron 资源目录...
if not exist "%~dp0..\electron\resources" mkdir "%~dp0..\electron\resources\backend"
xcopy /Y "%~dp0..\backend\dist\backend.exe" "%~dp0..\electron\resources\backend\"

REM Step 4: 打包 Electron 应用
echo [4/4] 打包桌面应用...
cd /d "%~dp0..\electron"
call npx electron-builder --win
if %ERRORLEVEL% neq 0 (
    echo Electron 打包失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo  构建完成！安装包位于 release/ 目录
echo ========================================
pause
