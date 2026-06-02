---
name: refactor-composition
description: "Use when refactoring multiple-inheritance mixins into a clean composition orchestrator architecture."
category: architecture
triggers: refactor, composition, mixin, inheritance, orchestrator, clean-architecture
---

# Composition-Over-Inheritance Refactoring Guide

Giao thức và quy trình chuẩn hóa dành cho Senior Developer để chuyển đổi cấu trúc đa thừa kế (Multiple Inheritance Mixins) thành cấu trúc kết hợp đối tượng (Composition Orchestrator) với cơ chế Inject Context an toàn và rõ ràng.

---

## 1. Triết lý Thiết kế (Core Philosophy)

Đa thừa kế (`Mixin`) thường dẫn đến:
* **Mất tính tường minh**: Các phương thức gọi chéo nhau qua `self` mà không có giao diện (interface/protocol) kiểm soát, gây khó khăn cho việc phát hiện nguồn gốc phương thức.
* **Cảnh báo IDE/Static Analysis**: Linter không thể nhận diện được các phương thức được định nghĩa chéo giữa các mixin khác nhau, dẫn đến hàng loạt cảnh báo `unresolved reference`.
* **Khó viết Unit Test**: Mỗi mixin phụ thuộc chặt chẽ vào các mixin khác, không thể chạy độc lập.

**Mục tiêu của Composition**:
* Tách các Mixin thành các **Service class** độc lập.
* Sử dụng một **Orchestrator Core** duy nhất chứa tất cả trạng thái dùng chung (shared state).
* Giao tiếp giữa các service thông qua một central **Context interface** (hoặc `Protocol` trong Python) để tránh circular imports.

---

## 2. Quy trình 3 bước Refactor Phẫu thuật

### Bước 1: Khai báo Protocol `IEngineContext`
Định nghĩa một interface mô tả toàn bộ thuộc tính, hàng đợi (queues), thread locks, và các phương thức delegation mà các service dùng chung cần truy cập.

```python
# protocols.py
from typing import Protocol, Any, Dict, Optional

class IEngineContext(Protocol):
    running: bool
    download_dir: str
    stats: Dict[str, int]
    utils_service: Any
    chrome_service: Any
    # Khai báo các delegation helper
    def log(self, level: str, message: str) -> None: ...
    def get_db_path(self) -> str: ...
```

### Bước 2: Chuyển đổi Mixin thành Service Class
1. Chuyển đổi tên lớp từ `class FeatureMixin:` thành `class FeatureService:`.
2. Định nghĩa hàm khởi tạo `__init__(self, context: Optional[IEngineContext] = None)`.
3. Thay thế toàn bộ các lời gọi biến/phương thức ngầm định qua `self` trước đây bằng cách đi qua `self.context`.
   * Ví dụ: `self.log(...)` $\rightarrow$ `self.context.utils_service.log(...)` hoặc `self.context.log(...)`
   * Ví dụ: `self.download_dir` $\rightarrow$ `self.context.download_dir`

```python
# chrome.py
class ChromeService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    def ensure_chrome_debug_port(self, port: Optional[int] = None) -> bool:
        # Sử dụng self.context để gọi sibling services
        if self.context:
            self.context.log("info", "Checking chrome debug port...")
        ...
```

### Bước 3: Tái thiết lập Orchestrator Core (Core Composer)
1. Core Class không còn kế thừa các Mixin.
2. Khai báo và khởi tạo tất cả các Service Class mới bên trong hàm `__init__`, truyền `self` làm context.
3. Triển khai các phương thức delegation để giữ nguyên khả năng tương thích ngược (backwards compatibility) cho các file bên ngoài (API routes, CLI commands).

```python
# core/__init__.py
class SocialPetaDownloaderCore:
    def __init__(self):
        # Khởi tạo shared state
        self.running = False
        self.download_dir = "..."
        
        # Khởi tạo composition services
        self.utils_service = UtilsService(self)
        self.chrome_service = ChromeService(self)
        self.tab_scanner = TabScanner(self)
        
    # Delegation methods để giữ API ngoài không bị hỏng
    def check_and_launch_chrome(self, port=None):
        return self.chrome_service.check_and_launch_chrome(port)
```

---

## 3. Ràng buộc Kỹ thuật & Phòng ngừa Circular Imports

1. **Tránh circular imports ở mức module**:
   * Chỉ import `IEngineContext` từ `protocols.py` bên trong các service file.
   * Sử dụng kiểu gợi ý (Type hinting) và `if TYPE_CHECKING` nếu cần tham chiếu các kiểu dữ liệu cụ thể.
2. **Khởi tạo độc lập**:
   * Đảm bảo mọi service có thể được import và tạo instance độc lập với tham số mặc định `context=None`.
   * Thêm kiểm tra `if self.context:` trước khi truy cập tài nguyên dùng chung trong service để tránh `AttributeError` khi chạy Unit Test độc lập.
3. **Bảo toàn giao thức WebSocket & API endpoints**:
   * Các thread locks (`stats_lock`, `history_lock`) và dữ liệu trạng thái (`stats`, `tab_states`) phải được giữ nguyên cấu trúc tên tại Core composer để các websocket stream và HTTP routes tiếp tục hoạt động mà không cần viết lại.
