# Standoff 2 Upgrader Mini App

Telegram Mini App for a virtual Standoff 2-style upgrader.

## Included
- Upgrade
- Daily Case: free once every 24 hours
- Daily Case virtual Gold: 0.10 to 100
- Starter, Neon and Premium cases
- Inventory
- Catalog with public item names/categories/images when the source provides them
- Case opening animation
- FastAPI + SQLite backend

## Run backend
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py

For Telegram Mini App, publish frontend and backend over HTTPS and configure the bot's Main Mini App in @BotFather.

Catalog source used by the backend:
https://standoff-2.com/skins-new.php?command=getModelInfo

This is a third-party public catalog source, not an official Axlebolt API.
Virtual Gold in this starter project is in-app only.
