# Simple Setup - 4 Commands Only

## For Windows:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements-local.txt
python main.py
```

## For Mac/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-local.txt
python main.py
```

## First Time Only:
After running the app, create admin user:
```
python cli.py create-admin
```

Done! Open http://localhost:5000