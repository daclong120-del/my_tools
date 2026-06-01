Trước khi build Electron, kiểm tra requirements.txt đã đủ chưa:

Chạy lệnh này trong .venv để tìm các package đang dùng 
nhưng chưa có trong requirements.txt:

.venv\Scripts\pip.exe freeze > installed.txt

So sánh với requirements.txt hiện tại — bất kỳ package nào 
có trong code (import trong .py files) mà thiếu trong 
requirements.txt sẽ bị PyInstaller bỏ qua khi build.

Đặc biệt kiểm tra các package "hidden dependency" của uvicorn:
- websockets hoặc wsproto (bắt buộc cho WebSocket)
- uvicorn[standard] nếu muốn tất cả trong một

Sau mỗi lần thêm tính năng mới, chạy lại kiểm tra này 
trước khi build production.

--------------------------------
Trước mỗi lần build production (PyInstaller + Electron), 
chạy audit dependency cho dự án SocialPeta Downloader:

Viết script Python dùng AST parser (ast.parse) để:
1. Quét toàn bộ file .py trong tools/socialpeta_downloader/
2. Thu thập tất cả import statements (import X, from X import Y)
3. Lọc ra các third-party package (loại bỏ stdlib và relative imports)
4. So sánh với requirements.txt hiện tại
5. In ra: thiếu gì, thừa gì

Đặc biệt kiểm tra hidden dependencies không xuất hiện 
trong import trực tiếp:
- websockets / wsproto (uvicorn WebSocket backend)
- python-multipart (FastAPI form/file upload)
- Bất kỳ package nào được load động qua importlib

Sau khi script chạy xong, tự xóa script tạm.
Không rebuild nếu còn package thiếu.

C:\Users\PC\AppData\Roaming\my-tools-desktop\backend.log

-----------
SocialPeta Downloader: bản win-unpacked chạy được, 
bản MyTools Setup 1.0.0.exe cài xong thì không hoạt động.

Cần xác định tại sao installer build thiếu file hoặc sai đường dẫn.

Kiểm tra theo thứ tự:

1. So sánh cấu trúc thư mục:
   Chạy lệnh này và paste kết quả:
   
   Get-ChildItem -Recurse "d:\Python\my_tools\electron\dist\win-unpacked\resources" | Select-Object FullName
   
   và:
   
   Get-ChildItem -Recurse "C:\Users\PC\AppData\Local\Programs\my-tools-desktop\resources" | Select-Object FullName
   
   So sánh xem file nào có trong win-unpacked nhưng thiếu trong bản cài đặt.

2. Xem electron/package.json phần "build" và "files" / "extraResources":
   Paste toàn bộ section "build" trong electron/package.json
   → Kiểm tra xem api.exe, data/, chrome_debug_profile 
     có được khai báo trong extraResources không

3. Khi chạy bản installer, lỗi cụ thể là gì?
   Kiểm tra backend.log tại:
   C:\Users\PC\AppData\Roaming\my-tools-desktop\backend.log
   → 10 dòng đầu tiên sau "[Spawn] Starting backend" là gì?

Mục tiêu: tìm file nào bị thiếu trong installer 
so với win-unpacked để bổ sung vào extraResources.