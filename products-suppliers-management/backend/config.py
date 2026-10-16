import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "")
DATABASE_NAME = os.getenv("DATABASE_NAME", "neerus")
PRODUCTS_COLLECTION = os.getenv("PRODUCTS_COLLECTION", "inventory")
SUPPLIERS_COLLECTION = os.getenv("SUPPLIERS_COLLECTION", "suppliers")
PURCHASE_ORDERS_COLLECTION = os.getenv("PURCHASE_ORDERS_COLLECTION", "purchase_orders")
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "10"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
API_KEY = os.getenv("API_KEY", "")
