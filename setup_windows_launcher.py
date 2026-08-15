import os
import sys
import subprocess

python_exe = r"C:\Users\petrt\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
pythonw_exe = r"C:\Users\petrt\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
main_py = r"c:\Work\recorder\main.py"
work_dir = r"c:\Work\recorder"

# 1. Создаем VoiceTyper.bat в рабочей папке
bat_content = f'@echo off\nstart "" "{pythonw_exe}" "{main_py}"\n'
with open(os.path.join(work_dir, "VoiceTyper.bat"), "w", encoding="utf-8") as f:
    f.write(bat_content)

# 2. Создаем VoiceTyper.vbs
vbs_content = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{pythonw_exe}"" ""{main_py}""", 0, False\n'
with open(os.path.join(work_dir, "VoiceTyper.vbs"), "w", encoding="utf-8") as f:
    f.write(vbs_content)

# 3. Ищем все возможные пути к Рабочему столу и Автозагрузке
possible_desktops = [
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Рабочий стол"),
    r"C:\Users\Public\Desktop"
]

# Получаем системный путь к Desktop из реестра
import winreg
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
        reg_desktop, _ = winreg.QueryValueEx(key, "Desktop")
        expanded_reg = os.path.expandvars(reg_desktop)
        if expanded_reg not in possible_desktops:
            possible_desktops.insert(0, expanded_reg)
except Exception:
    pass

startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")

# 4. Создаем ярлык во всех найденных папках
for d in possible_desktops:
    if os.path.exists(d):
        lnk_path = os.path.join(d, "Voice Typer.lnk")
        ps_cmd = f'''
        $ws = New-Object -ComObject WScript.Shell;
        $s = $ws.CreateShortcut('{lnk_path}');
        $s.TargetPath = '{pythonw_exe}';
        $s.Arguments = '"{main_py}"';
        $s.WorkingDirectory = '{work_dir}';
        $s.IconLocation = 'shell32.dll,168';
        $s.Save();
        '''
        try:
            subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True)
            print(f"[OK] Создан ярлык: {lnk_path}")
        except Exception as e:
            print(f"[ERR] Не удалось создать в {lnk_path}: {e}")

# Создаем ярлык в автозагрузке
if os.path.exists(startup_dir):
    startup_lnk = os.path.join(startup_dir, "Voice Typer.lnk")
    ps_cmd = f'''
    $ws = New-Object -ComObject WScript.Shell;
    $s = $ws.CreateShortcut('{startup_lnk}');
    $s.TargetPath = '{pythonw_exe}';
    $s.Arguments = '"{main_py}"';
    $s.WorkingDirectory = '{work_dir}';
    $s.IconLocation = 'shell32.dll,168';
    $s.Save();
    '''
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True)
        print(f"[OK] Добавлен в автозагрузку: {startup_lnk}")
    except Exception as e:
        print(f"[ERR] Ошибка автозагрузки: {e}")

# 5. Запускаем приложение в фоне прямо сейчас!
subprocess.Popen([pythonw_exe, main_py], cwd=work_dir)
print("[OK] Voice Typer запущен в фоновом режиме через pythonw.exe!")
