# 🛒 SmartCart - Project Requirements & Specification Document

SmartCart is a full-featured, luxury e-commerce web platform engineered using **Python Flask**, **MySQL**, **Razorpay**, and modern responsive CSS/JavaScript.

---

## 1. System & Environment Requirements

### 1.1 Software Requirements
- **Python**: 3.10+ (tested and verified on Python 3.14)
- **Database Server**: MySQL 8.0+ or MariaDB 10.4+
- **Operating System**: Windows / macOS / Linux
- **Package Manager**: `pip`

### 1.2 Python Dependencies (`requirements.txt`)
- `Flask==3.1.3`: Web framework and routing engine
- `mysql-connector-python==9.7.0`: Native MySQL database driver
- `bcrypt==5.0.0`: Secure one-way salt hashing for passwords
- `razorpay==2.0.1`: Payment gateway API integration
- `xhtml2pdf==0.2.17` & `reportlab==4.5.1`: Automated PDF tax invoice rendering
- `Flask-Mail==0.10.0`: SMTP email dispatcher for OTP verification
- `pillow==12.3.0`: Image processing and validation
- `Werkzeug==3.1.8`: Secure file uploading and request utilities

---

## 2. Database Architecture & Schema

The application connects to a MySQL database named `smartcart` containing 5 core relational tables:

```
+-------------+         +-----------------+         +-------------------+
|    users    | 1     * |     orders      | 1     * |    order_items    |
|-------------|---------|-----------------|---------|-------------------|
| user_id     |<--------| user_id         |         | id                |
| name        |         | order_id (PK)   |<--------| order_id (FK)     |
| email (UNI) |         | amount          |         | product_id (FK)   |
| password    |         | razorpay_order  |         | product_name      |
+-------------+         | razorpay_pay_id |         | quantity          |
                        | payment_status  |         | price             |
                        | created_at      |         +-------------------+
                        +-----------------+                   ^
                                                              |
                                                    +-------------------+
                                                    |     products      |
                                                    |-------------------|
                                                    | product_id (PK)   |
+-------------+                                     | name              |
|    admin    |                                     | category          |
|-------------|                                     | price             |
| admin_id    |                                     | original_price    |
| name        |                                     | rating            |
| email (UNI) |                                     | image             |
| password    |                                     | is_featured       |
| profile_img |                                     | created_at        |
+-------------+                                     +-------------------+
```

---

## 3. Functional Requirements

### 3.1 Customer Storefront & Shopping Experience
- **Authentication**: Customer registration with bcrypt hashing, secure login session management, and logout.
- **Product Discovery**:
  - Live search across product names and descriptions.
  - Category pill filter tabs (Electronics, Wearables, Accessories, Fashion, Gourmet, Home & Living).
  - Sorting by Price (Low to High / High to Low), Customer Rating, and Featured.
  - Interactive product detail view with multi-point feature perks and related items recommendations.
- **Shopping Cart**:
  - Live asynchronous (AJAX) item addition with floating animated toast notification.
  - Live cart count badge with pulse animation in the sticky navbar.
  - Full shopping bag management: quantity stepper (+ / -), automatic subtotal, delivery fee calculation, and item removal.
- **Payment & Checkout**:
  - Pre-filled customer delivery address form.
  - Razorpay checkout integration with 256-bit SSL encryption.
  - Integrated simulation/sandbox fallback mode for instant test order evaluation.
- **Order Tracking & Confirmation**:
  - 4-stage visual tracking pipeline: `[Confirmed] -> [Processing] -> [Shipped] -> [Delivered]`.
  - Itemized receipt breakdown with order reference numbers.
  - Past orders list with item summary and order status badges.
  - **1-Click Official Tax Invoice (PDF)**: Server-rendered PDF document formatted with corporate styling, GST breakdown, customer bill-to details, and itemization.

### 3.2 Executive Management & Admin Suite
- **Two-Factor Admin Signup**: 6-digit OTP verification dispatched via email before admin activation.
- **Admin Dashboard**:
  - Real-time KPI analytics: Total Products, Customer Orders Placed, Gross Store Revenue, and Product Categories.
  - Recent products table and quick action buttons.
- **Product Inventory Management (CRUD)**:
  - Add product with live image drag-and-drop preview.
  - Edit existing products, update pricing, ratings, or replace product photography.
  - Delete products with safe confirmation.
  - Detailed product inspection view.
- **Admin Profile Management**:
  - Update administrator profile photo with live avatar preview.
  - Secure credential update and password modification.

---

## 4. Product Catalog Reference

The store includes 14 curated luxury and lifestyle products:

| ID | Product Name | Category | Selling Price | Original Price | Rating | Image File |
|---|---|---|---|---|---|---|
| 2 | Artisanal Reserve Coffee Beans (500g) | Gourmet & Beverages | ₹699.00 | ₹899.00 | 4.8 | `DSC_0231-1.jpg` |
| 3 | HydroPure Vacuum Insulated Flask (750ml) | Home & Living | ₹1,299.00 | ₹1,799.00 | 4.9 | `bottle.jpg` |
| 4 | SonicPro ANC Wireless Headphones | Electronics | ₹4,999.00 | ₹7,499.00 | 4.9 | `Head_Set.avif` |
| 5 | ChronoHeritage Sapphire Edition Wristwatch | Accessories | ₹6,499.00 | ₹8,999.00 | 4.9 | `watch.jpg` |
| 6 | Lumix 4K Pro Mirrorless Camera | Electronics | ₹54,999.00 | ₹62,999.00 | 4.9 | `camera.jpg` |
| 7 | Classic Heritage Cola (Vintage Pack of 6) | Gourmet & Beverages | ₹449.00 | ₹599.00 | 4.7 | `coke.jpg` |
| 8 | CyberKey Pro Wireless Mechanical Keyboard | Electronics | ₹3,899.00 | ₹5,299.00 | 4.8 | `keyboard.jpg` |
| 9 | Apex Flow Cloud Running Sneakers | Fashion & Footwear | ₹3,499.00 | ₹4,999.00 | 4.8 | `sneakers.jpg` |
| 10 | Titan Aero Ultra GPS Smartwatch | Wearables | ₹8,999.00 | ₹11,999.00 | 4.9 | `smartwatch.jpg` |
| 11 | Aviator Noir Polarized Sunglasses | Accessories | ₹2,199.00 | ₹3,299.00 | 4.7 | `sunglasses.jpg` |
| 12 | Heritage Full-Grain Leather Briefcase | Accessories | ₹5,999.00 | ₹7,999.00 | 4.9 | `leather_bag.jpg` |
| 13 | Aura Studio 360° Hi-Fi Bluetooth Speaker | Electronics | ₹7,499.00 | ₹9,999.00 | 4.8 | `speaker.jpg` |
| 14 | Oud Royal Reserve Eau De Parfum (100ml) | Personal Care & Luxury | ₹4,299.00 | ₹5,999.00 | 4.9 | `perfume.jpg` |
| 15 | SkyPhantom 4K Drone with 3-Axis Gimbal | Electronics | ₹29,999.00 | ₹37,999.00 | 4.9 | `drone.jpg` |

---

## 5. Quick Start Instructions

1. **Activate Virtual Environment**:
   ```powershell
   .\venv\Scripts\activate
   ```
2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. **Launch the Application**:
   ```powershell
   python app.py
   ```
4. **Access in Web Browser**:
   - Storefront Gateway: `http://127.0.0.1:5000/`
   - Customer Portal: `http://127.0.0.1:5000/user-login`
   - Admin Suite: `http://127.0.0.1:5000/admin-login`
