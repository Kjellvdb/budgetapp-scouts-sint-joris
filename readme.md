# Budgetapp Scouts Sint-Joris

To build the application, you can use the following command:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
$envContent = Get-Content .env
foreach ($line in $envContent) {
    if ($line -match "^GROQ_API_KEY=(.*)") {
        $apiKey = $Matches[1].Trim().Trim('"').Trim("'")
        "GROQ_API_KEY = '$apiKey'" | Out-File -Encoding utf8 config.py
    }
}
```

```bash
python -m PyInstaller --clean --onefile --windowed --name "Budgetapp Scouts Sint-Joris" main.py --icon .\budget.ico
```

```bash
Remove-Item config.py
```
