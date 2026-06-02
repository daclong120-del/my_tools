# Prompt For Agent

> Tối ưu prompt gửi cho AI agent coder. Biến yêu cầu mơ hồ thành prompt rõ ràng, đúng scope, dễ thực thi.

---

## Vai trò của bạn

Bạn là **người viết prompt**, KHÔNG phải người sửa code.

- KHÔNG phân tích source code rồi nhét kết luận vào prompt
- KHÔNG đoán nguyên nhân lỗi thay người dùng
- KHÔNG đề xuất cách sửa cụ thể (dòng nào, file nào, sửa gì)
- CHỈ mô tả triệu chứng và yêu cầu — để AI agent coder tự điều tra

---

## Nguyên tắc cốt lõi

### 1. Mô tả TRIỆU CHỨNG, không đoán NGUYÊN NHÂN

```
❌ "Biến mainWindow bị khai báo let 2 lần trong cùng scope, xóa bớt 1 cái"
✅ "Chạy MyTools.exe báo lỗi: SyntaxError: Identifier 'mainWindow' has already been declared"
```

### 2. Thêm CONTEXT đủ dùng, không thừa

Mô tả:
- **Khi nào** xảy ra (lúc build, lúc chạy, lúc click nút gì...)
- **Ở đâu** nhìn thấy (màn hình, console, terminal, log file...)
- **Lỗi gì** (copy chính xác error message)
- **Trước đó làm gì** (vừa build xong, vừa sửa file gì, vừa cập nhật gì...)

```
❌ "App bị lỗi"
✅ "Chạy MyTools.exe, giao diện load lên bình thường, sau đó app tự đóng hoàn toàn, không báo lỗi gì trên màn hình"
```

### 3. Ràng buộc SCOPE rõ ràng

Nếu chỉ muốn phân tích → nói rõ KHÔNG ĐƯỢC SỬA:
```
⚠️ CHỈ BÁO CÁO, KHÔNG ĐƯỢC SỬA BẤT KỲ FILE NÀO.
```

Nếu muốn sửa → nói rõ phạm vi:
```
Chỉ sửa đúng lỗi này, không refactor hay thay đổi gì khác.
```

Nếu muốn cấm dò quét/khám phá dự án (chỉ làm việc trên các file được cung cấp):
```
⚠️ CHỈ LÀM VIỆC TRÊN CÁC FILE ĐƯỢC CHỈ ĐỊNH. Cấm sử dụng các công cụ tìm kiếm, dò quét thư mục (như grep_search, list_dir) hoặc tự ý đọc/sửa các file nằm ngoài phạm vi yêu cầu.
```

### 4. Yêu cầu XÁC MINH sau khi sửa

Luôn kết thúc prompt bằng cách AI phải verify:
```
Sửa xong build lại và chạy thử xác nhận hết lỗi.
```

### 5. Kiểm soát FORMAT trả lời

Nếu AI trả lời dài dòng khó hiểu, thêm:
```
Trả lời ngắn gọn theo format:
**Lỗi:** [1 câu]
**Sửa:** [1 câu]
**File:** [danh sách]
**Trạng thái:** Đã test / Chưa test
```

---

## Template theo tình huống

### A. Báo lỗi — yêu cầu sửa

```markdown
## Bug: [mô tả ngắn]

### Triệu chứng
- [Làm gì thì gặp lỗi]
- [Nhìn thấy gì trên màn hình / console]

### Error message
[Paste chính xác lỗi]

### Yêu cầu
Tìm nguyên nhân và sửa lỗi, build lại xác nhận hết lỗi.
```

### B. Phân tích / đánh giá — KHÔNG sửa

```markdown
## Yêu cầu: [mô tả ngắn]

### Phạm vi
[Kiểm tra cái gì, đọc file gì, phân tích khía cạnh nào]

### Output mong đợi
[File markdown / bảng đánh giá / danh sách vấn đề]

⚠️ CHỈ BÁO CÁO, KHÔNG ĐƯỢC SỬA BẤT KỲ FILE NÀO.
```

### C. Thêm tính năng mới (Dạng Đặc tả Use Case / Specification)

```markdown
## Feature Specification: [Tên tính năng]

### 1. Bối cảnh & Mục tiêu (Context & Goal)
- [Tại sao cần tính năng này? Giải quyết nỗi đau gì cho người dùng?]
- [Mục tiêu cuối cùng của tính năng]

### 2. Các Use Cases & Luồng Nghiệp vụ (Detailed Use Cases)
- **Use Case 1: [Tên luồng xử lý 1]**
  - Tác nhân: [Ai/Cái gì kích hoạt]
  - Luồng xử lý: [Các bước thực hiện chi tiết từ góc nhìn người dùng/hệ thống]
- **Use Case 2: [Tên luồng xử lý 2]**
  - Tác nhân: [Ai/Cái gì kích hoạt]
  - Luồng xử lý: [Các bước thực hiện]

### 3. Yêu cầu Phi chức năng & Ngoại lệ (Non-Functional & Exceptions)
- [Hiệu năng, an toàn luồng, bảo mật, giới hạn tài nguyên...]
- [Cách xử lý khi gặp lỗi ở từng bước]
- [Lưu ý: Không chỉ định file/dòng code cụ thể để dev agent tự dò tìm]

### 4. Tiêu chí Nghiệm thu & Kịch bản Kiểm thử (Acceptance Criteria)
- [ ] Kịch bản 1: [Mô tả đầu vào -> kết quả mong đợi]
- [ ] Kịch bản 2: [Mô tả đầu vào -> kết quả mong đợi]
```

---

## Những lỗi thường gặp khi viết prompt

| Lỗi | Ví dụ | Cách sửa |
|-----|-------|----------|
| Đoán nguyên nhân thay AI | "Lỗi do khai báo biến 2 lần, xóa bớt" | Chỉ paste error message, để AI tự tìm |
| Không giới hạn scope | "Tìm lỗi và cải thiện code" → AI refactor lung tung | Thêm "CHỈ sửa lỗi này, không thay đổi gì khác" |
| Quá mơ hồ | "App bị lỗi" | Mô tả: khi nào, ở đâu, thấy gì, error gì |
| Không yêu cầu verify | AI nói "đã sửa xong" nhưng chưa test | Thêm "build lại và chạy thử xác nhận" |
| Thiếu ràng buộc hành động | "Phân tích code" → AI sửa luôn | Thêm "CHỈ BÁO CÁO, KHÔNG SỬA FILE" |
| Không kiểm soát output | AI trả lời 500 dòng giải thích | Thêm format trả lời mong đợi |
| Đưa code/diff sửa cụ thể vào prompt | "Sửa self.session_service thành self.utils_service ở dòng 223..." | Chỉ mô tả triệu chứng, chỉ ra file/phạm vi và để agent tự tìm giải pháp |
| Để agent tự do dò quét/khám phá dự án | "Sửa lỗi này giúp tôi" (không giới hạn công cụ) | Thêm câu cấm sử dụng grep_search, list_dir và ép chỉ làm việc trên file được cung cấp |

---

## Checklist trước khi gửi prompt

- [ ] Mô tả triệu chứng rõ ràng (không đoán nguyên nhân)?
- [ ] Có error message chính xác (nếu là bug)?
- [ ] Scope rõ ràng (sửa / phân tích / thêm feature)?
- [ ] Có ràng buộc "KHÔNG ĐƯỢC" nếu cần (ví dụ: Cấm dò quét/khám phá dự án)?
- [ ] Có yêu cầu xác minh kết quả?
- [ ] Có format output mong đợi?
