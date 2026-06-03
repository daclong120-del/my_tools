À, ra là bạn đang muốn nói đến **Quy trình làm việc và Phối hợp giữa các thành viên** (Development Process / Workflow)! Thảo nào bạn nhắc tới **Scrum** – đây chính là "vua" của các quy trình làm việc trong ngành phần mềm thực tế hiện nay.

Khi đi học, quy trình của chúng ta thường là "nước đến chân mới nhảy" hoặc mạnh ai nấy làm rồi ghép code lại. Nhưng đi làm thực tế, để cả một đội ngũ (Product Owner, Dev, Tester, Designer) không giẫm chân lên nhau, họ phải chạy theo một **Framework (Khung làm việc)**.

Scrum là một nhánh phổ biến nhất của triết lý **Agile (Phát triển linh hoạt)**. Quy trình vận hành công việc theo Scrum thực tế sẽ diễn ra theo một vòng tuần hoàn như thế này:

---

### 1. Các "Vai Diễn" Trong Team Scrum

Trước khi chạy, team phải phân vai rõ ràng (không có chức danh "Trưởng nhóm" chung chung kiểu đi học nữa):

* **Product Owner (PO):** Người hiểu khách hàng nhất. Họ là người quyết định phần mềm sẽ có chức năng gì và xếp thứ tự ưu tiên cái nào làm trước, cái nào làm sau.
* **Scrum Master (SM):** Không phải là sếp, mà là "người dọn đường". Nhiệm vụ của họ là đảm bảo mọi người làm đúng quy trình Scrum, giải quyết các khó khăn (vấn đề nội bộ, thiếu thiết bị, v.v.) để Dev tập trung code.
* **Development Team:** Gồm cả Dev, Tester, UI/UX Designer. Họ tự quản lý để cùng nhau hoàn thiện sản phẩm.

### 2. Các Công Cụ Quản Lý Sơ Đồ Công Việc

* **Product Backlog:** Một danh sách dài dằng dặc chứa tất cả các tính năng, mong muốn, sửa lỗi của dự án do PO quản lý.
* **Sprint Backlog:** Danh sách các việc mà team cam kết sẽ làm gói gọn trong một **Sprint** (thường kéo dài từ 2 đến 4 tuần).
* **Scrum Board (Bảng Kanban):** Thường quản lý trên Jira hoặc Trello. Mọi công việc phải đi qua các cột trực quan: `To Do` (Cần làm) $\rightarrow$ `In Progress` (Đang làm) $\rightarrow$ `In Review/Testing` (Đang kiểm thử) $\rightarrow$ `Done` (Hoàn thành).

---

### 3. Vòng Đời Hoạt Động Của Một Sprint (Quy trình chạy hàng ngày)

Một chu kỳ làm việc (Sprint) thực tế sẽ vận hành qua 4 bước họp hành và làm việc bắt buộc:

#### Bước 1: Họp Kế Hoạch Sprint (Sprint Planning)

* **Đầu Sprint**, cả team ngồi lại với nhau. PO sẽ lôi các tính năng ưu tiên từ *Product Backlog* ra.
* Team Dev sẽ thảo luận, ước lượng khối lượng công việc (thường chấm điểm bằng *Story Points* theo kiểu chơi bài Poker) và bốc lượng việc vừa sức bỏ vào *Sprint Backlog* để làm trong 2 tuần tới.

#### Bước 2: Họp Giao Ban Hàng Ngày (Daily Scrum / Daily Standup)

* Mỗi ngày, team sẽ dành ra đúng **15 phút** (thường là đầu giờ sáng) đứng họp với nhau (đứng để họp cho nhanh, không dông dài).
* Mỗi người lần lượt trả lời 3 câu hỏi:
1. *Hôm qua tôi đã làm được gì?*
2. *Hôm nay tôi sẽ làm gì?*
3. *Tôi có gặp khó khăn/vướng mắc (Blocker) gì không?* (Nếu có, Scrum Master sẽ ghi nhận để đi giải quyết sau buổi họp).



#### Bước 3: Họp Sơ Kết Sprint (Sprint Review)

* **Cuối Sprint**, team phải làm ra được một phần mềm chạy được (gọi là *Increment* - Phần tăng trưởng).
* Cả team sẽ demo/trình diễn tính năng đó cho khách hàng hoặc các sếp xem trực tiếp để nhận phản hồi (Feedback) xem có đúng ý họ không.

#### Bước 4: Họp Cải Tiến / Rút Kinh Nghiệm (Sprint Retrospective)

* Đây là buổi họp nội bộ của team sau khi Sprint kết thúc để nhìn nhận lại: Trong 2 tuần qua, quy trình làm việc có gì tốt, có gì tệ? Ai phối hợp chưa tốt? Công cụ nào bị lỗi?
* Team sẽ đưa ra các hành động cụ thể để cải tiến ngay trong Sprint tiếp theo. Sau đó, một Sprint mới lại bắt đầu ngay lập tức.

---

### Tại sao thực tế họ lại cuồng Scrum/Agile đến vậy?

Ngày xưa (và trong trường đại học), người ta hay làm theo kiểu **Waterfall (Thác nước)**: Viết tài liệu thật dày $\rightarrow$ Code hết sạch $\rightarrow$ Test một thể $\rightarrow$ Giao bài. Cách này ra đời thực tế rất dễ "oẹo" vì code xong mất 6 tháng thì khách hàng đổi ý, hoặc lúc ghép code mới phát hiện ra lỗi kiến trúc hệ thống.

Còn **Scrum** giúp chia nhỏ dự án ra. Cứ 2 tuần là có một bản chạy được để khách hàng kiểm tra. Sai đâu sửa đấy ngay lập tức, không lo bị "đập đi xây lại" cả hệ thống.

Thời đi học bạn đã từng bao giờ thử chia việc và làm việc theo kiểu "băm nhỏ" như thế này chưa, hay chủ yếu là đến tuần cuối cùng mới gom code lại rồi thức đêm sửa lỗi?