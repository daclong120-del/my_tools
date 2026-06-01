# FastAPI Architecture - auto_tiktok

Tài liệu này ghi lại kiến trúc chuẩn được sử dụng cho dự án FastAPI `auto_tiktok` nhằm phân tách rõ ràng vai trò và luồng xử lý dữ liệu.

---

## 🏗️ Kiến trúc thư mục FastAPI — Phân tách vai trò

```
auto_tiktok/
├── app/
│   ├── api/                  ← 📡 NHẬN & GỬI (tầng HTTP)
│   │   └── routes/
│   │       ├── user_router.py
│   │       └── product_router.py
│   │
│   ├── schemas/              ← 📋 Định dạng dữ liệu vào/ra (Pydantic Models)
│   │   └── user_schema.py
│   │
│   ├── services/             ← ⚙️ XỬ LÝ LOGIC nghiệp vụ
│   │   └── user_service.py
│   │
│   ├── repositories/         ← 🗄️ QUERY DATABASE
│   │   └── user_repo.py
│   │
│   ├── models/               ← 💾 Định nghĩa bảng DB (SQLAlchemy/SQLModel)
│   │   └── user_model.py
│   │
│   └── core/                 ← ⚙️ Config, kết nối DB
│       ├── config.py
│       └── database.py
│
├── main.py                   ← Khởi động app
└── setup_boilerplate.py      ← Script khởi tạo cấu trúc thư mục thô
```

---

## 🔄 Luồng dữ liệu chạy như thế này

```
CLIENT (Postman/App)
    ↓ gửi HTTP Request
ROUTER (app/api/routes/)   ← chỉ nhận & trả response
    ↓ gọi
SERVICE (app/services/)    ← xử lý logic chính
    ↓ gọi
REPOSITORY (app/repositories/) ← chỉ đọc/ghi DB
    ↓ truy vấn
DATABASE
```

---

## 📌 Vai trò từng tầng — cụ thể

### 1. `app/api/routes/user_router.py` — **Tầng nhận & gửi**
- Nhận request từ Client.
- Gọi tầng Service để xử lý logic.
- Trả response về cho Client dựa trên Schema định sẵn.
- **KHÔNG** viết logic nghiệp vụ hay query database trực tiếp tại đây.

### 2. `app/schemas/user_schema.py` — **Định dạng dữ liệu**
- Sử dụng Pydantic để validate dữ liệu đầu vào (`UserCreate`) và định hình dữ liệu đầu ra (`UserResponse`).
- Giúp tự động generate tài liệu OpenAPI (Swagger UI).

### 3. `app/services/user_service.py` — **Logic nghiệp vụ (Business Logic)**
- Là bộ não của ứng dụng.
- Xử lý các phép tính toán, logic nghiệp vụ, gọi bên thứ ba, hash mật khẩu, kiểm tra nghiệp vụ...
- Gọi Repository để lưu trữ hoặc lấy dữ liệu khi cần.

### 4. `app/repositories/user_repo.py` — **Chỉ làm việc với Database (CRUD)**
- Nhận dữ liệu sạch từ Service.
- Thực hiện các câu lệnh query ORM (thêm, sửa, xóa, tìm kiếm).
- **KHÔNG** chứa logic nghiệp vụ.

---

## 🧠 Nguyên tắc cốt lõi cần nhớ

| Tầng | Được làm | KHÔNG được làm |
|---|---|---|
| **Router** | Nhận request, gọi service, trả response | Viết logic, query DB |
| **Service** | Xử lý logic, tính toán, validate nghiệp vụ | Query DB trực tiếp |
| **Repository** | Query DB (CRUD) | Chứa logic nghiệp vụ |
| **Schema** | Định nghĩa cấu trúc dữ liệu | Bất cứ thứ gì khác |

Tóm lại: **Router = cửa ngõ**, **Service = bộ não**, **Repository = tay chân với DB**.
