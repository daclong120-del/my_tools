Đây là kỹ thuật quan trọng — gọi là **design extraction prompt**. Làm theo flow này:

---

**Bước 1 — Extract design system từ code cũ**

Upload code frontend cũ lên rồi prompt:

```
Phân tích toàn bộ code frontend này và extract ra:

1. Color palette (primary, secondary, background, text, border — hex cụ thể)
2. Typography (font family, size scale, font weight đang dùng)
3. Spacing system (padding, margin, gap đang dùng — 4px, 8px, 16px...)
4. Border radius pattern
5. Component patterns (button styles, card styles, input styles)
6. Layout pattern (sidebar? topbar? content width?)
7. Animation/transition nếu có

Trả ra dạng design token JSON và mô tả ngắn từng pattern.
```

---

**Bước 2 — Tạo file design token**

Lưu output đó thành `frontends/design-system.json` hoặc `tailwind.config.js` dùng chung cho tất cả tool:

```
frontends/
├── design-system.json       ← source of truth
├── invoice_parser/
├── socialpeta_downloader/
└── web_scraper/
```

---

**Bước 3 — Prompt khi tạo UI cho từng tool**

```
Tạo giao diện Next.js cho tool [tên tool] với chức năng [mô tả].

Design system cần follow (copy từ file đã extract):
- Colors: primary #... background #...
- Font: ... size ...
- Border radius: ...
- Button style: ...
- Layout: sidebar trái + content phải

Chức năng cần có:
1. ...
2. ...

API endpoint sẽ call:
- POST /api/... nhận { ... } trả về { ... }
- GET /api/...
```

---

**Bước 4 — Prompt bổ sung nếu chưa đúng**

```
Giữ nguyên logic và chức năng, chỉ điều chỉnh UI:
- Component X trông chưa giống design gốc vì [lý do]
- Cụ thể: [mô tả chi tiết]
```

---

**Điểm mấu chốt:**

Prompt càng cụ thể về design token thì kết quả càng sát. Đừng nói chung chung kiểu *"làm giống design cũ"* — AI không thấy được design cũ trừ khi mày extract ra thành số liệu cụ thể rồi paste vào.

Mày có thể upload code frontend cũ lên đây, tao extract design system ra luôn cho mày nếu muốn.