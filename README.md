# 🛒 FreshGrocery — Real-Time Grocery Delivery Web App

[![Live Demo](https://img.shields.io/badge/Live%20Demo-akshayerukulla.pythonanywhere.com-27ae60?style=for-the-badge&logo=python)](https://akshayerukulla.pythonanywhere.com)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite)](https://sqlite.org)

> A full-stack real-time grocery delivery web application with live GPS tracking, role-based access, Razorpay payment integration, and 30 km delivery radius enforcement.

---

## 🌐 Live Demo

**→ [https://akshayerukulla.pythonanywhere.com](https://akshayerukulla.pythonanywhere.com)**

| Role | Email | Password |
|------|-------|----------|
| 🔑 Admin | ram@gmail.com | ram123 |
| 🚚 Delivery | krish@gmail.com | krish123 |
| 👤 Customer | Register a new account | — |

---

## ✨ Features

- 🏠 **Public Home Page** — Browse all products without login
- 🛒 **Shopping Cart** — Add/remove items, live sidebar, quantity controls
- 📍 **Location-Based Checkout** — GPS captured at checkout for live tracking
- 🚫 **30 km Delivery Radius** — Orders outside range are automatically rejected
- 💳 **Razorpay Payment** — Cards, UPI, Net Banking (test mode)
- 🚚 **Live GPS Order Tracking** — Real-time truck marker on Leaflet.js map
- 🗺️ **Real Road Routing** — OSRM API draws actual driving routes (free, no API key)
- 📦 **Stock Management** — Stock decreases automatically when order is placed
- 🔐 **Security Question Password Recovery** — No OTP/SMS needed
- 👥 **3-Role System** — Admin, Delivery Agent, Customer
- 🏪 **Store Settings** — Admin sets store location and delivery radius
- 📊 **Admin Dashboard** — Manage products, orders, users with live stats

---

## 🖼️ Screenshots

| Home Page | Live Tracking | Admin Dashboard |
|-----------|--------------|-----------------|
| Browse products, search by category | 🚚 Truck moves in real-time on map | Manage products, orders, users |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10, Flask |
| **Database** | SQLite (deployed) / MySQL (local) |
| **ORM** | Flask-SQLAlchemy |
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla) |
| **Maps** | Leaflet.js + OpenStreetMap |
| **Road Routing** | OSRM API (free, no key needed) |
| **Payment** | Razorpay |
| **Password Security** | Werkzeug scrypt hashing |
| **Deployment** | PythonAnywhere |

---

## 🗄️ Database Schema

7 tables — `users`, `products`, `cart`, `cart_items`, `orders`, `order_items`, `settings`

```
users ──────────────── cart ──── cart_items ──── products
  │                                                  │
  └──────────────── orders ─── order_items ──────────┘

settings  (key-value store for admin config)
```

---

## 📁 Project Structure

```
FreshGrocery/
├── app.py                  ← Flask backend (all routes, models, logic)
├── grocery.db              ← SQLite database (auto-created on first run)
│
├── templates/
│   ├── home.html           ← Product listing page
│   ├── login.html          ← Login page
│   ├── register.html       ← Registration with security question
│   ├── cart.html           ← Shopping cart
│   ├── checkout.html       ← 3-step checkout with Razorpay
│   ├── orders.html         ← User order history
│   ├── track.html          ← Live GPS order tracking (Leaflet.js)
│   ├── delivery.html       ← Delivery agent dashboard
│   ├── forgot_password.html← 3-step security question password reset
│   ├── admin_dashboard.html← Admin home
│   ├── admin_products.html ← Product management + store settings
│   ├── admin_orders.html   ← Order management
│   └── admin_users.html    ← User management with GPS map
│
└── static/
    ├── css/
    │   └── style.css       ← Global stylesheet
    └── images/
        └── default.png     ← Default product image
```

---

## 🚀 Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/freshgrocery.git
cd freshgrocery
```

### 2. Install dependencies
```bash
pip install flask flask-sqlalchemy werkzeug razorpay requests
```

### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
```
http://127.0.0.1:5000
```

> The database is created automatically on first run with sample products and default admin/delivery accounts.

---

## ☁️ Deploy to PythonAnywhere (Free)

1. Upload your project ZIP via **Files** tab
2. Open **Bash Console** → `unzip yourproject.zip`
3. Install packages: `pip install flask flask-sqlalchemy werkzeug razorpay requests`
4. Create Web App → Manual configuration → Python 3.10
5. Edit WSGI file:
```python
import sys
path = '/home/YOUR_USERNAME/YOUR_FOLDER'
if path not in sys.path:
    sys.path.append(path)
from app import app as application
```
6. Click **Reload** → Your app is live!

> Make sure `app.py` uses `sqlite:///grocery.db` (not MySQL) for PythonAnywhere free plan.

---

## 🔑 How Live Tracking Works

```
Customer places order → Browser GPS captured → user_lat/lng saved in orders table
         ↓
Delivery agent clicks "Start Delivery" → navigator.geolocation.watchPosition()
         ↓
GPS sent to /update-location every ~5 seconds → delivery_lat/lng updated
         ↓
Customer's /track page polls /get-tracking every 4 seconds
         ↓
Leaflet.js moves 🚚 truck marker + OSRM redraws real road route
```

---

## 📦 Key Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Home — browse products |
| `/login` | GET/POST | User login |
| `/register` | GET/POST | Register with security question |
| `/cart` | GET | Shopping cart page |
| `/checkout` | GET | 3-step checkout |
| `/place-order` | POST | Place order + stock deduction |
| `/track` | GET | Live order tracking map |
| `/update-location` | POST | Delivery agent GPS update |
| `/get-tracking/<id>` | GET | Returns live GPS coordinates |
| `/admin` | GET | Admin dashboard |
| `/admin/products` | GET | Manage products + store settings |
| `/forgot-password` | GET/POST | Security question password reset |

---

## 👨‍💻 Developer

**Akshay Erukulla**
- 🌐 Live: [akshayerukulla.pythonanywhere.com](https://akshayerukulla.pythonanywhere.com)
- 📧 Email: akshay@gmail.com

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

*Built with ❤️ using Python & Flask*
