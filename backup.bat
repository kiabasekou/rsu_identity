@echo off
set "COMMIT_MESSAGE=Sauvegarde automatique - %date% %time%"

echo Ajout des fichiers au staging area...
git add .

echo.
echo Verification des modifications...
git diff --quiet --cached
if %errorlevel% neq 0 (
    echo Creation du commit avec le message: "%COMMIT_MESSAGE%"
    git commit -m "%COMMIT_MESSAGE%"

    echo.
    echo Poussee des modifications vers le depot local...
    git push

    echo.
    echo Poussee des modifications vers le depot distant (GitHub)...
    git push origin main
) else (
    echo Aucune modification a sauvegarder.
)

echo.
echo Sauvegarde terminee.
pause